from config.settings import load_app_config
from controllers.scraper_controller import scrape_and_persist
from utils.logging_config import configure_logging


def main() -> None:
    # Configura o logging padrão da aplicação, com formato legível em console.
    configure_logging()

    # Carrega as configurações da aplicação a partir das variáveis de ambiente.
    config = load_app_config()

    # Executa o fluxo principal: scraping e persistência dos dados.
    scrape_and_persist(config)


if __name__ == "__main__":
    # Garante que o main só seja executado quando o módulo for rodado diretamente.
    main()
