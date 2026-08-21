"""
Roots of Brazil — serialização das respostas (Ordem 4).

Duas responsabilidades, ambas com consequência no contrato publicado:

1. **Converter o que o SQLite não tem tipo para.** `oficial_ibge` é INTEGER 0/1
   no banco porque SQLite não tem booleano, mas a Seção 2.6 da Especificação
   exige literalmente `oficial_ibge: false`. Sem esta camada, o cliente
   receberia `0` e o contrato estaria mentindo.

2. **Montar `_links`.** A Seção 1 diz que toda resposta que referencia outra
   entidade traz o ID puro para navegação. Os `_links` são derivados do
   catálogo, então um endpoint de navegação novo aparece no link
   automaticamente — não há segunda lista para esquecer de atualizar.
"""

from __future__ import annotations

from typing import Any

from app.models.catalogo import Recurso, campos_de

#: Campos que o banco guarda como 0/1 e a API expõe como booleano.
CAMPOS_BOOLEANOS: frozenset[str] = frozenset({"oficial_ibge"})


def serializar(recurso: Recurso, linha: dict[str, Any]) -> dict[str, Any]:
    """Converte uma linha do banco no objeto de resposta do `openapi.yaml`.

    Campos nulos são omitidos: o schema os declara como união com `null`, e
    omitir mantém a resposta enxuta sem quebrar o contrato. Campos fora do
    catálogo são descartados — é a última barreira da restrição "nenhum
    endpoint expõe campo ausente do Dicionário v1.2".
    """
    permitidos = set(campos_de(recurso))
    saida: dict[str, Any] = {}
    for campo, valor in linha.items():
        if campo not in permitidos or valor is None:
            continue
        saida[campo] = bool(valor) if campo in CAMPOS_BOOLEANOS else valor
    saida["_links"] = links_de(recurso, str(linha.get("id", "")))
    return saida


def links_de(recurso: Recurso, id_legivel: str) -> dict[str, str]:
    """URLs dos sub-recursos de navegação deste objeto."""
    return {
        nav.sub: f"/v1/{recurso.nome}/{id_legivel}/{nav.sub}"
        for nav in recurso.navegacoes
    }


def pagina(total: int, page: int, page_size: int, itens: list[Any]) -> dict[str, Any]:
    """Envelope de paginação da Seção 5.1: total, page, page_size, items."""
    return {"total": total, "page": page, "page_size": page_size, "items": itens}
