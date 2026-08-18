import pytest_asyncio


@pytest_asyncio.fixture
async def project_id(auth_client):
    resp = await auth_client.post("/projects", json={"name": "Sprint"})
    return resp.json()["id"]


async def test_create_and_list_task(auth_client, project_id):
    resp = await auth_client.post(
        f"/projects/{project_id}/tasks", json={"title": "Write tests", "status": "todo"}
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "todo"

    listing = await auth_client.get("/tasks")
    assert listing.json()["total"] == 1


async def test_filter_by_status(auth_client, project_id):
    await auth_client.post(f"/projects/{project_id}/tasks", json={"title": "a", "status": "todo"})
    await auth_client.post(
        f"/projects/{project_id}/tasks", json={"title": "b", "status": "done"}
    )

    resp = await auth_client.get("/tasks", params={"status": "done"})
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "b"


async def test_filter_by_due_date_range(auth_client, project_id):
    await auth_client.post(
        f"/projects/{project_id}/tasks",
        json={"title": "early", "due_date": "2026-01-01T00:00:00Z"},
    )
    await auth_client.post(
        f"/projects/{project_id}/tasks",
        json={"title": "late", "due_date": "2026-12-31T00:00:00Z"},
    )

    resp = await auth_client.get(
        "/tasks", params={"due_after": "2026-06-01T00:00:00Z"}
    )
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "late"


async def test_pagination(auth_client, project_id):
    for i in range(5):
        await auth_client.post(f"/projects/{project_id}/tasks", json={"title": f"t{i}"})

    page = await auth_client.get("/tasks", params={"limit": 2, "offset": 2})
    body = page.json()
    assert body["total"] == 5
    assert len(body["items"]) == 2


async def test_update_task_status(auth_client, project_id):
    created = await auth_client.post(f"/projects/{project_id}/tasks", json={"title": "x"})
    task_id = created.json()["id"]

    resp = await auth_client.patch(f"/tasks/{task_id}", json={"status": "in_progress"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"


async def test_delete_task(auth_client, project_id):
    created = await auth_client.post(f"/projects/{project_id}/tasks", json={"title": "x"})
    task_id = created.json()["id"]

    assert (await auth_client.delete(f"/tasks/{task_id}")).status_code == 204
    assert (await auth_client.get(f"/tasks/{task_id}")).status_code == 404
