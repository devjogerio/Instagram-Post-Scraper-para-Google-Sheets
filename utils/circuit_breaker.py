import time
from dataclasses import dataclass
from typing import Callable, Generic, Optional, TypeVar


T = TypeVar("T")


@dataclass
class CircuitState:
    state: str = "closed"
    failures: int = 0
    last_failure_at: Optional[float] = None
    next_try_at: Optional[float] = None


class CircuitBreaker(Generic[T]):
    def __init__(
        self,
        max_failures: int = 3,
        base_backoff_seconds: float = 0.5,
        max_backoff_seconds: float = 30.0,
    ) -> None:
        self._state = CircuitState()
        self._max_failures = max_failures
        self._base_backoff = base_backoff_seconds
        self._max_backoff = max_backoff_seconds

    def execute(self, fn: Callable[[], T]) -> T:
        now = time.time()
        if self._state.state == "open":
            if self._state.next_try_at and now < self._state.next_try_at:
                raise RuntimeError("circuit_open")
            self._state.state = "half_open"

        try:
            result = fn()
            self._state = CircuitState(state="closed")
            return result
        except Exception as exc:  # noqa: BLE001
            self._state.failures += 1
            self._state.last_failure_at = now

            backoff = min(self._max_backoff, self._base_backoff * (2 ** (self._state.failures - 1)))
            self._state.next_try_at = now + backoff
            self._state.state = "open"

            raise exc

