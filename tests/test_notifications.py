"""Tests for notification creation via background-job logic.

These exercise the service functions the Celery tasks delegate to, plus the
enqueue-on-reassignment path in the request handler.
"""

from datetime import UTC, datetime, timedelta

import pytest_asyncio
from sqlalchemy import select

from app.models import Notification, NotificationType, Project, Task, TaskStatus, User
from app.services.notifications import sweep_overdue_tasks


@pytest_asyncio.fixture
async def seeded(session_factory):
    """A user with an assigned, already-overdue task that is not done."""
    async with session_factory() as session:
        user = User(email="owner@example.com", password_hash="x")
        assignee = User(email="assignee@example.com", password_hash="x")
        session.add_all([user, assignee])
        await session.flush()

        project = Project(name="P", owner_id=user.id)
        session.add(project)
        await session.flush()

        task = Task(
            title="Overdue task",
            project_id=project.id,
            assignee_id=assignee.id,
            due_date=datetime.now(UTC) - timedelta(hours=1),
            status=TaskStatus.todo,
        )
        session.add(task)
        await session.commit()
        return {"assignee_id": assignee.id, "task_id": task.id}


async def test_overdue_sweep_creates_notification(session_factory, seeded):
    async with session_factory() as session:
        created = await sweep_overdue_tasks(session)
    assert created == 1

    async with session_factory() as session:
        notifications = (await session.scalars(select(Notification))).all()
    assert len(notifications) == 1
    assert notifications[0].type == NotificationType.task_overdue
    assert notifications[0].recipient_id == seeded["assignee_id"]


async def test_overdue_sweep_is_idempotent(session_factory, seeded):
    async with session_factory() as session:
        assert await sweep_overdue_tasks(session) == 1
    async with session_factory() as session:
        # Second sweep must not emit a duplicate for the same task.
        assert await sweep_overdue_tasks(session) == 0


async def test_done_task_is_not_notified(session_factory):
    async with session_factory() as session:
        user = User(email="u@example.com", password_hash="x")
        session.add(user)
        await session.flush()
        project = Project(name="P", owner_id=user.id)
        session.add(project)
        await session.flush()
        session.add(
            Task(
                title="Done",
                project_id=project.id,
                assignee_id=user.id,
                due_date=datetime.now(UTC) - timedelta(hours=1),
                status=TaskStatus.done,
            )
        )
        await session.commit()

        assert await sweep_overdue_tasks(session) == 0


async def test_reassignment_enqueues_background_job(auth_client, monkeypatch):
    calls = []

    from app.workers import tasks as worker_tasks

    monkeypatch.setattr(
        worker_tasks.notify_task_reassigned, "delay", lambda *args: calls.append(args)
    )

    project = (await auth_client.post("/projects", json={"name": "P"})).json()
    other = await auth_client.post(
        "/auth/signup", json={"email": "target@example.com", "password": "password123"}
    )
    target_id = other.json()["id"]

    created = await auth_client.post(
        f"/projects/{project['id']}/tasks", json={"title": "assign me"}
    )
    task_id = created.json()["id"]

    await auth_client.patch(f"/tasks/{task_id}", json={"assignee_id": target_id})

    assert calls == [(task_id, target_id)]
