import hashlib
import json

import redis.asyncio as redis
import structlog

from app.core.config import get_settings

logger = structlog.get_logger()
_client: redis.Redis | None = None

# TTLs in seconds
TTL_ARCHITECTURE = 86_400  # 24h — static analysis is deterministic
TTL_CODE_REVIEW = 3_600  # 1h
TTL_DOCUMENTATION = 3_600  # 1h
TTL_ONBOARDING = 3_600  # 1h
TTL_CHAT = 1_800  # 30m — same question gets instant replay


async def get_redis() -> redis.Redis | None:
    global _client
    if _client is not None:
        return _client
    try:
        _client = redis.from_url(get_settings().redis_url, decode_responses=True)
        await _client.ping()
        logger.info("redis_connected")
        return _client
    except Exception as error:
        logger.warning("redis_unavailable", error=str(error))
        _client = None
        return None


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def _hash_key(*parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]
    return digest


async def cache_get(namespace: str, *key_parts: str) -> str | None:
    client = await get_redis()
    if client is None:
        return None
    try:
        return await client.get(f"ghm:{namespace}:{_hash_key(*key_parts)}")
    except Exception as error:
        logger.warning("cache_get_failed", namespace=namespace, error=str(error))
        return None


async def cache_set(namespace: str, value: str, ttl: int, *key_parts: str) -> None:
    client = await get_redis()
    if client is None:
        return
    try:
        await client.setex(f"ghm:{namespace}:{_hash_key(*key_parts)}", ttl, value)
    except Exception as error:
        logger.warning("cache_set_failed", namespace=namespace, error=str(error))



