"""Contract: GET /health -> No auth, 200, {"status": "ok"}."""


def test_health_returns_ok_without_auth(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_health_ignores_bogus_auth_header(client):
    # No-auth endpoint: an invalid token must not be able to break it.
    resp = client.get("/health", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
