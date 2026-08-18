"""Cache-correctness tests.

The assignment treats a stale read after a status change as a bug, so these
tests assert both that the cache is actually used and that a write makes the
next read reflect the new state.
"""

import pytest_asyncio


@pytest_asyncio.fixture
async def project_id(auth_client):
    resp = await auth_client.post("/projects", json={"name": "Cache"})
    return resp.json()["id"]


async def test_task_list_is_cached(auth_client, project_id, fake_redis):
    await auth_client.post(f"/projects/{project_id}/tasks", json={"title": "cached"})
    await auth_client.get("/tasks")

    keys = [k async for k in fake_redis.scan_iter(match="tasks:list:*")]
    assert keys, "expected the task listing to be written to the cache"


async def test_status_change_invalidates_cache(auth_client, project_id):
    created = await auth_client.post(
        f"/projects/{project_id}/tasks", json={"title": "x", "status": "todo"}
    )
    task_id = created.json()["id"]

    # Prime the cache with the todo-filtered listing.
    first = await auth_client.get("/tasks", params={"status": "todo"})
    assert first.json()["total"] == 1

    # Change the status; the previously cached result must not be served.
    await auth_client.patch(f"/tasks/{task_id}", json={"status": "done"})

    after = await auth_client.get("/tasks", params={"status": "todo"})
    assert after.json()["total"] == 0, "stale cached result served after status change"


async def test_new_task_invalidates_cache(auth_client, project_id):
    await auth_client.post(f"/projects/{project_id}/tasks", json={"title": "one"})
    assert (await auth_client.get("/tasks")).json()["total"] == 1

    await auth_client.post(f"/projects/{project_id}/tasks", json={"title": "two"})
    assert (await auth_client.get("/tasks")).json()["total"] == 2
