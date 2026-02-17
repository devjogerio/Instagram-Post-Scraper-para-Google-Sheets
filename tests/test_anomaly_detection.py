import time

from utils.anomaly_detection import MetricSample, AnomalyResult, compute_thresholds, detect_anomaly


def _build_samples(now: float) -> list[MetricSample]:
    return [
        MetricSample(timestamp=now - 60, latency_ms=100, error_rate=0.01, throughput=50),
        MetricSample(timestamp=now - 120, latency_ms=110, error_rate=0.02, throughput=45),
        MetricSample(timestamp=now - 180, latency_ms=90, error_rate=0.01, throughput=55),
        MetricSample(timestamp=now - 240, latency_ms=95, error_rate=0.015, throughput=52),
    ]


def test_compute_thresholds_produces_values():
    now = time.time()
    samples = _build_samples(now)

    thresholds = compute_thresholds(samples, now=now)

    assert thresholds.latency_ms["24h"].p95 > 0
    assert thresholds.error_rate["24h"].p95 > 0
    assert thresholds.throughput["24h"].p95 > 0


def test_detect_anomaly_returns_low_score_for_normal_values():
    now = time.time()
    samples = _build_samples(now)
    thresholds = compute_thresholds(samples, now=now)

    result = detect_anomaly(
        current_latency_ms=100,
        current_error_rate=0.02,
        current_throughput=50,
        thresholds=thresholds,
    )

    assert isinstance(result, AnomalyResult)
    assert result.anomaly_score < 0.7
    assert not result.is_anomalous


def test_detect_anomaly_flags_extreme_latency_as_anomalous():
    now = time.time()
    samples = _build_samples(now)
    thresholds = compute_thresholds(samples, now=now)

    result = detect_anomaly(
        current_latency_ms=5000,
        current_error_rate=0.5,
        current_throughput=5,
        thresholds=thresholds,
    )

    assert result.anomaly_score >= 0.7
    assert result.is_anomalous

