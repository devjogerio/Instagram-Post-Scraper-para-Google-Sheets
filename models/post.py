from dataclasses import dataclass
from datetime import datetime


@dataclass
class InstagramPost:
    post_url: str
    caption: str
    likes_count: int
    comments_count: int
    published_at: datetime
    media_type: str

