import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notification, NotificationType, Task, TaskStatus

logger = logging.getLogger("taskflow.notifications")


async def _record(
    session: AsyncSession,
    *,
    recipient_id: int,
    task_id: int,
    type_: NotificationType,
    message: str,
) -> Notification:
    """Persist a notification and simulate delivery by writing to the log."""
    notification = Notification(
        recipient_id=recipient_id, task_id=task_id, type=type_, message=message
    )
    session.add(notification)
    await session.flush()
    logger.info("notification.delivered type=%s recipient=%s task=%s", type_.value,
                recipient_id, task_id)
    return notification


async def create_reassignment_notification(
    session: AsyncSession, task_id: int, recipient_id: int
) -> Notification | None:
    task = await session.get(Task, task_id)
    if task is None:
        return None
    notification = await _record(
        session,
        recipient_id=recipient_id,
        task_id=task_id,
        type_=NotificationType.task_reassigned,
        message=f"You have been assigned to task '{task.title}'.",
    )
    await session.commit()
    return notification


async def sweep_overdue_tasks(session: AsyncSession) -> int:
    """Create overdue notifications for tasks past due and not yet done.

    Each task is flagged with `overdue_notified` so repeated sweeps do not emit
    duplicate notifications. Returns the number of notifications created.
    """
    now = datetime.now(UTC)
    overdue = await session.scalars(
        select(Task).where(
            Task.due_date.is_not(None),
            Task.due_date < now,
            Task.status != TaskStatus.done,
            Task.overdue_notified.is_(False),
        )
    )

    count = 0
    for task in overdue:
        if task.assignee_id is not None:
            await _record(
                session,
                recipient_id=task.assignee_id,
                task_id=task.id,
                type_=NotificationType.task_overdue,
                message=f"Task '{task.title}' is overdue.",
            )
            count += 1
        task.overdue_notified = True

    await session.commit()
    return count
