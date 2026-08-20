"""
Testes da Ordem 3 — ETL (dry-run, sem servidor).

Exercitam o caminho inteiro do ETL menos a escrita no Neo4j: leitura do SQLite,
montagem dos lotes, validação offline e emissão do Cypher. Rodam contra o corpus
sintético da `conftest.py`, que reproduz as cardinalidades auditadas.

Cada teste "negativo" corrompe uma cópia descartável do banco de um jeito
específico e exige que o ETL PARE — a garantia que importa é que ele recusa a
carga em vez de escrever dado errado no grafo.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.models import grafo
from scripts.ordem3 import etl_neo4j


@pytest.fixture
def plano(corpus_sintetico: Path) -> etl_neo4j.PlanoDeCarga:
    conn = etl_neo4j.abre_sqlite_somente_leitura(corpus_sintetico)
    try:
        return etl_neo4j.monta_plano(conn)
    finally:
        conn.close()


# --- Caminho feliz ------------------------------------------------------------

def test_corpus_integro_nao_produz_divergencia(plano):
    assert plano.divergencias == []


def test_plano_carrega_381_nos_com_a_contagem_de_cada_catalogo(plano):
    assert plano.total_nos == grafo.TOTAL_NOS_ESPERADO == 381
    for spec in grafo.NOS:
        assert len(plano.nos_por_label[spec.label]) == spec.contagem_esperada, spec.label


def test_plano_carrega_1585_arestas_com_a_distribuicao_por_tipo(plano):
    assert plano.total_relacoes == grafo.TOTAL_RELACOES_ESPERADO == 1585
    for spec in grafo.RELACOES:
        assert len(plano.relacoes_por_tipo.get(spec.tipo, [])) == spec.instancias_esperadas


def test_livro_fonte_carrega_zero_nos(plano):
    # Dicionário v1.2, Seção 19: esquema definido, população pendente.
    # O ETL não pode inventar linha nenhuma para preencher.
    assert plano.nos_por_label["LivroFonte"] == []


def test_propriedades_nulas_sao_omitidas_e_nao_viram_string_vazia(plano):
    for item in plano.nos_por_label["Ingrediente"]:
        assert None not in item["props"].values()
        assert item["props"]["id"] == item["id"]


def test_arestas_carregam_as_propriedades_de_aresta(plano):
    aresta = plano.relacoes_por_tipo["USA_INGREDIENTE"][0]
    assert set(aresta) == {"rel_id", "origem_id", "destino_id", "props"}
    assert 0.0 <= aresta["props"]["peso"] <= 1.0
    assert set(aresta["props"]) <= set(grafo.PROPRIEDADES_ARESTA)
    # tipo_relacao é o TIPO da aresta no grafo, não uma propriedade dela.
    assert "tipo_relacao" not in aresta["props"]


def test_fonte_sqlite_e_aberta_somente_para_leitura(corpus_sintetico: Path):
    conn = etl_neo4j.abre_sqlite_somente_leitura(corpus_sintetico)
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("DELETE FROM relacoes")
    finally:
        conn.close()


def test_sqlite_ausente_falha_com_instrucao_para_rodar_a_ordem_2(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="ordem2"):
        etl_neo4j.abre_sqlite_somente_leitura(tmp_path / "nao_existe.db")


# --- Detecção de corrupção: o ETL precisa PARAR -------------------------------

def _plano_de(caminho: Path) -> etl_neo4j.PlanoDeCarga:
    conn = etl_neo4j.abre_sqlite_somente_leitura(caminho)
    try:
        return etl_neo4j.monta_plano(conn)
    finally:
        conn.close()


def _executa_sql(caminho: Path, sql: str, params: tuple = ()) -> None:
    conn = sqlite3.connect(caminho)
    try:
        conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def test_detecta_contagem_de_nos_divergente(corpus_editavel: Path):
    _executa_sql(corpus_editavel, "DELETE FROM bioma WHERE id = 'BIO-000007'")
    divergencias = _plano_de(corpus_editavel).divergencias
    assert any("nós Bioma: esperado 7, obtido 6" in d for d in divergencias)


def test_detecta_contagem_de_arestas_divergente(corpus_editavel: Path):
    _executa_sql(corpus_editavel, "DELETE FROM relacoes WHERE rel_id = 'REL-000001'")
    divergencias = _plano_de(corpus_editavel).divergencias
    assert any("USA_INGREDIENTE: esperado 895, obtido 894" in d for d in divergencias)
    assert any("total de arestas: esperado 1585" in d for d in divergencias)


def test_detecta_violacao_de_dominio_da_ontologia(corpus_editavel: Path):
    # USA_INGREDIENTE tem rdfs:domain roots:Receita — trocar a origem por um Povo
    # é exatamente o erro que o relacional NÃO conseguia barrar (FK polimórfica).
    _executa_sql(
        corpus_editavel,
        "UPDATE relacoes SET origem_id = 'POV-000001' WHERE rel_id = 'REL-000001'",
    )
    divergencias = _plano_de(corpus_editavel).divergencias
    assert any("rdfs:domain" in d and "REL-000001" in d for d in divergencias)


def test_detecta_violacao_de_imagem_da_ontologia(corpus_editavel: Path):
    # USA_INGREDIENTE tem rdfs:range roots:Ingrediente.
    _executa_sql(
        corpus_editavel,
        "UPDATE relacoes SET destino_id = 'TER-000001' WHERE rel_id = 'REL-000002'",
    )
    divergencias = _plano_de(corpus_editavel).divergencias
    assert any("rdfs:range" in d and "REL-000002" in d for d in divergencias)


def test_detecta_ponta_de_aresta_inexistente(corpus_editavel: Path):
    _executa_sql(
        corpus_editavel,
        "UPDATE relacoes SET destino_id = 'ING-999999' WHERE rel_id = 'REL-000003'",
    )
    divergencias = _plano_de(corpus_editavel).divergencias
    assert any("ING-999999 não existe" in d for d in divergencias)


def test_detecta_mudanca_no_numero_de_orfaos(corpus_editavel: Path):
    # Liga um dos 18 órfãos a uma receita: passam a ser 17.
    _executa_sql(
        corpus_editavel,
        """INSERT INTO relacoes VALUES
           ('REL-900001','REC-000001','ING-000130','USA_INGREDIENTE',NULL,NULL,NULL,
            'aresta extra de teste','2026-08-05T00:00:00Z',0.5,'teste')""",
    )
    divergencias = _plano_de(corpus_editavel).divergencias
    assert any("órfãos: esperado 18, obtido 17" in d for d in divergencias)


def test_detecta_uuid_duplicado(corpus_editavel: Path):
    _executa_sql(
        corpus_editavel,
        "UPDATE receita SET uuid = (SELECT uuid FROM ingrediente WHERE id='ING-000001') "
        "WHERE id = 'REC-000001'",
    )
    divergencias = _plano_de(corpus_editavel).divergencias
    assert any("uuid duplicado" in d for d in divergencias)


def test_detecta_peso_fora_da_faixa(corpus_editavel: Path):
    # O CHECK do SQLite barra a escrita; aqui simulamos um banco que o perdeu,
    # para provar que o ETL do grafo não depende só da constraint da origem.
    conn = sqlite3.connect(corpus_editavel)
    try:
        conn.execute("PRAGMA writable_schema = ON")
        conn.execute(
            "UPDATE sqlite_master SET sql = replace(sql, "
            "'CHECK (peso >= 0.0 AND peso <= 1.0)', '') WHERE name = 'relacoes'"
        )
        conn.commit()
    finally:
        conn.close()
    _executa_sql(corpus_editavel, "UPDATE relacoes SET peso = 1.5 WHERE rel_id = 'REL-000004'")
    divergencias = _plano_de(corpus_editavel).divergencias
    assert any("REL-000004" in d and "fora de [0.0, 1.0]" in d for d in divergencias)


def test_tipo_de_relacao_fora_do_enum_e_rejeitado(corpus_editavel: Path):
    conn = sqlite3.connect(corpus_editavel)
    try:
        conn.execute("PRAGMA writable_schema = ON")
        conn.execute(
            "UPDATE sqlite_master SET sql = replace(sql, 'CHECK (tipo_relacao IN', "
            "'CHECK (tipo_relacao NOT IN') WHERE name = 'relacoes'"
        )
        conn.commit()
    finally:
        conn.close()
    _executa_sql(corpus_editavel, "UPDATE relacoes SET tipo_relacao = 'INVENTADO' "
                                  "WHERE rel_id = 'REL-000005'")
    with pytest.raises(grafo.TipoRelacaoInvalido):
        _plano_de(corpus_editavel)


# --- CLI ----------------------------------------------------------------------

def test_dry_run_e_o_padrao_e_nao_conecta_em_nada(corpus_sintetico: Path, capsys, monkeypatch):
    def nunca(*_args, **_kwargs):  # pragma: no cover - só dispara se o dry-run regredir
        raise AssertionError("dry-run tentou abrir conexão com o Neo4j")

    monkeypatch.setattr("app.database.neo4j.cria_driver", nunca)
    codigo = etl_neo4j.main(["--sqlite", str(corpus_sintetico)])
    saida = capsys.readouterr().out

    assert codigo == 0
    assert "DRY-RUN" in saida
    assert "nada foi enviado ao Neo4j" in saida
    assert "sem divergências" in saida


def test_dry_run_sai_com_erro_quando_ha_divergencia(corpus_editavel: Path, capsys):
    _executa_sql(corpus_editavel, "DELETE FROM relacoes WHERE rel_id = 'REL-000001'")
    codigo = etl_neo4j.main(["--sqlite", str(corpus_editavel)])
    saida = capsys.readouterr().out

    assert codigo == 1
    assert "DIVERGÊNCIA DETECTADA" in saida
    assert "Nenhum dado foi enviado ao Neo4j" in saida


def test_limpar_sem_executar_nao_faz_nada(corpus_sintetico: Path, capsys):
    codigo = etl_neo4j.main(["--sqlite", str(corpus_sintetico), "--limpar"])
    assert codigo == 2
    assert "Nada foi feito" in capsys.readouterr().out


def test_emitir_cypher_produz_arquivo_revisavel(corpus_sintetico: Path, tmp_path: Path, capsys):
    destino = tmp_path / "carga.cypher"
    codigo = etl_neo4j.main([
        "--sqlite", str(corpus_sintetico), "--emitir-cypher", str(destino), "--tamanho-lote", "200",
    ])
    capsys.readouterr()

    assert codigo == 0
    conteudo = destino.read_text(encoding="utf-8")
    assert "CREATE CONSTRAINT roots_objetoroots_id_unico" in conteudo
    assert "MERGE (n:Ingrediente {id: linha.id})" in conteudo
    for spec in grafo.RELACOES:
        if spec.instancias_esperadas:
            assert f"[r:{spec.tipo} " in conteudo
        else:
            assert f"// {spec.tipo}: 0 instâncias" in conteudo


def test_emitir_schema_regrava_o_ddl(tmp_path: Path, capsys):
    destino = tmp_path / "ddl_neo4j.cypher"
    codigo = etl_neo4j.main(["--emitir-schema", str(destino)])
    capsys.readouterr()
    assert codigo == 0
    assert destino.read_text(encoding="utf-8") == grafo.cypher_schema()


def test_literais_cypher_escapam_aspas_e_quebras_de_linha():
    assert etl_neo4j._literal_cypher("d'água") == "'d\\'água'"
    assert etl_neo4j._literal_cypher("linha\nquebrada") == "'linha\\nquebrada'"
    assert etl_neo4j._literal_cypher(None) == "null"
    assert etl_neo4j._literal_cypher(0.95) == "0.95"
