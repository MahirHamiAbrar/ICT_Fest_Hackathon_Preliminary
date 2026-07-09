"""Business rule 15 (Registration) and rule 8 (Auth) + auth API contract."""
from datetime import timedelta

from tests.conftest import (
    DEFAULT_PASSWORD,
    assert_error,
    decode_claims,
    login_raw,
    new_admin,
    new_member,
    register_raw,
    unique,
)


# ---------------------------------------------------------------------------
# Rule 15: Registration
# ---------------------------------------------------------------------------

def test_register_unknown_org_creates_org_and_admin(client):
    org = unique("org")
    resp = register_raw(client, org, "alice")
    assert resp.status_code == 201
    body = resp.json()
    assert set(body.keys()) == {"user_id", "org_id", "username", "role"}
    assert body["username"] == "alice"
    assert body["role"] == "admin"


def test_register_known_org_joins_as_member(client):
    org = unique("org")
    first = register_raw(client, org, "alice").json()
    second = register_raw(client, org, "bob").json()
    assert first["role"] == "admin"
    assert second["role"] == "member"
    assert second["org_id"] == first["org_id"]


def test_register_duplicate_username_in_org_is_rejected(client):
    org = unique("org")
    register_raw(client, org, "alice", "correct-password")
    dup = register_raw(client, org, "alice", "correct-password")
    assert_error(dup, 409, "USERNAME_TAKEN")


def test_register_duplicate_username_rejected_even_with_different_password(client):
    """A duplicate-username registration must not silently succeed/impersonate."""
    org = unique("org")
    register_raw(client, org, "alice", "correct-password")
    dup = register_raw(client, org, "alice", "totally-different-password")
    assert_error(dup, 409, "USERNAME_TAKEN")


def test_same_username_allowed_in_different_orgs(client):
    org_a = unique("org")
    org_b = unique("org")
    a = register_raw(client, org_a, "alice")
    b = register_raw(client, org_b, "alice")
    assert a.status_code == 201
    assert b.status_code == 201
    assert a.json()["org_id"] != b.json()["org_id"]


# ---------------------------------------------------------------------------
# Login contract
# ---------------------------------------------------------------------------

def test_login_success_shape(client):
    org = unique("org")
    register_raw(client, org, "alice")
    resp = login_raw(client, org, "alice")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"access_token", "refresh_token", "token_type"}
    assert body["token_type"] == "bearer"


def test_login_wrong_password_is_invalid_credentials(client):
    org = unique("org")
    register_raw(client, org, "alice")
    resp = login_raw(client, org, "alice", "wrong-password")
    assert_error(resp, 401, "INVALID_CREDENTIALS")


def test_login_unknown_username_is_invalid_credentials(client):
    org = unique("org")
    register_raw(client, org, "alice")
    resp = login_raw(client, org, "nobody")
    assert_error(resp, 401, "INVALID_CREDENTIALS")


def test_login_unknown_org_is_invalid_credentials(client):
    resp = login_raw(client, unique("ghost-org"), "alice")
    assert_error(resp, 401, "INVALID_CREDENTIALS")


# ---------------------------------------------------------------------------
# Rule 8: JWT claims
# ---------------------------------------------------------------------------

def test_access_token_claims_shape(client):
    actor = new_admin(client)
    claims = decode_claims(actor.access_token)
    assert claims["sub"] == str(actor.user_id)
    assert isinstance(claims["sub"], str)
    assert claims["org"] == actor.org_id
    assert claims["role"] == actor.role
    assert claims["type"] == "access"
    assert "jti" in claims and isinstance(claims["jti"], str)
    assert "iat" in claims and "exp" in claims


def test_refresh_token_claims_shape(client):
    actor = new_admin(client)
    claims = decode_claims(actor.refresh_token)
    assert claims["sub"] == str(actor.user_id)
    assert claims["type"] == "refresh"
    assert "jti" in claims


def test_access_token_lifetime_is_exactly_900_seconds(client):
    actor = new_admin(client)
    claims = decode_claims(actor.access_token)
    assert claims["exp"] - claims["iat"] == 900


def test_refresh_token_lifetime_is_exactly_7_days(client):
    actor = new_admin(client)
    claims = decode_claims(actor.refresh_token)
    assert claims["exp"] - claims["iat"] == int(timedelta(days=7).total_seconds())


def test_jti_is_unique_per_token(client):
    actor = new_admin(client)
    access_claims = decode_claims(actor.access_token)
    refresh_claims = decode_claims(actor.refresh_token)
    assert access_claims["jti"] != refresh_claims["jti"]

    # Logging in again must mint fresh tokens with fresh jtis.
    second_login = login_raw(client, actor.org_name, actor.username).json()
    second_claims = decode_claims(second_login["access_token"])
    assert second_claims["jti"] != access_claims["jti"]


# ---------------------------------------------------------------------------
# Rule 8: Logout invalidation
# ---------------------------------------------------------------------------

def test_logout_invalidates_the_presented_access_token(client):
    actor = new_admin(client)
    ok = client.get("/rooms", headers=actor.headers)
    assert ok.status_code == 200

    logout = client.post("/auth/logout", headers=actor.headers)
    assert logout.status_code == 200

    reused = client.get("/rooms", headers=actor.headers)
    assert reused.status_code == 401


def test_logout_does_not_invalidate_other_users_tokens(client):
    org = unique("org")
    alice = new_admin(client, org)
    bob = new_member(client, alice.org_name)

    client.post("/auth/logout", headers=alice.headers)

    still_ok = client.get("/rooms", headers=bob.headers)
    assert still_ok.status_code == 200


def test_logout_requires_auth(client):
    resp = client.post("/auth/logout")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Rule 8: Refresh rotation / single use
# ---------------------------------------------------------------------------

def test_refresh_returns_new_access_and_refresh_token(client):
    actor = new_admin(client)
    resp = client.post("/auth/refresh", json={"refresh_token": actor.refresh_token})
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"access_token", "refresh_token", "token_type"}
    assert body["token_type"] == "bearer"
    assert body["access_token"] != actor.access_token
    assert body["refresh_token"] != actor.refresh_token

    # New access token must actually work.
    resp2 = client.get("/rooms", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert resp2.status_code == 200


def test_refresh_token_is_single_use(client):
    actor = new_admin(client)
    first = client.post("/auth/refresh", json={"refresh_token": actor.refresh_token})
    assert first.status_code == 200

    reused = client.post("/auth/refresh", json={"refresh_token": actor.refresh_token})
    assert reused.status_code == 401


def test_access_token_cannot_be_used_as_refresh_token(client):
    actor = new_admin(client)
    resp = client.post("/auth/refresh", json={"refresh_token": actor.access_token})
    assert resp.status_code == 401


def test_refresh_token_cannot_be_used_as_access_token(client):
    actor = new_admin(client)
    resp = client.get("/rooms", headers={"Authorization": f"Bearer {actor.refresh_token}"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# General token validation
# ---------------------------------------------------------------------------

def test_missing_token_is_401(client):
    resp = client.get("/rooms")
    assert resp.status_code == 401


def test_malformed_token_is_401(client):
    resp = client.get("/rooms", headers={"Authorization": "Bearer garbage.not.a.jwt"})
    assert resp.status_code == 401


def test_token_signed_with_wrong_secret_is_401(client):
    import jwt as pyjwt

    from app.config import JWT_ALGORITHM

    bad_token = pyjwt.encode(
        {"sub": "1", "org": 1, "role": "admin", "jti": "x", "iat": 0, "exp": 9999999999, "type": "access"},
        "some-other-secret",
        algorithm=JWT_ALGORITHM,
    )
    resp = client.get("/rooms", headers={"Authorization": f"Bearer {bad_token}"})
    assert resp.status_code == 401


def test_expired_token_is_401(client):
    import time as _time

    import jwt as pyjwt

    from app.config import JWT_ALGORITHM, JWT_SECRET

    now = int(_time.time())
    expired = pyjwt.encode(
        {"sub": "1", "org": 1, "role": "admin", "jti": "x", "iat": now - 1000, "exp": now - 10, "type": "access"},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )
    resp = client.get("/rooms", headers={"Authorization": f"Bearer {expired}"})
    assert resp.status_code == 401
