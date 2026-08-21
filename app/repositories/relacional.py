"""
Roots of Brazil — repositório do banco relacional (Ordem 4).

Resolve **listagem e detalhe** dos 7 recursos contra o banco da Ordem 2. A
navegação entre entidades e a busca global NÃO passam por aqui: vão para o
grafo (`app/repositories/grafo.py`), como manda o passo 3 da Ordem 4.

A divisão não é arbitrária. Listar e filtrar um catálogo é exatamente o que um
banco relacional faz melhor — índice em coluna, `WHERE`, `ORDER BY`, `LIMIT`.
Já "quais receitas usam este ingrediente, e com que peso" é uma travessia, e no
modelo relacional exigiria join sobre `relacoes` para cada salto.

Toda coluna devolvida vem de `app/models/catalogo.py`, que por sua vez espelha
o DDL da Ordem 2. Nenhuma query usa `SELECT *`: o conjunto de campos é o que o
`openapi.yaml` promete, e nada além.
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Final

from app.models.catalogo import EMOJI_CONFIABILIDADE, Recurso, campos_de

#: Caminho do SQLite da Ordem 2. Em produção a Ordem 6 troca por PostgreSQL;
#: o formato das queries é ANSI o bastante para a migração ser mecânica.
CAMINHO_PADRAO: Final = "roots_of_brazil_dev.db"


def caminho_banco() -> Path:
    return Path(os.getenv("ROOTS_SQLITE_PATH", CAMINHO_PADRAO))


@contextmanager
def conexao() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(caminho_banco(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def _colunas(recurso: Recurso, conn: sqlite3.Connection) -> list[str]:
    """Campos do catálogo que existem de fato na tabela.

    A interseção protege contra um campo declarado no catálogo mas ausente do
    schema — a query falharia em runtime; assim ela apenas não o devolve, e o
    teste de contrato que compara resposta e `openapi.yaml` acusa a diferença.
    """
    existentes = {linha[1] for linha in conn.execute(f"PRAGMA table_info({recurso.tabela})")}
    return [c for c in campos_de(recurso) if c in existentes]


def _clausulas(recurso: Recurso, filtros: dict[str, Any]) -> tuple[str, list[Any]]:
    """Monta o WHERE a partir dos filtros da Seção 2 da Especificação.

    Nomes de coluna nunca vêm do cliente: só entram nomes já presentes em
    `recurso.filtros`, que é uma lista fechada no catálogo. Os valores vão
    sempre por parâmetro ligado.
    """
    partes: list[str] = []
    valores: list[Any] = []
    for nome, valor in filtros.items():
        if valor is None or nome not in recurso.filtros:
            continue
        if nome == "q":
            # Busca textual simples no nome próprio do recurso. A busca global
            # com relevância é outra coisa, e mora no grafo (Seção 4).
            alvos = [recurso.campo_nome, "nome_pt"]
            if recurso.nome == "ingredientes":
                alvos.append("nomes_regionais")  # Seção 2.1 cita os dois campos
            partes.append("(" + " OR ".join(f"{a} LIKE ?" for a in alvos) + ")")
            valores.extend([f"%{valor}%"] * len(alvos))
        elif nome == "confiabilidade":
            # Casa por prefixo de emoji, não por igualdade: o Dicionário v1.2
            # (Seção 11) permite texto livre depois do emoji, e o corpus real
            # traz "🔵 Inferido com cautela" — achado registrado na Ordem 2.
            partes.append("confiabilidade LIKE ?")
            valores.append(f"{EMOJI_CONFIABILIDADE.get(str(valor), str(valor))}%")
        elif nome == "bioma":
            partes.append("bioma_texto LIKE ?")
            valores.append(f"%{valor}%")
        elif nome == "oficial_ibge":
            partes.append("oficial_ibge = ?")
            valores.append(1 if valor else 0)
        else:
            partes.append(f"{nome} = ?")
            valores.append(valor)
    return (" WHERE " + " AND ".join(partes) if partes else ""), valores


def listar(
    recurso: Recurso,
    filtros: dict[str, Any],
    page: int,
    page_size: int,
    sort: str | None = None,
    order: str = "asc",
) -> tuple[int, list[dict[str, Any]]]:
    """Página de um catálogo. Devolve (total, itens).

    `total` é o total que casa com o filtro, não o tamanho da página — é o que
    a Seção 5.1 especifica no envelope de resposta.
    """
    with conexao() as conn:
        colunas = _colunas(recurso, conn)
        onde, valores = _clausulas(recurso, filtros)

        total = conn.execute(
            f"SELECT COUNT(*) FROM {recurso.tabela}{onde}", valores
        ).fetchone()[0]

        ordenacao = ""
        if sort:
            if sort not in colunas:
                # Coluna inexistente vira erro de parâmetro, não SQL inválido.
                raise ValueError(
                    f"Campo de ordenação '{sort}' não existe em {recurso.nome}. "
                    f"Campos válidos: {', '.join(sorted(colunas))}."
                )
            sentido = "DESC" if order.lower() == "desc" else "ASC"
            ordenacao = f" ORDER BY {sort} {sentido}"  # `sort` validado contra a lista acima
        else:
            ordenacao = " ORDER BY id ASC"

        linhas = conn.execute(
            f"SELECT {', '.join(colunas)} FROM {recurso.tabela}{onde}{ordenacao} "
            f"LIMIT ? OFFSET ?",
            [*valores, page_size, (page - 1) * page_size],
        ).fetchall()
        return total, [dict(linha) for linha in linhas]


def obter(recurso: Recurso, id_legivel: str) -> dict[str, Any] | None:
    """Um objeto pelo ID legível, ou None se não existir."""
    with conexao() as conn:
        colunas = _colunas(recurso, conn)
        linha = conn.execute(
            f"SELECT {', '.join(colunas)} FROM {recurso.tabela} WHERE id = ?", (id_legivel,)
        ).fetchone()
        return dict(linha) if linha else None


def obter_varios(recurso: Recurso, ids: list[str]) -> dict[str, dict[str, Any]]:
    """Vários objetos de um catálogo, indexados por ID.

    Usado para hidratar o resultado de uma travessia: o grafo devolve os IDs
    alcançados e o peso da aresta, e os atributos completos vêm daqui. Assim o
    grafo não precisa carregar toda a coluna do Dicionário, e o relacional
    continua sendo a fonte dos atributos.
    """
    if not ids:
        return {}
    with conexao() as conn:
        colunas = _colunas(recurso, conn)
        marcadores = ",".join("?" * len(ids))
        linhas = conn.execute(
            f"SELECT {', '.join(colunas)} FROM {recurso.tabela} WHERE id IN ({marcadores})", ids
        ).fetchall()
        return {linha["id"]: dict(linha) for linha in linhas}


def existe(id_legivel: str) -> bool:
    """True se o ID existe em qualquer um dos catálogos.

    Espelha a view `objeto_universal` da Ordem 2 — é o que permite responder
    404 (`NOT_FOUND`, ID não existe em catálogo nenhum) de forma diferente de
    422 (`REFERENTIAL_INTEGRITY_ERROR`), como a Seção 5.3 distingue.
    """
    with conexao() as conn:
        linha = conn.execute(
            "SELECT 1 FROM objeto_universal WHERE id = ? LIMIT 1", (id_legivel,)
        ).fetchone()
        return linha is not None
