from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings

# bcrypt operates on at most 72 bytes; longer inputs are silently truncated by
# the algorithm, so we cap explicitly to make the behaviour obvious.
_MAX_PASSWORD_BYTES = 72


def _encode(raw_password: str) -> bytes:
    return raw_password.encode("utf-8")[:_MAX_PASSWORD_BYTES]


def hash_password(raw_password: str) -> str:
    return bcrypt.hashpw(_encode(raw_password), bcrypt.gensalt()).decode("utf-8")


def verify_password(raw_password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_encode(raw_password), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(subject: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_ttl_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
