"""
Roots of Brazil — ETL da Ordem 3 (carga do grafo no Neo4j).

Fonte: o banco relacional produzido pela Ordem 2 (`roots_of_brazil_dev.db`), não
a planilha. O Corpus_Fundador_v1.1.xlsx já foi normalizado, deduplicado e
validado uma vez em `scripts/ordem2/etl.py`; reler a planilha aqui abriria a
possibilidade de os dois bancos divergirem. O SQLite é a fonte estruturada
canônica, e esta Ordem projeta esse mesmo conteúdo no property graph.

    Corpus_Fundador_v1.1.xlsx  --Ordem 2-->  SQLite  --Ordem 3-->  Neo4j
             (read-only)                   (canônico)             (grafo)

MODO PADRÃO: DRY-RUN. Sem `--execute`, o script lê o SQLite, valida tudo contra
a ontologia e contra o baseline do Relatório de Auditoria Sprint 2, imprime o
plano de carga e o Cypher que rodaria — e NÃO abre conexão com o Neo4j nem
escreve um byte. Escrever exige o flag explícito `--execute`.

Mesma disciplina fail-fast da Ordem 2: se qualquer contagem divergir do baseline
(381 objetos, 1.585 relações), ou se uma aresta violar o domain/range da
ontologia, o script PARA e reporta — nunca ajusta dado para bater número.

Uso:
    python scripts/ordem3/etl_neo4j.py                      # dry-run (padrão)
    python scripts/ordem3/etl_neo4j.py --db caminho.db      # dry-run em outro banco
    python scripts/ordem3/etl_neo4j.py --execute            # carrega de fato
    python scripts/ordem3/etl_neo4j.py --execute --limpar   # apaga o grafo antes
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from neo4j import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.models.grafo import (  # noqa: E402
    CONSTRAINTS,
    ENTIDADES,
    INDICES,
    LABEL_SUPERCLASSE,
    PROPRIEDADES_ARESTA,
    TIPO_RELACAO_POR_NOME,
    TIPOS_RELACAO,
    TOTAL_OBJETOS_ESPERADO,
    TOTAL_RELACOES_ESPERADO,
    label_do_id,
    valida_aresta,
)

DB_PADRAO = Path("roots_of_brazil_dev.db")

#: Linhas por transação nas escritas com UNWIND. 500 mantém cada transação
#: pequena o bastante para o heap padrão do container `neo4j:5`.
TAMANHO_LOTE = 500


# =============================================================
# Leitura da fonte (SQLite da Ordem 2)
# =============================================================


def _sem_nulos(linha: sqlite3.Row) -> dict[str, Any]:
    """Converte a linha em dict descartando NULLs.

    O Neo4j não armazena propriedade nula: gravar `None` e gravar nada são a
    mesma coisa. Descartar aqui deixa explícito que a ausência veio da fonte e
    evita propriedades vazias poluindo o grafo.
    """
    return {k: linha[k] for k in linha.keys() if linha[k] is not None}


def le_nos(conn: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
    """Lê as 8 tabelas de entidade. Todas as colunas viram propriedades do nó.

    Copiar todas as colunas (em vez de uma lista escrita à mão) garante que o
    grafo carregue exatamente os campos do Dicionário v1.2 que a Ordem 2 já
    materializou, sem uma segunda lista para sair de sincronia com o DDL.
    """
    nos: dict[str, list[dict[str, Any]]] = {}
    for entidade in ENTIDADES:
        linhas = conn.execute(f"SELECT * FROM {entidade.tabela_sqlite}").fetchall()
        nos[entidade.label] = [_sem_nulos(linha) for linha in linhas]
    return nos


def le_relacoes(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Lê a tabela `relacoes` — cada linha vira uma aresta com suas propriedades."""
    return [_sem_nulos(linha) for linha in conn.execute("SELECT * FROM relacoes").fetchall()]


# =============================================================
# Plano de carga e validação (roda sempre, inclusive em dry-run)
# =============================================================


@dataclass
class PlanoCarga:
    """O que seria escrito, mais as divergências encontradas antes de escrever."""

    nos: dict[str, list[dict[str, Any]]]
    relacoes: list[dict[str, Any]]
    divergencias: list[str] = field(default_factory=list)

    @property
    def total_nos(self) -> int:
        return sum(len(v) for v in self.nos.values())

    @property
    def contagem_por_tipo(self) -> Counter[str]:
        return Counter(r["tipo_relacao"] for r in self.relacoes)

    @property
    def valido(self) -> bool:
        return not self.divergencias


def monta_plano(conn: sqlite3.Connection) -> PlanoCarga:
    """Lê a fonte e valida tudo o que dá para validar sem tocar no Neo4j."""
    plano = PlanoCarga(nos=le_nos(conn), relacoes=le_relacoes(conn))
    div = plano.divergencias

    # --- 1. Contagem de nós por label vs. Relatório de Auditoria Sprint 2 ---
    for entidade in ENTIDADES:
        obtido = len(plano.nos[entidade.label])
        if obtido != entidade.instancias_esperadas:
            div.append(
                f"nós :{entidade.label} — esperado {entidade.instancias_esperadas}, obtido {obtido}"
            )
    if plano.total_nos != TOTAL_OBJETOS_ESPERADO:
        div.append(f"total de nós — esperado {TOTAL_OBJETOS_ESPERADO}, obtido {plano.total_nos}")

    # --- 2. Chaves de identidade: `id` e `uuid` únicos em todo o corpus ---
    # É o que as constraints do grafo vão exigir; conferir antes evita descobrir
    # a colisão no meio da carga, com o grafo já parcialmente escrito.
    ids = [n["id"] for linhas in plano.nos.values() for n in linhas]
    uuids = [n["uuid"] for linhas in plano.nos.values() for n in linhas]
    if len(set(ids)) != len(ids):
        duplicados = [i for i, c in Counter(ids).items() if c > 1]
        div.append(f"IDs duplicados entre catálogos: {duplicados}")
    if len(set(uuids)) != len(uuids):
        div.append(f"UUIDs duplicados: {len(uuids) - len(set(uuids))} colisão(ões)")

    # --- 3. Contagem de arestas por tipo ---
    por_tipo = plano.contagem_por_tipo
    for definicao in TIPOS_RELACAO:
        obtido = por_tipo.get(definicao.tipo, 0)
        if obtido != definicao.instancias_esperadas:
            div.append(
                f"arestas [:{definicao.tipo}] — esperado {definicao.instancias_esperadas}, "
                f"obtido {obtido}"
            )
    desconhecidos = set(por_tipo) - set(TIPO_RELACAO_POR_NOME)
    if desconhecidos:
        div.append(f"tipos de relação fora da ontologia: {sorted(desconhecidos)}")
    if len(plano.relacoes) != TOTAL_RELACOES_ESPERADO:
        div.append(
            f"total de arestas — esperado {TOTAL_RELACOES_ESPERADO}, obtido {len(plano.relacoes)}"
        )

    # --- 4. rel_id único ---
    rel_ids = [r["rel_id"] for r in plano.relacoes]
    if len(set(rel_ids)) != len(rel_ids):
        div.append(f"rel_id duplicado: {len(rel_ids) - len(set(rel_ids))} colisão(ões)")

    # --- 5. Pontas resolvem para nós existentes (a FK polimórfica da Seção 25.3) ---
    #     e a aresta respeita o domain/range declarado na ontologia.
    conhecidos = set(ids)
    orfas = 0
    violacoes: list[str] = []
    for r in plano.relacoes:
        origem, destino, tipo = r["origem_id"], r["destino_id"], r["tipo_relacao"]
        if origem not in conhecidos or destino not in conhecidos:
            orfas += 1
            continue
        try:
            valida_aresta(label_do_id(origem), tipo, label_do_id(destino))
        except ValueError as erro:
            violacoes.append(f"{r['rel_id']} ({origem} -> {destino}): {erro}")
    if orfas:
        div.append(f"arestas apontando para ID inexistente: {orfas}")
    if violacoes:
        div.append(
            f"arestas violando domain/range da ontologia: {len(violacoes)}. "
            f"Primeiras: {violacoes[:5]}"
        )

    # --- 6. Faixa de `peso` (CHECK do DDL da Ordem 2, replicado aqui) ---
    fora_faixa = [
        r["rel_id"] for r in plano.relacoes if not 0.0 <= float(r.get("peso", -1)) <= 1.0
    ]
    if fora_faixa:
        div.append(f"peso fora de [0,1] em {len(fora_faixa)} aresta(s): {fora_faixa[:5]}")

    return plano


# =============================================================
# Cypher de escrita
# =============================================================


def cypher_merge_nos(label: str) -> str:
    """MERGE idempotente de um lote de nós de um label.

    MERGE por `id` (não CREATE) torna a carga repetível: rodar duas vezes não
    duplica nó. O label vem da lista fechada de `app.models.grafo`, nunca de
    dado de entrada — labels não podem ser parametrizados em Cypher.
    """
    if label not in {e.label for e in ENTIDADES}:
        raise ValueError(f"Label {label!r} não pertence à ontologia.")
    return (
        f"UNWIND $linhas AS linha\n"
        f"MERGE (n:{LABEL_SUPERCLASSE} {{id: linha.id}})\n"
        f"SET n:{label}, n += linha"
    )


def cypher_merge_relacoes(tipo: str) -> str:
    """MERGE idempotente de um lote de arestas de um tipo.

    A chave do MERGE é `rel_id`: é o que dá identidade à aresta na fonte, e é o
    que permite duas arestas do mesmo tipo entre o mesmo par de nós (a v1.1 tem
    duas subséries de REL_ID, REL-xxxxxx e REL-Bxxxxx, preservadas como estão).
    """
    if tipo not in TIPO_RELACAO_POR_NOME:
        raise ValueError(f"Tipo de relação {tipo!r} não pertence à ontologia.")
    return (
        f"UNWIND $linhas AS linha\n"
        f"MATCH (origem:{LABEL_SUPERCLASSE} {{id: linha.origem_id}})\n"
        f"MATCH (destino:{LABEL_SUPERCLASSE} {{id: linha.destino_id}})\n"
        f"MERGE (origem)-[r:{tipo} {{rel_id: linha.rel_id}}]->(destino)\n"
        f"SET r += linha.props"
    )


def _props_aresta(r: dict[str, Any]) -> dict[str, Any]:
    """Extrai as propriedades da aresta (tudo menos as pontas e o tipo)."""
    return {k: r[k] for k in PROPRIEDADES_ARESTA if k in r}


def lotes(itens: list[dict[str, Any]], tamanho: int = TAMANHO_LOTE) -> list[list[dict[str, Any]]]:
    return [itens[i : i + tamanho] for i in range(0, len(itens), tamanho)]


# =============================================================
# Impressão do plano (dry-run)
# =============================================================


def imprime_plano(plano: PlanoCarga, db: Path) -> None:
    print("=" * 72)
    print("PLANO DE CARGA — ORDEM 3 (Neo4j)   [DRY-RUN: nada foi escrito]")
    print("=" * 72)
    print(f"Fonte: {db}")
    print()

    print("DDL do grafo que seria aplicado:")
    for c in CONSTRAINTS:
        print(f"  {c.splitlines()[0]} ...")
    print(f"  (+ {len(INDICES)} índices: slug, categoria/classe, confiabilidade por tipo, full-text)")
    print()

    print(f"Nós a criar — {plano.total_nos} (baseline: {TOTAL_OBJETOS_ESPERADO})")
    for entidade in ENTIDADES:
        obtido = len(plano.nos[entidade.label])
        marca = "ok" if obtido == entidade.instancias_esperadas else "DIVERGE"
        print(
            f"  :{entidade.label:<12} {obtido:>5}  "
            f"(esperado {entidade.instancias_esperadas:>4}) [{marca}]"
        )
    print()

    por_tipo = plano.contagem_por_tipo
    print(f"Arestas a criar — {len(plano.relacoes)} (baseline: {TOTAL_RELACOES_ESPERADO})")
    for definicao in TIPOS_RELACAO:
        obtido = por_tipo.get(definicao.tipo, 0)
        marca = "ok" if obtido == definicao.instancias_esperadas else "DIVERGE"
        reservado = " [reservado]" if definicao.reservado else ""
        print(
            f"  [:{definicao.tipo + ']':<21} {obtido:>5}  "
            f"(esperado {definicao.instancias_esperadas:>4}) [{marca}]{reservado}"
        )
    print()

    print("Propriedades de aresta (nativas — sem reificação, ao contrário do RDF da Ordem 1):")
    print(f"  {', '.join(PROPRIEDADES_ARESTA)}")
    print()

    if plano.valido:
        print("VALIDAÇÃO: nenhuma divergência. Pronto para `--execute`.")
    else:
        print("VALIDAÇÃO: DIVERGÊNCIAS ENCONTRADAS — carga bloqueada:")
        for d in plano.divergencias:
            print(f"  - {d}")
    print("=" * 72)


# =============================================================
# Execução real (só com --execute)
# =============================================================


def _gravador(consulta: str, lote: list[dict[str, Any]]) -> Any:
    """Fecha consulta e lote numa função de transação para `Session.execute_write`.

    Cada lote roda em sua própria transação gerenciada, que o driver reexecuta
    em caso de erro transitório (deadlock, troca de líder no cluster).
    """

    def grava(tx: Any) -> None:
        tx.run(consulta, linhas=lote).consume()

    return grava


def executa(plano: PlanoCarga, limpar: bool) -> None:
    """Aplica o DDL e carrega o grafo. Só chamada quando `--execute` foi passado."""
    from app.database.neo4j import sessao  # import tardio: dry-run não precisa do driver

    with sessao() as s:
        if limpar:
            print("Limpando o grafo existente...")
            # Em lotes, para não estourar a memória de transação num grafo grande.
            while True:
                resumo = s.run(
                    f"MATCH (n:{LABEL_SUPERCLASSE}) WITH n LIMIT 10000 DETACH DELETE n"
                ).consume()
                if resumo.counters.nodes_deleted == 0:
                    break

        print("Aplicando constraints e índices...")
        for comando in (*CONSTRAINTS, *INDICES):
            s.run(comando)
        # Índices/constraints são populados de forma assíncrona; esperar evita
        # carregar contra um índice ainda não disponível.
        s.run("CALL db.awaitIndexes(300)")

        print("Carregando nós...")
        for entidade in ENTIDADES:
            linhas = plano.nos[entidade.label]
            consulta = cypher_merge_nos(entidade.label)
            for lote in lotes(linhas):
                s.execute_write(_gravador(consulta, lote))
            print(f"  :{entidade.label:<12} {len(linhas):>5} nós")

        print("Carregando arestas...")
        for definicao in TIPOS_RELACAO:
            do_tipo = [
                {
                    "origem_id": r["origem_id"],
                    "destino_id": r["destino_id"],
                    "rel_id": r["rel_id"],
                    "props": _props_aresta(r),
                }
                for r in plano.relacoes
                if r["tipo_relacao"] == definicao.tipo
            ]
            if not do_tipo:
                continue
            consulta = cypher_merge_relacoes(definicao.tipo)
            for lote in lotes(do_tipo):
                s.execute_write(_gravador(consulta, lote))
            print(f"  [:{definicao.tipo + ']':<21} {len(do_tipo):>5} arestas")

        verifica_pos_carga(s)


def verifica_pos_carga(s: Session) -> None:
    """Reconta o grafo carregado e compara com o baseline. Sai com 1 se divergir."""
    print("\nVerificação pós-carga (consultando o Neo4j, não a fonte):")
    divergencias: list[str] = []

    total_nos = s.run(f"MATCH (n:{LABEL_SUPERCLASSE}) RETURN count(n) AS n").single()["n"]
    if total_nos != TOTAL_OBJETOS_ESPERADO:
        divergencias.append(f"total de nós no grafo: esperado {TOTAL_OBJETOS_ESPERADO}, obtido {total_nos}")

    for entidade in ENTIDADES:
        obtido = s.run(f"MATCH (n:{entidade.label}) RETURN count(n) AS n").single()["n"]
        if obtido != entidade.instancias_esperadas:
            divergencias.append(
                f":{entidade.label}: esperado {entidade.instancias_esperadas}, obtido {obtido}"
            )

    total_arestas = s.run("MATCH ()-[r]->() RETURN count(r) AS n").single()["n"]
    if total_arestas != TOTAL_RELACOES_ESPERADO:
        divergencias.append(
            f"total de arestas no grafo: esperado {TOTAL_RELACOES_ESPERADO}, obtido {total_arestas}"
        )

    for definicao in TIPOS_RELACAO:
        obtido = s.run(f"MATCH ()-[r:{definicao.tipo}]->() RETURN count(r) AS n").single()["n"]
        if obtido != definicao.instancias_esperadas:
            divergencias.append(
                f"[:{definicao.tipo}]: esperado {definicao.instancias_esperadas}, obtido {obtido}"
            )

    # Órfãos: a Auditoria Sprint 2 conta 18 objetos sem nenhuma relação.
    orfaos = s.run(
        f"MATCH (n:{LABEL_SUPERCLASSE}) WHERE NOT (n)--() RETURN count(n) AS n"
    ).single()["n"]
    if orfaos != 18:
        divergencias.append(f"nós órfãos: esperado 18 (Auditoria Sprint 2), obtido {orfaos}")

    if divergencias:
        print("DIVERGÊNCIA DETECTADA — a carga NÃO bate com o baseline:")
        for d in divergencias:
            print(f"  - {d}")
        sys.exit(1)

    print(f"  nós: {total_nos} (esperado {TOTAL_OBJETOS_ESPERADO}) ok")
    print(f"  arestas: {total_arestas} (esperado {TOTAL_RELACOES_ESPERADO}) ok")
    print(f"  órfãos: {orfaos} (esperado 18) ok")
    print("Carga concluída sem divergências.")


# =============================================================


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", type=Path, default=DB_PADRAO, help="SQLite gerado pela Ordem 2")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="ESCREVE no Neo4j. Sem este flag o script só valida e imprime o plano.",
    )
    parser.add_argument(
        "--limpar",
        action="store_true",
        help="Apaga o grafo antes de carregar. Exige --execute.",
    )
    args = parser.parse_args(argv)

    if args.limpar and not args.execute:
        parser.error("--limpar só faz sentido junto com --execute.")

    if not args.db.exists():
        print(f"Banco {args.db} não encontrado. Rode scripts/ordem2/etl.py primeiro.", file=sys.stderr)
        return 2

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    try:
        plano = monta_plano(conn)
    finally:
        conn.close()

    if not args.execute:
        imprime_plano(plano, args.db)
        return 0 if plano.valido else 1

    if not plano.valido:
        print("DIVERGÊNCIA DETECTADA NA FONTE — PARANDO ANTES DE ESCREVER NO NEO4J:")
        for d in plano.divergencias:
            print(f"  - {d}")
        print("Nenhuma escrita foi feita. Corrija a fonte (Ordem 2) e rode de novo.")
        return 1

    executa(plano, limpar=args.limpar)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
