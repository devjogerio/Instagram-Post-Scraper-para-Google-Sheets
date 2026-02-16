from collections.abc import Iterable
from datetime import datetime
from typing import List

import instaloader

from config.settings import InstagramConfig
from models.post import InstagramPost


def _build_loader(proxy: str | None) -> instaloader.Instaloader:
    loader = instaloader.Instaloader()
    if proxy:
        loader.context._default_ip_address = proxy  # type: ignore[attr-defined]
    return loader


def fetch_posts_for_target(
    instagram_config: InstagramConfig,
    target: str,
    proxy: str | None = None,
    max_count: int = 20,
) -> List[InstagramPost]:
    loader = _build_loader(proxy)
    loader.login(instagram_config.username, instagram_config.password)

    posts_iter: Iterable[instaloader.Post]
    if target.startswith("#"):
        hashtag = target[1:]
        posts_iter = loader.get_hashtag_posts(hashtag)
    else:
        profile = instaloader.Profile.from_username(loader.context, target)
        posts_iter = profile.get_posts()

    posts: List[InstagramPost] = []

    for index, post in enumerate(posts_iter):
        if index >= max_count:
            break

        posts.append(
            InstagramPost(
                post_url=f"https://www.instagram.com/p/{post.shortcode}/",
                caption=post.caption or "",
                likes_count=post.likes,
                comments_count=post.comments,
                published_at=datetime.fromtimestamp(post.date_utc.timestamp()),
                media_type=post.typename,
            )
        )

    return posts

