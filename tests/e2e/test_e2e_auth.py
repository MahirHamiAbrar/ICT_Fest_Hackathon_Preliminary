"""Tier 1 E2E workflows: auth token lifecycle (A1–A6)."""

from tests.conftest import (
    assert_error,
    auth_header,
    login_raw,
    new_admin,
    register_raw,
    unique,
)


def test_a1_login_refresh_logout(client):
    """A1: POST /auth/login → POST /auth/refresh → POST /auth/logout"""
    actor = new_admin(client)

    rooms = client.get("/rooms", headers=actor.headers)
    assert rooms.status_code == 200

    refreshed = client.post(
        "/auth/refresh", json={"refresh_token": actor.refresh_token}
    )
    assert refreshed.status_code == 200
    new_tokens = refreshed.json()
    new_access = new_tokens["access_token"]

    assert client.get("/rooms", headers=auth_header(new_access)).status_code == 200

    logout = client.post("/auth/logout", headers=auth_header(new_access))
    assert logout.status_code == 200
    assert logout.json() == {"status": "ok"}

    assert client.get("/rooms", headers=auth_header(new_access)).status_code == 401


def test_a2_refresh_token_is_single_use(client):
    """A2: login → refresh → refresh with old token → 401"""
    actor = new_admin(client)

    first = client.post("/auth/refresh", json={"refresh_token": actor.refresh_token})
    assert first.status_code == 200

    reused = client.post("/auth/refresh", json={"refresh_token": actor.refresh_token})
    assert reused.status_code == 401


def test_a3_logout_invalidates_access_token(client):
    """A3: login → logout → GET /rooms with old access → 401"""
    actor = new_admin(client)

    logout = client.post("/auth/logout", headers=actor.headers)
    assert logout.status_code == 200

    assert client.get("/rooms", headers=actor.headers).status_code == 401


def test_a4_refresh_still_works_after_logout(client):
    """A4: login → logout → refresh → new access works"""
    actor = new_admin(client)

    client.post("/auth/logout", headers=actor.headers)

    refreshed = client.post(
        "/auth/refresh", json={"refresh_token": actor.refresh_token}
    )
    assert refreshed.status_code == 200
    new_access = refreshed.json()["access_token"]
    assert client.get("/rooms", headers=auth_header(new_access)).status_code == 200


def test_a5_refresh_then_use_new_access_token(client):
    """A5: login → refresh → GET /rooms with new access"""
    actor = new_admin(client)

    refreshed = client.post(
        "/auth/refresh", json={"refresh_token": actor.refresh_token}
    )
    assert refreshed.status_code == 200
    new_access = refreshed.json()["access_token"]

    rooms = client.get("/rooms", headers=auth_header(new_access))
    assert rooms.status_code == 200
    assert isinstance(rooms.json(), list)


def test_a6_login_with_bad_credentials(client):
    """A6: login with wrong password → 401 INVALID_CREDENTIALS"""
    org = unique("org")
    register_raw(client, org, "alice")

    bad = login_raw(client, org, "alice", "wrong-password")
    assert_error(bad, 401, "INVALID_CREDENTIALS")
