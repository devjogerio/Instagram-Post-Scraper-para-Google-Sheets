import math
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Literal, Tuple


MetricName = Literal["latency_ms", "error_rate", "throughput"]
WindowName = Literal["24h", "7d", "30d"]


@dataclass
class MetricSample:
    timestamp: float
    latency_ms: float
    error_rate: float
    throughput: float


@dataclass
class WindowThresholds:
    p95: float
    p99: float
    two_sigma: float
    three_sigma: float


@dataclass
class MetricThresholds:
    latency_ms: Dict[WindowName, WindowThresholds]
    error_rate: Dict[WindowName, WindowThresholds]
    throughput: Dict[WindowName, WindowThresholds]


@dataclass
class AnomalyResult:
    anomaly_score: float
    is_anomalous: bool
    metric_scores: Dict[MetricName, float]


WINDOWS_SECONDS: Dict[WindowName, int] = {
    "24h": 24 * 60 * 60,
    "7d": 7 * 24 * 60 * 60,
    "30d": 30 * 24 * 60 * 60,
}


def _percentiles(values: List[float]) -> Tuple[float, float]:
    if not values:
        return 0.0, 0.0
    sorted_values = sorted(values)
    n = len(sorted_values)
    p95_index = max(0, int(0.95 * (n - 1)))
    p99_index = max(0, int(0.99 * (n - 1)))
    return sorted_values[p95_index], sorted_values[p99_index]


def _mean_std(values: List[float]) -> Tuple[float, float]:
    if not values:
        return 0.0, 0.0
    mean = sum(values) / float(len(values))
    variance = sum((v - mean) ** 2 for v in values) / float(len(values))
    std = math.sqrt(variance)
    return mean, std


def _window_samples(samples: Iterable[MetricSample], window_seconds: int, now: float) -> List[MetricSample]:
    cutoff = now - float(window_seconds)
    return [s for s in samples if s.timestamp >= cutoff]


def compute_thresholds(samples: Iterable[MetricSample], now: float | None = None) -> MetricThresholds:
    reference_time = now or time.time()
    samples_list = list(samples)

    latency: Dict[WindowName, WindowThresholds] = {}
    error_rate: Dict[WindowName, WindowThresholds] = {}
    throughput: Dict[WindowName, WindowThresholds] = {}

    for window_name, window_seconds in WINDOWS_SECONDS.items():
        window_samples = _window_samples(samples_list, window_seconds, reference_time)
        latency_values = [s.latency_ms for s in window_samples]
        error_values = [s.error_rate for s in window_samples]
        throughput_values = [s.throughput for s in window_samples]

        latency_p95, latency_p99 = _percentiles(latency_values)
        latency_mean, latency_std = _mean_std(latency_values)
        error_p95, error_p99 = _percentiles(error_values)
        error_mean, error_std = _mean_std(error_values)
        throughput_p95, throughput_p99 = _percentiles(throughput_values)
        throughput_mean, throughput_std = _mean_std(throughput_values)

        latency[window_name] = WindowThresholds(
            p95=latency_p95,
            p99=latency_p99,
            two_sigma=latency_mean + 2 * latency_std,
            three_sigma=latency_mean + 3 * latency_std,
        )
        error_rate[window_name] = WindowThresholds(
            p95=error_p95,
            p99=error_p99,
            two_sigma=error_mean + 2 * error_std,
            three_sigma=error_mean + 3 * error_std,
        )
        throughput[window_name] = WindowThresholds(
            p95=throughput_p95,
            p99=throughput_p99,
            two_sigma=throughput_mean + 2 * throughput_std,
            three_sigma=throughput_mean + 3 * throughput_std,
        )

    return MetricThresholds(
        latency_ms=latency,
        error_rate=error_rate,
        throughput=throughput,
    )


def _score_value(value: float, thresholds: WindowThresholds) -> float:
    if thresholds.p95 == thresholds.p99 == thresholds.two_sigma == thresholds.three_sigma == 0:
        return 0.0
    base = max(thresholds.p95, thresholds.two_sigma)
    extreme = max(thresholds.p99, thresholds.three_sigma)
    if value <= base:
        return 0.0
    if value >= extreme:
        return 1.0
    return (value - base) / (extreme - base)


def detect_anomaly(
    current_latency_ms: float,
    current_error_rate: float,
    current_throughput: float,
    thresholds: MetricThresholds,
) -> AnomalyResult:
    metric_scores: Dict[MetricName, float] = {}

    for metric_name, value in [
        ("latency_ms", current_latency_ms),
        ("error_rate", current_error_rate),
        ("throughput", current_throughput),
    ]:
        windows = getattr(thresholds, metric_name)
        window_scores = [
            _score_value(value, windows["24h"]),
            _score_value(value, windows["7d"]),
            _score_value(value, windows["30d"]),
        ]
        metric_scores[metric_name] = max(window_scores)

    anomaly_score = max(metric_scores.values()) if metric_scores else 0.0
    is_anomalous = anomaly_score >= 0.7

    return AnomalyResult(
        anomaly_score=round(anomaly_score, 4),
        is_anomalous=is_anomalous,
        metric_scores=metric_scores,
    )

