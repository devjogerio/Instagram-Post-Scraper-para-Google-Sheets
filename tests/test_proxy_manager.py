import os
import tempfile
import time

from utils.proxy_manager import ProxyManager, ProxyStats, proxy_cycle


def _create_proxy_file(proxies: list[str]) -> str:
    # Cria um arquivo temporário contendo a lista de proxies para uso nos testes.
    file_descriptor, path = tempfile.mkstemp()
    os.close(file_descriptor)

    with open(path, "w", encoding="utf-8") as handle:
        for proxy in proxies:
            handle.write(proxy + "\n")

    return path


def test_proxy_manager_cycles_through_proxies():
    # Garante que o ProxyManager percorre os proxies na ordem esperada.
    proxies = ["http://p1", "http://p2", "http://p3"]
    manager = ProxyManager(proxies)

    seen = {manager.get_next(), manager.get_next(), manager.get_next()}

    assert seen == set(proxies)


def test_proxy_manager_failover_on_failures(monkeypatch):
    # Verifica que proxies com muitas falhas deixam de ser utilizados.
    proxies = ["http://p1", "http://p2"]
    manager = ProxyManager(proxies, max_consecutive_failures=2, failure_cooldown_seconds=60)

    manager.mark_failure("http://p1")
    manager.mark_failure("http://p1")

    next_proxy = manager.get_next()
    assert next_proxy == "http://p2"


def test_proxy_manager_cooldown_restores_proxy(monkeypatch):
    # Confirma que após o período de cooldown o proxy volta a ser elegível.
    proxies = ["http://p1"]
    manager = ProxyManager(proxies, max_consecutive_failures=1, failure_cooldown_seconds=10)

    manager.mark_failure("http://p1")

    base_time = time.time()
    monkeypatch.setattr(time, "time", lambda: base_time + 11)

    next_proxy = manager.get_next()
    assert next_proxy == "http://p1"


def test_proxy_manager_health_check_marks_unhealthy_proxies(monkeypatch):
    # Garante que o health check desativa proxies considerados não saudáveis.
    proxies = ["http://p1", "http://p2"]

    def fake_health_check(proxy: str) -> bool:
        return proxy == "http://p2"

    manager = ProxyManager(
        proxies,
        max_consecutive_failures=1,
        failure_cooldown_seconds=60,
        health_check=fake_health_check,
        health_check_interval_seconds=0,
    )

    base_time = time.time()

    def fake_time() -> float:
        return base_time + 1

    monkeypatch.setattr(time, "time", fake_time)

    result = manager.get_next()
    assert result == "http://p2"


def test_snapshot_metrics_returns_copy():
    # Valida que o snapshot de métricas não expõe a estrutura interna mutável.
    proxies = ["http://p1"]
    manager = ProxyManager(proxies)

    manager.mark_success("http://p1")

    snapshot = manager.snapshot_metrics()
    stats = snapshot["http://p1"]
    assert isinstance(stats, ProxyStats)
    assert stats.successes == 1

    stats.successes = 100
    assert manager.snapshot_metrics()["http://p1"].successes == 1


def test_proxy_cycle_backwards_compatible_when_no_path():
    # Garante compatibilidade retrocompatível quando nenhum caminho de arquivo é informado.
    generator = proxy_cycle(None)
    assert next(generator) is None
    assert next(generator) is None


def test_proxy_cycle_with_file(tmp_path):
    # Verifica que proxy_cycle continua iterando pelos proxies definidos em arquivo.
    path = _create_proxy_file(["http://p1", "http://p2"])
    generator = proxy_cycle(path)

    first = next(generator)
    second = next(generator)
    third = next(generator)

    assert {first, second} == {"http://p1", "http://p2"}
    assert third in {"http://p1", "http://p2"}

