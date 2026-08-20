"""
Roots of Brazil — modelo de grafo da Ordem 3 (Neo4j).

Tradução literal da ontologia OWL de `schemas/ontologia.ttl` para o modelo de
property graph do Neo4j. Nada aqui é inventado: cada label, tipo de relação e
contagem esperada tem origem declarada na ontologia (Ordem 1) e no Relatório de
Auditoria Sprint 2 (mesmo baseline usado por `scripts/ordem2/etl.py`).

Correspondência OWL -> Neo4j
----------------------------
| OWL / RDF (Ordem 1)                    | Property graph (Ordem 3)                    |
|----------------------------------------|---------------------------------------------|
| `roots:Ingrediente` (owl:Class)         | label `:Ingrediente`                        |
| `roots:ObjetoRoots` (superclasse)       | label adicional `:ObjetoRoots` em todo nó   |
| `rdfs:subClassOf`                       | multi-label (nó carrega os dois labels)     |
| `roots:USA_INGREDIENTE` (ObjectProperty)| tipo de relação `[:USA_INGREDIENTE]`        |
| `rdfs:domain` / `rdfs:range`            | `dominio` / `alcance` em `TipoRelacao`      |
| reificação de aresta (nota da Ordem 1)  | propriedades nativas de aresta              |

A última linha é o ponto da Ordem 3: `schemas/ontologia.ttl` (linhas 183-186)
registra que RDF/OWL simples não representa os atributos próprios da tabela
RELACOES (peso, confiabilidade, proveniência) em uma única tripla, e delega
explicitamente essa modelagem à Ordem 3. No Neo4j eles são propriedades da
aresta, sem reificação.

O label `:ObjetoRoots` cumpre em Neo4j o mesmo papel que a view
`objeto_universal` cumpre no SQLite da Ordem 2: dá um alvo único para resolver
as pontas polimórficas de `relacoes` e para ancorar as constraints de unicidade
de `id` e `uuid` sobre todo o corpus.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

# =============================================================
# Nós — as 8 classes de entidade (ontologia, linhas 92-107)
# =============================================================

#: Label adicional carregado por TODOS os nós de entidade.
#: Equivalente a `roots:ObjetoRoots` (superclasse abstrata, ontologia linha 18) e
#: à view `objeto_universal` do DDL da Ordem 2.
LABEL_SUPERCLASSE: Final = "ObjetoRoots"


@dataclass(frozen=True)
class Entidade:
    """Uma das 8 classes do corpus, com sua tabela de origem no banco da Ordem 2."""

    label: str
    prefixo: str
    tabela_sqlite: str
    instancias_esperadas: int
    secao_dicionario: str


#: Ordem preservada como na ontologia. `instancias_esperadas` vem do Relatório de
#: Auditoria Sprint 2 (381 objetos), idêntico ao dicionário `esperado` de
#: `scripts/ordem2/etl.py`.
ENTIDADES: Final[tuple[Entidade, ...]] = (
    Entidade("Ingrediente", "ING", "ingrediente", 130, "Seção 12"),
    Entidade("Receita", "REC", "receita", 136, "Seção 14"),
    Entidade("Tecnica", "TEC", "tecnica", 38, "Seção 16"),
    Entidade("Povo", "POV", "povo", 17, "Seção 18"),
    Entidade("Territorio", "TER", "territorio", 18, "Seção 20"),
    Entidade("Patrimonio", "PAT", "patrimonio", 35, "Seção 22"),
    Entidade("Bioma", "BIO", "bioma", 7, "Seção 24"),
    # Entidade nova na v1.2: esquema definido, 0 instâncias nesta versão.
    # Nenhum nó é inventado para preenchê-la (mesma decisão da Ordem 2).
    Entidade("LivroFonte", "LIV", "livro_fonte", 0, "Seção 19"),
)

ENTIDADE_POR_LABEL: Final[dict[str, Entidade]] = {e.label: e for e in ENTIDADES}

#: Resolve a ponta polimórfica de `relacoes` (origem_id/destino_id) para o label
#: do nó, pelo prefixo do ID legível — Dicionário v1.2, Seção 3.
LABEL_POR_PREFIXO: Final[dict[str, str]] = {e.prefixo: e.label for e in ENTIDADES}

LABELS: Final[frozenset[str]] = frozenset(e.label for e in ENTIDADES)

TOTAL_OBJETOS_ESPERADO: Final = 381


def label_do_id(id_legivel: str) -> str:
    """Devolve o label do nó a partir do ID legível (ex.: 'ING-000001' -> 'Ingrediente').

    Levanta ValueError para prefixo desconhecido — nunca adivinha um label.
    """
    prefixo = id_legivel.split("-", 1)[0]
    try:
        return LABEL_POR_PREFIXO[prefixo]
    except KeyError:
        raise ValueError(
            f"ID {id_legivel!r} tem prefixo {prefixo!r}, que não corresponde a nenhuma "
            f"das 8 entidades da ontologia ({sorted(LABEL_POR_PREFIXO)})."
        ) from None


# =============================================================
# Arestas — os 12 tipos de relação (ontologia, linhas 133-181)
# =============================================================


@dataclass(frozen=True)
class TipoRelacao:
    """Um `owl:ObjectProperty` da ontologia, com domain/range preservados.

    `dominio` e `alcance` são conjuntos porque duas relações têm união em OWL:
    ASSOCIADO_A_POVO tem `owl:unionOf (Receita Ingrediente)` como domain, e
    ORIGINARIO_DE tem `owl:unionOf (Povo Bioma)` como range.
    """

    tipo: str
    dominio: frozenset[str]
    alcance: frozenset[str]
    instancias_esperadas: int
    reservado: bool = False


_TODOS = frozenset(e.label for e in ENTIDADES)

#: Domain/range copiados de `schemas/ontologia.ttl`; contagens do Relatório de
#: Auditoria Sprint 2 (as mesmas conferidas por `mv_grafo_agregado` na Ordem 2).
TIPOS_RELACAO: Final[tuple[TipoRelacao, ...]] = (
    TipoRelacao("USA_INGREDIENTE", frozenset({"Receita"}), frozenset({"Ingrediente"}), 895),
    TipoRelacao(
        "ASSOCIADO_A_POVO",
        frozenset({"Receita", "Ingrediente"}),  # owl:unionOf — ontologia linha 138
        frozenset({"Povo"}),
        205,
    ),
    TipoRelacao("CULTIVADO_EM", frozenset({"Ingrediente"}), frozenset({"Territorio"}), 106),
    TipoRelacao("UTILIZA_TECNICA", frozenset({"Receita"}), frozenset({"Tecnica"}), 85),
    TipoRelacao("PREPARADO_COM", frozenset({"Tecnica"}), frozenset({"Ingrediente"}), 81),
    TipoRelacao("OCORRE_EM", frozenset({"Receita"}), frozenset({"Territorio"}), 77),
    TipoRelacao(
        "ORIGINARIO_DE",
        frozenset({"Ingrediente"}),
        frozenset({"Povo", "Bioma"}),  # owl:unionOf — ontologia linha 160
        67,
    ),
    TipoRelacao("PATRIMONIO_DE", frozenset({"Patrimonio"}), frozenset({"Povo"}), 38),
    TipoRelacao("LOCALIZADO_EM_BIOMA", frozenset({"Territorio"}), frozenset({"Bioma"}), 24),
    TipoRelacao("DERIVA_DE", frozenset({"Ingrediente"}), frozenset({"Ingrediente"}), 7),
    # Reservados: a ontologia mantém domain/range em roots:ObjetoRoots por não
    # haver base documental para restringir mais (ontologia, linhas 175-181).
    # Mantido igual aqui — 0 instâncias, nenhuma semântica inventada.
    TipoRelacao("VARIANTE_REGIONAL", _TODOS, _TODOS, 0, reservado=True),
    TipoRelacao("SIMILAR_A", _TODOS, _TODOS, 0, reservado=True),
)

TIPO_RELACAO_POR_NOME: Final[dict[str, TipoRelacao]] = {t.tipo: t for t in TIPOS_RELACAO}

TIPOS_RELACAO_VALIDOS: Final[frozenset[str]] = frozenset(TIPO_RELACAO_POR_NOME)

TOTAL_RELACOES_ESPERADO: Final = 1585

#: Propriedades da ARESTA (tabela `relacoes` da Ordem 2). No RDF da Ordem 1 elas
#: exigiriam reificação; aqui são nativas.
PROPRIEDADES_ARESTA: Final[tuple[str, ...]] = (
    "rel_id",
    "fonte",
    "pagina",
    "confiabilidade",
    "observacoes",
    "data_criacao",
    "peso",
    "metodo_calculo_peso",
)


def valida_aresta(label_origem: str, tipo: str, label_destino: str) -> None:
    """Confere uma aresta contra o domain/range da ontologia.

    Levanta ValueError descrevendo a violação. Usado pelo ETL em modo dry-run e
    antes de qualquer escrita — o mesmo princípio fail-fast da Ordem 2: o script
    para e reporta, não ajusta dado para bater a regra.
    """
    definicao = TIPO_RELACAO_POR_NOME.get(tipo)
    if definicao is None:
        raise ValueError(
            f"Tipo de relação {tipo!r} não existe na ontologia "
            f"(válidos: {sorted(TIPOS_RELACAO_VALIDOS)})."
        )
    if label_origem not in definicao.dominio:
        raise ValueError(
            f"{tipo}: origem :{label_origem} viola o rdfs:domain da ontologia "
            f"({sorted(definicao.dominio)})."
        )
    if label_destino not in definicao.alcance:
        raise ValueError(
            f"{tipo}: destino :{label_destino} viola o rdfs:range da ontologia "
            f"({sorted(definicao.alcance)})."
        )


# =============================================================
# DDL do grafo — constraints e índices
# =============================================================

# Neo4j 5 Community suporta apenas constraints de UNICIDADE DE NÓ. Constraints de
# existência (IS NOT NULL), node key e qualquer constraint de RELAÇÃO são recursos
# exclusivos do Enterprise Edition. Como o docker-compose usa a imagem `neo4j:5`
# (Community), só emitimos aqui o que roda de fato nela; o equivalente Enterprise
# fica registrado em CONSTRAINTS_ENTERPRISE, não executado, para não dar a falsa
# impressão de que a regra está sendo aplicada pelo banco.

CONSTRAINTS: Final[tuple[str, ...]] = (
    # Espelha PRIMARY KEY de cada tabela da Ordem 2, unificada no label da superclasse.
    "CREATE CONSTRAINT objeto_roots_id_unico IF NOT EXISTS "
    f"FOR (n:{LABEL_SUPERCLASSE}) REQUIRE n.id IS UNIQUE",
    # Espelha `uuid TEXT NOT NULL UNIQUE` — Dicionário v1.2, Seção 5.
    "CREATE CONSTRAINT objeto_roots_uuid_unico IF NOT EXISTS "
    f"FOR (n:{LABEL_SUPERCLASSE}) REQUIRE n.uuid IS UNIQUE",
)

#: Só roda em Enterprise. A unicidade de `rel_id` e a obrigatoriedade de `peso`/
#: `metodo_calculo_peso` são garantidas pelo ETL (fail-fast em Python) quando o
#: banco é Community — mesma estratégia que a Ordem 2 adotou para a FK polimórfica.
CONSTRAINTS_ENTERPRISE: Final[tuple[str, ...]] = (
    "CREATE CONSTRAINT relacao_rel_id_unico IF NOT EXISTS "
    "FOR ()-[r:RELACIONA]-() REQUIRE r.rel_id IS UNIQUE",
    "CREATE CONSTRAINT objeto_roots_nome_pt_obrigatorio IF NOT EXISTS "
    f"FOR (n:{LABEL_SUPERCLASSE}) REQUIRE n.nome_pt IS NOT NULL",
)


def indices() -> tuple[str, ...]:
    """Índices do grafo, espelhando os da Seção 24 do Dicionário (DDL da Ordem 2).

    Índices de nó e de relação (range e full-text) são suportados no Community.
    """
    cypher: list[str] = [
        # Resolução por slug (rota amigável da API, Ordem 4).
        "CREATE INDEX objeto_roots_slug IF NOT EXISTS "
        f"FOR (n:{LABEL_SUPERCLASSE}) ON (n.slug)",
        # Equivalentes a idx_ingrediente_categoria / _classe / idx_receita_categoria.
        "CREATE INDEX ingrediente_categoria IF NOT EXISTS FOR (n:Ingrediente) ON (n.categoria)",
        "CREATE INDEX ingrediente_classe IF NOT EXISTS FOR (n:Ingrediente) ON (n.classe)",
        "CREATE INDEX receita_categoria IF NOT EXISTS FOR (n:Receita) ON (n.categoria)",
    ]
    # Equivalentes a idx_relacoes_confiabilidade e ao filtro por peso. O índice
    # composto (origem_id, tipo_relacao) da Ordem 2 não tem equivalente aqui: no
    # property graph a travessia por tipo a partir de um nó já é O(1) por natureza,
    # então esse índice existia justamente para compensar o modelo relacional.
    for definicao in TIPOS_RELACAO:
        nome = definicao.tipo.lower()
        cypher.append(
            f"CREATE INDEX rel_{nome}_confiabilidade IF NOT EXISTS "
            f"FOR ()-[r:{definicao.tipo}]-() ON (r.confiabilidade)"
        )
    # Busca textual por nome, base da futura busca semântica (Ordem 5).
    labels = "|".join(e.label for e in ENTIDADES)
    cypher.append(
        f"CREATE FULLTEXT INDEX objeto_roots_nome_ft IF NOT EXISTS "
        f"FOR (n:{labels}) ON EACH [n.nome_pt, n.descricao_pt]"
    )
    return tuple(cypher)


INDICES: Final[tuple[str, ...]] = indices()
