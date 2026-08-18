from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project, User
from app.schemas.project import ProjectCreate, ProjectUpdate


async def get_owned_project(session: AsyncSession, project_id: int, user: User) -> Project:
    """Fetch a project, enforcing that the caller owns it.

    Returns 404 (not 403) for projects owned by someone else so the API does
    not disclose the existence of resources the caller may not access.
    """
    project = await session.get(Project, project_id)
    if project is None or project.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


async def list_projects(session: AsyncSession, user: User) -> list[Project]:
    result = await session.scalars(
        select(Project).where(Project.owner_id == user.id).order_by(Project.id)
    )
    return list(result)


async def create_project(session: AsyncSession, data: ProjectCreate, user: User) -> Project:
    project = Project(name=data.name, description=data.description, owner_id=user.id)
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def update_project(
    session: AsyncSession, project_id: int, data: ProjectUpdate, user: User
) -> Project:
    project = await get_owned_project(session, project_id, user)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    await session.commit()
    await session.refresh(project)
    return project


async def delete_project(session: AsyncSession, project_id: int, user: User) -> None:
    project = await get_owned_project(session, project_id, user)
    await session.delete(project)
    await session.commit()
