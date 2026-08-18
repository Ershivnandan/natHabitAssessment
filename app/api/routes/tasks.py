import json
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query
from starlette import status

from app.api.deps import CurrentUser, SessionDep
from app.core.cache import get_redis, task_list_key
from app.core.config import settings
from app.models.task import TaskStatus
from app.schemas.task import PaginatedTasks, TaskCreate, TaskRead, TaskUpdate
from app.services import tasks as service
from app.services.tasks import TaskFilters

router = APIRouter(tags=["tasks"])


def _cache_key(user_id: int, version: str, params: dict) -> str:
    encoded = json.dumps(params, sort_keys=True, default=str)
    return f"tasks:list:{user_id}:v{version}:{encoded}"


@router.get("/tasks", response_model=PaginatedTasks)
async def list_tasks(
    session: SessionDep,
    current_user: CurrentUser,
    status: Annotated[TaskStatus | None, Query()] = None,
    assignee_id: Annotated[int | None, Query()] = None,
    due_after: Annotated[datetime | None, Query()] = None,
    due_before: Annotated[datetime | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PaginatedTasks:
    redis = get_redis()
    version = await redis.get(task_list_key(current_user.id)) or "0"
    params = {
        "status": status.value if status else None,
        "assignee_id": assignee_id,
        "due_after": due_after,
        "due_before": due_before,
        "limit": limit,
        "offset": offset,
    }
    key = _cache_key(current_user.id, version, params)

    cached = await redis.get(key)
    if cached is not None:
        return PaginatedTasks.model_validate_json(cached)

    filters = TaskFilters(status, assignee_id, due_before, due_after)
    items, total = await service.list_tasks(session, current_user, filters, limit, offset)
    response = PaginatedTasks(
        items=[TaskRead.model_validate(t) for t in items],
        total=total,
        limit=limit,
        offset=offset,
    )
    await redis.set(key, response.model_dump_json(), ex=settings.task_cache_ttl_seconds)
    return response


@router.post(
    "/projects/{project_id}/tasks",
    response_model=TaskRead,
    status_code=status.HTTP_201_CREATED,
    tags=["tasks"],
)
async def create_task(
    project_id: int, data: TaskCreate, session: SessionDep, current_user: CurrentUser
) -> TaskRead:
    task = await service.create_task(session, project_id, data, current_user)
    return TaskRead.model_validate(task)


@router.get("/tasks/{task_id}", response_model=TaskRead)
async def get_task(task_id: int, session: SessionDep, current_user: CurrentUser) -> TaskRead:
    task = await service.get_owned_task(session, task_id, current_user)
    return TaskRead.model_validate(task)


@router.patch("/tasks/{task_id}", response_model=TaskRead)
async def update_task(
    task_id: int, data: TaskUpdate, session: SessionDep, current_user: CurrentUser
) -> TaskRead:
    task = await service.update_task(session, task_id, data, current_user)
    return TaskRead.model_validate(task)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: int, session: SessionDep, current_user: CurrentUser) -> None:
    await service.delete_task(session, task_id, current_user)
