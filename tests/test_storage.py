from config.settings import AppConfig, DatabaseConfig, GoogleSheetsConfig, InstagramConfig, ProxyConfig, RateLimitConfig
from models.post import InstagramPost
from utils.storage import build_post_storages, DatabasePostStorage


def _build_minimal_app_config(db_enabled: bool) -> AppConfig:
    return AppConfig(
        instagram=InstagramConfig(username="u", password="p", targets=[]),
        google_sheets=GoogleSheetsConfig(
            service_account_json_path="path.json",
            spreadsheet_id="sheet",
            worksheet_name="Sheet1",
        ),
        rate_limit=RateLimitConfig(request_delay_seconds=1.0),
        proxy=ProxyConfig(proxy_list_file_path=None),
        database=DatabaseConfig(
            enabled=db_enabled,
            backend="postgres" if db_enabled else None,
            dsn="postgresql://user:pass@localhost:5432/db" if db_enabled else None,
        ),
    )


def test_build_post_storages_without_database():
    config = _build_minimal_app_config(db_enabled=False)

    storages = build_post_storages(config)

    assert len(storages) == 1


def test_build_post_storages_with_database():
    config = _build_minimal_app_config(db_enabled=True)

    storages = build_post_storages(config)

    assert any(isinstance(storage, DatabasePostStorage) for storage in storages)

