from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

RedisClient: Any
try:
    from redis import Redis as _RedisClient
except ModuleNotFoundError:  # pragma: no cover - optional adapter dependency
    RedisClient = None
else:
    RedisClient = _RedisClient


@dataclass
class RateLimitResult:
    allowed: bool
    remaining: int
    reset_seconds: int


class RedisRuntimeService:
    """Redis-backed short-term memory, stream status, and rate limiting."""

    backend_name = "redis"

    def __init__(self, redis_url: str, rate_limit_per_minute: int = 30) -> None:
        if RedisClient is None:
            raise RuntimeError("Install redis to use the Redis runtime service")
        self.redis_url = redis_url
        self.rate_limit_per_minute = rate_limit_per_minute
        self.client: Any = RedisClient.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        self.client.ping()

    def ping(self) -> bool:
        return bool(self.client.ping())

    def check_rate_limit(self, user_id: str) -> RateLimitResult:
        now = int(time.time())
        window = now // 60
        key = f"smartcs:rate:{user_id}:{window}"
        count = int(self.client.incr(key))
        if count == 1:
            self.client.expire(key, 70)
        remaining = max(0, self.rate_limit_per_minute - count)
        return RateLimitResult(
            allowed=count <= self.rate_limit_per_minute,
            remaining=remaining,
            reset_seconds=60 - (now % 60),
        )

    def cache_message(self, conversation_id: str, role: str, content: str) -> None:
        key = f"smartcs:memory:{conversation_id}"
        payload = json.dumps(
            {"role": role, "content": content, "timestamp": time.time()},
            ensure_ascii=False,
        )
        pipe = self.client.pipeline()
        pipe.rpush(key, payload)
        pipe.ltrim(key, -30, -1)
        pipe.expire(key, 3600)
        pipe.execute()

    def get_short_memory(self, conversation_id: str) -> list[dict[str, Any]]:
        key = f"smartcs:memory:{conversation_id}"
        rows = list(self.client.lrange(key, 0, -1))
        return [json.loads(row) for row in rows]

    def append_stream_event(
        self,
        conversation_id: str,
        event: str,
        data: dict[str, Any],
    ) -> None:
        key = f"smartcs:stream:{conversation_id}"
        self.client.xadd(
            key,
            {
                "event": event,
                "data": json.dumps(data, ensure_ascii=False, default=str),
                "timestamp": str(time.time()),
            },
            maxlen=500,
            approximate=True,
        )
        self.client.expire(key, 3600)

    def latest_stream_events(self, conversation_id: str, count: int = 50) -> list[dict[str, Any]]:
        key = f"smartcs:stream:{conversation_id}"
        rows = list(self.client.xrevrange(key, count=count))
        events: list[dict[str, Any]] = []
        for event_id, values in reversed(rows):
            events.append(
                {
                    "id": event_id,
                    "event": values.get("event"),
                    "data": json.loads(values.get("data", "{}")),
                    "timestamp": values.get("timestamp"),
                }
            )
        return events


class NullRuntimeService:
    """No-op runtime used when Redis is unavailable."""

    backend_name = "memory"

    def check_rate_limit(self, user_id: str) -> RateLimitResult:
        return RateLimitResult(allowed=True, remaining=999999, reset_seconds=60)

    def cache_message(self, conversation_id: str, role: str, content: str) -> None:
        return None

    def get_short_memory(self, conversation_id: str) -> list[dict[str, Any]]:
        return []

    def append_stream_event(
        self,
        conversation_id: str,
        event: str,
        data: dict[str, Any],
    ) -> None:
        return None

    def latest_stream_events(self, conversation_id: str, count: int = 50) -> list[dict[str, Any]]:
        return []
