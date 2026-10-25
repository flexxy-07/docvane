import asyncio
from typing import Any

import redis.asyncio as aioredis
from sqlalchemy import text

from backend.app.core.config import settings
from backend.app.db.session import engine


async def check_database() -> dict[str, Any]:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "healthy"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


async def check_redis() -> dict[str, Any]:
    try:
        client = aioredis.from_url(settings.REDIS_URL, socket_timeout=2.0)
        await client.ping()
        await client.aclose()
        return {"status": "healthy"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


async def check_all_services() -> dict[str, Any]:
    db_res, redis_res = await asyncio.gather(
        check_database(),
        check_redis(),
    )

    all_healthy = db_res.get("status") == "healthy" and redis_res.get("status") == "healthy"

    return {
        "status": "ready" if all_healthy else "degraded",
        "services": {"database": db_res, "redis": redis_res},
    }
