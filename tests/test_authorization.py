"""Authorization boundary tests: one user must never reach another's data."""

import pytest_asyncio


@pytest_asyncio.fixture
async def two_users(client):
    async def make(email):
        await client.post("/auth/signup", json={"email": email, "password": "password123"})
        resp = await client.post("/auth/login", json={"email": email, "password": "password123"})
        return resp.json()["access_token"]

    return {"alice": await make("a@example.com"), "bob": await make("b@example.com")}


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


async def test_user_cannot_read_another_users_project(client, two_users):
    created = await client.post(
        "/projects", json={"name": "Alice project"}, headers=_auth(two_users["alice"])
    )
    project_id = created.json()["id"]

    resp = await client.get(f"/projects/{project_id}", headers=_auth(two_users["bob"]))
    assert resp.status_code == 404


async def test_user_cannot_update_another_users_project(client, two_users):
    created = await client.post(
        "/projects", json={"name": "Alice project"}, headers=_auth(two_users["alice"])
    )
    project_id = created.json()["id"]

    resp = await client.patch(
        f"/projects/{project_id}", json={"name": "hijacked"}, headers=_auth(two_users["bob"])
    )
    assert resp.status_code == 404


async def test_user_cannot_create_task_in_another_users_project(client, two_users):
    created = await client.post(
        "/projects", json={"name": "Alice project"}, headers=_auth(two_users["alice"])
    )
    project_id = created.json()["id"]

    resp = await client.post(
        f"/projects/{project_id}/tasks", json={"title": "sneaky"}, headers=_auth(two_users["bob"])
    )
    assert resp.status_code == 404


async def test_task_list_is_scoped_to_owner(client, two_users):
    created = await client.post(
        "/projects", json={"name": "Alice project"}, headers=_auth(two_users["alice"])
    )
    project_id = created.json()["id"]
    await client.post(
        f"/projects/{project_id}/tasks",
        json={"title": "Alice task"},
        headers=_auth(two_users["alice"]),
    )

    resp = await client.get("/tasks", headers=_auth(two_users["bob"]))
    assert resp.status_code == 200
    assert resp.json()["total"] == 0
