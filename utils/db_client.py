from collections.abc import Iterable
from typing import Any

import psycopg2

from config.settings import DatabaseConfig
from models.post import InstagramPost


def _get_connection(config: DatabaseConfig) -> Any:
    if not config.dsn:
        raise RuntimeError("DSN de banco de dados não configurado")
    return psycopg2.connect(config.dsn)


def init_post_table(config: DatabaseConfig) -> None:
    connection = _get_connection(config)
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS instagram_posts (
                        id SERIAL PRIMARY KEY,
                        post_url TEXT NOT NULL,
                        caption TEXT,
                        likes_count INTEGER NOT NULL,
                        comments_count INTEGER NOT NULL,
                        published_at TIMESTAMP WITH TIME ZONE NOT NULL,
                        media_type TEXT NOT NULL
                    )
                    """
                )
    finally:
        connection.close()


def save_posts_to_db(
    config: DatabaseConfig,
    posts: Iterable[InstagramPost],
) -> None:
    posts_list = list(posts)
    if not posts_list:
        return

    connection = _get_connection(config)
    try:
        with connection:
            with connection.cursor() as cursor:
                for post in posts_list:
                    cursor.execute(
                        """
                        INSERT INTO instagram_posts (
                            post_url,
                            caption,
                            likes_count,
                            comments_count,
                            published_at,
                            media_type
                        )
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            post.post_url,
                            post.caption,
                            post.likes_count,
                            post.comments_count,
                            post.published_at,
                            post.media_type,
                        ),
                    )
    finally:
        connection.close()

