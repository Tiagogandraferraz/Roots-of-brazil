"""
Fixtures da Ordem 3.

Constrói um corpus SINTÉTICO em SQLite, com o mesmo DDL da Ordem 2
(`schemas/ddl_sqlite.sql`) e exatamente as mesmas cardinalidades homologadas no
Relatório de Auditoria Sprint 2: 381 objetos, 1.585 relações, 18 órfãos e a
distribuição por tipo de relação da Ata v1.1.

Por que sintético e não o corpus real: o `Corpus_Fundador_v1.1.xlsx` e o
`roots_of_brazil_dev.db` gerado a partir dele não são versionados (dado, não
código). Os testes precisam rodar em CI sem eles. O que estes testes provam não
é o conteúdo do corpus — isso a Ordem 2 já validou — e sim que a PROJEÇÃO em
grafo preserva a forma auditada: as contagens, a unicidade e o
`rdfs:domain`/`rdfs:range` da ontologia.

Nenhum valor aqui é apresentado como dado do corpus; os nomes são
`Ingrediente sintético 001` etc., justamente para que nunca sejam confundidos
com conteúdo real.
"""

from __future__ import annotations

import sqlite3
import sys
import uuid
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from app.models.grafo import NOS, RELACOES  # noqa: E402

DDL = RAIZ / "schemas" / "ddl_sqlite.sql"

TIMESTAMP = "2026-08-05T00:00:00Z"
CONFIABILIDADE = "🟢 Confirmado em várias fontes"
PESO = 0.95
METODO_PESO = "Mapeamento determinístico de confiabilidade (Dicionário v1.2, Seção 20.2)"

#: Ingredientes reservados para ficarem SEM nenhuma aresta — reproduzem os 18
#: objetos órfãos registrados na Ata de Homologação v1.1.
N_ORFAOS = 18

#: Colunas obrigatórias (NOT NULL sem default) de cada tabela, além das transversais.
COLUNAS_ESPECIFICAS: dict[str, tuple[str, ...]] = {
    "ingrediente": ("nome_principal", "categoria", "subcategoria", "classe"),
    "receita": ("nome", "categoria", "subcategoria", "estado", "regiao", "livros_fonte"),
    "tecnica": ("nome", "descricao", "livros_fonte", "categoria", "subcategoria", "descricao_pt"),
    "povo": ("povo", "livros_fonte", "categoria", "subcategoria"),
    "territorio": ("estado", "livros_fonte", "categoria", "subcategoria"),
    "patrimonio": ("categoria", "elemento", "descricao", "livros_fonte", "subcategoria", "descricao_pt"),
    "bioma": ("nome", "descricao", "fonte", "descricao_pt"),
    "livro_fonte": ("titulo", "autor", "tipo_documento", "idioma"),
}


def _valores_especificos(tabela: str, indice: int, nome: str) -> dict[str, object]:
    base: dict[str, object] = {}
    for coluna in COLUNAS_ESPECIFICAS[tabela]:
        base[coluna] = nome
    if tabela == "ingrediente":
        base["classe"] = ("Vegetal", "Animal", "Processado/Outro")[indice % 3]
    if tabela == "bioma":
        base["fonte"] = "IBGE (sintético)"
    if tabela == "livro_fonte":
        base["tipo_documento"] = "Livro"
        base["idioma"] = "pt"
    return base


def _insere_nos(conn: sqlite3.Connection) -> dict[str, list[str]]:
    """Insere as 8 tabelas com a contagem exata de cada catálogo. Devolve os IDs por label."""
    ids_por_label: dict[str, list[str]] = {}
    for spec in NOS:
        ids: list[str] = []
        for i in range(1, spec.contagem_esperada + 1):
            objeto_id = f"{spec.prefixo_id}-{i:06d}"
            nome = f"{spec.label} sintético {i:03d}"
            valores: dict[str, object] = {
                "id": objeto_id,
                "uuid": str(uuid.uuid4()),
                "slug": f"{spec.label.lower()}-sintetico-{i:03d}",
                "created_at": TIMESTAMP,
                "updated_at": TIMESTAMP,
                "version": 1,
                "nome_pt": nome,
            }
            # `bioma` e `livro_fonte` não têm coluna `confiabilidade` no DDL da
            # Ordem 2 — bioma carrega `fonte`/`oficial_ibge` no lugar.
            if spec.tabela_sqlite not in {"bioma", "livro_fonte"}:
                valores["confiabilidade"] = CONFIABILIDADE
            valores.update(_valores_especificos(spec.tabela_sqlite, i, nome))

            colunas = ", ".join(valores)
            marcadores = ", ".join("?" for _ in valores)
            conn.execute(
                f"INSERT INTO {spec.tabela_sqlite} ({colunas}) VALUES ({marcadores})",
                tuple(valores.values()),
            )
            ids.append(objeto_id)
        ids_por_label[spec.label] = ids
    return ids_por_label


def _pares(origens: list[str], destinos: list[str], quantidade: int) -> list[tuple[str, str]]:
    """Round-robin nos dois lados: garante que todo nó de ambos os pools recebe
    pelo menos uma aresta quando `quantidade >= len(pool)` — é assim que a
    fixture controla exatamente quais nós ficam órfãos."""
    return [
        (origens[i % len(origens)], destinos[i % len(destinos)])
        for i in range(quantidade)
    ]


def _insere_relacoes(conn: sqlite3.Connection, ids: dict[str, list[str]]) -> None:
    """Gera 1.585 arestas com a distribuição por tipo da Auditoria Sprint 2,
    respeitando o rdfs:domain/rdfs:range de cada owl:ObjectProperty."""
    # Os últimos N_ORFAOS ingredientes ficam de fora de toda aresta.
    ing = ids["Ingrediente"][:-N_ORFAOS]
    rec, tec, pov, ter, pat, bio = (
        ids["Receita"], ids["Tecnica"], ids["Povo"],
        ids["Territorio"], ids["Patrimonio"], ids["Bioma"],
    )

    arestas: list[tuple[str, str, str]] = []

    def adiciona(tipo: str, pares: list[tuple[str, str]]) -> None:
        arestas.extend((origem, destino, tipo) for origem, destino in pares)

    adiciona("USA_INGREDIENTE", _pares(rec, ing, 895))
    # 205 = 134 Receita→Povo + 71 Ingrediente→Povo (owl:unionOf no domain)
    adiciona("ASSOCIADO_A_POVO", _pares(rec, pov, 134) + _pares(ing, pov, 71))
    adiciona("CULTIVADO_EM", _pares(ing, ter, 106))
    adiciona("UTILIZA_TECNICA", _pares(rec, tec, 85))
    adiciona("PREPARADO_COM", _pares(tec, ing, 81))
    adiciona("OCORRE_EM", _pares(rec, ter, 77))
    # 67 = 39 Ingrediente→Povo + 28 Ingrediente→Bioma (owl:unionOf no range)
    adiciona("ORIGINARIO_DE", _pares(ing, pov, 39) + _pares(ing, bio, 28))
    adiciona("PATRIMONIO_DE", _pares(pat, pov, 38))
    adiciona("LOCALIZADO_EM_BIOMA", _pares(ter, bio, 24))
    # DERIVA_DE é auto-relação: destino deslocado para não gerar laço em si mesmo.
    adiciona("DERIVA_DE", [(ing[i], ing[i + 1]) for i in range(7)])

    for numero, (origem, destino, tipo) in enumerate(arestas, start=1):
        conn.execute(
            """INSERT INTO relacoes (rel_id, origem_id, destino_id, tipo_relacao, fonte, pagina,
                   confiabilidade, observacoes, data_criacao, peso, metodo_calculo_peso)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (f"REL-{numero:06d}", origem, destino, tipo, "fonte sintética", "1",
             CONFIABILIDADE, "registro sintético de teste", TIMESTAMP, PESO, METODO_PESO),
        )


def constroi_corpus_sintetico(caminho: Path) -> Path:
    """Cria o banco sintético e confere, na própria fixture, que ele reproduz o baseline."""
    conn = sqlite3.connect(caminho)
    try:
        conn.executescript(DDL.read_text(encoding="utf-8"))
        ids = _insere_nos(conn)
        _insere_relacoes(conn, ids)
        conn.commit()

        total_arestas = conn.execute("SELECT COUNT(*) FROM relacoes").fetchone()[0]
        orfaos = conn.execute(
            """SELECT COUNT(*) FROM objeto_universal
               WHERE id NOT IN (SELECT origem_id FROM relacoes
                                UNION SELECT destino_id FROM relacoes)"""
        ).fetchone()[0]
        # Se a própria fixture não reproduzir o baseline, os testes que dependem
        # dela seriam vacuamente verdes — melhor falhar aqui, alto e claro.
        assert total_arestas == sum(r.instancias_esperadas for r in RELACOES), total_arestas
        assert orfaos == N_ORFAOS, orfaos
    finally:
        conn.close()
    return caminho


@pytest.fixture(scope="session")
def corpus_sintetico(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Banco sintético compartilhado pela sessão (construí-lo custa ~1s)."""
    destino = tmp_path_factory.mktemp("ordem3") / "corpus_sintetico.db"
    return constroi_corpus_sintetico(destino)


@pytest.fixture
def corpus_editavel(tmp_path: Path, corpus_sintetico: Path) -> Path:
    """Cópia descartável do banco sintético, para testes que corrompem o dado de propósito."""
    copia = tmp_path / "corpus_editavel.db"
    copia.write_bytes(corpus_sintetico.read_bytes())
    return copia
