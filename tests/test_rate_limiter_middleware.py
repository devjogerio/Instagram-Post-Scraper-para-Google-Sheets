from types import SimpleNamespace

from utils.rate_limiter import (
    InMemoryRateLimitStorage,
    LimitConfig,
    RateLimitExceededError,
    RateLimiter,
    RateLimitMiddleware,
)


def _build_middleware() -> RateLimitMiddleware:
    storage = InMemoryRateLimitStorage()
    default = LimitConfig(requests=1, window_seconds=10, strategy="token_bucket")  # type: ignore[arg-type]
    limits_by_endpoint = {
        "/endpoint": {
            "anonymous": LimitConfig(
                requests=1,
                window_seconds=10,
                strategy="token_bucket",  # type: ignore[arg-type]
            )
        }
    }
    limiter = RateLimiter(storage=storage, limits_by_endpoint=limits_by_endpoint, default_limit=default)

    def app(request: object) -> str:
        return "ok"

    return RateLimitMiddleware(app, limiter)


def test_middleware_blocks_after_limit():
    middleware = _build_middleware()

    request = SimpleNamespace(endpoint="/endpoint", user=None, client_ip="127.0.0.1")

    response = middleware(request)
    assert response == "ok"

    try:
        middleware(request)
    except RateLimitExceededError:
        assert True
    else:
        assert False

