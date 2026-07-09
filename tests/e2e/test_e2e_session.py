"""Realistic session and authentication journeys."""

from tests.conftest import (
    assert_error,
    auth_header,
    login_raw,
    new_admin,
    register_raw,
    unique,
)


def test_register_alone_does_not_grant_api_access(client):
    """User registers but skips login → protected routes return 401."""
    org = unique("org")
    reg = register_raw(client, org, "alice")
    assert reg.status_code == 201

    assert client.get("/rooms").status_code == 401
    assert (
        client.post(
            "/bookings", json={"room_id": 1, "start_time": "x", "end_time": "y"}
        ).status_code
        == 401
    )


def test_logout_then_relogin_restores_full_access(client):
    """User logs out, logs back in, and can use the API again."""
    actor = new_admin(client)
    assert client.get("/rooms", headers=actor.headers).status_code == 200

    client.post("/auth/logout", headers=actor.headers)
    assert client.get("/rooms", headers=actor.headers).status_code == 401

    actor.relogin()
    assert client.get("/rooms", headers=actor.headers).status_code == 200


def test_refresh_mid_session_then_continue_working(client):
    """User refreshes tokens mid-session and keeps working without re-login."""
    admin = new_admin(client)
    room = admin.client.post(
        "/rooms",
        json={"name": "Refresh Room", "capacity": 4, "hourly_rate_cents": 1000},
        headers=admin.headers,
    ).json()

    refreshed = client.post(
        "/auth/refresh", json={"refresh_token": admin.refresh_token}
    )
    assert refreshed.status_code == 200
    new_headers = auth_header(refreshed.json()["access_token"])

    listed = client.get("/rooms", headers=new_headers)
    assert listed.status_code == 200
    assert room["id"] in {r["id"] for r in listed.json()}


def test_unauthenticated_retry_after_login(client):
    """User hits API without token, logs in, retries the same action."""
    admin = new_admin(client)
    room = admin.client.post(
        "/rooms",
        json={"name": "Retry Room", "capacity": 2, "hourly_rate_cents": 500},
        headers=admin.headers,
    ).json()

    denied = client.get("/rooms")
    assert denied.status_code == 401

    login = login_raw(client, admin.org_name, admin.username, admin.password)
    assert login.status_code == 200
    headers = auth_header(login.json()["access_token"])

    ok = client.get("/rooms", headers=headers)
    assert ok.status_code == 200
    assert room["id"] in {r["id"] for r in ok.json()}


def test_health_always_reachable_during_auth_lifecycle(client):
    """Health stays up through register, login, logout, and re-login."""
    org = unique("org")
    assert client.get("/health").json() == {"status": "ok"}

    register_raw(client, org, "alice")
    assert client.get("/health").json() == {"status": "ok"}

    login = login_raw(client, org, "alice")
    headers = auth_header(login.json()["access_token"])
    assert client.get("/health").json() == {"status": "ok"}

    client.post("/auth/logout", headers=headers)
    assert client.get("/health").json() == {"status": "ok"}

    relogin = login_raw(client, org, "alice")
    assert client.get("/health").json() == {"status": "ok"}
    assert (
        client.get(
            "/rooms", headers=auth_header(relogin.json()["access_token"])
        ).status_code
        == 200
    )


def test_double_refresh_rotation_chain(client):
    """User refreshes twice in a row, each time using only the latest refresh token."""
    admin = new_admin(client)

    first = client.post("/auth/refresh", json={"refresh_token": admin.refresh_token})
    assert first.status_code == 200
    first_body = first.json()

    second = client.post(
        "/auth/refresh", json={"refresh_token": first_body["refresh_token"]}
    )
    assert second.status_code == 200
    second_body = second.json()

    assert (
        client.get(
            "/rooms", headers=auth_header(second_body["access_token"])
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/auth/refresh", json={"refresh_token": first_body["refresh_token"]}
        ).status_code
        == 401
    )
