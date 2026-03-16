# tests/unit/bazaar/test_billing.py
"""
Unit tests for marketplace.billing.

Covers:
  - SkillPricing / PurchaseRecord serialization round-trips
  - set_pricing() / get_pricing() — create and retrieve
  - is_free() — defaults to free, premium returns false
  - create_checkout() — creates payment intent, blocks free / already-owned
  - confirm_purchase() — records purchase with revenue split
  - has_purchased() — checks ownership
  - get_creator_earnings() — validates 70/30 split
  - list_purchases() — filters by buyer
  - Persistence across BillingManager instances
  - remove() — clears pricing but keeps purchases
"""

from __future__ import annotations

from pathlib import Path

import pytest

from marketplace.billing import (
    BillingManager,
    BillingResult,
    PricingTier,
    PurchaseRecord,
    SkillPricing,
    CREATOR_SHARE_PERCENT,
    PLATFORM_SHARE_PERCENT,
)


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

class TestSerialization:

    def test_skill_pricing_round_trip(self):
        p = SkillPricing(
            skill_name="pro_skill", tier="premium",
            price_cents=999, creator_account_id="acct_123",
        )
        restored = SkillPricing.from_dict(p.to_dict())
        assert restored.skill_name == "pro_skill"
        assert restored.price_cents == 999

    def test_purchase_record_round_trip(self):
        r = PurchaseRecord(
            skill_name="pro_skill", buyer_id="user42",
            amount_cents=999, creator_share_cents=699,
            platform_share_cents=300,
            payment_intent_id="pi_123",
            purchased_at="2026-01-01T00:00:00+00:00",
        )
        restored = PurchaseRecord.from_dict(r.to_dict())
        assert restored.buyer_id == "user42"
        assert restored.creator_share_cents == 699


# ---------------------------------------------------------------------------
# Pricing
# ---------------------------------------------------------------------------

class TestPricing:

    def test_default_pricing_is_free(self, tmp_path):
        bm = BillingManager(skills_dir=tmp_path)
        pricing = bm.get_pricing("unknown_skill")
        assert pricing.tier == PricingTier.FREE.value
        assert pricing.price_cents == 0

    def test_set_premium_pricing(self, tmp_path):
        bm = BillingManager(skills_dir=tmp_path)
        result = bm.set_pricing(
            "pro_skill", PricingTier.PREMIUM,
            price_cents=999, creator_account_id="acct_creator",
        )
        assert result.price_cents == 999
        assert result.tier == PricingTier.PREMIUM.value

    def test_set_free_forces_zero_price(self, tmp_path):
        bm = BillingManager(skills_dir=tmp_path)
        bm.set_pricing("freebie", PricingTier.FREE, price_cents=500)
        assert bm.get_pricing("freebie").price_cents == 0

    def test_is_free_true_for_default(self, tmp_path):
        bm = BillingManager(skills_dir=tmp_path)
        assert bm.is_free("unknown") is True

    def test_is_free_false_for_premium(self, tmp_path):
        bm = BillingManager(skills_dir=tmp_path)
        bm.set_pricing("pro", PricingTier.PREMIUM, price_cents=500)
        assert bm.is_free("pro") is False


# ---------------------------------------------------------------------------
# Checkout & Purchase
# ---------------------------------------------------------------------------

class TestCheckout:

    def test_create_checkout_returns_intent(self, tmp_path):
        bm = BillingManager(skills_dir=tmp_path)
        bm.set_pricing("pro", PricingTier.PREMIUM, price_cents=999,
                       creator_account_id="acct_c")
        result = bm.create_checkout("pro", "buyer_1")
        assert result.success is True
        assert result.payment_intent_id is not None
        assert result.payment_intent_id.startswith("pi_stub_")

    def test_checkout_free_skill_fails(self, tmp_path):
        bm = BillingManager(skills_dir=tmp_path)
        result = bm.create_checkout("free_skill", "buyer_1")
        assert result.success is False
        assert "free" in result.message.lower()

    def test_checkout_already_owned_fails(self, tmp_path):
        bm = BillingManager(skills_dir=tmp_path)
        bm.set_pricing("pro", PricingTier.PREMIUM, price_cents=999,
                       creator_account_id="acct_c")
        checkout = bm.create_checkout("pro", "buyer_1")
        bm.confirm_purchase("pro", "buyer_1", checkout.payment_intent_id)

        # Second checkout should fail
        result = bm.create_checkout("pro", "buyer_1")
        assert result.success is False
        assert "already owns" in result.message.lower()


class TestConfirmPurchase:

    def test_confirm_records_purchase(self, tmp_path):
        bm = BillingManager(skills_dir=tmp_path)
        bm.set_pricing("pro", PricingTier.PREMIUM, price_cents=1000,
                       creator_account_id="acct_c")
        result = bm.confirm_purchase("pro", "buyer_1", "pi_123")
        assert result.success is True
        assert bm.has_purchased("pro", "buyer_1") is True

    def test_revenue_split_70_30(self, tmp_path):
        bm = BillingManager(skills_dir=tmp_path)
        bm.set_pricing("pro", PricingTier.PREMIUM, price_cents=1000,
                       creator_account_id="acct_c")
        bm.confirm_purchase("pro", "buyer_1", "pi_123")

        purchases = bm.list_purchases("buyer_1")
        assert len(purchases) == 1
        assert purchases[0].creator_share_cents == 700     # 70%
        assert purchases[0].platform_share_cents == 300    # 30%

    def test_has_purchased_false_for_non_buyer(self, tmp_path):
        bm = BillingManager(skills_dir=tmp_path)
        assert bm.has_purchased("pro", "nobody") is False


# ---------------------------------------------------------------------------
# Earnings
# ---------------------------------------------------------------------------

class TestEarnings:

    def test_creator_earnings(self, tmp_path):
        bm = BillingManager(skills_dir=tmp_path)
        bm.set_pricing("skill_a", PricingTier.PREMIUM, price_cents=1000,
                       creator_account_id="acct_alice")
        bm.set_pricing("skill_b", PricingTier.PREMIUM, price_cents=500,
                       creator_account_id="acct_alice")

        bm.confirm_purchase("skill_a", "u1", "pi_1")
        bm.confirm_purchase("skill_a", "u2", "pi_2")
        bm.confirm_purchase("skill_b", "u3", "pi_3")

        earnings = bm.get_creator_earnings("acct_alice")
        assert earnings["total_sales"] == 3
        assert earnings["gross_revenue_cents"] == 2500     # 1000+1000+500
        assert earnings["creator_earnings_cents"] == 1750  # 70% of 2500
        assert earnings["platform_fees_cents"] == 750      # 30% of 2500

    def test_earnings_empty_for_unknown_creator(self, tmp_path):
        bm = BillingManager(skills_dir=tmp_path)
        earnings = bm.get_creator_earnings("acct_nobody")
        assert earnings["total_sales"] == 0


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

class TestPersistence:

    def test_pricing_survives_reload(self, tmp_path):
        bm1 = BillingManager(skills_dir=tmp_path)
        bm1.set_pricing("pro", PricingTier.PREMIUM, price_cents=999)

        bm2 = BillingManager(skills_dir=tmp_path)
        assert bm2.get_pricing("pro").price_cents == 999

    def test_purchases_survive_reload(self, tmp_path):
        bm1 = BillingManager(skills_dir=tmp_path)
        bm1.set_pricing("pro", PricingTier.PREMIUM, price_cents=500)
        bm1.confirm_purchase("pro", "u1", "pi_1")

        bm2 = BillingManager(skills_dir=tmp_path)
        assert bm2.has_purchased("pro", "u1") is True


# ---------------------------------------------------------------------------
# Remove
# ---------------------------------------------------------------------------

class TestRemove:

    def test_remove_clears_pricing(self, tmp_path):
        bm = BillingManager(skills_dir=tmp_path)
        bm.set_pricing("pro", PricingTier.PREMIUM, price_cents=999)
        bm.remove("pro")
        assert bm.is_free("pro") is True

    def test_remove_keeps_purchases(self, tmp_path):
        bm = BillingManager(skills_dir=tmp_path)
        bm.set_pricing("pro", PricingTier.PREMIUM, price_cents=999)
        bm.confirm_purchase("pro", "u1", "pi_1")
        bm.remove("pro")
        # Purchase history preserved
        assert bm.has_purchased("pro", "u1") is True
