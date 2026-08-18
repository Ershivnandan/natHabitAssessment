from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep
from app.models import Notification
from app.schemas.notification import NotificationRead

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationRead])
async def list_notifications(
    session: SessionDep,
    current_user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[NotificationRead]:
    result = await session.scalars(
        select(Notification)
        .where(Notification.recipient_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return [NotificationRead.model_validate(n) for n in result]
