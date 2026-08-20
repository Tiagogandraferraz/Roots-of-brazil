```
# Relatório — Ordem 0 (Setup, Stack e CI/CD)
Data: 2026-08-19

## Executado
- `pyproject.toml` — Stack Oficial fixada (Python 3.13, FastAPI, SQLAlchemy, Alembic, PostgreSQL/SQLite, Neo4j driver, Pydantic, Poetry, pytest, sentence-transformers, FAISS, MCP SDK).
- Esqueleto `app/` idêntico à Seção 6: `api/`, `core/`, `models/`, `schemas/`, `services/`, `repositories/`, `database/`, `ai/`, `tests/` — todos vazios de código de domínio, só `__init__.py`.
- `app/core/logging.py` — logging estruturado em JSON, 4 níveis (INFO/WARNING/ERROR/AUDIT), handler dedicado para AUDIT em arquivo separado (nunca descartado por rotação padrão).
- `app/main.py` — apenas `/health`, sem rota de domínio.
- `docker-compose.yml` — 3 serviços (api, postgres:17, neo4j:5), todos com healthcheck.
- `Dockerfile` — build via Poetry.
- `alembic.ini` + `alembic/env.py` — aponta para `app/models` (vazio nesta Ordem; populado na Ordem 2), lê `DATABASE_URL` do ambiente.
- `.github/workflows/ci.yml` — pipeline: ruff → mypy → bandit → safety → pip-audit → pytest (cobertura ≥90%) → build Docker.
- `mkdocs.yml` — site apontando para `/docs`, navegação já referenciando os relatórios das Ordens -2 a 0.
- `.env.example` — todas as variáveis conhecidas nesta fase, valores fictícios.

## Limitação declarada (importante)
**Este ambiente sandbox não tem acesso à rede.** Não foi possível executar `poetry install`, `docker-compose up`, nem rodar o pipeline de CI de verdade para confirmar que passam. Os arquivos foram escritos seguindo rigorosamente a Stack Oficial (Seção 4) e a estrutura exigida (Seção 6), mas **nenhum critério de aceite desta Ordem foi validado por execução real** — apenas por revisão estática do conteúdo. Isso precisa ser confirmado rodando de fato em um ambiente com rede/Docker (sua máquina, ou CI real no GitHub) antes de considerar a Ordem 0 formalmente encerrada.

## Critérios de aceite — status
| Critério | Status |
|---|---|
| `poetry install` resolve dependências | Não executável nesta sandbox (sem rede) — arquivo revisado estaticamente |
| `docker-compose up` sobe 3 serviços com healthcheck | Não executável nesta sandbox (sem Docker) — config revisada estaticamente |
| Pipeline de CI roda e passa | Não executável nesta sandbox — arquivo `.github/workflows/ci.yml` revisado estaticamente |
| `mkdocs serve` sobe o site | Não executável nesta sandbox — config revisada estaticamente |
| Bandit/Safety/pip-audit zero vulnerabilidades altas/críticas | Não executável nesta sandbox |
| `.env.example` com todas as variáveis, sem valor real | ✅ Verificado |

## Status: Ordem 0 ESCRITA, PENDENTE DE VALIDAÇÃO POR EXECUÇÃO REAL
```
