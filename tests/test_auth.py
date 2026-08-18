

async def test_signup_returns_user_without_password(client):
    resp = await client.post(
        "/auth/signup", json={"email": "shiv@example.com", "password": "shiv@123"}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "shiv@example.com"
    assert "password" not in body
    assert "password_hash" not in body


async def test_signup_rejects_duplicate_email(client):
    payload = {"email": "shiv@example.com", "password": "shiv@123"}
    assert (await client.post("/auth/signup", json=payload)).status_code == 201
    assert (await client.post("/auth/signup", json=payload)).status_code == 409


async def test_signup_rejects_short_password(client):
    resp = await client.post("/auth/signup", json={"email": "x@example.com", "password": "short"})
    assert resp.status_code == 422


async def test_login_with_wrong_password_is_rejected(client):
    await client.post("/auth/signup", json={"email": "c@example.com", "password": "password123"})
    resp = await client.post("/auth/login", json={"email": "c@example.com", "password": "wrong"})
    assert resp.status_code == 401


async def test_login_for_unknown_email_is_rejected(client):
    resp = await client.post(
        "/auth/login", json={"email": "shiv@example.com", "password": "shiv@123"}
    )
    assert resp.status_code == 401


async def test_protected_route_requires_token(client):
    assert (await client.get("/auth/me")).status_code == 401


async def test_me_returns_current_user(auth_client):
    resp = await auth_client.get("/auth/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == "alice@example.com"
