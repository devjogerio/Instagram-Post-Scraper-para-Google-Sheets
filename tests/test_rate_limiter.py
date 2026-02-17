import json
import time

from utils.rate_limiter import (
    InMemoryRateLimitStorage,
    LimitConfig,
    RateLimitExceededError,
    RateLimiter,
)


def _build_limiter(strategy: str) -> RateLimiter:
    storage = InMemoryRateLimitStorage()
    default = LimitConfig(requests=3, window_seconds=10, strategy=strategy)  # type: ignore[arg-type]
    limits_by_endpoint = {
        "/resource": {
            "anonymous": LimitConfig(
                requests=2,
                window_seconds=10,
                strategy=strategy,  # type: ignore[arg-type]
            )
        }
    }
    return RateLimiter(storage=storage, limits_by_endpoint=limits_by_endpoint, default_limit=default)


def test_token_bucket_allows_within_limit(monkeypatch):
    limiter = _build_limiter("token_bucket")

    fixed_time = 1_000_000.0
    monkeypatch.setattr(time, "time", lambda: fixed_time)

    for _ in range(2):
        result = limiter.check("/resource", "anonymous", identifier="ip-1")
        assert result.allowed


def test_token_bucket_blocks_after_limit(monkeypatch):
    limiter = _build_limiter("token_bucket")

    current = 1_000_000.0

    def fake_time() -> float:
        return current

    monkeypatch.setattr(time, "time", fake_time)

    for _ in range(2):
        limiter.check("/resource", "anonymous", identifier="ip-1")

    try:
        limiter.check("/resource", "anonymous", identifier="ip-1")
    except RateLimitExceededError as error:
        assert error.retry_after is not None
    else:
        assert False


def test_sliding_window_blocks_when_window_full(monkeypatch):
    limiter = _build_limiter("sliding_window")

    base = 1_000_000.0
    offsets = [0.0, 1.0, 2.0, 3.0]
    index = {"value": 0}

    def fake_time() -> float:
        value = base + offsets[index["value"]]
        index["value"] = min(index["value"] + 1, len(offsets) - 1)
        return value

    monkeypatch.setattr(time, "time", fake_time)

    limiter.check("/resource", "anonymous", identifier="ip-1")
    limiter.check("/resource", "anonymous", identifier="ip-1")

    try:
        limiter.check("/resource", "anonymous", identifier="ip-1")
    except RateLimitExceededError as error:
        assert error.retry_after is not None
    else:
        assert False


def test_different_limits_for_authenticated_user(monkeypatch):
    storage = InMemoryRateLimitStorage()
    default = LimitConfig(requests=1, window_seconds=10, strategy="token_bucket")  # type: ignore[arg-type]
    limits_by_endpoint = {
        "/protected": {
            "authenticated": LimitConfig(
                requests=5,
                window_seconds=10,
                strategy="token_bucket",  # type: ignore[arg-type]
            )
        }
    }
    limiter = RateLimiter(storage=storage, limits_by_endpoint=limits_by_endpoint, default_limit=default)

    fixed_time = 1_000_000.0
    monkeypatch.setattr(time, "time", lambda: fixed_time)

    for _ in range(5):
        limiter.check("/protected", "authenticated", identifier="user-1")

    try:
        limiter.check("/protected", "authenticated", identifier="user-1")
    except RateLimitExceededError:
        assert True
    else:
        assert False

