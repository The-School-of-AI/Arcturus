"""
TG3 — Logged-in user, registration, migration. Skips when JWT not configured.
"""

import os
import pytest

from tests.automation.p11_mnemo.conftest import requires_qdrant_neo4j

pytestmark = [
    pytest.mark.p11_automation,
    pytest.mark.integration,
]

# Unique email per run to avoid conflicts
import time
_unique = f"tg3_{int(time.time())}@example.com"


def _auth_configured() -> bool:
    return bool(os.environ.get("MNEMO_SECRET_KEY"))


def _skip_if_no_auth():
    if not _auth_configured():
        pytest.skip("MNEMO_SECRET_KEY not set; auth tests require JWT config")


def test_tg3_01_register(client):
    """TG3: Register new user."""
    _skip_if_no_auth()
    res = client.post(
        "/api/auth/register",
        json={"email": _unique, "password": "TestPass123!"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert "access_token" in body
    assert "user_id" in body
    assert body.get("email") == _unique


def test_tg3_02_login(client):
    """TG3: Login with registered user."""
    _skip_if_no_auth()
    res = client.post(
        "/api/auth/login",
        json={"email": _unique, "password": "TestPass123!"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert "access_token" in body
    assert "user_id" in body


def test_tg3_03_auth_me_with_token(client):
    """TG3: GET /auth/me with Bearer token."""
    _skip_if_no_auth()
    login_res = client.post("/api/auth/login", json={"email": _unique, "password": "TestPass123!"})
    assert login_res.status_code == 200
    token = login_res.json().get("access_token")
    assert token
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    body = res.json()
    assert body.get("auth_type") == "registered"
    assert body.get("email") == _unique


@requires_qdrant_neo4j
def test_tg3_04_register_with_guest_id_migration(client):
    """TG3: Register with guest_id triggers migration."""
    _skip_if_no_auth()
    guest_id = "10000000-0000-0000-0000-000000000099"
    email = f"tg3_mig_{int(time.time())}@example.com"
    # First add memory as guest
    add_res = client.post(
        "/api/remme/add",
        headers={"X-User-Id": guest_id},
        json={"text": "Guest memory before migration", "category": "general"},
    )
    assert add_res.status_code == 200
    # Register with guest_id
    reg_res = client.post(
        "/api/auth/register",
        json={"email": email, "password": "TestPass123!", "guest_id": guest_id},
    )
    assert reg_res.status_code == 200
    user_id = reg_res.json().get("user_id")
    token = reg_res.json().get("access_token")
    # List memories as registered user — should include migrated
    list_res = client.get("/api/remme/memories", headers={"Authorization": f"Bearer {token}"})
    assert list_res.status_code == 200
    mems = list_res.json().get("memories", [])
    texts = [m.get("text", "") for m in mems]
    assert any("Guest memory before migration" in t for t in texts)
