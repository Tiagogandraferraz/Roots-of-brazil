"""Testes de integração da Ordem 3 — exigem um Neo4j de verdade no ar.

Estes testes NÃO usam o corpus real: eles sobem o mini-corpus da fixture
`fonte_sintetica` em um banco descartável, para provar que o DDL do grafo e o
Cypher de carga funcionam contra o Neo4j, sem tocar nos dados de produção.

Quando não há Neo4j alcançável, cada teste se PULA (`pytest.skip`) em vez de
falhar — um ambiente sem banco de grafo deve declarar que não validou, não
fingir que validou nem quebrar a suíte.

Para rodar de verdade:
    docker compose up -d neo4j
    export NEO4J_URI=bolt://localhost:7687 NEO4J_USER=neo4j NEO4J_PASSWORD=<senha>
    pytest tests/ordem3/test_carga_neo4j.py
"""

from __future__ import annotations

import sqlite3
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from app.models.grafo import (  # noqa: E402
    CONSTRAINTS,
    ENTIDADES,
    INDICES,
    LABEL_SUPERCLASSE,
)
from scripts.ordem3.etl_neo4j import (  # noqa: E402
    _gravador,
    _props_aresta,
    cypher_merge_nos,
    cypher_merge_relacoes,
    le_nos,
    le_relacoes,
)

neo4j = pytest.importorskip("neo4j", reason="driver neo4j não instalado")


def _config() -> Any:
    from app.database.neo4j import ConfiguracaoNeo4j

    try:
        return ConfiguracaoNeo4j.do_ambiente()
    except RuntimeError as erro:
        pytest.skip(str(erro))


@pytest.fixture
def grafo() -> Iterator[Any]:
    """Sessão em um Neo4j alcançável, com o grafo limpo antes e depois.

    O escopo do teste é o banco de testes apontado por NEO4J_URI. A limpeza é
    restrita ao label :ObjetoRoots — nunca um `MATCH (n) DETACH DELETE n` cego,
    que apagaria qualquer outra coisa que esteja no mesmo banco.
    """
    from app.database.neo4j import sessao, verifica_conectividade

    config = _config()
    if not verifica_conectividade(config):
        pytest.skip(f"Neo4j não alcançável em {config.uri} — subir com `docker compose up -d neo4j`")

    with sessao(config) as s:
        s.run(f"MATCH (n:{LABEL_SUPERCLASSE}) DETACH DELETE n")
        yield s
        s.run(f"MATCH (n:{LABEL_SUPERCLASSE}) DETACH DELETE n")


@pytest.fixture
def grafo_carregado(grafo: Any, fonte_sintetica: sqlite3.Connection) -> Any:
    """Aplica o DDL e carrega o mini-corpus da fixture no Neo4j."""
    for comando in (*CONSTRAINTS, *INDICES):
        grafo.run(comando)
    grafo.run("CALL db.awaitIndexes(120)")

    nos = le_nos(fonte_sintetica)
    for entidade in ENTIDADES:
        if nos[entidade.label]:
            grafo.execute_write(_gravador(cypher_merge_nos(entidade.label), nos[entidade.label]))

    for r in le_relacoes(fonte_sintetica):
        linha = {
            "origem_id": r["origem_id"],
            "destino_id": r["destino_id"],
            "rel_id": r["rel_id"],
            "props": _props_aresta(r),
        }
        grafo.execute_write(_gravador(cypher_merge_relacoes(r["tipo_relacao"]), [linha]))
    return grafo


# =============================================================
# DDL do grafo
# =============================================================


def test_constraints_aplicam_no_neo4j(grafo: Any) -> None:
    """Todo comando de CONSTRAINTS/INDICES é aceito pelo servidor.

    É a checagem que nenhum teste offline consegue fazer: sintaxe de Cypher e
    disponibilidade do recurso na edição em uso (Community vs Enterprise).
    """
    for comando in (*CONSTRAINTS, *INDICES):
        grafo.run(comando)
    nomes = {registro["name"] for registro in grafo.run("SHOW CONSTRAINTS YIELD name")}
    assert "objeto_roots_id_unico" in nomes
    assert "objeto_roots_uuid_unico" in nomes


def test_ddl_e_idempotente(grafo: Any) -> None:
    """Rodar o DDL duas vezes não quebra — todo comando tem IF NOT EXISTS."""
    for _ in range(2):
        for comando in (*CONSTRAINTS, *INDICES):
            grafo.run(comando)


def test_constraint_de_id_rejeita_duplicata(grafo: Any) -> None:
    """A unicidade de `id` vale sobre todo o corpus, não por label."""
    for comando in CONSTRAINTS:
        grafo.run(comando)
    grafo.run(f"CREATE (n:{LABEL_SUPERCLASSE}:Ingrediente {{id: 'ING-000001', uuid: 'u1'}})")
    with pytest.raises(neo4j.exceptions.ClientError):
        # Mesmo id, outro label: ainda assim é o mesmo objeto do corpus.
        grafo.run(f"CREATE (n:{LABEL_SUPERCLASSE}:Receita {{id: 'ING-000001', uuid: 'u2'}})")


# =============================================================
# Carga
# =============================================================


def test_nos_carregados_com_os_dois_labels(grafo_carregado: Any) -> None:
    """Cada nó carrega o label da entidade E o da superclasse."""
    n = grafo_carregado.run(
        f"MATCH (n:Ingrediente) WHERE n:{LABEL_SUPERCLASSE} RETURN count(n) AS n"
    ).single()["n"]
    assert n == 2


def test_contagem_de_nos_por_label(grafo_carregado: Any) -> None:
    esperado = {"Ingrediente": 2, "Receita": 1, "Tecnica": 1, "Povo": 1,
                "Territorio": 1, "Patrimonio": 1, "Bioma": 1, "LivroFonte": 0}
    for label, quantidade in esperado.items():
        obtido = grafo_carregado.run(f"MATCH (n:{label}) RETURN count(n) AS n").single()["n"]
        assert obtido == quantidade, label


def test_propriedades_do_dicionario_chegaram_ao_no(grafo_carregado: Any) -> None:
    """Os blocos transversais (Seções 2-9) estão no nó, não só o nome."""
    no = grafo_carregado.run(
        "MATCH (n:Ingrediente {id: 'ING-000001'}) RETURN n"
    ).single()["n"]
    assert no["nome_pt"] == "Mandioca"
    assert no["slug"] == "mandioca"
    assert no["version"] == 1
    assert no["confiabilidade"].startswith("🟢")


def test_arestas_carregadas_com_propriedades_nativas(grafo_carregado: Any) -> None:
    """peso/confiabilidade/proveniência ficam NA aresta — sem reificação.

    É a diferença concreta em relação ao RDF da Ordem 1, que precisaria de um
    nó intermediário para dizer a mesma coisa.
    """
    aresta = grafo_carregado.run(
        "MATCH (:Receita {id: 'REC-000001'})-[r:USA_INGREDIENTE]->(:Ingrediente) RETURN r"
    ).single()["r"]
    assert aresta["rel_id"] == "REL-000001"
    assert aresta["peso"] == 0.95
    assert aresta["metodo_calculo_peso"] == "det"


def test_uniao_de_domain_e_range_funciona_na_pratica(grafo_carregado: Any) -> None:
    """As duas uniões OWL geram arestas reais, nas duas pontas."""
    n = grafo_carregado.run(
        "MATCH (:Ingrediente)-[:ASSOCIADO_A_POVO]->(:Povo) RETURN count(*) AS n"
    ).single()["n"]
    assert n == 1  # domain via união: Ingrediente, não só Receita
    n = grafo_carregado.run(
        "MATCH (:Ingrediente)-[:ORIGINARIO_DE]->(:Bioma) RETURN count(*) AS n"
    ).single()["n"]
    assert n == 1  # range via união: Bioma, não só Povo


def test_auto_relacao_entre_ingredientes(grafo_carregado: Any) -> None:
    """DERIVA_DE liga dois nós do mesmo label — farinha deriva de mandioca."""
    destino = grafo_carregado.run(
        "MATCH (:Ingrediente {id: 'ING-000002'})-[:DERIVA_DE]->(d:Ingrediente) RETURN d.id AS id"
    ).single()["id"]
    assert destino == "ING-000001"


def test_carga_e_idempotente(grafo_carregado: Any, fonte_sintetica: sqlite3.Connection) -> None:
    """Recarregar não duplica nó nem aresta — MERGE, nunca CREATE.

    Importante para poder reprocessar o corpus sem derrubar o grafo antes.
    """
    antes_nos = grafo_carregado.run(
        f"MATCH (n:{LABEL_SUPERCLASSE}) RETURN count(n) AS n"
    ).single()["n"]
    antes_arestas = grafo_carregado.run("MATCH ()-[r]->() RETURN count(r) AS n").single()["n"]

    nos = le_nos(fonte_sintetica)
    for entidade in ENTIDADES:
        if nos[entidade.label]:
            grafo_carregado.execute_write(
                _gravador(cypher_merge_nos(entidade.label), nos[entidade.label])
            )
    for r in le_relacoes(fonte_sintetica):
        linha = {"origem_id": r["origem_id"], "destino_id": r["destino_id"],
                 "rel_id": r["rel_id"], "props": _props_aresta(r)}
        grafo_carregado.execute_write(_gravador(cypher_merge_relacoes(r["tipo_relacao"]), [linha]))

    depois_nos = grafo_carregado.run(
        f"MATCH (n:{LABEL_SUPERCLASSE}) RETURN count(n) AS n"
    ).single()["n"]
    depois_arestas = grafo_carregado.run("MATCH ()-[r]->() RETURN count(r) AS n").single()["n"]
    assert (depois_nos, depois_arestas) == (antes_nos, antes_arestas)


def test_travessia_multi_hop(grafo_carregado: Any) -> None:
    """A pergunta que justifica o grafo: caminho receita -> ingrediente -> povo.

    No modelo relacional da Ordem 2 isso é um JOIN encadeado sobre `relacoes`;
    aqui é uma travessia direta de 2 saltos.
    """
    povo = grafo_carregado.run(
        "MATCH (:Receita {id: 'REC-000001'})-[:USA_INGREDIENTE]->(:Ingrediente)"
        "-[:DERIVA_DE]->(:Ingrediente)-[:ASSOCIADO_A_POVO]->(p:Povo) RETURN p.nome_pt AS nome"
    ).single()["nome"]
    assert povo == "Tupinambá"


def test_fulltext_encontra_por_nome(grafo_carregado: Any) -> None:
    """O índice full-text (base da busca da Ordem 5) responde de fato."""
    resultado = grafo_carregado.run(
        "CALL db.index.fulltext.queryNodes('objeto_roots_nome_ft', 'mandioca') "
        "YIELD node RETURN node.id AS id"
    )
    assert {registro["id"] for registro in resultado} >= {"ING-000001"}
