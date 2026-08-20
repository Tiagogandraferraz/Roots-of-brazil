"""
Testes da Ordem 3 — modelo de grafo.

Rodam sem servidor, sem rede e sem o driver instalado: `app/models/grafo.py` é
um módulo de dados puro. O que se valida aqui é a fidelidade do modelo às suas
duas fontes (a ontologia da Ordem 1 e o baseline auditado do Sprint 2).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.models import grafo

RAIZ = Path(__file__).resolve().parents[2]
ONTOLOGIA = (RAIZ / "schemas" / "ontologia.ttl").read_text(encoding="utf-8")
DDL_NEO4J = RAIZ / "schemas" / "ddl_neo4j.cypher"


# --- Fidelidade à ontologia (schemas/ontologia.ttl, Ordem 1) ------------------

def test_labels_sao_exatamente_as_8_classes_owl():
    classes_owl = set(re.findall(r"roots:(\w+) a owl:Class", ONTOLOGIA))
    classes_owl.discard("ObjetoRoots")  # superclasse, vira label transversal
    assert set(grafo.LABELS) == classes_owl


def test_tipos_de_relacao_sao_exatamente_as_12_object_properties():
    propriedades = set(re.findall(r"roots:(\w+) a owl:ObjectProperty", ONTOLOGIA))
    assert set(grafo.TIPOS_RELACAO) == propriedades
    assert len(grafo.TIPOS_RELACAO) == 12


def test_label_transversal_corresponde_a_superclasse_da_ontologia():
    assert "roots:ObjetoRoots a owl:Class" in ONTOLOGIA
    assert grafo.LABEL_OBJETO_ROOTS == "ObjetoRoots"


def test_pontas_de_cada_relacao_usam_apenas_labels_conhecidos():
    for spec in grafo.RELACOES:
        assert spec.origem, f"{spec.tipo} sem domain"
        assert spec.destino, f"{spec.tipo} sem range"
        assert set(spec.origem) <= set(grafo.LABELS), spec.tipo
        assert set(spec.destino) <= set(grafo.LABELS), spec.tipo


def test_relacoes_de_uniao_refletem_o_owl_unionof_da_ontologia():
    # ASSOCIADO_A_POVO: domain é owl:unionOf(Receita, Ingrediente)
    assert set(grafo.RELACAO_POR_TIPO["ASSOCIADO_A_POVO"].origem) == {"Receita", "Ingrediente"}
    # ORIGINARIO_DE: range é owl:unionOf(Povo, Bioma)
    assert set(grafo.RELACAO_POR_TIPO["ORIGINARIO_DE"].destino) == {"Povo", "Bioma"}


def test_tipos_reservados_tem_zero_instancias():
    reservados = [spec for spec in grafo.RELACOES if spec.reservado]
    assert {spec.tipo for spec in reservados} == {"VARIANTE_REGIONAL", "SIMILAR_A"}
    assert all(spec.instancias_esperadas == 0 for spec in reservados)


# --- Fidelidade ao baseline auditado (Sprint 2) -------------------------------

def test_contagens_batem_com_a_auditoria_do_sprint_2():
    esperado = {"Ingrediente": 130, "Receita": 136, "Tecnica": 38, "Povo": 17,
                "Territorio": 18, "Patrimonio": 35, "Bioma": 7, "LivroFonte": 0}
    assert {spec.label: spec.contagem_esperada for spec in grafo.NOS} == esperado
    assert grafo.TOTAL_NOS_ESPERADO == 381


def test_distribuicao_de_arestas_bate_com_mv_grafo_agregado_da_ordem_2():
    # Mesmos números conferidos em tests/ordem2/test_etl.py::test_mv_grafo_agregado...
    esperado = {"USA_INGREDIENTE": 895, "ASSOCIADO_A_POVO": 205, "CULTIVADO_EM": 106,
                "UTILIZA_TECNICA": 85, "PREPARADO_COM": 81, "OCORRE_EM": 77,
                "ORIGINARIO_DE": 67, "PATRIMONIO_DE": 38, "LOCALIZADO_EM_BIOMA": 24,
                "DERIVA_DE": 7}
    obtido = {spec.tipo: spec.instancias_esperadas
              for spec in grafo.RELACOES if not spec.reservado}
    assert obtido == esperado
    assert grafo.TOTAL_RELACOES_ESPERADO == 1585
    assert grafo.TOTAL_ORFAOS_ESPERADO == 18


def test_prefixos_de_id_seguem_a_politica_de_identificadores():
    assert grafo.label_para_id("ING-000001") == "Ingrediente"
    assert grafo.label_para_id("LIV-000001") == "LivroFonte"
    with pytest.raises(grafo.PrefixoIdInvalido):
        grafo.label_para_id("XXX-000001")
    with pytest.raises(grafo.PrefixoIdInvalido):
        grafo.label_para_id("sem-prefixo")


# --- Geração de Cypher --------------------------------------------------------

def test_todo_label_tem_constraint_de_unicidade():
    ddl = "\n".join(grafo.cypher_constraints())
    for label in grafo.LABELS:
        assert f"FOR (n:{label}) REQUIRE n.id IS UNIQUE" in ddl
    # Equivalente em grafo da view objeto_universal do SQLite.
    assert f"FOR (n:{grafo.LABEL_OBJETO_ROOTS}) REQUIRE n.id IS UNIQUE" in ddl
    assert f"FOR (n:{grafo.LABEL_OBJETO_ROOTS}) REQUIRE n.uuid IS UNIQUE" in ddl


def test_indices_da_secao_24_estao_presentes():
    ddl = "\n".join(grafo.cypher_indices())
    assert "FOR (n:Ingrediente) ON (n.categoria)" in ddl
    assert "FOR (n:Ingrediente) ON (n.classe)" in ddl
    assert "FOR (n:Receita) ON (n.categoria)" in ddl
    for spec in grafo.RELACOES:
        assert f"FOR ()-[r:{spec.tipo}]-() ON (r.rel_id)" in ddl


def test_merge_de_no_aplica_o_label_transversal():
    cypher = grafo.cypher_merge_nos("Ingrediente")
    assert "MERGE (n:Ingrediente {id: linha.id})" in cypher
    assert f"SET n:{grafo.LABEL_OBJETO_ROOTS}" in cypher
    # MERGE, não CREATE: recarregar não pode duplicar.
    assert "CREATE (" not in cypher


def test_merge_de_aresta_casa_as_pontas_polimorficamente():
    cypher = grafo.cypher_merge_relacoes("USA_INGREDIENTE")
    assert f"MATCH (origem:{grafo.LABEL_OBJETO_ROOTS} {{id: linha.origem_id}})" in cypher
    assert f"MATCH (destino:{grafo.LABEL_OBJETO_ROOTS} {{id: linha.destino_id}})" in cypher
    assert "MERGE (origem)-[r:USA_INGREDIENTE {rel_id: linha.rel_id}]->(destino)" in cypher


@pytest.mark.parametrize("label", list(grafo.LABELS))
def test_merge_de_no_gera_cypher_para_todo_label(label):
    assert f"MERGE (n:{label} " in grafo.cypher_merge_nos(label)


@pytest.mark.parametrize("tipo", list(grafo.TIPOS_RELACAO))
def test_merge_de_aresta_gera_cypher_para_todo_tipo(tipo):
    assert f"[r:{tipo} " in grafo.cypher_merge_relacoes(tipo)


# --- Guardas de segurança -----------------------------------------------------

def test_tipo_de_aresta_passa_por_whitelist_e_nao_por_escaping():
    # O tipo é interpolado literalmente no Cypher (o Neo4j 5 não o parametriza),
    # então a whitelist é a única barreira — precisa rejeitar antes de gerar texto.
    injecao = "USA_INGREDIENTE]->() DETACH DELETE n //"
    with pytest.raises(grafo.TipoRelacaoInvalido):
        grafo.valida_tipo_relacao(injecao)
    with pytest.raises(grafo.TipoRelacaoInvalido):
        grafo.cypher_merge_relacoes(injecao)
    with pytest.raises(grafo.TipoRelacaoInvalido):
        grafo.cypher_viola_dominio_imagem(injecao)


def test_label_desconhecido_e_rejeitado():
    with pytest.raises(ValueError):
        grafo.cypher_merge_nos("Ingrediente) DETACH DELETE n //")


def test_limpeza_atinge_apenas_o_subgrafo_do_roots():
    cypher = grafo.cypher_limpa_grafo()
    assert f":{grafo.LABEL_OBJETO_ROOTS}" in cypher
    assert "MATCH (n) DETACH DELETE n" not in cypher


# --- Sincronia com o arquivo versionado ---------------------------------------

def test_ddl_neo4j_esta_sincronizado_com_o_gerador():
    assert DDL_NEO4J.exists(), (
        "schemas/ddl_neo4j.cypher não existe. Gere com: "
        "python -m scripts.ordem3.etl_neo4j --emitir-schema schemas/ddl_neo4j.cypher"
    )
    assert DDL_NEO4J.read_text(encoding="utf-8") == grafo.cypher_schema(), (
        "schemas/ddl_neo4j.cypher divergiu de app/models/grafo.py. Regere com: "
        "python -m scripts.ordem3.etl_neo4j --emitir-schema schemas/ddl_neo4j.cypher"
    )


def test_ddl_neo4j_nao_usa_recurso_exclusivo_do_enterprise():
    # O docker-compose sobe `neo4j:5` (Community). Constraints de existência,
    # NODE KEY e unicidade de relacionamento não existem lá — se aparecerem no
    # DDL, `docker compose up` sobe mas a carga quebra.
    ddl = DDL_NEO4J.read_text(encoding="utf-8")
    for recurso in ("IS NOT NULL", "IS NODE KEY", "IS RELATIONSHIP KEY", "IS UNIQUE\nFOR ()-["):
        assert recurso not in ddl, f"recurso Enterprise no DDL: {recurso}"
