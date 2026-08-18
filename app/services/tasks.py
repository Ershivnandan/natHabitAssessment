from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import bump_task_cache_version
from app.models import Project, Task, TaskStatus, User
from app.schemas.task import TaskCreate, TaskUpdate
from app.services.projects import get_owned_project


class TaskFilters:
    def __init__(
        self,
        status: TaskStatus | None = None,
        assignee_id: int | None = None,
        due_before: datetime | None = None,
        due_after: datetime | None = None,
    ):
        self.status = status
        self.assignee_id = assignee_id
        self.due_before = due_before
        self.due_after = due_after


def _owned_task_query(user: User) -> Select:
    """Base query scoped to tasks in projects the caller owns."""
    return select(Task).join(Project, Task.project_id == Project.id).where(
        Project.owner_id == user.id
    )


def _apply_filters(query: Select, filters: TaskFilters) -> Select:
    if filters.status is not None:
        query = query.where(Task.status == filters.status)
    if filters.assignee_id is not None:
        query = query.where(Task.assignee_id == filters.assignee_id)
    if filters.due_after is not None:
        query = query.where(Task.due_date >= filters.due_after)
    if filters.due_before is not None:
        query = query.where(Task.due_date <= filters.due_before)
    return query


async def get_owned_task(session: AsyncSession, task_id: int, user: User) -> Task:
    task = await session.scalar(_owned_task_query(user).where(Task.id == task_id))
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


async def list_tasks(
    session: AsyncSession, user: User, filters: TaskFilters, limit: int, offset: int
) -> tuple[list[Task], int]:
    filtered = _apply_filters(_owned_task_query(user), filters)

    total = await session.scalar(select(func.count()).select_from(filtered.subquery()))
    result = await session.scalars(
        filtered.order_by(Task.id).limit(limit).offset(offset)
    )
    return list(result), int(total or 0)


async def create_task(
    session: AsyncSession, project_id: int, data: TaskCreate, user: User
) -> Task:
    await get_owned_project(session, project_id, user)
    task = Task(project_id=project_id, **data.model_dump())
    session.add(task)
    await session.commit()
    await session.refresh(task)
    await bump_task_cache_version(user.id)
    return task


async def update_task(
    session: AsyncSession, task_id: int, data: TaskUpdate, user: User
) -> Task:
    task = await get_owned_task(session, task_id, user)
    changes = data.model_dump(exclude_unset=True)

    previous_assignee = task.assignee_id
    for field, value in changes.items():
        setattr(task, field, value)

    # Re-arm the overdue notification whenever the due date is pushed out or the
    # task moves off "done", so a task that becomes overdue again is picked up.
    if "due_date" in changes or ("status" in changes and task.status != TaskStatus.done):
        task.overdue_notified = False

    await session.commit()
    await session.refresh(task)
    await bump_task_cache_version(user.id)

    new_assignee = task.assignee_id
    if new_assignee is not None and new_assignee != previous_assignee:
        # Imported lazily to keep the web process independent of the Celery app.
        from app.workers.tasks import notify_task_reassigned

        notify_task_reassigned.delay(task.id, new_assignee)

    return task


async def delete_task(session: AsyncSession, task_id: int, user: User) -> None:
    task = await get_owned_task(session, task_id, user)
    await session.delete(task)
    await session.commit()
    await bump_task_cache_version(user.id)
