"""
Roots of Brazil — recursos de grafo puro (Ordem 4).

Dois endpoints que não pertencem a nenhum catálogo:

  - `/v1/relacoes` — Seção 3 da Especificação: a camada RELACOES exposta
    diretamente, para consultas de grafo mais flexíveis que os sub-recursos de
    navegação.
  - `/v1/busca` — Seção 4: busca textual multi-entidade sobre o índice
    full-text criado na carga da Ordem 3.

Ambos resolvem pelo banco de grafo.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from starlette.requests import Request

from app.api import parametros, serializacao
from app.api.erros import integridade_referencial, parametro_invalido
from app.models.catalogo import TIPOS_BUSCA
from app.models.grafo import TIPO_RELACAO_POR_NOME
from app.repositories import grafo, relacional

router = APIRouter()

_TRANSVERSAIS_RELACOES = {"origem_id", "destino_id", "tipo_relacao", "confiabilidade",
                          "page", "page_size"}


@router.get("/v1/relacoes", name="listar_relacoes")
async def listar_relacoes(request: Request) -> dict[str, Any]:
    desconhecidos = set(request.query_params) - _TRANSVERSAIS_RELACOES
    if desconhecidos:
        raise parametro_invalido(
            f"Parâmetro(s) não aceito(s) por /v1/relacoes: {', '.join(sorted(desconhecidos))}."
        )

    tipo = request.query_params.get("tipo_relacao") or None
    if tipo and tipo not in TIPO_RELACAO_POR_NOME:
        raise parametro_invalido(
            f"'tipo_relacao' fora do domínio. Aceitos: "
            f"{', '.join(sorted(TIPO_RELACAO_POR_NOME))}."
        )

    origem = request.query_params.get("origem_id") or None
    destino = request.query_params.get("destino_id") or None
    # A Seção 5.3 reserva 422 REFERENTIAL_INTEGRITY_ERROR exatamente para isto:
    # um ID sintaticamente plausível que não resolve para entidade nenhuma. É
    # diferente de 404, que é o objeto pedido não existir.
    for identificador in (origem, destino):
        if identificador and not relacional.existe(identificador):
            raise integridade_referencial(identificador)

    conf = parametros.confiabilidade(request)
    page, page_size = parametros.paginacao(request)
    total, itens = grafo.listar_relacoes(origem, destino, tipo, conf, page, page_size)
    return serializacao.pagina(total, page, page_size, itens)


@router.get("/v1/busca", name="busca_global")
async def busca_global(request: Request) -> dict[str, Any]:
    desconhecidos = set(request.query_params) - {"q", "tipos", "page", "page_size"}
    if desconhecidos:
        raise parametro_invalido(
            f"Parâmetro(s) não aceito(s) por /v1/busca: {', '.join(sorted(desconhecidos))}."
        )

    termo = (request.query_params.get("q") or "").strip()
    if not termo:
        raise parametro_invalido(
            "Parâmetro 'q' é obrigatório na busca global e não pode ser vazio."
        )
    tipos = parametros.tipos_busca(request)
    page, page_size = parametros.paginacao(request)
    try:
        total, itens = grafo.buscar(termo, tipos, page, page_size)
    except ValueError as erro:
        raise parametro_invalido(str(erro)) from None
    return serializacao.pagina(total, page, page_size, itens)


@router.get("/v1/tipos", name="listar_tipos", include_in_schema=False)
async def listar_tipos() -> dict[str, Any]:
    """Domínios aceitos pela API. Auxiliar de descoberta, fora do contrato.

    Marcado `include_in_schema=False` porque não está na Especificação
    Conceitual — expor no contrato publicado seria inventar endpoint.
    """
    return {
        "tipos_busca": list(TIPOS_BUSCA),
        "tipos_relacao": sorted(TIPO_RELACAO_POR_NOME),
    }
