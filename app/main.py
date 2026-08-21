"""
Roots of Brazil — API do Corpus Fundador.

Esqueleto criado na Ordem 0; as rotas de domínio foram acrescentadas na Ordem 4,
como o próprio esqueleto previa. Implementa a Especificação Conceitual da API
v1.1 — 34 endpoints somente leitura sobre as 381 entidades e 1.585 relações do
corpus homologado.

**O contrato publicado é `api/openapi.yaml`, não um gerado a partir do código.**
A geração automática do FastAPI está desligada de propósito: a especificação é
o artefato revisado, validado com Spectral e derivado do Dicionário de Dados
v1.2, e é ela que a API serve em `/openapi.yaml` e `/docs`. Um contrato
reverso-engenheirado do código descreveria o que o código faz; este descreve o
que o corpus é, que é o compromisso da Especificação Conceitual (Seção 7).
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

from app.api.erros import (
    ErroAPI,
    handler_erro_api,
    handler_nao_tratado,
    handler_validacao,
)
from app.api.routers import catalogo, relacoes_busca
from app.core.logging import configure_logging, get_logger
from app.core.middleware import MiddlewareETag, MiddlewareLimiteDeTaxa

configure_logging(level=os.getenv("API_LOG_LEVEL", "INFO"))
logger = get_logger(__name__)

RAIZ = Path(__file__).resolve().parents[1]
OPENAPI = RAIZ / "api" / "openapi.yaml"
SWAGGER_UI = RAIZ / "api" / "swagger_ui" / "index.html"

app = FastAPI(
    title="Roots of Brazil — API do Corpus Fundador",
    version="1.1.0",
    # Desligados: quem serve o contrato é o arquivo revisado, abaixo.
    openapi_url=None,
    docs_url=None,
    redoc_url=None,
)

# --- Middlewares -------------------------------------------------------
# A ordem importa. No Starlette, o ÚLTIMO adicionado é o mais externo, então
# esta sequência produz, de fora para dentro:
#   CORS -> limite de taxa -> gzip -> ETag -> aplicação
# CORS por fora para que até a resposta 429 saia com os cabeçalhos de origem;
# ETag por dentro para calcular o hash sobre o corpo antes de comprimir.
app.add_middleware(MiddlewareETag)
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(MiddlewareLimiteDeTaxa)
app.add_middleware(
    CORSMiddleware,
    # Decisão do fundador para o placeholder da Seção 6: CORS aberto. A API é
    # pública e de leitura, e não usa credenciais — por isso `*` é seguro aqui,
    # ao contrário de um serviço com sessão, onde `*` com credenciais é falha.
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["ETag", "X-RateLimit-Limit", "X-RateLimit-Remaining", "Retry-After"],
)

# --- Erros no formato da Seção 5.3 -------------------------------------
app.add_exception_handler(ErroAPI, handler_erro_api)
app.add_exception_handler(RequestValidationError, handler_validacao)
app.add_exception_handler(Exception, handler_nao_tratado)

# --- Rotas de domínio (Seções 2, 3 e 4) --------------------------------
app.include_router(catalogo.router)
app.include_router(relacoes_busca.router)


@app.get("/health", tags=["Operação"])
def health() -> dict[str, str]:
    logger.info("health check requisitado")
    return {"status": "ok"}


@app.get("/openapi.yaml", include_in_schema=False)
def contrato() -> FileResponse:
    """Serve a especificação revisada — o contrato oficial da API."""
    return FileResponse(OPENAPI, media_type="application/yaml")


@app.get("/docs", include_in_schema=False)
def documentacao() -> HTMLResponse:
    """Swagger UI apontando para `api/openapi.yaml`."""
    return HTMLResponse(SWAGGER_UI.read_text(encoding="utf-8"))
