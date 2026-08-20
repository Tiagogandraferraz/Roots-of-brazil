"""Testes da Ordem 2 — validam o banco SQLite carregado pelo ETL contra o baseline
do Relatório de Auditoria Sprint 2 (381 objetos, 1.585 relações, 18 órfãos, 0 duplicidades)."""
import sqlite3
from pathlib import Path

import pytest

DB_PATH = Path(__file__).resolve().parents[2] / "roots_of_brazil_dev.db"


@pytest.fixture
def conn():
    if not DB_PATH.exists():
        pytest.skip("Banco não gerado — rodar scripts/ordem2/etl.py primeiro")
    c = sqlite3.connect(DB_PATH)
    yield c
    c.close()


def test_contagem_por_catalogo(conn):
    esperado = {"ingrediente": 130, "receita": 136, "tecnica": 38, "povo": 17,
                "territorio": 18, "patrimonio": 35, "bioma": 7, "livro_fonte": 0}
    for tabela, n in esperado.items():
        assert conn.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0] == n


def test_total_relacoes(conn):
    assert conn.execute("SELECT COUNT(*) FROM relacoes").fetchone()[0] == 1585


def test_uuids_unicos(conn):
    n = conn.execute("""
        SELECT COUNT(DISTINCT uuid) FROM (
          SELECT uuid FROM ingrediente UNION ALL SELECT uuid FROM receita UNION ALL SELECT uuid FROM tecnica
          UNION ALL SELECT uuid FROM povo UNION ALL SELECT uuid FROM territorio UNION ALL SELECT uuid FROM patrimonio
          UNION ALL SELECT uuid FROM bioma)
    """).fetchone()[0]
    assert n == 381


def test_zero_fk_orfas(conn):
    n = conn.execute("""
        SELECT COUNT(*) FROM relacoes
        WHERE origem_id NOT IN (SELECT id FROM objeto_universal)
           OR destino_id NOT IN (SELECT id FROM objeto_universal)
    """).fetchone()[0]
    assert n == 0


def test_objetos_orfaos_18(conn):
    n = conn.execute("""
        SELECT COUNT(*) FROM objeto_universal
        WHERE id NOT IN (SELECT origem_id FROM relacoes UNION SELECT destino_id FROM relacoes)
    """).fetchone()[0]
    assert n == 18


def test_check_peso_rejeita_fora_de_faixa(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO relacoes VALUES ('REL-X','ING-000001','ING-000002','DERIVA_DE',NULL,NULL,NULL,'t','2026-01-01', 1.5, 't')"
        )


def test_mv_grafo_agregado_bate_com_auditoria(conn):
    esperado = {"USA_INGREDIENTE": 895, "ASSOCIADO_A_POVO": 205, "CULTIVADO_EM": 106,
                "UTILIZA_TECNICA": 85, "PREPARADO_COM": 81, "OCORRE_EM": 77,
                "ORIGINARIO_DE": 67, "PATRIMONIO_DE": 38, "LOCALIZADO_EM_BIOMA": 24, "DERIVA_DE": 7}
    obtido = dict(conn.execute("SELECT tipo_relacao, n_instancias FROM mv_grafo_agregado").fetchall())
    assert obtido == esperado
