import time
from collections.abc import Iterable
from typing import List

from config.settings import AppConfig
from models.post import InstagramPost
from utils.instagram_client import fetch_posts_for_target
from utils.logging_config import get_logger
from utils.proxy_manager import proxy_cycle
from utils.sheets_client import append_posts_to_sheet


# Cria um logger específico para este módulo, permitindo rastrear o fluxo de scraping.
logger = get_logger(__name__)


def _scrape_single_target(
    config: AppConfig,
    target: str,
    proxy: str | None,
    max_posts_per_target: int,
) -> List[InstagramPost]:
    # Registra o início do processo de scraping para um alvo específico.
    logger.info("Iniciando scraping para alvo '%s' com proxy '%s'",
                target, proxy)

    # Chama o cliente de Instagram para buscar os posts do alvo.
    posts = fetch_posts_for_target(
        instagram_config=config.instagram,
        target=target,
        proxy=proxy,
        max_count=max_posts_per_target,
    )

    # Registra um resumo da quantidade de posts coletados.
    logger.info(
        "Scraping concluído para alvo '%s' com %d posts",
        target,
        len(posts),
    )

    # Retorna a lista de posts coletados para que o chamador agregue ou persista.
    return list(posts)


def _persist_posts(config: AppConfig, posts: Iterable[InstagramPost]) -> None:
    # Converte o iterável em lista para poder reutilizar e logar o tamanho.
    posts_list = list(posts)

    # Se não houver posts, registra e sai sem tentar escrever na planilha.
    if not posts_list:
        logger.info("Nenhum post coletado; nada será enviado ao Google Sheets")
        return

    # Loga a intenção de persistir a quantidade total de posts.
    logger.info("Persistindo %d posts no Google Sheets", len(posts_list))

    # Chama o cliente de Google Sheets para fazer o append das linhas.
    append_posts_to_sheet(config.google_sheets, posts_list)


def scrape_and_persist(config: AppConfig, max_posts_per_target: int = 20) -> None:
    # Cria um iterador de proxies para realizar a rotação a cada alvo.
    proxy_iterator = proxy_cycle(config.proxy.proxy_list_file_path)

    # Lista que acumula todos os posts coletados de todos os alvos.
    all_posts: list[InstagramPost] = []

    # Percorre todos os alvos configurados (perfis ou hashtags).
    for target in config.instagram.targets:
        # Aguarda o intervalo configurado para respeitar rate limiting.
        time.sleep(config.rate_limit.request_delay_seconds)

        # Obtém o próximo proxy do ciclo (ou None se não houver proxy configurado).
        proxy = next(proxy_iterator)

        try:
            # Executa o scraping de um único alvo e agrega os posts retornados.
            posts_for_target = _scrape_single_target(
                config=config,
                target=target,
                proxy=proxy,
                max_posts_per_target=max_posts_per_target,
            )
            all_posts.extend(posts_for_target)
        except Exception as error:
            # Em caso de erro, registra o problema, mas continua com outros alvos.
            logger.error("Erro ao coletar dados para '%s': %s", target, error)

    # Após processar todos os alvos, persiste o conjunto completo de posts.
    _persist_posts(config, all_posts)
