from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from config.settings import AppConfig
from models.post import InstagramPost
from utils.db_client import init_post_table, save_posts_to_db
from utils.sheets_client import append_posts_to_sheet


@runtime_checkable
class PostStorage(Protocol):
    def save_posts(self, posts: Iterable[InstagramPost]) -> None:
        ...


@dataclass
class SheetsPostStorage:
    app_config: AppConfig

    def save_posts(self, posts: Iterable[InstagramPost]) -> None:
        append_posts_to_sheet(self.app_config.google_sheets, posts)


@dataclass
class DatabasePostStorage:
    app_config: AppConfig

    def save_posts(self, posts: Iterable[InstagramPost]) -> None:
        if (
            not self.app_config.database.enabled
            or not self.app_config.database.backend
        ):
            return

        init_post_table(self.app_config.database)
        save_posts_to_db(self.app_config.database, posts)


def build_post_storages(app_config: AppConfig) -> list[PostStorage]:
    storages: list[PostStorage] = []

    storages.append(SheetsPostStorage(app_config=app_config))

    if app_config.database.enabled and app_config.database.backend:
        storages.append(DatabasePostStorage(app_config=app_config))

    return storages

