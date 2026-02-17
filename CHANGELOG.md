# Changelog

Todas as mudanças notáveis deste projeto serão documentadas neste arquivo.

O formato segue, de forma simplificada, as boas práticas de versionamento semântico.

## [0.3.0] - 2026-02-16

### Adicionado

- Conector opcional para banco de dados relacional (backend configurável, padrão PostgreSQL).
- Interface genérica de armazenamento de posts (`PostStorage`) com implementações para:
  - Google Sheets
  - Banco de dados
- Migração de dados de Google Sheets para banco de dados via `migration_controller`.
- Novos testes automatizados para camada de armazenamento e cliente de banco.

## [0.2.0] - 2026-02-16

### Adicionado

- Workflow de CI/CD com GitHub Actions:
  - Job de lint básico via `python -m compileall .`
  - Job de testes automatizados com `pytest`
  - Job de análise de segurança com `pip-audit`
  - Job de deploy que executa o scraper usando variáveis de ambiente vindas de `secrets`

## [0.1.0] - 2026-02-16

### Adicionado

- Estrutura inicial MVC para o scraper de Instagram:
  - Camadas `config`, `models`, `controllers`, `views`, `utils`
  - Integração básica com Google Sheets
  - Esboço de testes automatizados com `pytest`
