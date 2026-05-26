"""SSE endpoint with Redis Pub/Sub dispatch."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator

import structlog
from fastapi import APIRouter, HTTPException, Query
from redis.asyncio import Redis
from sse_starlette.sse import EventSourceResponse

from app.core.sse_auth import validate_sse_token
from app.infrastructure.settings import get_settings

log = structlog.get_logger()

router = APIRouter(prefix="/sse", tags=["sse"])


async def _event_stream(user_id: str) -> AsyncGenerator[dict, None]:
    settings = get_settings()
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    channel = f"sse:user:{user_id}"

    try:
        pubsub = redis.pubsub()
        await pubsub.subscribe(channel)
        log.info("sse_subscribed", user_id=user_id, channel=channel)

        # Send initial retry directive
        yield {"retry": 3000}

        while True:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=30.0
            )
            if message and message["type"] == "message":
                data = message["data"]
                yield {"event": "notification", "data": data}
            else:
                # Send keepalive comment to prevent timeout
                yield {"comment": "keepalive"}
            await asyncio.sleep(0.1)

    except asyncio.CancelledError:
        log.info("sse_disconnected", user_id=user_id)
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
        await redis.aclose()


@router.get("/notifications")
async def sse_notifications(
    token: str = Query(..., description="JWT access token"),
) -> EventSourceResponse:
    user_id = validate_sse_token(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid token")

    return EventSourceResponse(_event_stream(str(user_id)))


async def publish_to_user(user_id: str, event_type: str, data: dict) -> None:
    """Publish an event to a specific user's SSE channel."""
    settings = get_settings()
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        channel = f"sse:user:{user_id}"
        payload = json.dumps({"type": event_type, **data})
        await redis.publish(channel, payload)
    finally:
        await redis.aclose()
