# Changelog — Ordem 4 (API)

Formato: [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).
Versionamento da **API** por path (`/v1`), independente do versionamento do
corpus (v1.1, v1.2…) — Especificação Conceitual, Seção 1.

## [1.1.0] — 2026-08-21

Primeira implementação da Especificação Conceitual da API v1.1. Contrato
inaugural: não há versão anterior a quebrar.

### Adicionado

**Contrato**
- `api/openapi.yaml` — OpenAPI 3.1.0 com 35 paths, 35 operações e 19 schemas.
- `api/gerar_openapi.py` — gera o contrato a partir de `app/models/catalogo.py`
  e do DDL da Ordem 2. Os exemplos são lidos do corpus real carregado.
- `api/.spectral.yaml` — ruleset baseado no oficial da OpenAPI.
- `api/postman_collection.json` + `api/gerar_postman.py` — 35 requisições em 10
  pastas, com testes de status, ETag e envelope de paginação.
- `api/swagger_ui/index.html` — Swagger UI apontando para o contrato revisado.

**Endpoints** — 34, todos `GET`
- 7 listagens `/v1/{recurso}` com os filtros da Seção 2, paginação (5.1) e
  ordenação (5.2).
- 7 detalhes `/v1/{recurso}/{id}`, com `_links` de navegação e `?expand=`.
- 18 navegações `/v1/{recurso}/{id}/{relacao}`, resolvidas pelo grafo, com as
  propriedades da aresta em `_relacao`.
- `/v1/relacoes` — camada RELACOES direta (Seção 3).
- `/v1/busca` — busca global sobre o índice full-text (Seção 4).

**Servidor**
- `app/models/catalogo.py` — metadados dos 7 recursos: campos, filtros,
  navegações e domínios. Fonte única para o contrato e para os routers.
- `app/repositories/relacional.py` — listagem e detalhe (Ordem 2).
- `app/repositories/grafo.py` — navegação, relações e busca (Ordem 3).
- `app/api/erros.py` — formato de erro da Seção 5.3, com 5 códigos.
- `app/api/parametros.py` — validação de query, sempre em 400 `INVALID_PARAMETER`.
- `app/api/serializacao.py` — `_links`, conversão de tipos e corte de campos
  fora do Dicionário.
- `app/api/routers/` — routers construídos a partir do catálogo.
- `app/core/middleware.py` — limite de taxa e ETag.

**Infra e documentação**
- `.github/workflows/contrato_api.yml` — Spectral, `--check` do contrato e da
  coleção, ruff, mypy e a suíte com `--cov-fail-under=90`, contra o grafo real.
- `tests/contract_tests/` — 205 testes.
- `docs/diagrama_api.png` + `api/gerar_diagrama.py`.
- `app/__init__.py` e `logs/.gitkeep` — faltavam desde a Ordem 0; sem eles o
  mypy não roda e a API não sobe num clone limpo.

### Decidido (externo à engenharia)
Resolução do placeholder da Seção 6, por decisão do fundador:
- **Sem API Key.** A Especificação recomendava `X-API-Key`; a decisão foi o
  contrário — API pública de catalogação cultural, leitura livre.
- **Rate limiting** de 100 req/min por IP, com 429.
- **CORS aberto**, `Access-Control-Allow-Origin: *`, sem credenciais.

### Alterado
- `app/main.py` — o esqueleto da Ordem 0 passou a montar os routers de domínio,
  como o próprio arquivo previa. A geração automática de OpenAPI do FastAPI foi
  **desligada**: o contrato servido é o arquivo revisado e validado.
- `pyproject.toml` — duas exceções ao `mypy --strict`, restritas a
  `app.main`/`app.api.routers.*` (decoradores do FastAPI) e
  `app.core.middleware` (`BaseHTTPMiddleware` sem stubs). A lógica de domínio
  segue sob `strict` integral.

### Não alterado
Nada de código ou teste das Ordens 1-3, conforme a restrição da Ordem 4. O
modelo de grafo e a camada de conexão são importados **apenas para leitura**.

### Notas de contrato para clientes
- Toda propriedade corresponde 1:1 a uma coluna do Dicionário v1.2. `_links` e
  `_relacao` são as únicas construídas pela API, e ambas são navegação.
- Campos nulos são **omitidos** da resposta, não enviados como `null`.
- `oficial_ibge` é booleano na API, embora seja 0/1 no banco.
- `confiabilidade` casa por prefixo de emoji: o valor pode trazer texto livre
  depois dele.
- `page_size` tem teto de 100; acima disso, 400.
- Respostas trazem `ETag` e `Cache-Control`; use `If-None-Match` para 304.
- `rel_id` **ainda não é um identificador estável**: a unificação das duas
  subséries está pendente (Seção 8 da Especificação).

### Conhecido em aberto
- Rate limiting é por processo; com várias réplicas o limite efetivo multiplica.
- `?expand=` só expande no detalhe. Na listagem é validado, mas não expande.
- `/v1/patrimonio/{id}/povos_territorios` devolve apenas Povo — `PATRIMONIO_DE`
  não tem instância para Território no corpus.
- Cobertura e os p95 de navegação e busca dependem de uma execução do workflow
  com o grafo alcançável.
