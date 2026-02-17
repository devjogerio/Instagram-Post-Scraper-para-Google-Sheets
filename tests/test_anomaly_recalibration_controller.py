import time

from controllers.anomaly_recalibration_controller import (
    AnomalyRecalibrationController,
    InMemoryMetricsSource,
)
from utils.anomaly_detection import MetricSample
from utils.proxy_manager import ProxyManager


def test_recalibration_applies_policies_to_proxy_manager():
    now = time.time()
    samples = [
        MetricSample(timestamp=now - 60, latency_ms=120, error_rate=0.02, throughput=0.9),
        MetricSample(timestamp=now - 120, latency_ms=150, error_rate=0.03, throughput=0.85),
        MetricSample(timestamp=now - 180, latency_ms=110, error_rate=0.01, throughput=0.95),
        MetricSample(timestamp=now - 240, latency_ms=130, error_rate=0.02, throughput=0.92),
    ]
    source = InMemoryMetricsSource(samples)
    manager = ProxyManager(["http://p1", "http://p2"])

    controller = AnomalyRecalibrationController(source, manager)
    policies = controller.run()

    assert policies.max_failures in (1, 2, 3)
    assert policies.base_cooldown >= 30
