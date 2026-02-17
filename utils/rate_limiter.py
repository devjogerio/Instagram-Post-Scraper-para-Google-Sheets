import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional, Protocol, TYPE_CHECKING

from utils.logging_config import get_logger

try:  # pragma: no cover - import de infraestrutura
    import redis  # type: ignore[import]
except ModuleNotFoundError:  # pragma: no cover - ambiente sem redis instalado
    redis = None  # type: ignore[assignment]


RateLimitStrategy = Literal["token_bucket", "sliding_window"]
UserType = Literal["anonymous", "authenticated"]


logger = get_logger(__name__)


@dataclass
class LimitConfig:
    requests: int
    window_seconds: int
    strategy: RateLimitStrategy = "token_bucket"


@dataclass
class RateLimitResult:
    allowed: bool
    remaining: int
    reset_at: Optional[float]


class RateLimitExceededError(Exception):
    def __init__(self, message: str, retry_after: Optional[float] = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class RateLimitStorage(Protocol):
    def get(self, key: str) -> Optional[str]:
        ...

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        ...


class InMemoryRateLimitStorage:
    def __init__(self) -> None:
        self._store: Dict[str, tuple[str, float]] = {}

    def get(self, key: str) -> Optional[str]:
        entry = self._store.get(key)
        if not entry:
            return None
        value, expires_at = entry
        if expires_at < time.time():
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        expires_at = time.time() + ttl_seconds
        self._store[key] = (value, expires_at)


class RedisRateLimitStorage:
    def __init__(self, client: Any) -> None:
        if redis is None:
            raise RuntimeError("redis não está instalado no ambiente atual")
        self._client = client

    def get(self, key: str) -> Optional[str]:
        value = self._client.get(key)
        if value is None:
            return None
        return value.decode("utf-8")

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        self._client.setex(key, ttl_seconds, value)


class RateLimiter:
    def __init__(
        self,
        storage: RateLimitStorage,
        limits_by_endpoint: Dict[str, Dict[UserType, LimitConfig]],
        default_limit: LimitConfig,
    ) -> None:
        self._storage = storage
        self._limits_by_endpoint = limits_by_endpoint
        self._default_limit = default_limit

    def _build_key(
        self,
        endpoint: str,
        user_type: UserType,
        identifier: Optional[str],
    ) -> str:
        suffix = identifier or "anonymous"
        return f"rl:{endpoint}:{user_type}:{suffix}"

    def _resolve_limit(self, endpoint: str, user_type: UserType) -> LimitConfig:
        endpoint_limits = self._limits_by_endpoint.get(endpoint) or {}
        limit = endpoint_limits.get(user_type)
        if limit:
            return limit
        wildcard_limits = self._limits_by_endpoint.get("*") or {}
        wildcard_limit = wildcard_limits.get(user_type)
        if wildcard_limit:
            return wildcard_limit
        return self._default_limit

    def check(
        self,
        endpoint: str,
        user_type: UserType,
        identifier: Optional[str] = None,
        now: Optional[float] = None,
    ) -> RateLimitResult:
        current_time = now or time.time()
        key = self._build_key(endpoint, user_type, identifier)
        limit = self._resolve_limit(endpoint, user_type)

        if limit.strategy == "token_bucket":
            result = self._check_token_bucket(key, limit, current_time)
        else:
            result = self._check_sliding_window(key, limit, current_time)

        payload = {
            "endpoint": endpoint,
            "user_type": user_type,
            "identifier": identifier or "anonymous",
            "strategy": limit.strategy,
            "allowed": result.allowed,
            "remaining": result.remaining,
            "reset_at": result.reset_at,
        }

        logger.info("rate_limit_event=%s", json.dumps(
            payload, ensure_ascii=False))

        if not result.allowed:
            message = "Limite de requisições excedido"
            raise RateLimitExceededError(message, retry_after=result.reset_at)

        return result

    def _check_token_bucket(
        self,
        key: str,
        limit: LimitConfig,
        now: float,
    ) -> RateLimitResult:
        raw = self._storage.get(key)
        capacity = limit.requests
        refill_rate = capacity / float(limit.window_seconds)

        if raw is None:
            tokens = float(capacity - 1)
            state = {"tokens": tokens, "last": now}
            self._storage.set(key, json.dumps(state), limit.window_seconds)
            return RateLimitResult(True, int(tokens), now + limit.window_seconds)

        data = json.loads(raw)
        tokens = float(data.get("tokens", capacity))
        last = float(data.get("last", now))

        elapsed = max(0.0, now - last)
        tokens = min(float(capacity), tokens + elapsed * refill_rate)

        if tokens < 1.0:
            needed = 1.0 - tokens
            retry_after = now + needed / refill_rate
            state = {"tokens": tokens, "last": now}
            self._storage.set(key, json.dumps(state), limit.window_seconds)
            return RateLimitResult(False, int(tokens), retry_after)

        tokens -= 1.0
        state = {"tokens": tokens, "last": now}
        self._storage.set(key, json.dumps(state), limit.window_seconds)
        reset_at = now + (float(capacity) - tokens) / refill_rate
        return RateLimitResult(True, int(tokens), reset_at)

    def _check_sliding_window(
        self,
        key: str,
        limit: LimitConfig,
        now: float,
    ) -> RateLimitResult:
        raw = self._storage.get(key)
        window_start = now - float(limit.window_seconds)

        if raw is None:
            timestamps = [now]
        else:
            timestamps = [float(v) for v in json.loads(raw)]
            timestamps = [t for t in timestamps if t >= window_start]
            timestamps.append(now)

        used = len(timestamps)
        remaining = limit.requests - used

        self._storage.set(
            key,
            json.dumps(timestamps),
            limit.window_seconds,
        )

        if used > limit.requests:
            first = min(timestamps)
            reset_at = first + float(limit.window_seconds)
            return RateLimitResult(False, 0, reset_at)

        reset_at = window_start + float(limit.window_seconds)
        return RateLimitResult(True, max(0, remaining), reset_at)


class RateLimitMiddleware:
    def __init__(
        self,
        app: Any,
        rate_limiter: RateLimiter,
    ) -> None:
        self._app = app
        self._rate_limiter = rate_limiter

    def __call__(self, request: Any) -> Any:
        endpoint = getattr(request, "endpoint", "*")
        user_type: UserType
        identifier: Optional[str]

        if getattr(request, "user", None) and getattr(
            request.user, "is_authenticated", False
        ):
            user_type = "authenticated"
            identifier = getattr(request.user, "id", None)
        else:
            user_type = "anonymous"
            identifier = getattr(request, "client_ip", None)

        self._rate_limiter.check(endpoint, user_type, identifier)
        return self._app(request)


def build_redis_storage_from_url(url: str) -> RedisRateLimitStorage:
    if redis is None:
        raise RuntimeError("redis não está instalado no ambiente atual")
    client = redis.Redis.from_url(url)  # type: ignore[call-arg]
    return RedisRateLimitStorage(client)
