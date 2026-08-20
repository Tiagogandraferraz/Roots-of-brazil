"""
Roots of Brazil — API (esqueleto da Ordem 0).

Nenhum código de domínio (models, rotas de recurso, ontologia) é criado aqui —
apenas o esqueleto mínimo para validar o pipeline de CI/CD e o healthcheck
do docker-compose. Rotas de domínio são adicionadas na Ordem 4.
"""

from __future__ import annotations

import os

from fastapi import FastAPI

from app.core.logging import configure_logging, get_logger

configure_logging(level=os.getenv("API_LOG_LEVEL", "INFO"))
logger = get_logger(__name__)

app = FastAPI(
    title="Roots of Brazil API",
    version="0.1.0",
    description="Esqueleto da Ordem 0 — rotas de domínio adicionadas na Ordem 4.",
)


@app.get("/health")
def health() -> dict[str, str]:
    logger.info("health check requisitado")
    return {"status": "ok"}
