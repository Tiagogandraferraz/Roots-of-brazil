"""
Roots of Brazil — repositório do banco de grafo (Ordem 4).

Resolve o que é travessia: os 18 endpoints de navegação da Seção 2, o recurso
`/v1/relacoes` da Seção 3 e a busca global da Seção 4. Listagem e detalhe
simples ficam no relacional (`app/repositories/relacional.py`).

Por que esta divisão. "Quais receitas usam este ingrediente, e com que
confiança" é uma travessia de um salto; no relacional seria um join sobre
`relacoes` mais um join na tabela de destino, e a cada salto adicional mais um
join. No property graph é `MATCH (o)-[r]->(d)`, e o peso e a proveniência já
vêm na aresta, sem reificação — que é exatamente o ganho que a Ordem 3
materializou.

O grafo devolve **IDs alcançados e propriedades da aresta**; os atributos
completos das entidades são hidratados pelo relacional. Assim cada banco
responde pelo que é bom, e não há duplicação de "quem é a fonte da verdade dos
campos do Dicionário".

Este módulo importa `app/models/grafo.py` e `app/database/neo4j.py` (Ordem 3)
apenas para leitura — nada das Ordens 1-3 é alterado.
"""

from __future__ import annotations

from typing import Any, Final

from app.models.catalogo import EMOJI_CONFIABILIDADE, Navegacao, Recurso
from app.models.grafo import (
    LABEL_SUPERCLASSE,
    TIPO_RELACAO_POR_NOME,
    label_do_id,
)

#: Nome do índice full-text criado na carga da Ordem 3, sobre nome_pt e
#: descricao_pt de todas as 8 entidades. Dicionário v1.2, Seção 24.
INDICE_FULLTEXT: Final = "objeto_roots_nome_ft"

#: Propriedades da aresta devolvidas junto de cada item navegado.
PROPS_ARESTA: Final[tuple[str, ...]] = (
    "rel_id", "tipo_relacao", "fonte", "pagina", "confiabilidade",
    "observacoes", "data_criacao", "peso", "metodo_calculo_peso",
)


def _valida_tipos(tipos: tuple[str, ...]) -> str:
    """Devolve o padrão `TIPO1|TIPO2` para o Cypher, validando cada tipo.

    Tipos de relação não são parametrizáveis em Cypher, então entram
    interpolados. Só passam nomes que existem na ontologia da Ordem 3 — a
    lista é fechada e nenhum valor de cliente chega aqui, mas a checagem fica
    de qualquer forma, porque uma interpolação sem validação vira injeção no
    dia em que alguém ligar um parâmetro a ela.
    """
    for t in tipos:
        if t not in TIPO_RELACAO_POR_NOME:
            raise ValueError(f"Tipo de relação {t!r} não existe na ontologia.")
    return "|".join(tipos)


def _sessao() -> Any:
    from app.database.neo4j import sessao

    return sessao()


def navegar(
    origem: Recurso,
    id_legivel: str,
    nav: Navegacao,
    page: int,
    page_size: int,
    confiabilidade: str | None = None,
) -> tuple[int, list[dict[str, Any]]]:
    """Percorre uma relação a partir de um nó. Devolve (total, itens).

    Cada item traz `id` do destino e `_relacao` com as propriedades da aresta —
    peso, fonte, página, observações. A Especificação Conceitual é explícita
    quanto a isso na Seção 1: "a API nunca esconde o grau de certeza de uma
    informação".
    """
    tipos = _valida_tipos(nav.tipos)
    if nav.sentido == "direta":
        padrao = f"(o:{origem.label} {{id: $id}})-[r:{tipos}]->(d:{LABEL_SUPERCLASSE})"
    else:
        padrao = f"(o:{origem.label} {{id: $id}})<-[r:{tipos}]-(d:{LABEL_SUPERCLASSE})"

    filtro = ""
    parametros: dict[str, Any] = {"id": id_legivel}
    if confiabilidade:
        filtro = " WHERE r.confiabilidade STARTS WITH $conf"
        parametros["conf"] = EMOJI_CONFIABILIDADE.get(confiabilidade, confiabilidade)

    with _sessao() as s:
        total = s.run(
            f"MATCH {padrao}{filtro} RETURN count(d) AS n", **parametros
        ).single()["n"]
        registros = s.run(
            f"MATCH {padrao}{filtro} RETURN d.id AS id, r AS rel "
            f"ORDER BY r.peso DESC, d.id ASC SKIP $skip LIMIT $limit",
            **parametros, skip=(page - 1) * page_size, limit=page_size,
        )
        itens = [
            {
                "id": reg["id"],
                "_relacao": {k: reg["rel"].get(k) for k in PROPS_ARESTA
                             if reg["rel"].get(k) is not None},
            }
            for reg in registros
        ]
    # O tipo não é propriedade da aresta no grafo (é o próprio tipo dela), então
    # é reposto aqui, para o cliente saber por qual relação o item foi alcançado.
    if len(nav.tipos) == 1:
        for item in itens:
            item["_relacao"].setdefault("tipo_relacao", nav.tipos[0])
    return total, itens


def existe_no_grafo(id_legivel: str) -> bool:
    """True se o nó existe. Usado para separar 404 de lista vazia legítima."""
    with _sessao() as s:
        registro = s.run(
            f"MATCH (n:{LABEL_SUPERCLASSE} {{id: $id}}) RETURN count(n) AS n", id=id_legivel
        ).single()
        return bool(registro["n"])


def listar_relacoes(
    origem_id: str | None,
    destino_id: str | None,
    tipo_relacao: str | None,
    confiabilidade: str | None,
    page: int,
    page_size: int,
) -> tuple[int, list[dict[str, Any]]]:
    """Camada RELACOES crua — Especificação Conceitual, Seção 3."""
    tipo = f":{_valida_tipos((tipo_relacao,))}" if tipo_relacao else ""
    condicoes: list[str] = []
    parametros: dict[str, Any] = {}
    if origem_id:
        condicoes.append("o.id = $origem")
        parametros["origem"] = origem_id
    if destino_id:
        condicoes.append("d.id = $destino")
        parametros["destino"] = destino_id
    if confiabilidade:
        condicoes.append("r.confiabilidade STARTS WITH $conf")
        parametros["conf"] = EMOJI_CONFIABILIDADE.get(confiabilidade, confiabilidade)
    onde = (" WHERE " + " AND ".join(condicoes)) if condicoes else ""
    padrao = f"(o:{LABEL_SUPERCLASSE})-[r{tipo}]->(d:{LABEL_SUPERCLASSE})"

    with _sessao() as s:
        total = s.run(f"MATCH {padrao}{onde} RETURN count(r) AS n", **parametros).single()["n"]
        registros = s.run(
            f"MATCH {padrao}{onde} "
            f"RETURN o.id AS origem_id, d.id AS destino_id, type(r) AS tipo_relacao, r AS rel "
            f"ORDER BY r.rel_id ASC SKIP $skip LIMIT $limit",
            **parametros, skip=(page - 1) * page_size, limit=page_size,
        )
        itens = []
        for reg in registros:
            item: dict[str, Any] = {
                "origem_id": reg["origem_id"],
                "destino_id": reg["destino_id"],
                "tipo_relacao": reg["tipo_relacao"],
            }
            item.update({k: reg["rel"].get(k) for k in PROPS_ARESTA
                         if k != "tipo_relacao" and reg["rel"].get(k) is not None})
            itens.append(item)
    return total, itens


def buscar(
    termo: str, tipos: list[str] | None, page: int, page_size: int
) -> tuple[int, list[dict[str, Any]]]:
    """Busca global sobre o índice full-text — Seção 4 da Especificação.

    Usa `objeto_roots_nome_ft`, criado na carga da Ordem 3 sobre `nome_pt` e
    `descricao_pt` das 8 entidades (Dicionário v1.2, Seção 24). A relevância
    vem do próprio índice, em `score`.

    A paginação é feita depois da consulta ao índice porque o procedimento
    full-text do Neo4j devolve os resultados já ordenados por relevância, e
    cortar antes perderia itens melhores das páginas seguintes. Com um corpus
    de 381 objetos isso é barato; se crescer, vale usar `SKIP`/`LIMIT` nativos.
    """
    labels = None
    if tipos:
        from app.models.catalogo import RECURSO_POR_NOME

        labels = set()
        for t in tipos:
            recurso = RECURSO_POR_NOME.get(f"{t}s") or RECURSO_POR_NOME.get(t)
            if recurso is None:
                raise ValueError(f"Tipo '{t}' não é um catálogo conhecido.")
            labels.add(recurso.label)

    with _sessao() as s:
        registros = list(s.run(
            f"CALL db.index.fulltext.queryNodes('{INDICE_FULLTEXT}', $q) "
            f"YIELD node, score "
            f"RETURN node.id AS id, node.nome_pt AS nome, node.descricao_pt AS descricao, "
            f"node.slug AS slug, node.confiabilidade AS confiabilidade, "
            f"labels(node) AS labels, score",
            q=termo,
        ))

    from app.models.catalogo import RECURSO_POR_LABEL

    itens: list[dict[str, Any]] = []
    for reg in registros:
        rotulos = [x for x in reg["labels"] if x != LABEL_SUPERCLASSE]
        if not rotulos:
            continue
        label = rotulos[0]
        if labels and label not in labels:
            continue
        recurso = RECURSO_POR_LABEL.get(label)
        if recurso is None:
            continue
        # `tipo` no singular, como a Seção 4 exemplifica ("ingrediente,receita").
        tipo = recurso.nome[:-1] if recurso.nome.endswith("s") else recurso.nome
        itens.append({
            "id": reg["id"], "tipo": tipo, "nome": reg["nome"],
            "descricao": reg["descricao"], "slug": reg["slug"],
            "confiabilidade": reg["confiabilidade"], "score": reg["score"],
        })

    total = len(itens)
    inicio = (page - 1) * page_size
    return total, itens[inicio:inicio + page_size]


def tipo_do_id(id_legivel: str) -> str:
    """Label do grafo para um ID legível. Levanta ValueError se o prefixo não existir."""
    return label_do_id(id_legivel)
