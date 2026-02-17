import os
import time
from typing import Dict

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from pydantic import BaseModel

from config.settings import load_app_config
from utils.anomaly_detection import AnomalyResult, MetricSample, compute_thresholds, detect_anomaly
from utils.proxy_manager import ProxyManager
from utils.rate_limiter import InMemoryRateLimitStorage, LimitConfig, RateLimiter


class DiagnosticThresholdsModel(BaseModel):
    window: str
    metric: str
    p95: float
    p99: float
    two_sigma: float
    three_sigma: float


class DiagnosticResponseModel(BaseModel):
    timestamp: float
    service_health: str
    anomaly_score: float
    thresholds_applied: Dict[str, DiagnosticThresholdsModel]
    recommended_actions: list[str]
    details: Dict[str, float]


def _build_rate_limiter() -> RateLimiter:
    storage = InMemoryRateLimitStorage()
    default = LimitConfig(requests=100, window_seconds=60,
                          strategy="sliding_window")  # type: ignore[arg-type]
    limits = {
        "/diagnostic": {
            "anonymous": default,
            "authenticated": default,
        }
    }
    return RateLimiter(storage=storage, limits_by_endpoint=limits, default_limit=default)


rate_limiter = _build_rate_limiter()


def _authenticate_request(x_api_key: str | None = Header(default=None)) -> str:
    expected = os.getenv("DIAGNOSTIC_API_KEY")
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Serviço de diagnóstico não configurado",
        )
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key ausente",
        )
    if x_api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key inválida",
        )
    return x_api_key


def create_app() -> FastAPI:
    app = FastAPI(title="Scraper Observability API", version="1.1.0")

    config = load_app_config()
    manager = ProxyManager.from_file(config.proxy.proxy_list_file_path)

    @app.get("/api/v1/proxies/diagnostic")
    def proxies_diagnostic() -> Dict[str, Dict[str, float | int | bool | None]]:
        return manager.diagnostic_snapshot()

    @app.get(
        "/diagnostic",
        response_model=DiagnosticResponseModel,
        responses={
            400: {"description": "Erro de validação"},
            401: {"description": "Não autenticado"},
            403: {"description": "Proibido"},
            404: {"description": "Recurso não encontrado"},
            500: {"description": "Erro interno"},
            503: {"description": "Serviço indisponível"},
        },
    )
    def diagnostic(
        request: Request,
        api_key: str = Depends(_authenticate_request),
    ) -> DiagnosticResponseModel:
        client_id = api_key

        try:
            rate_limiter.check(
                "/diagnostic", "authenticated", identifier=client_id)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Limite de requisições excedido",
            )

        snapshot = manager.diagnostic_snapshot()
        now = time.time()

        samples: list[MetricSample] = []
        for proxy, data in snapshot.items():
            requests_count = int(data.get("requests", 0) or 0)
            if requests_count <= 0:
                continue
            avg_latency = float(data.get("avg_latency_ms", 0.0) or 0.0)
            error_rate = float(data.get("error_rate", 0.0) or 0.0)
            throughput = float(data.get("availability", 0.0) or 0.0)
            for _ in range(min(requests_count, 3)):
                samples.append(
                    MetricSample(
                        timestamp=now,
                        latency_ms=avg_latency,
                        error_rate=error_rate,
                        throughput=throughput,
                    )
                )

        if not samples:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Sem dados suficientes para diagnóstico",
            )

        thresholds = compute_thresholds(samples, now=now)

        overall_latency = sum(
            s.latency_ms for s in samples) / float(len(samples))
        overall_error = sum(s.error_rate for s in samples) / \
            float(len(samples))
        overall_throughput = sum(
            s.throughput for s in samples) / float(len(samples))

        anomaly: AnomalyResult = detect_anomaly(
            current_latency_ms=overall_latency,
            current_error_rate=overall_error,
            current_throughput=overall_throughput,
            thresholds=thresholds,
        )

        if anomaly.anomaly_score >= 0.9:
            health = "unhealthy"
            recommended = ["Investigar proxies com alta latência",
                           "Aumentar cooldown ou reduzir tráfego"]
        elif anomaly.anomaly_score >= 0.7:
            health = "degraded"
            recommended = ["Monitorar de perto o comportamento",
                           "Considerar redução temporária de throughput"]
        else:
            health = "healthy"
            recommended = ["Nenhuma ação imediata necessária"]

        thresholds_payload: Dict[str, DiagnosticThresholdsModel] = {}
        for metric_name in ["latency_ms", "error_rate", "throughput"]:
            windows = getattr(thresholds, metric_name)
            window = windows["24h"]
            thresholds_payload[metric_name] = DiagnosticThresholdsModel(
                window="24h",
                metric=metric_name,
                p95=window.p95,
                p99=window.p99,
                two_sigma=window.two_sigma,
                three_sigma=window.three_sigma,
            )

        return DiagnosticResponseModel(
            timestamp=now,
            service_health=health,
            anomaly_score=anomaly.anomaly_score,
            thresholds_applied=thresholds_payload,
            recommended_actions=recommended,
            details={
                "latency_ms": overall_latency,
                "error_rate": overall_error,
                "throughput": overall_throughput,
            },
        )

    return app


app = create_app()
