import time
from dataclasses import dataclass
from threading import Lock
from typing import Iterable, List, Protocol

from utils.anomaly_detection import (
    AnomalyResult,
    MetricSample,
    MetricThresholds,
    compute_thresholds,
    detect_anomaly,
)
from utils.logging_config import get_logger
from utils.metrics import build_metrics_sink_from_env
from utils.proxy_manager import ProxyManager


logger = get_logger(__name__)


class MetricsSource(Protocol):
    # Recupera amostras históricas de métricas para avaliação de thresholds dinâmicos.
    def fetch_samples(self, since_seconds: int, now: float) -> List[MetricSample]:
        ...


@dataclass
class RecalibrationPolicies:
    max_failures: int
    timeout_seconds: int
    retry_attempts: int
    base_cooldown: int
    exponential_backoff: int
    max_cooldown: int


class InMemoryMetricsSource:
    # Implementação simples de fonte de métricas em memória para testes e ambientes locais.
    def __init__(self, samples: Iterable[MetricSample]) -> None:
        self._samples = list(samples)

    def fetch_samples(self, since_seconds: int, now: float) -> List[MetricSample]:
        cutoff = now - float(since_seconds)
        return [s for s in self._samples if s.timestamp >= cutoff]


class AnomalyRecalibrationController:
    # Controlador responsável por recalibrar automaticamente políticas de failover/cooldown usando dados históricos.
    def __init__(self, source: MetricsSource, proxy_manager: ProxyManager) -> None:
        self._source = source
        self._proxy_manager = proxy_manager
        self._lock = Lock()
        self._metrics_sink = build_metrics_sink_from_env()

    # Executa o ciclo completo de recalibração e aplica as novas políticas no ProxyManager.
    def run(self) -> RecalibrationPolicies:
        start = time.time()
        with self._lock:
            now = time.time()
            samples = self._source.fetch_samples(since_seconds=30 * 24 * 60 * 60, now=now)
            if not samples:
                logger.warning("recalibration_sem_amostras_disponiveis")
                # Mantém políticas padrão conservadoras.
                policies = RecalibrationPolicies(
                    max_failures=3,
                    timeout_seconds=10,
                    retry_attempts=3,
                    base_cooldown=60,
                    exponential_backoff=2,
                    max_cooldown=600,
                )
                return policies

            thresholds: MetricThresholds = compute_thresholds(samples, now=now)
            overall_latency = sum(s.latency_ms for s in samples) / float(len(samples))
            overall_error = sum(s.error_rate for s in samples) / float(len(samples))
            overall_throughput = sum(s.throughput for s in samples) / float(len(samples))

            anomaly: AnomalyResult = detect_anomaly(
                current_latency_ms=overall_latency,
                current_error_rate=overall_error,
                current_throughput=overall_throughput,
                thresholds=thresholds,
            )

            policies = self._derive_policies(thresholds, anomaly)

            self._proxy_manager.set_policies(
                max_consecutive_failures=policies.max_failures,
                failure_cooldown_seconds=policies.base_cooldown,
            )

            duration_ms = int((time.time() - start) * 1000)
            self._metrics_sink.emit(
                "recalibration_update",
                {
                    "anomaly_score": anomaly.anomaly_score,
                    "policies": vars(policies),
                    "duration_ms": duration_ms,
                },
            )

            return policies

    # Deriva políticas de failover/cooldown a partir de thresholds e score de anomalia de forma determinística.
    def _derive_policies(self, thresholds: MetricThresholds, anomaly: AnomalyResult) -> RecalibrationPolicies:
        lat_24h = thresholds.latency_ms["24h"]
        err_24h = thresholds.error_rate["24h"]

        base_cooldown = int(max(30, min(900, lat_24h.p95 / 5.0)))
        max_cooldown = int(max(base_cooldown * 5, lat_24h.p99 / 3.0))

        if err_24h.p99 >= 0.20:
            max_failures = 1
            retry_attempts = 2
            timeout_seconds = 15
        elif err_24h.p99 >= 0.10:
            max_failures = 2
            retry_attempts = 3
            timeout_seconds = 12
        else:
            max_failures = 3
            retry_attempts = 4
            timeout_seconds = 10

        if anomaly.anomaly_score >= 0.9:
            base_cooldown = int(min(1200, base_cooldown * 2))
            max_failures = max(1, max_failures - 1)
        elif anomaly.anomaly_score >= 0.7:
            base_cooldown = int(min(1200, base_cooldown * 1.5))

        return RecalibrationPolicies(
            max_failures=max_failures,
            timeout_seconds=timeout_seconds,
            retry_attempts=retry_attempts,
            base_cooldown=base_cooldown,
            exponential_backoff=2,
            max_cooldown=max_cooldown,
        )

