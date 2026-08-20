"""
Testes da Ordem 3 — carga real contra um servidor Neo4j.

PULADOS por padrão. Só rodam quando existe um Neo4j alcançável E o teste é
autorizado explicitamente:

    export NEO4J_URI=bolt://localhost:7687
    export NEO4J_USER=neo4j
    export NEO4J_PASSWORD=...
    export NEO4J_DATABASE=roots_teste     # NUNCA o banco de produção
    export ROOTS_TESTE_NEO4J=1
    pytest tests/ordem3/test_carga_neo4j.py

O guarda `ROOTS_TESTE_NEO4J` é deliberado: estes testes ESCREVEM e APAGAM nós
`:ObjetoRoots`. Não podem disparar por acidente só porque alguém tinha um Neo4j
rodando e as variáveis do docker-compose no ambiente.

O dado carregado é o corpus SINTÉTICO da `conftest.py`, nunca o corpus real.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.models import grafo
from scripts.ordem3 import etl_neo4j

pytest.importorskip("neo4j", reason="driver neo4j não instalado")

from app.database.neo4j import (  # noqa: E402
    ConfiguracaoNeo4jAusente,
    carrega_config,
    escalar,
    sessao,
    verifica_conectividade,
)

AUTORIZADO = os.getenv("ROOTS_TESTE_NEO4J") == "1"


def _config_ou_skip():
    if not AUTORIZADO:
        pytest.skip("defina ROOTS_TESTE_NEO4J=1 para autorizar escrita em um Neo4j de teste")
    try:
        config = carrega_config()
    except ConfiguracaoNeo4jAusente as exc:
        pytest.skip(str(exc))
    if config.database in {"neo4j", ""}:
        pytest.skip("aponte NEO4J_DATABASE para um banco de teste, não para o default 'neo4j'")
    if not verifica_conectividade(config):
        pytest.skip(f"nenhum Neo4j alcançável em {config.uri}")
    return config


@pytest.fixture(scope="module")
def grafo_carregado(corpus_sintetico: Path):
    """Carrega o corpus sintético num banco de teste e limpa no teardown."""
    config = _config_ou_skip()

    conn = etl_neo4j.abre_sqlite_somente_leitura(corpus_sintetico)
    try:
        plano = etl_neo4j.monta_plano(conn)
    finally:
        conn.close()
    assert plano.divergencias == [], plano.divergencias

    with sessao(config) as ses:
        ses.run(grafo.cypher_limpa_grafo())
        etl_neo4j.aplica_schema(ses)
        etl_neo4j.carrega(ses, plano, tamanho_lote=500)

    try:
        yield config
    finally:
        with sessao(config) as ses:
            ses.run(grafo.cypher_limpa_grafo())


def test_validacao_pos_carga_nao_acusa_divergencia(grafo_carregado):
    with sessao(grafo_carregado) as ses:
        assert etl_neo4j.valida_pos_carga(ses) == []


def test_total_de_nos_e_381(grafo_carregado):
    with sessao(grafo_carregado) as ses:
        total = escalar(ses, f"MATCH (n:{grafo.LABEL_OBJETO_ROOTS}) RETURN count(n)")
    assert total == grafo.TOTAL_NOS_ESPERADO


def test_contagem_por_label(grafo_carregado):
    with sessao(grafo_carregado) as ses:
        obtido = {r["label"]: r["n"] for r in
                  ses.run(grafo.cypher_conta_nos_por_label(), labels=list(grafo.LABELS))}
    for spec in grafo.NOS:
        assert obtido.get(spec.label, 0) == spec.contagem_esperada, spec.label


def test_contagem_por_tipo_de_aresta(grafo_carregado):
    with sessao(grafo_carregado) as ses:
        obtido = {r["tipo"]: r["n"] for r in
                  ses.run(grafo.cypher_conta_relacoes_por_tipo(), tipos=list(grafo.TIPOS_RELACAO))}
    for spec in grafo.RELACOES:
        assert obtido.get(spec.tipo, 0) == spec.instancias_esperadas, spec.tipo
    assert sum(obtido.values()) == grafo.TOTAL_RELACOES_ESPERADO


def test_orfaos_sao_18(grafo_carregado):
    with sessao(grafo_carregado) as ses:
        assert escalar(ses, grafo.cypher_conta_orfaos()) == grafo.TOTAL_ORFAOS_ESPERADO


def test_todo_no_tem_o_label_transversal_e_um_label_de_entidade(grafo_carregado):
    with sessao(grafo_carregado) as ses:
        fora = escalar(
            ses,
            f"MATCH (n:{grafo.LABEL_OBJETO_ROOTS}) "
            "WHERE size([l IN labels(n) WHERE l IN $labels]) <> 1 RETURN count(n)",
            labels=list(grafo.LABELS),
        )
    assert fora == 0


@pytest.mark.parametrize("tipo", [spec.tipo for spec in grafo.RELACOES])
def test_arestas_respeitam_dominio_e_imagem_da_ontologia(grafo_carregado, tipo):
    with sessao(grafo_carregado) as ses:
        assert escalar(ses, grafo.cypher_viola_dominio_imagem(tipo)) == 0


def test_rel_ids_sao_unicos(grafo_carregado):
    with sessao(grafo_carregado) as ses:
        duplicados = escalar(ses, grafo.cypher_rel_ids_duplicados(),
                             tipos=list(grafo.TIPOS_RELACAO))
    assert duplicados == 0


def test_pesos_estao_na_faixa_do_dicionario(grafo_carregado):
    with sessao(grafo_carregado) as ses:
        assert escalar(ses, grafo.cypher_peso_fora_da_faixa(),
                       tipos=list(grafo.TIPOS_RELACAO)) == 0


def test_constraint_de_unicidade_rejeita_id_repetido(grafo_carregado):
    from neo4j.exceptions import ClientError

    with sessao(grafo_carregado) as ses, pytest.raises(ClientError):
        ses.run(f"CREATE (n:Ingrediente:{grafo.LABEL_OBJETO_ROOTS} "
                "{id: 'ING-000001', uuid: 'colisao-de-teste'})").consume()


def test_recarga_e_idempotente(grafo_carregado, corpus_sintetico: Path):
    """MERGE, não CREATE: rodar o ETL duas vezes não pode duplicar nada."""
    conn = etl_neo4j.abre_sqlite_somente_leitura(corpus_sintetico)
    try:
        plano = etl_neo4j.monta_plano(conn)
    finally:
        conn.close()

    with sessao(grafo_carregado) as ses:
        etl_neo4j.carrega(ses, plano, tamanho_lote=500)
        assert etl_neo4j.valida_pos_carga(ses) == []


def test_travessia_de_dois_saltos_funciona(grafo_carregado):
    """A consulta que justifica a Ordem 3: receita → ingrediente → povo em um MATCH.

    No relacional isso exige dois JOINs contra a tabela plana `relacoes` com FK
    polimórfica; aqui é uma travessia direta.
    """
    with sessao(grafo_carregado) as ses:
        n = escalar(
            ses,
            "MATCH (:Receita)-[:USA_INGREDIENTE]->(:Ingrediente)-[:ORIGINARIO_DE]->(p:Povo) "
            "RETURN count(DISTINCT p)",
        )
    assert n > 0
