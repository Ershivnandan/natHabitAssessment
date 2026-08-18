from redis.asyncio import Redis

from app.core.config import settings

_redis: Redis | None = None


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


def task_list_key(user_id: int) -> str:
    """Namespaced version pointer for a user's cached task-list responses."""
    return f"tasks:version:{user_id}"


async def bump_task_cache_version(user_id: int) -> None:
    """Invalidate a user's cached task listings by advancing their version counter.

    Any keys encoding the old version become unreachable and expire via TTL,
    which keeps invalidation O(1) regardless of how many filter combinations
    were cached.
    """
    await get_redis().incr(task_list_key(user_id))
