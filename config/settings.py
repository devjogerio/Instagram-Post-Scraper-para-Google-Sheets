import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass
class InstagramConfig:
    username: str
    password: str
    targets: list[str]


@dataclass
class GoogleSheetsConfig:
    service_account_json_path: str
    spreadsheet_id: str
    worksheet_name: str


@dataclass
class RateLimitConfig:
    request_delay_seconds: float


@dataclass
class ProxyConfig:
    proxy_list_file_path: str | None


@dataclass
class DatabaseConfig:
    enabled: bool
    backend: str | None
    dsn: str | None


@dataclass
class AppConfig:
    instagram: InstagramConfig
    google_sheets: GoogleSheetsConfig
    rate_limit: RateLimitConfig
    proxy: ProxyConfig
    database: DatabaseConfig


def _get_env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default or "")
    if not value:
        raise RuntimeError(f"Variável de ambiente obrigatória ausente: {name}")
    return value


def _get_env_optional(name: str) -> str | None:
    value = os.getenv(name)
    return value or None


def load_app_config() -> AppConfig:
    instagram = InstagramConfig(
        username=_get_env("IG_USERNAME"),
        password=_get_env("IG_PASSWORD"),
        targets=[
            target.strip()
            for target in _get_env("SCRAPER_TARGETS").split(",")
            if target.strip()
        ],
    )

    google_sheets = GoogleSheetsConfig(
        service_account_json_path=_get_env("GOOGLE_SERVICE_ACCOUNT_JSON_PATH"),
        spreadsheet_id=_get_env("GOOGLE_SHEETS_SPREADSHEET_ID"),
        worksheet_name=_get_env("GOOGLE_SHEETS_WORKSHEET_NAME"),
    )

    rate_limit = RateLimitConfig(
        request_delay_seconds=float(
            os.getenv("SCRAPER_REQUEST_DELAY_SECONDS", "2")
        )
    )

    proxy = ProxyConfig(
        proxy_list_file_path=_get_env_optional("PROXY_LIST_FILE_PATH"),
    )

    database = DatabaseConfig(
        enabled=os.getenv("DB_ENABLED", "false").lower() == "true",
        backend=_get_env_optional("DB_BACKEND"),
        dsn=_get_env_optional("DB_DSN"),
    )

    return AppConfig(
        instagram=instagram,
        google_sheets=google_sheets,
        rate_limit=rate_limit,
        proxy=proxy,
        database=database,
    )
