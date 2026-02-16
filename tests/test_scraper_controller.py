from config.settings import AppConfig, GoogleSheetsConfig, InstagramConfig, ProxyConfig, RateLimitConfig
from controllers.scraper_controller import scrape_and_persist


class DummySheetsConfig(GoogleSheetsConfig):
    pass


class DummyInstagramConfig(InstagramConfig):
    pass


def test_scrape_and_persist_handles_empty_targets(monkeypatch):
    captured_calls: dict[str, int] = {"append_calls": 0}

    def fake_append_posts_to_sheet(config, posts):
        captured_calls["append_calls"] += 1

    monkeypatch.setattr(
        "controllers.scraper_controller.append_posts_to_sheet",
        fake_append_posts_to_sheet,
    )

    config = AppConfig(
        instagram=InstagramConfig(username="user", password="pass", targets=[]),
        google_sheets=GoogleSheetsConfig(
            service_account_json_path="path.json",
            spreadsheet_id="spreadsheet",
            worksheet_name="Sheet1",
        ),
        rate_limit=RateLimitConfig(request_delay_seconds=1.0),
        proxy=ProxyConfig(proxy_list_file_path=None),
    )

    scrape_and_persist(config)

    assert captured_calls["append_calls"] == 0

