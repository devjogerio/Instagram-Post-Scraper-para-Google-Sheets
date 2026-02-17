import argparse
import json
import time
import uuid
from typing import Any, Dict

from config.settings import load_app_config
from controllers.anomaly_recalibration_controller import (
    AnomalyRecalibrationController,
    CloudWatchMetricsSource,
    OpenSearchMetricsSource,
)
from utils.logging_config import configure_logging, get_logger
from utils.proxy_manager import ProxyManager


logger = get_logger(__name__)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    # Interpreta argumentos de linha de comando para execução da recalibração via CLI.
    parser = argparse.ArgumentParser(description="Recalibração automática de políticas de proxy")
    parser.add_argument(
        "--backend",
        choices=["cloudwatch", "opensearch"],
        default="cloudwatch",
        help="Backend de métricas a ser utilizado",
    )
    parser.add_argument(
        "--since-seconds",
        type=int,
        default=30 * 24 * 60 * 60,
        help="Intervalo de tempo em segundos para considerar na análise",
    )
    return parser.parse_args(argv)


def run(argv: list[str] | None = None) -> int:
    # Executa o fluxo de recalibração utilizando o backend configurado, com logs JSON e correlation ID.
    configure_logging()
    args = _parse_args(argv)
    correlation_id = str(uuid.uuid4())

    start = time.time()
    logger.info(
        json.dumps(
            {
                "event": "recalibration_cli_start",
                "correlation_id": correlation_id,
                "backend": args.backend,
                "since_seconds": args.since_seconds,
            }
        )
    )

    try:
        config = load_app_config()
        manager = ProxyManager.from_file(config.proxy.proxy_list_file_path)

        if args.backend == "cloudwatch":
            source = CloudWatchMetricsSource.from_env()
        else:
            source = OpenSearchMetricsSource.from_env()

        controller = AnomalyRecalibrationController(source, manager)
        policies = controller.run()

        duration_ms = int((time.time() - start) * 1000)
        payload: Dict[str, Any] = {
            "event": "recalibration_cli_success",
            "correlation_id": correlation_id,
            "backend": args.backend,
            "duration_ms": duration_ms,
            "policies": vars(policies),
        }
        logger.info(json.dumps(payload))
        return 0
    except Exception as exc:
        duration_ms = int((time.time() - start) * 1000)
        logger.error(
            json.dumps(
                {
                    "event": "recalibration_cli_error",
                    "correlation_id": correlation_id,
                    "backend": args.backend,
                    "duration_ms": duration_ms,
                    "error": str(exc),
                }
            )
        )
        return 1


def main() -> None:
    # Ponto de entrada padrão para execução via linha de comando.
    exit_code = run()
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()

