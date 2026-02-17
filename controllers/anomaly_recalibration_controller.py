import json
import os
import time
from dataclasses import dataclass
from threading import Lock
from typing import Dict, Iterable, List, Protocol

try:
    import boto3
except Exception:  # pragma: no cover - fallback para ambientes sem boto3
    boto3 = None  # type: ignore[assignment]

try:
    from opensearchpy import OpenSearch
except Exception:  # pragma: no cover - fallback para ambientes sem OpenSearch
    OpenSearch = None  # type: ignore[assignment]

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


class CloudWatchMetricsSource:
    # Fonte de métricas baseada em CloudWatch com suporte a paginação e filtros de tempo.
    def __init__(
        self,
        client: "boto3.client",
        namespace: str,
        latency_metric: str,
        error_metric: str,
        throughput_metric: str,
        dimension_name: str,
        dimension_value: str,
        period_seconds: int = 60,
    ) -> None:
        self._client = client
        self._namespace = namespace
        self._latency_metric = latency_metric
        self._error_metric = error_metric
        self._throughput_metric = throughput_metric
        self._dimension_name = dimension_name
        self._dimension_value = dimension_value
        self._period_seconds = period_seconds

    @classmethod
    def from_env(cls) -> "CloudWatchMetricsSource":
        if boto3 is None:
            raise RuntimeError("boto3 não está disponível no ambiente")
        client = boto3.client("cloudwatch")
        namespace = os.getenv("CW_NAMESPACE", "proxy-metrics")
        latency_metric = os.getenv("CW_LATENCY_METRIC", "proxy_latency_ms")
        error_metric = os.getenv("CW_ERROR_RATE_METRIC", "proxy_error_rate")
        throughput_metric = os.getenv(
            "CW_THROUGHPUT_METRIC", "proxy_throughput")
        dimension_name = os.getenv("CW_DIMENSION_NAME", "proxy_pool")
        dimension_value = os.getenv("CW_DIMENSION_VALUE", "default")
        period_seconds = int(os.getenv("CW_PERIOD_SECONDS", "60"))
        return cls(
            client=client,
            namespace=namespace,
            latency_metric=latency_metric,
            error_metric=error_metric,
            throughput_metric=throughput_metric,
            dimension_name=dimension_name,
            dimension_value=dimension_value,
            period_seconds=period_seconds,
        )

    def fetch_samples(self, since_seconds: int, now: float) -> List[MetricSample]:
        start_time = time.gmtime(now - float(since_seconds))
        end_time = time.gmtime(now)
        metrics_map = {
            "latency_ms": self._latency_metric,
            "error_rate": self._error_metric,
            "throughput": self._throughput_metric,
        }
        queries = []
        for idx, (metric_key, metric_name) in enumerate(metrics_map.items()):
            queries.append(
                {
                    "Id": f"m{idx}",
                    "MetricStat": {
                        "Metric": {
                            "Namespace": self._namespace,
                            "MetricName": metric_name,
                            "Dimensions": [
                                {
                                    "Name": self._dimension_name,
                                    "Value": self._dimension_value,
                                }
                            ],
                        },
                        "Period": self._period_seconds,
                        "Stat": "Average",
                    },
                    "ReturnData": True,
                }
            )

        samples_by_ts: Dict[float, Dict[str, float]] = {}
        next_token = None
        while True:
            try:
                params = {
                    "MetricDataQueries": queries,
                    "StartTime": time.strftime("%Y-%m-%dT%H:%M:%SZ", start_time),
                    "EndTime": time.strftime("%Y-%m-%dT%H:%M:%SZ", end_time),
                }
                if next_token:
                    params["NextToken"] = next_token
                response = self._client.get_metric_data(**params)
            except Exception as exc:  # pragma: no cover - falha de integração externa
                logger.error("cloudwatch_fetch_error %s", exc)
                break

            for query, (metric_key, _) in zip(response.get("MetricDataResults", []), metrics_map.items()):
                for ts, value in zip(query.get("Timestamps", []), query.get("Values", [])):
                    if hasattr(ts, "timestamp"):
                        ts_epoch = ts.timestamp()
                    else:
                        # time.struct_time compatível com testes simulados.
                        ts_epoch = time.mktime(ts)
                    bucket = samples_by_ts.setdefault(
                        ts_epoch,
                        {"latency_ms": 0.0, "error_rate": 0.0, "throughput": 0.0},
                    )
                    bucket[metric_key] = float(value)

            next_token = response.get("NextToken")
            if not next_token:
                break

        samples: List[MetricSample] = []
        for ts, values in samples_by_ts.items():
            samples.append(
                MetricSample(
                    timestamp=ts,
                    latency_ms=values["latency_ms"],
                    error_rate=values["error_rate"],
                    throughput=values["throughput"],
                )
            )
        return samples


class OpenSearchMetricsSource:
    # Fonte de métricas baseada em OpenSearch com paginação, agregações e filtros de tempo.
    def __init__(self, client: "OpenSearch", index: str, page_size: int = 500) -> None:
        self._client = client
        self._index = index
        self._page_size = page_size

    @classmethod
    def from_env(cls) -> "OpenSearchMetricsSource":
        if OpenSearch is None:
            raise RuntimeError("opensearch-py não está disponível no ambiente")
        host = os.getenv("OS_ENDPOINT", "http://localhost:9200")
        username = os.getenv("OS_USERNAME", "")
        password = os.getenv("OS_PASSWORD", "")
        index = os.getenv("OS_METRICS_INDEX", "proxy-metrics")
        client = OpenSearch(
            hosts=[host],
            http_auth=(username, password) if username or password else None,
            use_ssl=host.startswith("https"),
            verify_certs=False,
        )
        return cls(client=client, index=index, page_size=int(os.getenv("OS_PAGE_SIZE", "500")))

    def fetch_samples(self, since_seconds: int, now: float) -> List[MetricSample]:
        start_ms = int((now - float(since_seconds)) * 1000)
        end_ms = int(now * 1000)
        body = {
            "query": {
                "bool": {
                    "filter": [
                        {"range": {"ts": {"gte": start_ms, "lte": end_ms}}},
                    ]
                }
            },
            "aggs": {
                "latency_p95": {"percentiles": {"field": "latency_ms", "percents": [95, 99]}},
                "error_p95": {"percentiles": {"field": "error_rate", "percents": [95, 99]}},
                "throughput_p95": {"percentiles": {"field": "throughput", "percents": [95, 99]}},
            },
            "sort": [{"ts": "asc"}],
        }

        samples: List[MetricSample] = []
        offset = 0
        while True:
            try:
                response = self._client.search(
                    index=self._index,
                    body=body,
                    from_=offset,
                    size=self._page_size,
                )
            except Exception as exc:  # pragma: no cover - falha de integração externa
                logger.error("opensearch_fetch_error %s", exc)
                break

            hits = response.get("hits", {}).get("hits", [])
            if not hits:
                break
            for hit in hits:
                src = hit.get("_source", {})
                ts_ms = int(src.get("ts", end_ms))
                samples.append(
                    MetricSample(
                        timestamp=ts_ms / 1000.0,
                        latency_ms=float(src.get("latency_ms", 0.0)),
                        error_rate=float(src.get("error_rate", 0.0)),
                        throughput=float(src.get("throughput", 0.0)),
                    )
                )
            offset += len(hits)

        return samples


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
            samples = self._source.fetch_samples(
                since_seconds=30 * 24 * 60 * 60, now=now)
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
            overall_latency = sum(
                s.latency_ms for s in samples) / float(len(samples))
            overall_error = sum(
                s.error_rate for s in samples) / float(len(samples))
            overall_throughput = sum(
                s.throughput for s in samples) / float(len(samples))

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
