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

