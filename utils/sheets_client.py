from datetime import datetime
from typing import Iterable, List

import gspread
from google.oauth2.service_account import Credentials

from config.settings import GoogleSheetsConfig
from models.post import InstagramPost


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _build_client(config: GoogleSheetsConfig) -> gspread.Client:
    credentials = Credentials.from_service_account_file(
        config.service_account_json_path,
        scopes=SCOPES,
    )
    return gspread.authorize(credentials)


def append_posts_to_sheet(
    config: GoogleSheetsConfig,
    posts: Iterable[InstagramPost],
) -> None:
    client = _build_client(config)
    spreadsheet = client.open_by_key(config.spreadsheet_id)
    worksheet = spreadsheet.worksheet(config.worksheet_name)

    rows: List[list[str]] = []

    for post in posts:
        rows.append(
            [
                post.post_url,
                post.caption,
                str(post.likes_count),
                str(post.comments_count),
                post.published_at.isoformat(),
                post.media_type,
            ]
        )

    if rows:
        worksheet.append_rows(rows)


def fetch_posts_from_sheet(config: GoogleSheetsConfig) -> List[InstagramPost]:
    client = _build_client(config)
    spreadsheet = client.open_by_key(config.spreadsheet_id)
    worksheet = spreadsheet.worksheet(config.worksheet_name)

    values = worksheet.get_all_values()
    posts: List[InstagramPost] = []

    for row in values:
        if len(row) < 6:
            continue

        post_url, caption, likes, comments, published_at_str, media_type = row[:6]

        try:
            published_at = datetime.fromisoformat(published_at_str)
        except ValueError:
            continue

        posts.append(
            InstagramPost(
                post_url=post_url,
                caption=caption,
                likes_count=int(likes),
                comments_count=int(comments),
                published_at=published_at,
                media_type=media_type,
            )
        )

    return posts
