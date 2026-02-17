from config.settings import AppConfig
from models.post import InstagramPost
from utils.db_client import save_posts_to_db, init_post_table
from utils.logging_config import get_logger
from utils.sheets_client import fetch_posts_from_sheet


logger = get_logger(__name__)


def migrate_sheets_to_database(config: AppConfig) -> None:
    if not config.database.enabled or not config.database.backend:
        logger.info("Conector de banco de dados desabilitado; migração não será executada")
        return

    logger.info("Iniciando migração de dados do Google Sheets para o banco de dados")

    posts: list[InstagramPost] = fetch_posts_from_sheet(config.google_sheets)

    if not posts:
        logger.info("Nenhum dado encontrado no Google Sheets para migração")
        return

    init_post_table(config.database)
    save_posts_to_db(config.database, posts)

    logger.info("Migração concluída com %d posts transferidos", len(posts))

