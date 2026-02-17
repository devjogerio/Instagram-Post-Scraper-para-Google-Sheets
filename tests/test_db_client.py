from collections.abc import Iterable

from config.settings import DatabaseConfig
from models.post import InstagramPost
from utils import db_client


class _FakeCursor:
    def __init__(self) -> None:
        self.queries: list[tuple[str, tuple]] = []

    def execute(self, query: str, params: tuple) -> None:
        self.queries.append((query, params))

    def __enter__(self) -> "_FakeCursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class _FakeConnection:
    def __init__(self) -> None:
        self.cursor_instance = _FakeCursor()

    def cursor(self) -> _FakeCursor:
        return self.cursor_instance

    def __enter__(self) -> "_FakeConnection":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def close(self) -> None:
        return None


def _build_dummy_post() -> InstagramPost:
    from datetime import datetime

    return InstagramPost(
        post_url="https://instagram.com/p/abc",
        caption="teste",
        likes_count=1,
        comments_count=0,
        published_at=datetime.now(),
        media_type="image",
    )


def test_save_posts_to_db_executes_inserts(monkeypatch):
    fake_connection = _FakeConnection()

    def fake_get_connection(config: DatabaseConfig):
        return fake_connection

    monkeypatch.setattr(db_client, "_get_connection", fake_get_connection)

    config = DatabaseConfig(enabled=True, backend="postgres", dsn="dummy")
    posts: Iterable[InstagramPost] = [_build_dummy_post()]

    db_client.save_posts_to_db(config, posts)

    assert len(fake_connection.cursor_instance.queries) == 1

