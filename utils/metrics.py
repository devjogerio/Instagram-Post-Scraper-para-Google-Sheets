import json
import os
import time
from typing import Any, Dict, Optional

from utils.logging_config import get_logger


logger = get_logger(__name__)


class MetricsSink:
    def emit(self, event: str, payload: Dict[str, Any]) -> None:
        raise NotImplementedError()


class ConsoleMetricsSink(MetricsSink):
    def emit(self, event: str, payload: Dict[str, Any]) -> None:
        logger.info("metrics_event=%s %s", event, json.dumps(payload, ensure_ascii=False))


try:  # pragma: no cover
    import boto3  # type: ignore[import]
except ModuleNotFoundError:  # pragma: no cover
    boto3 = None  # type: ignore[assignment]


class CloudWatchMetricsSink(MetricsSink):
    def __init__(self, log_group: str, log_stream: str) -> None:
        if boto3 is None:
            raise RuntimeError("boto3 não está instalado para CloudWatch")
        self._client = boto3.client("logs")
        self._log_group = log_group
        self._log_stream = log_stream
        self._sequence_token: Optional[str] = None

    def emit(self, event: str, payload: Dict[str, Any]) -> None:  # pragma: no cover
        message = json.dumps({"event": event, "payload": payload}, ensure_ascii=False)
        timestamp_ms = int(time.time() * 1000)
        args: Dict[str, Any] = {
            "logGroupName": self._log_group,
            "logStreamName": self._log_stream,
            "logEvents": [{"timestamp": timestamp_ms, "message": message}],
        }
        if self._sequence_token:
            args["sequenceToken"] = self._sequence_token
        try:
            resp = self._client.put_log_events(**args)
            self._sequence_token = resp.get("nextSequenceToken")
        except Exception:
            logger.exception("falha_ao_emitir_cloudwatch")


try:  # pragma: no cover
    from opensearchpy import OpenSearch  # type: ignore[import]
except ModuleNotFoundError:  # pragma: no cover
    OpenSearch = None  # type: ignore[assignment]


class OpenSearchMetricsSink(MetricsSink):
    def __init__(self, url: str, index: str, username: Optional[str] = None, password: Optional[str] = None) -> None:
        if OpenSearch is None:
            raise RuntimeError("opensearch-py não está instalado")
        self._client = OpenSearch(
            hosts=[url],
            http_auth=(username, password) if username and password else None,
            use_ssl=url.startswith("https"),
            verify_certs=False,
        )
        self._index = index

    def emit(self, event: str, payload: Dict[str, Any]) -> None:  # pragma: no cover
        doc = {"event": event, "payload": payload, "ts": int(time.time() * 1000)}
        try:
            self._client.index(index=self._index, body=doc)
        except Exception:
            logger.exception("falha_ao_emitir_opensearch")


def build_metrics_sink_from_env() -> MetricsSink:
    backend = os.getenv("METRICS_BACKEND", "console").lower()
    if backend == "cloudwatch":
        group = os.getenv("CW_LOG_GROUP", "scraper-metrics")
        stream = os.getenv("CW_LOG_STREAM", "default")
        return CloudWatchMetricsSink(group, stream)
    if backend == "opensearch":
        url = os.getenv("OS_URL", "http://localhost:9200")
        index = os.getenv("OS_INDEX", "scraper-metrics")
        username = os.getenv("OS_USERNAME")
        password = os.getenv("OS_PASSWORD")
        return OpenSearchMetricsSink(url, index, username, password)
    return ConsoleMetricsSink()

