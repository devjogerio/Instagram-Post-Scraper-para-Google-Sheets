import time
from collections.abc import Callable
from functools import wraps
from typing import TypeVar, ParamSpec


P = ParamSpec("P")
R = TypeVar("R")


def sleep_between_calls(delay_seconds: float) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            time.sleep(delay_seconds)
            return func(*args, **kwargs)

        return wrapper

    return decorator

