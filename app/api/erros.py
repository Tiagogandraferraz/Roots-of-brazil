"""
Roots of Brazil — formato de erro da API (Ordem 4).

Implementa literalmente a Seção 5.3 da Especificação Conceitual: todo erro sai
como `{"error": {"code", "message", "status"}}`, com os quatro códigos que a
Especificação define, mais `RATE_LIMIT_EXCEEDED` para o 429 introduzido pela
decisão do fundador sobre a Seção 6.

O ponto de haver uma exceção própria em vez de `HTTPException` solta é que o
formato do corpo fica em um lugar só. Um handler que montasse o JSON à mão em
cada router acabaria divergindo — e o contrato publicado em `openapi.yaml`
promete um formato único.
"""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from app.models.catalogo import ERROS


class ErroAPI(Exception):
    """Erro de domínio da API, já no formato da Seção 5.3.

    `code` precisa ser um dos códigos declarados no catálogo — se não for, a
    construção falha aqui, em vez de publicar um código que o `openapi.yaml`
    não documenta.
    """

    def __init__(self, code: str, message: str) -> None:
        if code not in ERROS:
            raise ValueError(
                f"Código de erro {code!r} não está na Seção 5.3 (válidos: {sorted(ERROS)})."
            )
        self.code = code
        self.status = ERROS[code]
        self.message = message
        super().__init__(message)

    def corpo(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "message": self.message, "status": self.status}}


def nao_encontrado(id_legivel: str) -> ErroAPI:
    """404 — a mensagem segue o exemplo literal da Especificação, Seção 5.3."""
    return ErroAPI("NOT_FOUND", f"Objeto com ID '{id_legivel}' não encontrado.")


def parametro_invalido(mensagem: str) -> ErroAPI:
    return ErroAPI("INVALID_PARAMETER", mensagem)


def integridade_referencial(id_legivel: str) -> ErroAPI:
    """422 — origem_id/destino_id não resolve para nenhuma entidade conhecida."""
    return ErroAPI(
        "REFERENTIAL_INTEGRITY_ERROR",
        f"'{id_legivel}' não corresponde a nenhuma entidade conhecida do corpus.",
    )


async def handler_erro_api(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ErroAPI)
    return JSONResponse(status_code=exc.status, content=exc.corpo())


async def handler_validacao(_: Request, exc: Exception) -> JSONResponse:
    """Converte a falha de validação do FastAPI para o formato da Seção 5.3.

    Sem isto, o FastAPI devolveria 422 no formato dele (`{"detail": [...]}`),
    que não é o que o contrato promete. Parâmetro de query malformado é 400
    `INVALID_PARAMETER` pela Especificação, não 422 — o 422 fica reservado para
    integridade referencial.
    """
    detalhes: list[dict[str, Any]] = getattr(exc, "errors", lambda: [])()
    if detalhes:
        primeiro = detalhes[0]
        local = ".".join(str(p) for p in primeiro.get("loc", ()) if p != "query")
        mensagem = f"Parâmetro '{local}' inválido: {primeiro.get('msg', 'valor não aceito')}."
    else:
        mensagem = "Parâmetro de query inválido."
    erro = ErroAPI("INVALID_PARAMETER", mensagem)
    return JSONResponse(status_code=erro.status, content=erro.corpo())


async def handler_nao_tratado(_: Request, exc: Exception) -> JSONResponse:
    """500 — nunca vaza stack trace nem mensagem interna para o cliente."""
    erro = ErroAPI("INTERNAL_ERROR", "Erro não tratado no servidor.")
    return JSONResponse(status_code=erro.status, content=erro.corpo())
