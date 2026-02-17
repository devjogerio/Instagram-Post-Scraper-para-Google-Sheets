import time
from collections.abc import Iterator
from dataclasses import dataclass
from threading import Lock
from typing import Callable, Dict, Optional

from utils.logging_config import get_logger
from utils.metrics import build_metrics_sink_from_env


logger = get_logger(__name__)


HealthCheckFn = Callable[[str], bool]


@dataclass
class ProxyStats:
    successes: int = 0
    failures: int = 0
    consecutive_failures: int = 0
    last_success_at: Optional[float] = None
    last_failure_at: Optional[float] = None
    active: bool = True
    total_duration_ms: float = 0.0
    requests: int = 0


class ProxyManager:
    # Inicializa o gerenciador de proxies com métricas, limites e configurando health check opcional.
    def __init__(
        self,
        proxies: list[str],
        max_consecutive_failures: int = 3,
        failure_cooldown_seconds: int = 60,
        health_check: Optional[HealthCheckFn] = None,
        health_check_interval_seconds: int = 300,
    ) -> None:
        self._lock = Lock()
        self._proxies = proxies[:]
        self._index = 0
        self._stats: Dict[str, ProxyStats] = {
            proxy: ProxyStats() for proxy in proxies}
        self._max_consecutive_failures = max_consecutive_failures
        self._failure_cooldown_seconds = failure_cooldown_seconds
        self._health_check = health_check
        self._health_check_interval_seconds = health_check_interval_seconds
        self._metrics_sink = build_metrics_sink_from_env()

    # Cria um ProxyManager a partir de um arquivo de configuração de proxies.
    @classmethod
    def from_file(
        cls,
        path: Optional[str],
        max_consecutive_failures: int = 3,
        failure_cooldown_seconds: int = 60,
        health_check: Optional[HealthCheckFn] = None,
        health_check_interval_seconds: int = 300,
    ) -> "ProxyManager":
        proxies = _load_proxies_from_file(path) if path else []
        return cls(
            proxies=proxies,
            max_consecutive_failures=max_consecutive_failures,
            failure_cooldown_seconds=failure_cooldown_seconds,
            health_check=health_check,
            health_check_interval_seconds=health_check_interval_seconds,
        )

    # Retorna o próximo proxy saudável, aplicando failover e limpeza de proxies falhos.
    def get_next(self) -> Optional[str]:
        with self._lock:
            self._maybe_run_health_check_locked()
            self._prune_inactive_locked()

            if not self._proxies:
                return None

            start_index = self._index

            while True:
                proxy = self._proxies[self._index]
                stats = self._stats.get(proxy)

                if self._is_proxy_available_locked(proxy, stats):
                    self._index = (self._index + 1) % len(self._proxies)
                    return proxy

                self._index = (self._index + 1) % len(self._proxies)

                if self._index == start_index:
                    return None

    # Registra sucesso de uso de um proxy para fins de métricas.
    def mark_success(self, proxy: Optional[str], duration_ms: Optional[float] = None) -> None:
        if proxy is None:
            return

        with self._lock:
            stats = self._stats.setdefault(proxy, ProxyStats())
            stats.successes += 1
            stats.consecutive_failures = 0
            stats.last_success_at = time.time()
            stats.active = True
            if duration_ms is not None:
                stats.total_duration_ms += float(duration_ms)
            stats.requests += 1
            self._metrics_sink.emit(
                "proxy_success",
                {
                    "proxy": proxy,
                    "duration_ms": duration_ms,
                    "successes": stats.successes,
                    "requests": stats.requests,
                },
            )

    # Registra falha de uso de um proxy e aplica política de desativação.
    def mark_failure(self, proxy: Optional[str], duration_ms: Optional[float] = None) -> None:
        if proxy is None:
            return

        with self._lock:
            stats = self._stats.setdefault(proxy, ProxyStats())
            stats.failures += 1
            stats.consecutive_failures += 1
            stats.last_failure_at = time.time()
            if duration_ms is not None:
                stats.total_duration_ms += float(duration_ms)
            stats.requests += 1

            if stats.consecutive_failures >= self._max_consecutive_failures:
                if stats.active:
                    logger.warning(
                        "proxy_desativado_por_falhas proxy=%s falhas_consecutivas=%d",
                        proxy,
                        stats.consecutive_failures,
                    )
                stats.active = False
            self._metrics_sink.emit(
                "proxy_failure",
                {
                    "proxy": proxy,
                    "duration_ms": duration_ms,
                    "failures": stats.failures,
                    "requests": stats.requests,
                },
            )

    # Retorna uma cópia das métricas atuais de uso dos proxies.
    def snapshot_metrics(self) -> Dict[str, ProxyStats]:
        with self._lock:
            return {proxy: ProxyStats(**vars(stats)) for proxy, stats in self._stats.items()}
    # Retorna um diagnóstico consolidado em JSON com métricas derivadas por proxy.

    def diagnostic_snapshot(self) -> Dict[str, Dict[str, float | int | bool | None]]:
        with self._lock:
            result: Dict[str, Dict[str, float | int | bool | None]] = {}
            for proxy, stats in self._stats.items():
                total = max(1, stats.requests)
                avg_latency = stats.total_duration_ms / float(total)
                error_rate = stats.failures / float(total)
                availability = 1.0 if stats.active else 0.0
                result[proxy] = {
                    "successes": stats.successes,
                    "failures": stats.failures,
                    "requests": stats.requests,
                    "avg_latency_ms": round(avg_latency, 3),
                    "error_rate": round(error_rate, 5),
                    "availability": availability,
                    "last_success_at": stats.last_success_at,
                    "last_failure_at": stats.last_failure_at,
                    "active": stats.active,
                }
            return result

    # Executa health check em todos os proxies, se configurado, atualizando métricas.
    def _maybe_run_health_check_locked(self) -> None:
        if not self._health_check:
            return

        now = time.time()
        if now - self._last_health_check_at < self._health_check_interval_seconds:
            return

        self._last_health_check_at = now

        for proxy in list(self._proxies):
            try:
                healthy = self._health_check(proxy)
            except Exception:  # noqa: BLE001
                healthy = False

            stats = self._stats.setdefault(proxy, ProxyStats())
            if healthy:
                stats.last_success_at = now
                stats.consecutive_failures = 0
                stats.active = True
            else:
                stats.failures += 1
                stats.consecutive_failures += 1
                stats.last_failure_at = now
                if stats.consecutive_failures >= self._max_consecutive_failures:
                    stats.active = False

    # Verifica se o proxy está disponível para uso de acordo com as métricas atuais.
    def _is_proxy_available_locked(
        self,
        proxy: str,
        stats: Optional[ProxyStats],
    ) -> bool:
        if not stats:
            return True

        if not stats.active:
            if stats.last_failure_at is None:
                return False
            elapsed = time.time() - stats.last_failure_at
            if elapsed >= self._failure_cooldown_seconds:
                stats.consecutive_failures = 0
                stats.active = True
                return True
            return False

        return True

    # Remove proxies inativos que permaneceram em falha por tempo prolongado.
    def _prune_inactive_locked(self) -> None:
        now = time.time()
        to_remove: list[str] = []

        for proxy, stats in self._stats.items():
            if not stats.active and stats.last_failure_at is not None:
                if now - stats.last_failure_at > self._failure_cooldown_seconds * 10:
                    to_remove.append(proxy)

        if not to_remove:
            return

        for proxy in to_remove:
            if proxy in self._proxies:
                self._proxies.remove(proxy)
            self._stats.pop(proxy, None)
            logger.info("proxy_removido_definitivamente proxy=%s", proxy)


def _load_proxies_from_file(path: Optional[str]) -> list[str]:
    # Carrega a lista de proxies a partir de um arquivo de texto simples.
    if not path:
        return []

    try:
        with open(path, "r", encoding="utf-8") as file:
            return [
                line.strip()
                for line in file.readlines()
                if line.strip() and not line.strip().startswith("#")
            ]
    except FileNotFoundError:
        logger.warning("arquivo_de_proxies_nao_encontrado path=%s", path)
        return []


def proxy_cycle(path: Optional[str]) -> Iterator[Optional[str]]:
    # Preserva a API antiga expondo um gerador simples baseado em ProxyManager.
    manager = ProxyManager.from_file(path)

    if not manager._proxies:
        while True:
            yield None

    while True:
        proxy = manager.get_next()
        if proxy is None:
            yield None
        else:
            yield proxy
