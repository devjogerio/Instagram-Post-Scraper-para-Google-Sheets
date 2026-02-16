PRD: Instagram Post Scraper para Google Sheets
1. Visão Geral do Projeto
O objetivo é desenvolver uma ferramenta em Python que extraia dados de postagens (públicas) do Instagram — como legendas, contagem de curtidas, data e URLs — e os insira automaticamente em uma planilha do Google Sheets para análise posterior.

2. Objetivos Principais
Automatização: Eliminar a coleta manual de dados de engajamento.

Centralização: Manter um histórico estruturado em nuvem (Google Sheets).

Monitoramento: Acompanhar a performance de perfis específicos ou hashtags.

3. Requisitos Funcionais (O que deve fazer)
RF01: Extração de Dados

O script deve ser capaz de coletar:

URL da postagem.

Texto da legenda.

Quantidade de curtidas (Likes).

Quantidade de comentários.

Data de publicação.

Tipo de mídia (Imagem, Vídeo ou Carrossel).

RF02: Integração com Google Sheets

O sistema deve autenticar via Google Sheets API.

Novos dados devem ser anexados à última linha disponível (evitando sobrescrever dados antigos).

RF03: Configuração de Input

O usuário deve poder definir uma lista de perfis ou hashtags alvo através de um arquivo de configuração ou variável no código.

4. Requisitos Técnicos (A "Engine")
Stack Sugerida

Linguagem: Python 3.9+.

Bibliotecas de Scraping: * Instaloader (mais simples para iniciantes).

Selenium ou Playwright (se for necessário simular comportamento humano para evitar bloqueios).

Integração de Dados: gspread e google-auth.

Fluxo de Dados

Componente	Função
Scraper Core	Faz a requisição ao Instagram e faz o parse do JSON/HTML.
Data Cleaner	Formata datas e remove caracteres especiais das legendas.
Sheets Connector	Abre a planilha via Service Account e envia os dados.
5. Riscos e Mitigação
Bloqueio de IP: O Instagram tem limites rígidos de taxa (rate limiting).

Mitigação: Implementar time.sleep() entre as requisições e usar proxies se o volume for alto.

Mudança no HTML: O Instagram muda a estrutura das classes frequentemente.

Mitigação: Usar bibliotecas que foquem na API interna (como Instaloader) em vez de seletores CSS puramente visuais.

Login e Segurança: Evitar o uso de contas pessoais principais para o scraping para prevenir banimentos.

6. Roadmap de Desenvolvimento
Fase 1: Setup das credenciais no Google Cloud Console e criação da planilha.

Fase 2: Script base de extração via terminal (apenas printando os dados).

Fase 3: Implementação da função de escrita no Google Sheets.

Fase 4: Tratamento de erros e logs (ex: avisar se o perfil for privado).