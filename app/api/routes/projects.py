from fastapi import APIRouter, status

from app.api.deps import CurrentUser, SessionDep
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from app.services import projects as service

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectRead])
async def list_projects(session: SessionDep, current_user: CurrentUser) -> list[ProjectRead]:
    projects = await service.list_projects(session, current_user)
    return [ProjectRead.model_validate(p) for p in projects]


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    data: ProjectCreate, session: SessionDep, current_user: CurrentUser
) -> ProjectRead:
    project = await service.create_project(session, data, current_user)
    return ProjectRead.model_validate(project)


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: int, session: SessionDep, current_user: CurrentUser
) -> ProjectRead:
    project = await service.get_owned_project(session, project_id, current_user)
    return ProjectRead.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: int, data: ProjectUpdate, session: SessionDep, current_user: CurrentUser
) -> ProjectRead:
    project = await service.update_project(session, project_id, data, current_user)
    return ProjectRead.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int, session: SessionDep, current_user: CurrentUser
) -> None:
    await service.delete_project(session, project_id, current_user)
