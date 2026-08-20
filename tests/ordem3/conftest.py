"""Fixtures da Ordem 3.

`fonte_sintetica` monta um SQLite com o DDL real da Ordem 2 e um punhado de
linhas coerentes. Serve para exercitar o ETL (leitura, validação, geração de
Cypher) sem depender do Corpus_Fundador_v1.1.xlsx nem de um Neo4j no ar — o
banco de verdade (381 objetos / 1.585 relações) é validado pelos testes de
integração, que se pulam sozinhos quando o Neo4j não está disponível.
"""

from __future__ import annotations

import sqlite3
import sys
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

DDL = RAIZ / "schemas" / "ddl_sqlite.sql"
TS = "2026-08-05T00:00:00Z"
CONF = "🟢 Confirmado em várias fontes"


def le_ddl() -> str:
    """Lê o DDL da Ordem 2.

    Remove cercas markdown (```sql / ```) se houver: parte dos arquivos do
    repositório foi commitada com a cerca de bloco de código junto. Enquanto
    isso não é corrigido, ler o DDL exige tolerá-la.
    """
    linhas = DDL.read_text(encoding="utf-8").splitlines()
    if linhas and linhas[0].startswith("```"):
        linhas = linhas[1:]
    if linhas and linhas[-1].strip() == "```":
        linhas = linhas[:-1]
    return "\n".join(linhas)


@pytest.fixture
def banco_vazio(tmp_path: Path) -> Path:
    """Caminho de um SQLite com o schema da Ordem 2 e nenhuma linha.

    Usado pelos testes de CLI: é um banco legítimo (as tabelas existem), mas
    diverge do baseline — exatamente o cenário que o dry-run deve reportar.
    """
    caminho = tmp_path / "vazio.db"
    conn = sqlite3.connect(caminho)
    conn.executescript(le_ddl())
    conn.commit()
    conn.close()
    return caminho


@pytest.fixture
def fonte_sintetica(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """SQLite com o schema real da Ordem 2 e um mini-corpus consistente.

    2 ingredientes, 1 receita, 1 técnica, 1 povo, 1 território, 1 patrimônio,
    1 bioma — e 4 arestas cobrindo os casos interessantes: relação simples,
    domain com união (ASSOCIADO_A_POVO), range com união (ORIGINARIO_DE) e
    auto-relação entre nós do mesmo label (DERIVA_DE).
    """
    caminho = tmp_path / "sintetico.db"
    conn = sqlite3.connect(caminho)
    conn.row_factory = sqlite3.Row
    conn.executescript(le_ddl())

    def u() -> str:
        return str(uuid.uuid4())

    conn.executemany(
        "INSERT INTO ingrediente (id, uuid, slug, created_at, updated_at, version, "
        "nome_principal, categoria, subcategoria, classe, confiabilidade, nome_pt) "
        "VALUES (?,?,?,?,?,1,?,?,?,?,?,?)",
        [
            ("ING-000001", u(), "mandioca", TS, TS, "Mandioca", "Raiz", "Tubérculo",
             "Vegetal", CONF, "Mandioca"),
            ("ING-000002", u(), "farinha-de-mandioca", TS, TS, "Farinha de mandioca", "Farináceo",
             "Derivado", "Processado/Outro", CONF, "Farinha de mandioca"),
        ],
    )
    conn.execute(
        "INSERT INTO receita (id, uuid, slug, created_at, updated_at, version, nome, "
        "categoria, subcategoria, estado, regiao, livros_fonte, confiabilidade, nome_pt) "
        "VALUES (?,?,?,?,?,1,?,?,?,?,?,?,?,?)",
        ("REC-000001", u(), "tapioca", TS, TS, "Tapioca", "Prato", "Salgado",
         "Pará", "Norte", "Fonte X", CONF, "Tapioca"),
    )
    conn.execute(
        "INSERT INTO tecnica (id, uuid, slug, created_at, updated_at, version, nome, descricao, "
        "livros_fonte, confiabilidade, categoria, subcategoria, classe, nome_pt, descricao_pt) "
        "VALUES (?,?,?,?,?,1,?,?,?,?,?,?,?,?,?)",
        ("TEC-000001", u(), "torrar", TS, TS, "Torrar", "Aquecer em superfície seca",
         "Fonte X", CONF, "Térmica", "Seca", "Processo", "Torrar", "Aquecer em superfície seca"),
    )
    conn.execute(
        "INSERT INTO povo (id, uuid, slug, created_at, updated_at, version, povo, regiao, "
        "livros_fonte, confiabilidade, categoria, subcategoria, classe, nome_pt) "
        "VALUES (?,?,?,?,?,1,?,?,?,?,?,?,?,?)",
        ("POV-000001", u(), "tupinamba", TS, TS, "Tupinambá", "Litoral", "Fonte X", CONF,
         "Indígena", "Tupi", "Povo originário", "Tupinambá"),
    )
    conn.execute(
        "INSERT INTO territorio (id, uuid, slug, created_at, updated_at, version, estado, "
        "livros_fonte, confiabilidade, categoria, subcategoria, classe, nome_pt) "
        "VALUES (?,?,?,?,?,1,?,?,?,?,?,?,?)",
        ("TER-000001", u(), "para", TS, TS, "Pará", "Fonte X", CONF,
         "Estado", "Norte", "Unidade federativa", "Pará"),
    )
    conn.execute(
        "INSERT INTO patrimonio (id, uuid, slug, created_at, updated_at, version, categoria, "
        "elemento, descricao, livros_fonte, confiabilidade, subcategoria, classe, "
        "nome_pt, descricao_pt) VALUES (?,?,?,?,?,1,?,?,?,?,?,?,?,?,?)",
        ("PAT-000001", u(), "casa-de-farinha", TS, TS, "Saber-fazer", "Casa de farinha",
         "Espaço coletivo de produção de farinha", "Fonte X", CONF, "Ofício",
         "Patrimônio imaterial", "Casa de farinha", "Espaço coletivo de produção de farinha"),
    )
    conn.execute(
        "INSERT INTO bioma (id, uuid, slug, created_at, updated_at, version, nome, descricao, "
        "fonte, oficial_ibge, nome_pt, descricao_pt) VALUES (?,?,?,?,?,1,?,?,?,1,?,?)",
        ("BIO-000001", u(), "amazonia", TS, TS, "Amazônia", "Floresta tropical",
         "IBGE", "Amazônia", "Floresta tropical"),
    )

    conn.executemany(
        "INSERT INTO relacoes (rel_id, origem_id, destino_id, tipo_relacao, confiabilidade, "
        "observacoes, data_criacao, peso, metodo_calculo_peso) VALUES (?,?,?,?,?,?,?,?,?)",
        [
            # Receita -> Ingrediente: caso simples.
            ("REL-000001", "REC-000001", "ING-000002", "USA_INGREDIENTE", CONF, "-", TS, 0.95, "det"),
            # Ingrediente -> Povo: domain com owl:unionOf (Receita ou Ingrediente).
            ("REL-000002", "ING-000001", "POV-000001", "ASSOCIADO_A_POVO", CONF, "-", TS, 0.95, "det"),
            # Ingrediente -> Bioma: range com owl:unionOf (Povo ou Bioma).
            ("REL-000003", "ING-000001", "BIO-000001", "ORIGINARIO_DE", CONF, "-", TS, 0.95, "det"),
            # Ingrediente -> Ingrediente: auto-relação.
            ("REL-000004", "ING-000002", "ING-000001", "DERIVA_DE", CONF, "-", TS, 0.95, "det"),
        ],
    )
    conn.commit()
    yield conn
    conn.close()
