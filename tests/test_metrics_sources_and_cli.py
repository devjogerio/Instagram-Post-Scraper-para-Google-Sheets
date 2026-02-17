import json
import time
from types import SimpleNamespace

import pytest

from controllers.anomaly_recalibration_controller import (
    CloudWatchMetricsSource,
    OpenSearchMetricsSource,
)
from utils.anomaly_detection import MetricSample
from views.recalibration_cli import run as cli_run


class _FakeCloudWatchClient:
    # Cliente simulado do CloudWatch para validar paginação e montagem de amostras.
    def __init__(self) -> None:
        self._calls = 0

    def get_metric_data(self, **kwargs):
        self._calls += 1
        if self._calls == 1:
            return {
                "MetricDataResults": [
                    {
                        "Timestamps": [time.gmtime()],
                        "Values": [100.0],
                    },
                    {
                        "Timestamps": [time.gmtime()],
                        "Values": [0.05],
                    },
                    {
                        "Timestamps": [time.gmtime()],
                        "Values": [0.9],
                    },
                ],
                "NextToken": "token-2",
            }
        return {
            "MetricDataResults": [],
        }


class _FakeOpenSearchClient:
    # Cliente simulado do OpenSearch para validar paginação e filtros temporais.
    def __init__(self) -> None:
        self._calls = 0

    def search(self, index, body, from_, size):
        self._calls += 1
        if self._calls == 1:
            now_ms = int(time.time() * 1000)
            return {
                "hits": {
                    "hits": [
                        {
                            "_source": {
                                "ts": now_ms,
                                "latency_ms": 120.0,
                                "error_rate": 0.02,
                                "throughput": 0.9,
                            }
                        }
                    ]
                }
            }
        return {"hits": {"hits": []}}


def test_cloudwatch_metrics_source_fetch_samples(monkeypatch):
    fake_client = _FakeCloudWatchClient()

    def _fake_boto3_client(service_name):
        assert service_name == "cloudwatch"
        return fake_client

    monkeypatch.setattr("controllers.anomaly_recalibration_controller.boto3", SimpleNamespace(client=_fake_boto3_client))

    source = CloudWatchMetricsSource.from_env()
    samples = source.fetch_samples(since_seconds=3600, now=time.time())

    assert isinstance(samples, list)
    assert samples
    assert isinstance(samples[0], MetricSample)


def test_opensearch_metrics_source_fetch_samples(monkeypatch):
    fake_client = _FakeOpenSearchClient()

    def _fake_opensearch(*args, **kwargs):
        return fake_client

    monkeypatch.setattr("controllers.anomaly_recalibration_controller.OpenSearch", _fake_opensearch)

    source = OpenSearchMetricsSource.from_env()
    samples = source.fetch_samples(since_seconds=3600, now=time.time())

    assert isinstance(samples, list)
    assert samples
    assert isinstance(samples[0], MetricSample)


def test_recalibration_cli_run_returns_non_zero_on_error(monkeypatch):
    # Força erro de backend para validar tratamento e código de saída.
    def _fake_load_app_config():
        raise RuntimeError("config_error")

    monkeypatch.setattr("views.recalibration_cli.load_app_config", _fake_load_app_config)

    exit_code = cli_run(argv=["--backend", "cloudwatch"])
    assert exit_code == 1

