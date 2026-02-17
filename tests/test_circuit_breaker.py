import time

from utils.circuit_breaker import CircuitBreaker


def test_circuit_breaker_opens_on_failures(monkeypatch):
    cb = CircuitBreaker(max_failures=1, base_backoff_seconds=1, max_backoff_seconds=5)

    def failing():
        raise RuntimeError("fail")

    try:
        cb.execute(failing)
    except RuntimeError:
        pass

    now = time.time()
    monkeypatch.setattr(time, "time", lambda: now)

    try:
        cb.execute(lambda: "ok")
    except RuntimeError as e:
        assert str(e) == "circuit_open"
    else:
        assert False

    monkeypatch.setattr(time, "time", lambda: now + 2)
    result = cb.execute(lambda: "ok")
    assert result == "ok"

