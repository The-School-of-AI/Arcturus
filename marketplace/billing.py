# marketplace/billing.py
"""
marketplace/billing.py
-----------------------
Monetization for the Bazaar marketplace.

Manages skill pricing, purchases, and revenue split.
Persists state in ``<skills_dir>/.billing.json``.

Stripe integration is stubbed — replace ``_stripe_*`` methods
with real Stripe SDK calls for production use.

Usage:
    from marketplace.billing import BillingManager, PricingTier

    bm = BillingManager(skills_dir=Path("marketplace/skills"))
    bm.set_pricing("premium_skill", PricingTier.PREMIUM, price_cents=999,
                   creator_account_id="acct_creator123")
    result = bm.create_checkout("premium_skill", buyer_id="user42")
    bm.confirm_purchase("premium_skill", buyer_id="user42",
                        payment_intent_id=result.payment_intent_id)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("bazaar")

# Revenue split: 70% creator, 30% platform (per charter §9.4)
CREATOR_SHARE_PERCENT = 70
PLATFORM_SHARE_PERCENT = 30


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PricingTier(str, Enum):
    """Pricing tiers for marketplace skills."""
    FREE = "free"
    PREMIUM = "premium"
    SUBSCRIPTION = "subscription"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class SkillPricing:
    """Pricing configuration for a skill."""
    skill_name: str
    tier: str = PricingTier.FREE.value
    price_cents: int = 0                       # in USD cents (e.g., 999 = $9.99)
    creator_account_id: str = ""               # Stripe Connect account ID
    currency: str = "usd"

    def to_dict(self) -> dict:
        return {
            "skill_name": self.skill_name,
            "tier": self.tier,
            "price_cents": self.price_cents,
            "creator_account_id": self.creator_account_id,
            "currency": self.currency,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SkillPricing":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class PurchaseRecord:
    """Record of a completed purchase."""
    skill_name: str
    buyer_id: str
    amount_cents: int
    creator_share_cents: int
    platform_share_cents: int
    payment_intent_id: str
    purchased_at: str           # ISO-8601

    def to_dict(self) -> dict:
        return {
            "skill_name": self.skill_name,
            "buyer_id": self.buyer_id,
            "amount_cents": self.amount_cents,
            "creator_share_cents": self.creator_share_cents,
            "platform_share_cents": self.platform_share_cents,
            "payment_intent_id": self.payment_intent_id,
            "purchased_at": self.purchased_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PurchaseRecord":
        return cls(**d)


@dataclass
class BillingResult:
    """Result of a billing operation."""
    success: bool
    message: str
    payment_intent_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Stripe stubs (replace with real Stripe SDK in production)
# ---------------------------------------------------------------------------

def _stripe_create_payment_intent(
    amount_cents: int,
    currency: str,
    creator_account_id: str,
    creator_share_cents: int,
) -> str:
    """
    STUB: Create a Stripe PaymentIntent with application fee.

    In production, replace with:
        import stripe
        stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
        intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency=currency,
            application_fee_amount=amount_cents - creator_share_cents,
            transfer_data={"destination": creator_account_id},
        )
        return intent.id
    """
    import hashlib
    import time
    # Generate a deterministic-looking fake intent ID
    seed = f"{amount_cents}-{creator_account_id}-{time.time()}"
    stub_id = hashlib.md5(seed.encode()).hexdigest()[:16]
    return f"pi_stub_{stub_id}"


def _stripe_create_connect_account(email: str) -> str:
    """
    STUB: Create a Stripe Connect account for a skill creator.

    In production:
        account = stripe.Account.create(
            type="express",
            email=email,
            capabilities={"transfers": {"requested": True}},
        )
        return account.id
    """
    import hashlib
    stub_id = hashlib.md5(email.encode()).hexdigest()[:12]
    return f"acct_stub_{stub_id}"


# ---------------------------------------------------------------------------
# Billing Manager
# ---------------------------------------------------------------------------

class BillingManager:
    """
    Manages marketplace skill pricing and purchases.

    Persists to ``<skills_dir>/.billing.json``.
    """

    BILLING_FILENAME = ".billing.json"

    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self._billing_path = skills_dir / self.BILLING_FILENAME
        self._pricing: Dict[str, SkillPricing] = {}
        self._purchases: List[PurchaseRecord] = []
        self._load()

    # ---- persistence ----

    def _load(self) -> None:
        """Load billing data from disk."""
        if self._billing_path.exists():
            try:
                data = json.loads(self._billing_path.read_text(encoding="utf-8"))
                for name, p in data.get("pricing", {}).items():
                    self._pricing[name] = SkillPricing.from_dict(p)
                self._purchases = [
                    PurchaseRecord.from_dict(r)
                    for r in data.get("purchases", [])
                ]
            except (json.JSONDecodeError, KeyError) as exc:
                logger.warning("Failed to load billing data: %s", exc)

    def _save(self) -> None:
        """Persist billing data to disk."""
        self._billing_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "pricing": {n: p.to_dict() for n, p in self._pricing.items()},
            "purchases": [r.to_dict() for r in self._purchases],
        }
        self._billing_path.write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )

    # ---- pricing ----

    def set_pricing(
        self,
        skill_name: str,
        tier: PricingTier,
        price_cents: int = 0,
        creator_account_id: str = "",
        currency: str = "usd",
    ) -> SkillPricing:
        """
        Set pricing for a skill.

        Args:
            skill_name:          Skill identifier.
            tier:                FREE, PREMIUM, or SUBSCRIPTION.
            price_cents:         Price in cents (0 for free).
            creator_account_id:  Creator's Stripe Connect account.
            currency:            Currency code.

        Returns:
            The created SkillPricing object.
        """
        if tier == PricingTier.FREE:
            price_cents = 0

        pricing = SkillPricing(
            skill_name=skill_name,
            tier=tier.value,
            price_cents=price_cents,
            creator_account_id=creator_account_id,
            currency=currency,
        )
        self._pricing[skill_name] = pricing
        self._save()
        logger.info("Set pricing for '%s': %s ($%.2f)",
                     skill_name, tier.value, price_cents / 100)
        return pricing

    def get_pricing(self, skill_name: str) -> SkillPricing:
        """
        Get pricing for a skill.

        Returns FREE pricing if no pricing is set.
        """
        return self._pricing.get(
            skill_name,
            SkillPricing(skill_name=skill_name),  # defaults to FREE
        )

    def is_free(self, skill_name: str) -> bool:
        """Check if a skill is free to install."""
        pricing = self.get_pricing(skill_name)
        return pricing.tier == PricingTier.FREE.value

    # ---- purchases ----

    def create_checkout(
        self,
        skill_name: str,
        buyer_id: str,
    ) -> BillingResult:
        """
        Create a checkout session for a premium skill.

        Returns a payment intent ID that the frontend uses to confirm.

        Args:
            skill_name: Skill to purchase.
            buyer_id:   Buyer's user ID.

        Returns:
            BillingResult with payment_intent_id.
        """
        pricing = self.get_pricing(skill_name)

        if pricing.tier == PricingTier.FREE.value:
            return BillingResult(
                success=False,
                message=f"Skill '{skill_name}' is free — no payment needed",
            )

        if self.has_purchased(skill_name, buyer_id):
            return BillingResult(
                success=False,
                message=f"Buyer '{buyer_id}' already owns '{skill_name}'",
            )

        creator_share = int(pricing.price_cents * CREATOR_SHARE_PERCENT / 100)

        intent_id = _stripe_create_payment_intent(
            amount_cents=pricing.price_cents,
            currency=pricing.currency,
            creator_account_id=pricing.creator_account_id,
            creator_share_cents=creator_share,
        )

        logger.info("Checkout for '%s' by '%s': intent=%s",
                     skill_name, buyer_id, intent_id)
        return BillingResult(
            success=True,
            message="Payment intent created",
            payment_intent_id=intent_id,
        )

    def confirm_purchase(
        self,
        skill_name: str,
        buyer_id: str,
        payment_intent_id: str,
    ) -> BillingResult:
        """
        Confirm a purchase after successful payment.

        Records the purchase with revenue split.

        Args:
            skill_name:         Skill purchased.
            buyer_id:           Buyer's user ID.
            payment_intent_id:  Stripe PaymentIntent ID.

        Returns:
            BillingResult.
        """
        pricing = self.get_pricing(skill_name)
        creator_share = int(pricing.price_cents * CREATOR_SHARE_PERCENT / 100)
        platform_share = pricing.price_cents - creator_share

        record = PurchaseRecord(
            skill_name=skill_name,
            buyer_id=buyer_id,
            amount_cents=pricing.price_cents,
            creator_share_cents=creator_share,
            platform_share_cents=platform_share,
            payment_intent_id=payment_intent_id,
            purchased_at=datetime.now(timezone.utc).isoformat(),
        )
        self._purchases.append(record)
        self._save()

        logger.info("Purchase confirmed: '%s' by '%s' ($%.2f, creator: $%.2f)",
                     skill_name, buyer_id,
                     pricing.price_cents / 100, creator_share / 100)
        return BillingResult(
            success=True,
            message=f"Purchase confirmed: {skill_name}",
            payment_intent_id=payment_intent_id,
        )

    def has_purchased(self, skill_name: str, buyer_id: str) -> bool:
        """Check if a buyer already owns a skill."""
        return any(
            p.skill_name == skill_name and p.buyer_id == buyer_id
            for p in self._purchases
        )

    def list_purchases(self, buyer_id: str) -> List[PurchaseRecord]:
        """List all purchases by a buyer."""
        return [p for p in self._purchases if p.buyer_id == buyer_id]

    def get_creator_earnings(self, creator_account_id: str) -> dict:
        """
        Calculate total earnings for a creator.

        Returns:
            {
                "creator_account_id": "acct_...",
                "total_sales": 5,
                "gross_revenue_cents": 4995,
                "creator_earnings_cents": 3496,
                "platform_fees_cents": 1499,
            }
        """
        # Find all skills by this creator
        creator_skills = {
            name for name, p in self._pricing.items()
            if p.creator_account_id == creator_account_id
        }

        # Sum purchases for those skills
        relevant = [
            p for p in self._purchases
            if p.skill_name in creator_skills
        ]

        return {
            "creator_account_id": creator_account_id,
            "total_sales": len(relevant),
            "gross_revenue_cents": sum(p.amount_cents for p in relevant),
            "creator_earnings_cents": sum(p.creator_share_cents for p in relevant),
            "platform_fees_cents": sum(p.platform_share_cents for p in relevant),
        }

    def remove(self, skill_name: str) -> None:
        """Remove pricing for a skill (does NOT remove purchase history)."""
        self._pricing.pop(skill_name, None)
        self._save()
