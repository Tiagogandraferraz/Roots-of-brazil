"""Testes do ETL da Ordem 3 — leitura, validação e geração de Cypher.

Rodam offline contra a fixture `fonte_sintetica` (SQLite com o DDL real da
Ordem 2). Nenhum destes testes abre conexão com o Neo4j: o objetivo é provar
que o modo dry-run detecta problemas ANTES de qualquer escrita.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from app.models.grafo import LABEL_SUPERCLASSE  # noqa: E402
from scripts.ordem3.etl_neo4j import (  # noqa: E402
    cypher_merge_nos,
    cypher_merge_relacoes,
    le_nos,
    le_relacoes,
    lotes,
    main,
    monta_plano,
)

TS = "2026-08-05T00:00:00Z"
CONF = "🟢 Confirmado em várias fontes"


# =============================================================
# Leitura da fonte
# =============================================================


def test_le_nos_cobre_os_oito_labels(fonte_sintetica: sqlite3.Connection) -> None:
    nos = le_nos(fonte_sintetica)
    assert set(nos) == {"Ingrediente", "Receita", "Tecnica", "Povo",
                        "Territorio", "Patrimonio", "Bioma", "LivroFonte"}
    assert len(nos["Ingrediente"]) == 2
    assert nos["LivroFonte"] == []  # 0 instâncias na v1.2, nenhum nó inventado


def test_le_nos_descarta_nulos(fonte_sintetica: sqlite3.Connection) -> None:
    """Coluna NULL na fonte não vira propriedade vazia no grafo."""
    ingrediente = le_nos(fonte_sintetica)["Ingrediente"][0]
    assert "nome_en" not in ingrediente  # NULL na fixture
    assert ingrediente["nome_pt"] == "Mandioca"


def test_le_nos_carrega_todas_as_colunas_do_dicionario(
    fonte_sintetica: sqlite3.Connection,
) -> None:
    """Os blocos transversais (Seções 2-9) chegam ao nó, não só o nome."""
    ingrediente = le_nos(fonte_sintetica)["Ingrediente"][0]
    for campo in ("id", "uuid", "slug", "created_at", "updated_at", "version",
                  "categoria", "subcategoria", "classe", "confiabilidade", "nome_pt"):
        assert campo in ingrediente, campo


def test_le_relacoes_traz_propriedades_de_aresta(fonte_sintetica: sqlite3.Connection) -> None:
    relacoes = le_relacoes(fonte_sintetica)
    assert len(relacoes) == 4
    primeira = relacoes[0]
    assert primeira["peso"] == 0.95
    assert primeira["metodo_calculo_peso"] == "det"


# =============================================================
# Validação — o plano detecta divergência antes de escrever
# =============================================================


def _divergencias(conn: sqlite3.Connection) -> str:
    return " | ".join(monta_plano(conn).divergencias)


def test_arestas_da_fixture_respeitam_domain_e_range(
    fonte_sintetica: sqlite3.Connection,
) -> None:
    """As 4 arestas da fixture são ontologicamente válidas — nada de violação."""
    assert "violando domain/range" not in _divergencias(fonte_sintetica)


def test_aresta_com_domain_errado_e_reportada(fonte_sintetica: sqlite3.Connection) -> None:
    """Povo -> Ingrediente em USA_INGREDIENTE viola o rdfs:domain (Receita)."""
    fonte_sintetica.execute(
        "INSERT INTO relacoes (rel_id, origem_id, destino_id, tipo_relacao, confiabilidade, "
        "observacoes, data_criacao, peso, metodo_calculo_peso) VALUES (?,?,?,?,?,?,?,?,?)",
        ("REL-000099", "POV-000001", "ING-000001", "USA_INGREDIENTE", CONF, "-", TS, 0.5, "det"),
    )
    assert "violando domain/range" in _divergencias(fonte_sintetica)


def test_aresta_orfa_e_reportada(fonte_sintetica: sqlite3.Connection) -> None:
    """Ponta apontando para ID inexistente é a FK polimórfica quebrando."""
    fonte_sintetica.execute(
        "INSERT INTO relacoes (rel_id, origem_id, destino_id, tipo_relacao, confiabilidade, "
        "observacoes, data_criacao, peso, metodo_calculo_peso) VALUES (?,?,?,?,?,?,?,?,?)",
        ("REL-000098", "REC-000001", "ING-999999", "USA_INGREDIENTE", CONF, "-", TS, 0.5, "det"),
    )
    assert "apontando para ID inexistente" in _divergencias(fonte_sintetica)


def test_contagens_da_fixture_divergem_do_baseline(
    fonte_sintetica: sqlite3.Connection,
) -> None:
    """A fixture é um mini-corpus: o plano tem que acusar isso, não deixar passar.

    É a garantia de que a checagem de baseline está de fato ligada — se ela
    silenciasse aqui, silenciaria também numa carga real incompleta.
    """
    plano = monta_plano(fonte_sintetica)
    assert not plano.valido
    texto = " | ".join(plano.divergencias)
    assert "total de nós — esperado 381" in texto
    assert "total de arestas — esperado 1585" in texto


def test_fonte_no_baseline_passa_sem_divergencia(
    fonte_forma_baseline: sqlite3.Connection,
) -> None:
    """Uma fonte na forma do baseline é APROVADA — o caminho de sucesso.

    Contraparte necessária dos testes acima: eles provam que a validação pega
    erros; este prova que ela não reprova dado correto. Sem ele, um bug que
    reprovasse tudo passaria despercebido, já que todos os outros testes
    esperam divergência.
    """
    plano = monta_plano(fonte_forma_baseline)
    assert plano.divergencias == []
    assert plano.valido
    assert plano.total_nos == 381
    assert sum(plano.contagem_por_tipo.values()) == 1585


def test_unioes_owl_quebradas_nas_duas_pontas(
    fonte_forma_baseline: sqlite3.Connection,
) -> None:
    """As relações com owl:unionOf somam certo vindo de labels diferentes.

    ASSOCIADO_A_POVO = 134 de Receita + 71 de Ingrediente; ORIGINARIO_DE =
    39 para Povo + 28 para Bioma. Se o modelo tivesse achatado qualquer uma
    das uniões para um único label, o total bateria mas metade das arestas
    seria recusada por domain/range.
    """
    plano = monta_plano(fonte_forma_baseline)
    assert plano.contagem_por_tipo["ASSOCIADO_A_POVO"] == 205
    assert plano.contagem_por_tipo["ORIGINARIO_DE"] == 67
    assert "violando domain/range" not in " | ".join(plano.divergencias)


def test_cli_dry_run_aprova_fonte_correta(
    fonte_forma_baseline: sqlite3.Connection,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Ponta a ponta pela CLI: fonte correta -> código 0 e 'Pronto para --execute'."""
    caminho = fonte_forma_baseline.execute("PRAGMA database_list").fetchone()["file"]
    codigo = main(["--db", caminho])
    saida = capsys.readouterr().out
    assert codigo == 0
    assert "nenhuma divergência" in saida
    assert "Pronto para `--execute`" in saida
    assert "DRY-RUN: nada foi escrito" in saida


def test_uuid_duplicado_e_reportado(fonte_sintetica: sqlite3.Connection) -> None:
    """Colisão de UUID entre catálogos diferentes (o UNIQUE por tabela não pega)."""
    uuid_existente = fonte_sintetica.execute(
        "SELECT uuid FROM ingrediente LIMIT 1"
    ).fetchone()["uuid"]
    fonte_sintetica.execute("UPDATE receita SET uuid = ?", (uuid_existente,))
    assert "UUIDs duplicados" in _divergencias(fonte_sintetica)


def test_peso_fora_de_faixa_e_reportado(fonte_sintetica: sqlite3.Connection) -> None:
    """O CHECK `peso >= 0.0 AND peso <= 1.0` do DDL é replicado na validação do grafo.

    Numa fonte que passou pelo DDL da Ordem 2 esse valor nem entra — o CHECK
    rejeita antes. A checagem do ETL é segunda linha de defesa, para o caso de
    o grafo ser carregado de um SQLite gerado fora do DDL. Para exercitá-la,
    o CHECK é desligado com PRAGMA, simulando exatamente esse caso.
    """
    fonte_sintetica.execute("PRAGMA ignore_check_constraints = ON")
    fonte_sintetica.execute("UPDATE relacoes SET peso = 1.5 WHERE rel_id = 'REL-000001'")
    assert "peso fora de [0,1]" in _divergencias(fonte_sintetica)


def test_plano_conta_arestas_por_tipo(fonte_sintetica: sqlite3.Connection) -> None:
    plano = monta_plano(fonte_sintetica)
    assert plano.contagem_por_tipo == {
        "USA_INGREDIENTE": 1, "ASSOCIADO_A_POVO": 1, "ORIGINARIO_DE": 1, "DERIVA_DE": 1
    }
    assert plano.total_nos == 8


# =============================================================
# Geração de Cypher
# =============================================================


def test_merge_de_no_usa_a_superclasse_como_chave() -> None:
    """MERGE por :ObjetoRoots {id} — a unicidade vale sobre todo o corpus."""
    cypher = cypher_merge_nos("Ingrediente")
    assert f"MERGE (n:{LABEL_SUPERCLASSE} {{id: linha.id}})" in cypher
    assert "SET n:Ingrediente" in cypher
    assert "UNWIND $linhas AS linha" in cypher


def test_merge_de_no_rejeita_label_fora_da_ontologia() -> None:
    """Labels não são parametrizáveis em Cypher; só a lista fechada é aceita."""
    with pytest.raises(ValueError, match="não pertence à ontologia"):
        cypher_merge_nos("Ingrediente`) DETACH DELETE n //")


def test_merge_de_aresta_usa_rel_id_como_chave() -> None:
    """rel_id na chave do MERGE preserva as duas subséries REL- e REL-B."""
    cypher = cypher_merge_relacoes("USA_INGREDIENTE")
    assert "MERGE (origem)-[r:USA_INGREDIENTE {rel_id: linha.rel_id}]->(destino)" in cypher
    assert "SET r += linha.props" in cypher


def test_merge_de_aresta_rejeita_tipo_fora_da_ontologia() -> None:
    with pytest.raises(ValueError, match="não pertence à ontologia"):
        cypher_merge_relacoes("CONTEM")


def test_lotes_particiona_sem_perder_linha() -> None:
    itens = [{"i": i} for i in range(1201)]
    partes = lotes(itens, 500)
    assert [len(p) for p in partes] == [500, 500, 201]
    assert sum(len(p) for p in partes) == 1201


# =============================================================
# CLI — o padrão é não escrever
# =============================================================


def test_cli_sem_execute_nao_conecta_no_neo4j(
    banco_vazio: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Dry-run não toca no Neo4j: nem driver, nem variável de ambiente, nem conexão.

    Sem NEO4J_URI/USER/PASSWORD no ambiente, qualquer tentativa de conectar
    levantaria RuntimeError. O dry-run tem que chegar ao fim mesmo assim.
    """
    for var in ("NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD"):
        monkeypatch.delenv(var, raising=False)
    codigo = main(["--db", str(banco_vazio)])
    saida = capsys.readouterr().out
    assert codigo == 1  # banco vazio diverge do baseline, como esperado
    assert "DRY-RUN: nada foi escrito" in saida
    assert "DIVERGÊNCIAS ENCONTRADAS — carga bloqueada" in saida


def test_cli_limpar_exige_execute(banco_vazio: Path) -> None:
    """--limpar sozinho é erro de uso, não uma limpeza silenciosa."""
    with pytest.raises(SystemExit) as excinfo:
        main(["--db", str(banco_vazio), "--limpar"])
    assert excinfo.value.code == 2


def test_cli_banco_inexistente_falha_limpo(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    codigo = main(["--db", str(tmp_path / "nao-existe.db")])
    assert codigo == 2
    assert "Rode scripts/ordem2/etl.py primeiro" in capsys.readouterr().err
