"""
Roots of Brazil — Modelo de grafo do Neo4j (Ordem 3).

Tradução determinística de duas fontes já homologadas para o modelo de
propriedades (property graph) do Neo4j:

  * `schemas/ontologia.ttl`  (Ordem 1) — as 8 classes OWL e as 12 object
    properties, com seus `rdfs:domain` / `rdfs:range`;
  * `schemas/ddl_sqlite.sql` (Ordem 2) — os nomes de coluna que viram nomes de
    propriedade, e a view `objeto_universal` que resolve a FK polimórfica.

Nada aqui é inventado: cada label, cada tipo de aresta e cada contagem esperada
tem origem declarada em uma dessas duas fontes ou no Relatório de Auditoria do
Sprint 2 (381 objetos / 1.585 relações).

Este módulo é de DADOS PUROS — não importa o driver `neo4j`, não abre conexão e
não executa Cypher. Isso permite que os testes do modelo (`tests/ordem3/`) rodem
sem servidor e sem rede. A execução vive em `scripts/ordem3/etl_neo4j.py`.

Decisões de modelagem (justificadas no relatório da Ordem 3):

1. **Label transversal `:ObjetoRoots`** — todo nó recebe, além do seu label
   específico, o label `:ObjetoRoots`. É o equivalente em grafo da superclasse
   `roots:ObjetoRoots` da ontologia e da view `objeto_universal` do SQLite:
   permite `MATCH (n:ObjetoRoots {id: ...})` polimórfico, que é exatamente o que
   a carga de arestas precisa (origem/destino podem ser de qualquer catálogo).

2. **Atributos de aresta como propriedades de relacionamento.** A ontologia OWL
   não representa peso/proveniência em uma tripla simples e registra isso
   explicitamente (nota final de `ontologia.ttl`: "a Ordem 3 (Neo4j) modela isso
   nativamente como propriedades de aresta"). É o que fazemos: `peso`,
   `confiabilidade`, `fonte`, `pagina` etc. moram na aresta, não em um nó de
   reificação.

3. **Nomes de propriedade em snake_case**, idênticos às colunas do DDL da
   Ordem 2 — o grafo e o relacional falam o mesmo vocabulário, e a
   correspondência com o termo OWL fica registrada em `TERMO_OWL_POR_PROPRIEDADE`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Label transversal aplicado a todos os nós — ver decisão de modelagem 1.
LABEL_OBJETO_ROOTS = "ObjetoRoots"

# Namespace da ontologia (schemas/ontologia.ttl).
NS_ROOTS = "https://rootsofbrazil.org/ontology#"


@dataclass(frozen=True)
class EspecNo:
    """Um label de nó do grafo, derivado de uma classe OWL e de uma tabela SQL."""

    label: str
    classe_owl: str
    prefixo_id: str
    tabela_sqlite: str
    #: Coluna do DDL da Ordem 2 que carrega o nome humano do objeto.
    coluna_nome: str
    #: Contagem homologada no Relatório de Auditoria Sprint 2 / Ata v1.1.
    contagem_esperada: int
    secao_dicionario: str


@dataclass(frozen=True)
class EspecRelacao:
    """Um tipo de aresta do grafo, derivado de uma owl:ObjectProperty."""

    tipo: str
    #: Labels aceitos na ponta de origem (rdfs:domain; tupla = owl:unionOf).
    origem: tuple[str, ...]
    #: Labels aceitos na ponta de destino (rdfs:range; tupla = owl:unionOf).
    destino: tuple[str, ...]
    #: Contagem homologada no Relatório de Auditoria Sprint 2.
    instancias_esperadas: int
    nota: str = ""
    #: Tipos RESERVADOS pelo Dicionário v1.2 (enum válido, 0 instâncias na v1.1).
    reservado: bool = False


# =============================================================================
# As 8 classes de entidade — ontologia.ttl, Seções 12-24 do Dicionário v1.2
# =============================================================================

NOS: tuple[EspecNo, ...] = (
    EspecNo("Ingrediente", "roots:Ingrediente", "ING", "ingrediente",
            "nome_principal", 130, "Seção 12"),
    EspecNo("Receita", "roots:Receita", "REC", "receita",
            "nome", 136, "Seção 14"),
    EspecNo("Tecnica", "roots:Tecnica", "TEC", "tecnica",
            "nome", 38, "Seção 16"),
    EspecNo("Povo", "roots:Povo", "POV", "povo",
            "povo", 17, "Seção 18"),
    EspecNo("Territorio", "roots:Territorio", "TER", "territorio",
            "estado", 18, "Seção 20"),
    EspecNo("Patrimonio", "roots:Patrimonio", "PAT", "patrimonio",
            "elemento", 35, "Seção 22"),
    EspecNo("Bioma", "roots:Bioma", "BIO", "bioma",
            "nome", 7, "Seção 24"),
    # Entidade NOVA na v1.2: esquema definido, população pendente. NÃO inventar linhas.
    EspecNo("LivroFonte", "roots:LivroFonte", "LIV", "livro_fonte",
            "titulo", 0, "Seção 19"),
)

LABEL_POR_PREFIXO: dict[str, str] = {n.prefixo_id: n.label for n in NOS}
LABEL_POR_TABELA: dict[str, str] = {n.tabela_sqlite: n.label for n in NOS}
TABELA_POR_LABEL: dict[str, str] = {n.label: n.tabela_sqlite for n in NOS}
LABELS: tuple[str, ...] = tuple(n.label for n in NOS)

#: 381 objetos — Relatório de Auditoria Sprint 2.
TOTAL_NOS_ESPERADO: int = sum(n.contagem_esperada for n in NOS)


# =============================================================================
# Os 12 tipos de relação — ontologia.ttl (owl:ObjectProperty), Seção 21/29
# 10 com instância na v1.1 + 2 RESERVADOS (0 instâncias, enum válido)
# =============================================================================

RELACOES: tuple[EspecRelacao, ...] = (
    EspecRelacao("USA_INGREDIENTE", ("Receita",), ("Ingrediente",), 895),
    EspecRelacao("ASSOCIADO_A_POVO", ("Receita", "Ingrediente"), ("Povo",), 205,
                 nota="domain é owl:unionOf(Receita, Ingrediente) — 134 Receita→Povo + 71 Ingrediente→Povo"),
    EspecRelacao("CULTIVADO_EM", ("Ingrediente",), ("Territorio",), 106),
    EspecRelacao("UTILIZA_TECNICA", ("Receita",), ("Tecnica",), 85),
    EspecRelacao("PREPARADO_COM", ("Tecnica",), ("Ingrediente",), 81),
    EspecRelacao("OCORRE_EM", ("Receita",), ("Territorio",), 77),
    EspecRelacao("ORIGINARIO_DE", ("Ingrediente",), ("Povo", "Bioma"), 67,
                 nota="range é owl:unionOf(Povo, Bioma) — 39 Ingrediente→Povo + 28 Ingrediente→Bioma"),
    EspecRelacao("PATRIMONIO_DE", ("Patrimonio",), ("Povo",), 38),
    EspecRelacao("LOCALIZADO_EM_BIOMA", ("Territorio",), ("Bioma",), 24,
                 nota="tipo de extensão criado no Sprint 2 para a entidade Bioma"),
    EspecRelacao("DERIVA_DE", ("Ingrediente",), ("Ingrediente",), 7,
                 nota="auto-relação: Ingrediente→Ingrediente"),
    EspecRelacao("VARIANTE_REGIONAL", LABELS, LABELS, 0, reservado=True,
                 nota="RESERVADO — domain/range não restringidos pelo Dicionário v1.2 além do enum"),
    EspecRelacao("SIMILAR_A", LABELS, LABELS, 0, reservado=True,
                 nota="RESERVADO — mesma nota de VARIANTE_REGIONAL"),
)

TIPOS_RELACAO: tuple[str, ...] = tuple(r.tipo for r in RELACOES)
RELACAO_POR_TIPO: dict[str, EspecRelacao] = {r.tipo: r for r in RELACOES}

#: 1.585 relações — Relatório de Auditoria Sprint 2.
TOTAL_RELACOES_ESPERADO: int = sum(r.instancias_esperadas for r in RELACOES)

#: 18 objetos sem nenhuma aresta — Ata de Homologação v1.1 / Auditoria Sprint 2.
TOTAL_ORFAOS_ESPERADO: int = 18


# =============================================================================
# Propriedades
# =============================================================================

#: Colunas transversais presentes em toda tabela de entidade (Dicionário v1.2, Seções 2-9).
PROPRIEDADES_TRANSVERSAIS: tuple[str, ...] = (
    "id", "uuid", "slug", "created_at", "updated_at", "version", "confiabilidade",
    "categoria", "subcategoria", "classe", "familia", "ordem_taxonomica", "grupo", "macrogrupo",
    "nome_pt", "nome_en", "nome_es", "nome_fr", "nome_it", "nome_de", "nome_ja", "nome_zh",
    "descricao_pt", "descricao_en", "descricao_es",
)

#: Colunas da tabela `relacoes` que viram propriedades da ARESTA (decisão 2).
PROPRIEDADES_ARESTA: tuple[str, ...] = (
    "rel_id", "fonte", "pagina", "confiabilidade", "observacoes",
    "data_criacao", "peso", "metodo_calculo_peso",
)

#: Correspondência propriedade do grafo → termo OWL, para as que mudam de forma.
#: As demais são idênticas ao nome da coluna/termo (ex.: `slug` → `roots:slug`).
TERMO_OWL_POR_PROPRIEDADE: dict[str, str] = {
    "created_at": "roots:createdAt",
    "updated_at": "roots:updatedAt",
    "ordem_taxonomica": "roots:ordemTaxonomica",
    "bounding_box": "roots:boundingBox",
    "metodo_calculo_peso": "roots:metodoCalculoPeso",
}

#: Índices herdados da Seção 24 do Dicionário v1.2 (os mesmos do DDL da Ordem 2).
INDICES_DE_NO: tuple[tuple[str, str], ...] = (
    (LABEL_OBJETO_ROOTS, "slug"),
    ("Ingrediente", "categoria"),
    ("Ingrediente", "classe"),
    ("Receita", "categoria"),
)


# =============================================================================
# Helpers de validação
# =============================================================================

class TipoRelacaoInvalido(ValueError):
    """Tipo de aresta fora do enum de 12 tipos do Dicionário v1.2, Seção 21/29."""


class PrefixoIdInvalido(ValueError):
    """ID legível cujo prefixo não corresponde a nenhuma das 8 entidades."""


def valida_tipo_relacao(tipo: str) -> str:
    """Devolve `tipo` se ele estiver no enum de 12 tipos; senão levanta.

    Guarda de segurança obrigatória: o tipo de aresta é interpolado literalmente
    no Cypher (Neo4j 5 não parametriza tipo de relacionamento), então precisa
    passar por whitelist antes — nunca por escaping.
    """
    if tipo not in RELACAO_POR_TIPO:
        raise TipoRelacaoInvalido(
            f"{tipo!r} não é um dos 12 tipos do Dicionário v1.2, Seção 21/29: "
            f"{', '.join(TIPOS_RELACAO)}"
        )
    return tipo


def valida_label(label: str) -> str:
    """Devolve `label` se ele for um dos 8 labels de entidade; senão levanta."""
    if label not in LABELS:
        raise ValueError(f"{label!r} não é um dos 8 labels: {', '.join(LABELS)}")
    return label


def label_para_id(objeto_id: str) -> str:
    """Resolve o label a partir do prefixo do ID legível (ex.: 'ING-000001' → 'Ingrediente').

    Dicionário v1.2, Seção 3 (Política de Identificadores).
    """
    prefixo = objeto_id.split("-", 1)[0] if "-" in objeto_id else ""
    label = LABEL_POR_PREFIXO.get(prefixo)
    if label is None:
        raise PrefixoIdInvalido(
            f"{objeto_id!r} não tem prefixo de entidade conhecido "
            f"({', '.join(sorted(LABEL_POR_PREFIXO))})"
        )
    return label


# =============================================================================
# Geração de Cypher — schema (DDL) e carga (DML)
# =============================================================================

def cypher_constraints() -> list[str]:
    """Constraints de unicidade — equivalente em grafo das PK/UNIQUE do DDL da Ordem 2.

    Só usa *node uniqueness constraints*, disponíveis também no Neo4j Community.
    Constraints de existência de propriedade e de chave (`IS NODE KEY`) são
    exclusivas do Enterprise e por isso NÃO são emitidas aqui — a obrigatoriedade
    equivalente é verificada pelo ETL (fail-fast) e pelos testes da Ordem 3.
    """
    linhas = [
        (
            "CREATE CONSTRAINT roots_objetoroots_id_unico IF NOT EXISTS\n"
            f"FOR (n:{LABEL_OBJETO_ROOTS}) REQUIRE n.id IS UNIQUE;"
        ),
        (
            "CREATE CONSTRAINT roots_objetoroots_uuid_unico IF NOT EXISTS\n"
            f"FOR (n:{LABEL_OBJETO_ROOTS}) REQUIRE n.uuid IS UNIQUE;"
        ),
    ]
    for no in NOS:
        chave = no.label.lower()
        linhas.append(
            f"CREATE CONSTRAINT roots_{chave}_id_unico IF NOT EXISTS\n"
            f"FOR (n:{no.label}) REQUIRE n.id IS UNIQUE;"
        )
    return linhas


def cypher_indices() -> list[str]:
    """Índices de nó (Seção 24) e de aresta (busca por rel_id / peso / confiabilidade)."""
    linhas = [
        f"CREATE INDEX roots_{label.lower()}_{prop}_idx IF NOT EXISTS\n"
        f"FOR (n:{label}) ON (n.{prop});"
        for label, prop in INDICES_DE_NO
    ]
    for rel in RELACOES:
        chave = rel.tipo.lower()
        linhas.append(
            f"CREATE INDEX roots_rel_{chave}_rel_id_idx IF NOT EXISTS\n"
            f"FOR ()-[r:{rel.tipo}]-() ON (r.rel_id);"
        )
        linhas.append(
            f"CREATE INDEX roots_rel_{chave}_peso_idx IF NOT EXISTS\n"
            f"FOR ()-[r:{rel.tipo}]-() ON (r.peso);"
        )
    return linhas


def cypher_schema() -> str:
    """DDL completo do grafo — o conteúdo canônico de `schemas/ddl_neo4j.cypher`."""
    partes = [
        "// Roots of Brazil — DDL Neo4j (Ordem 3)",
        "//",
        "// ARQUIVO GERADO. Fonte da verdade: app/models/grafo.py (cypher_schema()).",
        "// Para regenerar:  python -m scripts.ordem3.etl_neo4j --emitir-schema schemas/ddl_neo4j.cypher",
        "// O teste tests/ordem3/test_modelo_grafo.py::test_ddl_neo4j_esta_sincronizado",
        "// falha se este arquivo divergir do gerador.",
        "//",
        "// Derivado de schemas/ontologia.ttl (Ordem 1) e schemas/ddl_sqlite.sql (Ordem 2).",
        "// Compatível com Neo4j 5 Community: apenas node uniqueness constraints e índices.",
        "",
        "// --- Constraints de unicidade (PK/UNIQUE do relacional) ---",
        "",
    ]
    partes.extend(f"{c}\n" for c in cypher_constraints())
    partes.extend(["", "// --- Índices (Dicionário v1.2, Seção 24 + busca por aresta) ---", ""])
    partes.extend(f"{i}\n" for i in cypher_indices())
    return "\n".join(partes).rstrip("\n") + "\n"


def cypher_merge_nos(label: str) -> str:
    """MERGE idempotente de um lote de nós de um label.

    `MERGE` por `id` (não `CREATE`) para que recargas não dupliquem: o ETL da
    Ordem 3 pode ser reexecutado sem limpar o grafo.
    """
    valida_label(label)
    return (
        "UNWIND $linhas AS linha\n"
        f"MERGE (n:{label} {{id: linha.id}})\n"
        f"SET n:{LABEL_OBJETO_ROOTS}\n"
        "SET n += linha.props"
    )


def cypher_merge_relacoes(tipo: str) -> str:
    """MERGE idempotente de um lote de arestas de um tipo.

    Casa as pontas por `:ObjetoRoots {id}` — polimórfico, exatamente como a view
    `objeto_universal` do SQLite resolve a FK polimórfica da tabela `relacoes`.
    A identidade da aresta é o `rel_id`, então recarga não duplica.
    """
    valida_tipo_relacao(tipo)
    return (
        "UNWIND $linhas AS linha\n"
        f"MATCH (origem:{LABEL_OBJETO_ROOTS} {{id: linha.origem_id}})\n"
        f"MATCH (destino:{LABEL_OBJETO_ROOTS} {{id: linha.destino_id}})\n"
        f"MERGE (origem)-[r:{tipo} {{rel_id: linha.rel_id}}]->(destino)\n"
        "SET r += linha.props"
    )


def cypher_conta_nos_por_label() -> str:
    return (
        f"MATCH (n:{LABEL_OBJETO_ROOTS})\n"
        "UNWIND labels(n) AS label\n"
        "WITH label WHERE label IN $labels\n"
        "RETURN label, count(*) AS n"
    )


def cypher_conta_relacoes_por_tipo() -> str:
    return (
        "MATCH ()-[r]->()\n"
        "WHERE type(r) IN $tipos\n"
        "RETURN type(r) AS tipo, count(*) AS n"
    )


def cypher_conta_orfaos() -> str:
    """Nós sem nenhuma aresta — deve bater com os 18 órfãos da Ata v1.1."""
    return f"MATCH (n:{LABEL_OBJETO_ROOTS}) WHERE NOT (n)--() RETURN count(n) AS n"


def cypher_rel_ids_duplicados() -> str:
    """`rel_id` é PK em `relacoes`; no grafo a unicidade é verificada por query.

    Constraint de unicidade em relacionamento não está disponível no Neo4j 5
    Community — por isso a checagem é feita aqui e no teste, e não no DDL.
    """
    return (
        "MATCH ()-[r]->()\n"
        "WHERE type(r) IN $tipos\n"
        "WITH r.rel_id AS rel_id, count(*) AS n\n"
        "WHERE n > 1\n"
        "RETURN count(rel_id) AS n"
    )


def cypher_peso_fora_da_faixa() -> str:
    """Equivalente do CHECK (peso >= 0.0 AND peso <= 1.0) do DDL da Ordem 2."""
    return (
        "MATCH ()-[r]->()\n"
        "WHERE type(r) IN $tipos AND (r.peso IS NULL OR r.peso < 0.0 OR r.peso > 1.0)\n"
        "RETURN count(r) AS n"
    )


def cypher_viola_dominio_imagem(tipo: str) -> str:
    """Arestas cujas pontas não respeitam o rdfs:domain/rdfs:range da ontologia.

    É a checagem que o relacional NÃO consegue fazer (lá `relacoes` é uma tabela
    plana com FK polimórfica); no grafo ela é uma query direta.
    """
    spec = RELACAO_POR_TIPO[valida_tipo_relacao(tipo)]
    origens = ", ".join(f"'{label}'" for label in spec.origem)
    destinos = ", ".join(f"'{label}'" for label in spec.destino)
    return (
        f"MATCH (origem)-[r:{tipo}]->(destino)\n"
        f"WHERE NOT any(l IN labels(origem) WHERE l IN [{origens}])\n"
        f"   OR NOT any(l IN labels(destino) WHERE l IN [{destinos}])\n"
        "RETURN count(r) AS n"
    )


def cypher_limpa_grafo() -> str:
    """Remove apenas o subgrafo do Roots — nunca um `MATCH (n) DETACH DELETE n` cego."""
    return f"MATCH (n:{LABEL_OBJETO_ROOTS}) DETACH DELETE n"


@dataclass(frozen=True)
class ResumoModelo:
    """Resumo do modelo, usado pelo relatório e pelo modo dry-run do ETL."""

    labels: tuple[str, ...] = LABELS
    tipos_relacao: tuple[str, ...] = TIPOS_RELACAO
    total_nos_esperado: int = TOTAL_NOS_ESPERADO
    total_relacoes_esperado: int = TOTAL_RELACOES_ESPERADO
    total_orfaos_esperado: int = TOTAL_ORFAOS_ESPERADO
    constraints: tuple[str, ...] = field(default_factory=lambda: tuple(cypher_constraints()))
    indices: tuple[str, ...] = field(default_factory=lambda: tuple(cypher_indices()))
