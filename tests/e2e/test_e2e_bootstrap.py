"""Tier 0 E2E workflows: bootstrap and registration (W0–W4)."""

from tests.conftest import (
    DEFAULT_PASSWORD,
    assert_error,
    login_raw,
    register_raw,
    unique,
)


def test_w0_health(client):
    """W0: GET /health"""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_w1_register_new_org_then_login(client):
    """W1: POST /auth/register (new org) → POST /auth/login"""
    org = unique("org")
    reg = register_raw(client, org, "alice")
    assert reg.status_code == 201
    body = reg.json()
    assert body["role"] == "admin"
    assert body["username"] == "alice"

    login = login_raw(client, org, "alice")
    assert login.status_code == 200
    tokens = login.json()
    assert set(tokens.keys()) == {"access_token", "refresh_token", "token_type"}
    assert tokens["token_type"] == "bearer"


def test_w2_admin_registers_org_member_joins_then_member_logs_in(client):
    """W2: register admin → register member → login member"""
    org = unique("org")
    admin_reg = register_raw(client, org, "alice")
    assert admin_reg.status_code == 201
    assert admin_reg.json()["role"] == "admin"

    member_reg = register_raw(client, org, "bob")
    assert member_reg.status_code == 201
    member_body = member_reg.json()
    assert member_body["role"] == "member"
    assert member_body["org_id"] == admin_reg.json()["org_id"]

    login = login_raw(client, org, "bob")
    assert login.status_code == 200
    assert login.json()["token_type"] == "bearer"


def test_w3_duplicate_username_in_same_org_is_rejected(client):
    """W3: register → register same username → 409 USERNAME_TAKEN"""
    org = unique("org")
    first = register_raw(client, org, "alice", DEFAULT_PASSWORD)
    assert first.status_code == 201

    dup = register_raw(client, org, "alice", DEFAULT_PASSWORD)
    assert_error(dup, 409, "USERNAME_TAKEN")


def test_w4_same_username_allowed_in_different_orgs(client):
    """W4: register org A → register org B with same username"""
    org_a = unique("org")
    org_b = unique("org")
    a = register_raw(client, org_a, "alice")
    b = register_raw(client, org_b, "alice")
    assert a.status_code == 201
    assert b.status_code == 201
    assert a.json()["org_id"] != b.json()["org_id"]
