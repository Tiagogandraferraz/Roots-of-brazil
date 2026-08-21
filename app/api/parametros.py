"""
Roots of Brazil — leitura e validação de parâmetros de query (Ordem 4).

A validação é feita à mão, lendo de `request.query_params`, em vez de declarada
nas assinaturas dos endpoints. A razão é o contrato: os 7 recursos aceitam
conjuntos de filtros diferentes (Seção 2 da Especificação), e declarar isso em
assinaturas exigiria sete conjuntos de funções quase idênticas, ou geração
dinâmica de assinatura — as duas piores do que uma leitura explícita.

Em troca, todo erro de parâmetro sai no formato exato da Seção 5.3
(`400 INVALID_PARAMETER`), e não no formato próprio do FastAPI.
"""

from __future__ import annotations

from typing import Any

from starlette.requests import Request

from app.api.erros import parametro_invalido
from app.models.catalogo import (
    CONFIABILIDADES,
    PAGE_SIZE_MAXIMO,
    PAGE_SIZE_PADRAO,
    TIPOS_BUSCA,
    Recurso,
)

#: Parâmetros aceitos em qualquer listagem, além dos filtros do recurso.
TRANSVERSAIS: frozenset[str] = frozenset({"page", "page_size", "sort", "order", "expand"})


def inteiro(request: Request, nome: str, padrao: int, minimo: int, maximo: int | None) -> int:
    bruto = request.query_params.get(nome)
    if bruto is None or bruto == "":
        return padrao
    try:
        valor = int(bruto)
    except ValueError:
        raise parametro_invalido(f"Parâmetro '{nome}' deve ser inteiro; recebido '{bruto}'.") from None
    if valor < minimo:
        raise parametro_invalido(f"Parâmetro '{nome}' deve ser >= {minimo}; recebido {valor}.")
    if maximo is not None and valor > maximo:
        raise parametro_invalido(f"Parâmetro '{nome}' deve ser <= {maximo}; recebido {valor}.")
    return valor


def paginacao(request: Request) -> tuple[int, int]:
    """(page, page_size) da Seção 5.1, com o teto de 100 aplicado."""
    page = inteiro(request, "page", 1, 1, None)
    page_size = inteiro(request, "page_size", PAGE_SIZE_PADRAO, 1, PAGE_SIZE_MAXIMO)
    return page, page_size


def ordenacao(request: Request) -> tuple[str | None, str]:
    """(sort, order) da Seção 5.2. `order` só aceita asc ou desc."""
    sort = request.query_params.get("sort") or None
    order = (request.query_params.get("order") or "asc").lower()
    if order not in ("asc", "desc"):
        raise parametro_invalido(f"Parâmetro 'order' deve ser 'asc' ou 'desc'; recebido '{order}'.")
    return sort, order


def confiabilidade(request: Request) -> str | None:
    """Valida contra os 4 rótulos canônicos da Seção 11 do Dicionário."""
    valor: str | None = request.query_params.get("confiabilidade")
    if not valor:
        return None
    if valor not in CONFIABILIDADES:
        raise parametro_invalido(
            f"Parâmetro 'confiabilidade' fora do domínio. Aceitos: {', '.join(CONFIABILIDADES)}."
        )
    return valor


def filtros_de(request: Request, recurso: Recurso) -> dict[str, Any]:
    """Lê os filtros declarados para o recurso e recusa os que não existem.

    Recusar parâmetro desconhecido em vez de ignorar é deliberado: um cliente
    que escreve `?categora=` (sem o 'i') receberia silenciosamente a lista
    inteira, achando que filtrou. A Seção 5.3 reserva
    `400 INVALID_PARAMETER` exatamente para isso.
    """
    desconhecidos = set(request.query_params) - set(recurso.filtros) - TRANSVERSAIS
    if desconhecidos:
        raise parametro_invalido(
            f"Parâmetro(s) não aceito(s) por /v1/{recurso.nome}: "
            f"{', '.join(sorted(desconhecidos))}. "
            f"Aceitos: {', '.join(sorted(set(recurso.filtros) | TRANSVERSAIS))}."
        )
    valores: dict[str, Any] = {}
    for nome in recurso.filtros:
        bruto = request.query_params.get(nome)
        if bruto is None or bruto == "":
            continue
        if nome == "confiabilidade":
            valores[nome] = confiabilidade(request)
        elif nome == "oficial_ibge":
            if bruto.lower() not in ("true", "false", "1", "0"):
                raise parametro_invalido(
                    f"Parâmetro 'oficial_ibge' deve ser booleano; recebido '{bruto}'."
                )
            valores[nome] = bruto.lower() in ("true", "1")
        else:
            valores[nome] = bruto
    return valores


def tipos_busca(request: Request) -> list[str] | None:
    """Lista de catálogos da Seção 4, ou None para buscar em todos."""
    bruto = request.query_params.get("tipos")
    if not bruto:
        return None
    tipos = [t.strip() for t in bruto.split(",") if t.strip()]
    invalidos = [t for t in tipos if t not in TIPOS_BUSCA]
    if invalidos:
        raise parametro_invalido(
            f"Tipo(s) desconhecido(s) em 'tipos': {', '.join(invalidos)}. "
            f"Aceitos: {', '.join(TIPOS_BUSCA)}."
        )
    return tipos
