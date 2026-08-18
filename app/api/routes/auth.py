from fastapi import APIRouter, status

from app.api.deps import CurrentUser, SessionDep
from app.core.security import create_access_token
from app.schemas.auth import Token, UserCreate, UserLogin, UserRead
from app.services.auth import authenticate_user, register_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def signup(data: UserCreate, session: SessionDep) -> UserRead:
    user = await register_user(session, data)
    return UserRead.model_validate(user)


@router.post("/login", response_model=Token)
async def login(data: UserLogin, session: SessionDep) -> Token:
    user = await authenticate_user(session, data)
    return Token(access_token=create_access_token(str(user.id)))


@router.get("/me", response_model=UserRead)
async def me(current_user: CurrentUser) -> UserRead:
    return UserRead.model_validate(current_user)
