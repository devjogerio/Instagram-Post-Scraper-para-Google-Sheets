# Instagram Post Scraper para Google Sheets

Ferramenta em Python para coletar dados públicos de postagens do Instagram e enviar os resultados para o Google Sheets, seguindo uma arquitetura MVC enxuta e preparada para evolução.

## Visão Geral

Este projeto automatiza a coleta de dados de engajamento de postagens do Instagram (legenda, curtidas, comentários, data, tipo de mídia, URL etc.) e centraliza tudo em uma planilha do Google Sheets para análise.

Arquitetura base:
- Linguagem: Python 3.9+
- Padrão: MVC (models, views, controllers) com camadas de config e utils
- Integrações: Instagram (via Instaloader) e Google Sheets (via gspread + google-auth)

## Estrutura de Pastas

```text
project-root/
  config/
    __init__.py
    settings.py
  controllers/
    __init__.py
    scraper_controller.py
  models/
    __init__.py
    post.py
  views/
    __init__.py
    cli.py
  utils/
    __init__.py
    instagram_client.py
    sheets_client.py
    logging_config.py
    rate_limiter.py
    proxy_manager.py
  tests/
    __init__.py
    test_scraper_controller.py
  .env.example
  .gitignore
  prd.md
  README.md
  requirements.txt
```

## Requisitos Funcionais (Resumo)

- Extração de dados de postagens do Instagram:
  - URL da postagem
  - Texto da legenda
  - Quantidade de curtidas
  - Quantidade de comentários
  - Data de publicação
  - Tipo de mídia (imagem, vídeo ou carrossel)
- Integração com Google Sheets com append de novas linhas.
- Configuração de perfis ou hashtags via variável de ambiente ou arquivo de configuração.

## Stack Técnica

- Python 3.9+
- Instaloader (scraping de posts públicos)
- gspread e google-auth (integração com Google Sheets)
- pytest (testes automatizados)

## Configuração de Ambiente

1. Crie e ative um ambiente virtual:

```bash
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate    # Windows
```

2. Instale as dependências:

```bash
pip install -r requirements.txt
```

3. Crie um arquivo `.env` na raiz do projeto com base em `.env.example` e preencha as variáveis obrigatórias.

## Execução Básica

Após configurar o ambiente e o `.env`:

```bash
python -m views.cli
```

Este comando executa o fluxo principal:
- lê perfis/hashtags de configuração,
- dispara o scraper de Instagram,
- envia os dados para o Google Sheets e, opcionalmente, para o banco de dados quando configurado.

## Uso opcional de banco de dados

Além do Google Sheets, é possível armazenar os dados em um banco de dados relacional (por exemplo, PostgreSQL). Para isso:

1. Configure no `.env`:

```bash
DB_ENABLED=true
DB_BACKEND=postgres
DB_DSN=postgresql://usuario:senha@host:porta/nome_do_banco
```

2. Garanta que o banco esteja acessível a partir do ambiente de execução.

Quando `DB_ENABLED=true` e `DB_BACKEND`/`DB_DSN` estiverem definidos, o sistema:
- cria (se necessário) a tabela `instagram_posts`;
- grava cada post tanto no Google Sheets quanto no banco de dados.

## Testes Automatizados

Para rodar os testes:

```bash
pytest
```

Os testes cobrem o fluxo de alto nível do controlador e partes críticas de integração, permitindo refatorações seguras.

## Fluxo de Git e Branches

- Branch principal: `main`
- Cada nova funcionalidade deve ser desenvolvida em uma branch específica:
  - Padrão: `feature/nome-da-funcionalidade`
  - Exemplos:
    - `feature/extracao-posts-instagram`
    - `feature/integracao-google-sheets`
    - `feature/tratamento-erros-logging`

### Commits

- Utilize Conventional Commits em português:
  - `feat: adicionar controlador de scraping`
  - `fix: corrigir tratamento de posts privados`
  - `refactor: reorganizar utils de rate limiting`

### Pull Requests e Code Review

1. Crie uma branch de feature.
2. Implemente a funcionalidade com testes e atualização de documentação quando necessário.
3. Abra um Pull Request para `main`.
4. Garanta que:
   - testes passem,
   - cobertura mínima seja preservada,
   - o fluxo manual de execução esteja funcional.

## GitHub – Configuração Inicial

Para conectar o repositório local ao GitHub:

```bash
git init
git remote add origin git@github.com:devjogerio/Instagram-Post-Scraper-para-Google-Sheets.git
git add .
git commit -m "feat: criar estrutura inicial do projeto"
git push -u origin main
```

Depois, para uma nova funcionalidade:

```bash
git checkout -b feature/nome-da-funcionalidade
# ... implementar, testar ...
git add .
git commit -m "feat: descrever funcionalidade em pt-br"
git push -u origin feature/nome-da-funcionalidade
```

## CI/CD com GitHub Actions

Este repositório conta com um workflow de CI/CD em `.github/workflows/ci.yml` com os seguintes jobs:

- **lint**: valida a sintaxe de todos os arquivos Python com `python -m compileall .`.
- **tests**: executa os testes automatizados com `pytest`.
- **security**: roda `pip-audit` para analisar vulnerabilidades nas dependências.
- **deploy**: executa o scraper (`python -m views.cli`) usando variáveis definidas em `secrets`.

### Disparadores do workflow

O workflow é disparado automaticamente em:

- `push` para as branches:
  - `main`
  - `feature/**`
- `pull_request` direcionados para `main`
- `release` do tipo `created`
- Execução manual via `workflow_dispatch`

### Secrets necessários para o deploy

Para que o job de deploy consiga executar o scraper em ambiente de CI, configure os seguintes `secrets` no GitHub (Settings → Secrets and variables → Actions):

- `IG_USERNAME`
- `IG_PASSWORD`
- `SCRAPER_TARGETS`
- `GOOGLE_SERVICE_ACCOUNT_JSON_PATH`
- `GOOGLE_SHEETS_SPREADSHEET_ID`
- `GOOGLE_SHEETS_WORKSHEET_NAME`
- `SCRAPER_REQUEST_DELAY_SECONDS`
- `PROXY_LIST_FILE_PATH`

Os nomes correspondem às variáveis de ambiente esperadas pelo código, conforme `.env.example`.

## Próximos Passos Evolutivos

- Scraping de múltiplas fontes (perfis, hashtags, listas configuráveis).
- Rate limiting configurável e uso opcional de proxies.
- Tratamento robusto de erros e logs estruturados.
- Dashboard para visualização dos dados (web ou notebook).
- Aprimorar pipeline de deploy automatizado (CI/CD) com monitoramento e alertas.
