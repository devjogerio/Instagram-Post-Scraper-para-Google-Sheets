from typing import Any, Dict

from fastapi import FastAPI

from config.settings import load_app_config
from utils.proxy_manager import ProxyManager


def create_app() -> FastAPI:
    app = FastAPI(title="Scraper Observability API", version="1.0.0")

    config = load_app_config()
    manager = ProxyManager.from_file(config.proxy.proxy_list_file_path)

    @app.get("/api/v1/proxies/diagnostic")
    def proxies_diagnostic() -> Dict[str, Dict[str, float | int | bool | None]]:
        return manager.diagnostic_snapshot()

    return app


app = create_app()

