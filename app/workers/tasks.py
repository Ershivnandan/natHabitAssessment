import asyncio

from app.core.database import SessionLocal
from app.services.notifications import (
    create_reassignment_notification,
    sweep_overdue_tasks,
)
from app.workers.celery_app import celery_app


def _run(coro):
    """Execute an async service call from a synchronous Celery worker."""
    return asyncio.run(coro)


async def _reassign(task_id: int, recipient_id: int) -> None:
    async with SessionLocal() as session:
        await create_reassignment_notification(session, task_id, recipient_id)


async def _sweep() -> int:
    async with SessionLocal() as session:
        return await sweep_overdue_tasks(session)


@celery_app.task(name="app.workers.tasks.notify_task_reassigned")
def notify_task_reassigned(task_id: int, recipient_id: int) -> None:
    _run(_reassign(task_id, recipient_id))


@celery_app.task(name="app.workers.tasks.scan_overdue_tasks")
def scan_overdue_tasks() -> int:
    return _run(_sweep())
