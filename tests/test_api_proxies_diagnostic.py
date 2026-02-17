try:
    from fastapi.testclient import TestClient  # type: ignore
    from views.api import create_app
    from utils.proxy_manager import ProxyManager
except Exception:  # noqa: BLE001
    import pytest
    pytest.skip("FastAPI indisponível no ambiente de testes",
                allow_module_level=True)


def test_diagnostic_endpoint_returns_json(monkeypatch):
    app = create_app()
    client = TestClient(app)

    # Substitui ProxyManager.from_file para injetar métricas controladas
    def fake_from_file(path):
        m = ProxyManager(["http://p1", "http://p2"])
        m.mark_success("http://p1", duration_ms=100)
        m.mark_failure("http://p2", duration_ms=200)
        return m

    monkeypatch.setattr("views.api.ProxyManager.from_file", fake_from_file)

    response = client.get("/api/v1/proxies/diagnostic")
    assert response.status_code == 200
    data = response.json()

    assert "http://p1" in data and "http://p2" in data
    assert "avg_latency_ms" in data["http://p1"]
    assert "error_rate" in data["http://p2"]
