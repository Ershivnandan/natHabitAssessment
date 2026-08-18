from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from app.api.deps import SessionDep
from app.core.cache import get_redis

router = APIRouter(tags=["ops"])


@router.get("/health")
async def health(session: SessionDep) -> dict:
    """Liveness plus a dependency check on Postgres and Redis."""
    checks = {"database": False, "redis": False}
    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        pass
    try:
        checks["redis"] = bool(await get_redis().ping())
    except Exception:
        pass

    ok = all(checks.values())
    return {"status": "ok" if ok else "degraded", "checks": checks}


@router.get("/metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
