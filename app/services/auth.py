from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models import User
from app.schemas.auth import UserCreate, UserLogin

# A precomputed hash used to equalise login timing when the account is missing.
_DUMMY_HASH = hash_password("shivnandan")


async def register_user(session: AsyncSession, data: UserCreate) -> User:
    existing = await session.scalar(select(User).where(User.email == data.email))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )

    user = User(email=data.email, password_hash=hash_password(data.password))
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def authenticate_user(session: AsyncSession, data: UserLogin) -> User:
    user = await session.scalar(select(User).where(User.email == data.email))
    
    password_hash = user.password_hash if user is not None else _DUMMY_HASH
    password_ok = verify_password(data.password, password_hash)
    if user is None or not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )
    return user
