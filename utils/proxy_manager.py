from collections.abc import Iterator
from typing import Optional


def _load_proxies_from_file(path: str) -> list[str]:
    try:
        with open(path, "r", encoding="utf-8") as file:
            return [
                line.strip()
                for line in file.readlines()
                if line.strip() and not line.strip().startswith("#")
            ]
    except FileNotFoundError:
        return []


def proxy_cycle(path: Optional[str]) -> Iterator[Optional[str]]:
    if not path:
        while True:
            yield None

    proxies = _load_proxies_from_file(path)

    if not proxies:
        while True:
            yield None

    index = 0
    total = len(proxies)

    while True:
        yield proxies[index]
        index = (index + 1) % total

