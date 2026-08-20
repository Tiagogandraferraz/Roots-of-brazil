"""
Roots of Brazil — ETL da Ordem 3 (carga do grafo no Neo4j).

Mesmo padrão do `scripts/ordem2/etl.py`, com uma diferença de fonte:

    Ordem 2:  Corpus_Fundador_v1.1.xlsx  ->  SQLite   (extração do dado bruto)
    Ordem 3:  SQLite (saída da Ordem 2)  ->  Neo4j    (projeção em grafo)

A fonte é o banco já estruturado e AUDITADO da Ordem 2, nunca a planilha de novo.
Isso é deliberado: o corpus tem uma única porta de entrada (o ETL da Ordem 2, que
gera uuid/slug e valida contra a Auditoria do Sprint 2). Reextrair do .xlsx aqui
geraria uuids diferentes dos que já estão no relacional e quebraria a
correspondência 1:1 entre os dois bancos.

O SQLite é aberto em modo READ-ONLY (URI `?mode=ro`) — este script nunca escreve
na fonte.

MODO PADRÃO: DRY-RUN. Sem `--executar` nada é enviado ao servidor; o script lê o
SQLite, monta os lotes, valida tudo o que dá para validar offline e imprime o
plano de carga. Escrever no Neo4j exige `--executar` explicitamente.

Uso:
    # 1) inspecionar o plano (não conecta em nada)
    python -m scripts.ordem3.etl_neo4j --sqlite roots_of_brazil_dev.db

    # 2) revisar o Cypher que seria executado
    python -m scripts.ordem3.etl_neo4j --sqlite roots_of_brazil_dev.db \\
        --emitir-cypher /tmp/carga_ordem3.cypher

    # 3) carregar de verdade (exige NEO4J_PASSWORD no ambiente)
    python -m scripts.ordem3.etl_neo4j --sqlite roots_of_brazil_dev.db --executar

Assim como na Ordem 2: se qualquer contagem pós-carga divergir do Relatório de
Auditoria Sprint 2 (381 nós, 1.585 arestas, 18 órfãos), o script PARA com código
de saída 1 e reporta a divergência — nunca ajusta dado para bater número.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Permite `python scripts/ordem3/etl_neo4j.py` além de `python -m scripts.ordem3.etl_neo4j`.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.models import grafo  # noqa: E402
from app.models.grafo import (  # noqa: E402
    LABEL_OBJETO_ROOTS,
    NOS,
    RELACOES,
    TIPOS_RELACAO,
    TOTAL_NOS_ESPERADO,
    TOTAL_ORFAOS_ESPERADO,
    TOTAL_RELACOES_ESPERADO,
    EspecNo,
)

SQLITE_PADRAO = Path("roots_of_brazil_dev.db")
TAMANHO_LOTE_PADRAO = 500


class DivergenciaDeCarga(RuntimeError):
    """Contagem pós-carga diferente do baseline auditado — a carga é rejeitada."""


# =============================================================================
# Leitura da fonte (SQLite da Ordem 2, READ-ONLY)
# =============================================================================

def abre_sqlite_somente_leitura(caminho: Path) -> sqlite3.Connection:
    if not caminho.exists():
        raise FileNotFoundError(
            f"Banco da Ordem 2 não encontrado em {caminho}. "
            "Rode antes: python scripts/ordem2/etl.py Corpus_Fundador_v1.1.xlsx"
        )
    conn = sqlite3.connect(f"file:{caminho}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _props_sem_nulos(linha: sqlite3.Row) -> dict[str, Any]:
    """Neo4j não armazena propriedade com valor nulo — colunas NULL são omitidas.

    Omitir (em vez de gravar string vazia) preserva a distinção entre "campo não
    informado" e "campo informado como vazio", que o Dicionário v1.2 trata como
    coisas diferentes.
    """
    return {chave: valor for chave, valor in dict(linha).items() if valor is not None}


def le_nos(conn: sqlite3.Connection, spec: EspecNo) -> list[dict[str, Any]]:
    """Uma linha da tabela vira `{id, props}` — props = todas as colunas não nulas."""
    linhas = conn.execute(f"SELECT * FROM {spec.tabela_sqlite}").fetchall()
    lote: list[dict[str, Any]] = []
    for linha in linhas:
        props = _props_sem_nulos(linha)
        objeto_id = props["id"]
        if grafo.label_para_id(objeto_id) != spec.label:
            raise DivergenciaDeCarga(
                f"{objeto_id!r} está na tabela {spec.tabela_sqlite} mas o prefixo do ID "
                f"resolve para {grafo.label_para_id(objeto_id)}, não {spec.label}"
            )
        lote.append({"id": objeto_id, "props": props})
    return lote


def le_relacoes(conn: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
    """Arestas agrupadas por tipo — um lote por tipo, porque o Neo4j 5 não
    parametriza o tipo do relacionamento (ele é interpolado após whitelist)."""
    por_tipo: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for linha in conn.execute("SELECT * FROM relacoes").fetchall():
        dados = dict(linha)
        tipo = grafo.valida_tipo_relacao(dados["tipo_relacao"])
        props = {
            chave: valor
            for chave, valor in dados.items()
            if chave in grafo.PROPRIEDADES_ARESTA and valor is not None
        }
        por_tipo[tipo].append(
            {
                "rel_id": dados["rel_id"],
                "origem_id": dados["origem_id"],
                "destino_id": dados["destino_id"],
                "props": props,
            }
        )
    return dict(por_tipo)


# =============================================================================
# Validação offline (roda em dry-run, antes de qualquer escrita)
# =============================================================================

@dataclass
class PlanoDeCarga:
    """O que seria escrito, mais o resultado das checagens que independem do servidor."""

    nos_por_label: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    relacoes_por_tipo: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    divergencias: list[str] = field(default_factory=list)

    @property
    def total_nos(self) -> int:
        return sum(len(v) for v in self.nos_por_label.values())

    @property
    def total_relacoes(self) -> int:
        return sum(len(v) for v in self.relacoes_por_tipo.values())


def monta_plano(conn: sqlite3.Connection) -> PlanoDeCarga:
    """Lê a fonte inteira, monta os lotes e roda todas as checagens offline."""
    plano = PlanoDeCarga()

    for spec in NOS:
        plano.nos_por_label[spec.label] = le_nos(conn, spec)
    plano.relacoes_por_tipo = le_relacoes(conn)

    plano.divergencias.extend(_confere_contagens(plano))
    plano.divergencias.extend(_confere_integridade(plano))
    return plano


def _confere_contagens(plano: PlanoDeCarga) -> list[str]:
    """Contagens contra o baseline homologado (Relatório de Auditoria Sprint 2)."""
    divergencias: list[str] = []
    for spec in NOS:
        obtido = len(plano.nos_por_label.get(spec.label, []))
        if obtido != spec.contagem_esperada:
            divergencias.append(
                f"nós {spec.label}: esperado {spec.contagem_esperada}, obtido {obtido}"
            )
    if plano.total_nos != TOTAL_NOS_ESPERADO:
        divergencias.append(f"total de nós: esperado {TOTAL_NOS_ESPERADO}, obtido {plano.total_nos}")

    for spec_rel in RELACOES:
        obtido = len(plano.relacoes_por_tipo.get(spec_rel.tipo, []))
        if obtido != spec_rel.instancias_esperadas:
            divergencias.append(
                f"arestas {spec_rel.tipo}: esperado {spec_rel.instancias_esperadas}, obtido {obtido}"
            )
    if plano.total_relacoes != TOTAL_RELACOES_ESPERADO:
        divergencias.append(
            f"total de arestas: esperado {TOTAL_RELACOES_ESPERADO}, obtido {plano.total_relacoes}"
        )
    return divergencias


def _confere_integridade(plano: PlanoDeCarga) -> list[str]:
    """UUID único, rel_id único, pontas existentes, domain/range da ontologia, peso em [0,1].

    A checagem de domain/range é o ganho real da Ordem 3 sobre a Ordem 2: no
    relacional `relacoes` é uma tabela plana com FK polimórfica e o
    `rdfs:domain`/`rdfs:range` da ontologia não era verificável por constraint.
    """
    divergencias: list[str] = []

    label_por_id: dict[str, str] = {}
    uuids: dict[str, str] = {}
    for label, lote in plano.nos_por_label.items():
        for item in lote:
            objeto_id = item["id"]
            if objeto_id in label_por_id:
                divergencias.append(f"id duplicado entre catálogos: {objeto_id}")
            label_por_id[objeto_id] = label
            uuid_ = item["props"].get("uuid")
            if uuid_ is None:
                divergencias.append(f"{objeto_id} sem uuid")
            elif uuid_ in uuids:
                divergencias.append(f"uuid duplicado: {uuid_} ({uuids[uuid_]} e {objeto_id})")
            else:
                uuids[uuid_] = objeto_id

    rel_ids: set[str] = set()
    com_aresta: set[str] = set()
    for tipo, lote in plano.relacoes_por_tipo.items():
        spec_rel = grafo.RELACAO_POR_TIPO[tipo]
        for item in lote:
            rel_id = item["rel_id"]
            if rel_id in rel_ids:
                divergencias.append(f"rel_id duplicado: {rel_id}")
            rel_ids.add(rel_id)

            origem_id, destino_id = item["origem_id"], item["destino_id"]
            label_origem = label_por_id.get(origem_id)
            label_destino = label_por_id.get(destino_id)
            if label_origem is None:
                divergencias.append(f"{rel_id}: origem_id {origem_id} não existe em nenhum catálogo")
                continue
            if label_destino is None:
                divergencias.append(f"{rel_id}: destino_id {destino_id} não existe em nenhum catálogo")
                continue
            com_aresta.update((origem_id, destino_id))

            if label_origem not in spec_rel.origem:
                divergencias.append(
                    f"{rel_id}: {tipo} tem origem {label_origem}, mas rdfs:domain admite "
                    f"{'/'.join(spec_rel.origem)}"
                )
            if label_destino not in spec_rel.destino:
                divergencias.append(
                    f"{rel_id}: {tipo} tem destino {label_destino}, mas rdfs:range admite "
                    f"{'/'.join(spec_rel.destino)}"
                )

            peso = item["props"].get("peso")
            if peso is None or not (0.0 <= float(peso) <= 1.0):
                divergencias.append(f"{rel_id}: peso {peso!r} fora de [0.0, 1.0]")

    orfaos = len(label_por_id) - len(com_aresta)
    if orfaos != TOTAL_ORFAOS_ESPERADO:
        divergencias.append(f"órfãos: esperado {TOTAL_ORFAOS_ESPERADO}, obtido {orfaos}")

    return divergencias


# =============================================================================
# Emissão de Cypher (revisável antes de qualquer execução)
# =============================================================================

def _literal_cypher(valor: Any) -> str:
    if valor is None:
        return "null"
    if isinstance(valor, bool):
        return "true" if valor else "false"
    if isinstance(valor, (int, float)):
        return repr(valor)
    texto = str(valor).replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
    return f"'{texto}'"


def _mapa_cypher(dados: dict[str, Any]) -> str:
    return "{" + ", ".join(f"{k}: {_literal_cypher(v)}" for k, v in sorted(dados.items())) + "}"


def emite_cypher(plano: PlanoDeCarga, destino: Path, *, tamanho_lote: int) -> None:
    """Escreve, em arquivo, o Cypher exato que `--executar` enviaria.

    Serve para revisão humana antes de autorizar a carga — é o artefato que
    fecha a exigência "me mostre o plano antes de rodar contra dados reais".
    """
    partes: list[str] = [
        "// Roots of Brazil — carga da Ordem 3 (GERADO POR scripts/ordem3/etl_neo4j.py)",
        "// Este arquivo é o plano de execução, não a fonte da verdade. Não editar à mão.",
        "",
        "// --- 1. Schema (constraints + índices) ---",
        "",
        grafo.cypher_schema(),
        "",
        "// --- 2. Nós ---",
        "",
    ]
    for label, lote in plano.nos_por_label.items():
        if not lote:
            partes.append(f"// {label}: 0 linhas (nada a carregar)")
            continue
        for bloco in _em_lotes(lote, tamanho_lote):
            linhas = ", ".join(
                _mapa_cypher({"id": item["id"], "props": item["props"]}) for item in bloco
            )
            partes.append(f":param linhas => [{linhas}]")
            partes.append(grafo.cypher_merge_nos(label) + ";")
            partes.append("")

    partes.extend(["// --- 3. Arestas ---", ""])
    for tipo in TIPOS_RELACAO:
        lote = plano.relacoes_por_tipo.get(tipo, [])
        if not lote:
            partes.append(f"// {tipo}: 0 instâncias na v1.1 (tipo reservado no enum)")
            continue
        for bloco in _em_lotes(lote, tamanho_lote):
            linhas = ", ".join(_mapa_cypher(item) for item in bloco)
            partes.append(f":param linhas => [{linhas}]")
            partes.append(grafo.cypher_merge_relacoes(tipo) + ";")
            partes.append("")

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("\n".join(partes).rstrip("\n") + "\n", encoding="utf-8")


def _em_lotes(sequencia: Sequence[Any], tamanho: int) -> Iterable[Sequence[Any]]:
    for inicio in range(0, len(sequencia), tamanho):
        yield sequencia[inicio : inicio + tamanho]


# =============================================================================
# Execução real (só com --executar)
# =============================================================================

def aplica_schema(ses: Any) -> int:
    """Cria constraints e índices. Todos são `IF NOT EXISTS` — reexecutável."""
    comandos = grafo.cypher_constraints() + grafo.cypher_indices()
    for comando in comandos:
        ses.run(comando.rstrip(";"))
    return len(comandos)


def carrega(ses: Any, plano: PlanoDeCarga, *, tamanho_lote: int) -> None:
    """Envia os lotes de nós e depois os de arestas (nós primeiro: o MATCH depende deles)."""
    for label, lote in plano.nos_por_label.items():
        for bloco in _em_lotes(lote, tamanho_lote):
            ses.run(grafo.cypher_merge_nos(label), linhas=list(bloco))
    for tipo, lote in plano.relacoes_por_tipo.items():
        for bloco in _em_lotes(lote, tamanho_lote):
            ses.run(grafo.cypher_merge_relacoes(tipo), linhas=list(bloco))


def valida_pos_carga(ses: Any) -> list[str]:
    """Reconsulta o servidor e compara com o baseline auditado. Nada é corrigido aqui."""
    from app.database.neo4j import escalar

    divergencias: list[str] = []

    contagens = {
        registro["label"]: registro["n"]
        for registro in ses.run(grafo.cypher_conta_nos_por_label(), labels=list(grafo.LABELS))
    }
    for spec in NOS:
        obtido = contagens.get(spec.label, 0)
        if obtido != spec.contagem_esperada:
            divergencias.append(f"nós {spec.label}: esperado {spec.contagem_esperada}, obtido {obtido}")

    total_nos = escalar(ses, f"MATCH (n:{LABEL_OBJETO_ROOTS}) RETURN count(n)")
    if total_nos != TOTAL_NOS_ESPERADO:
        divergencias.append(f"total de nós: esperado {TOTAL_NOS_ESPERADO}, obtido {total_nos}")

    por_tipo = {
        registro["tipo"]: registro["n"]
        for registro in ses.run(grafo.cypher_conta_relacoes_por_tipo(), tipos=list(TIPOS_RELACAO))
    }
    for spec_rel in RELACOES:
        obtido = por_tipo.get(spec_rel.tipo, 0)
        if obtido != spec_rel.instancias_esperadas:
            divergencias.append(
                f"arestas {spec_rel.tipo}: esperado {spec_rel.instancias_esperadas}, obtido {obtido}"
            )
    total_rel = sum(por_tipo.values())
    if total_rel != TOTAL_RELACOES_ESPERADO:
        divergencias.append(f"total de arestas: esperado {TOTAL_RELACOES_ESPERADO}, obtido {total_rel}")

    orfaos = escalar(ses, grafo.cypher_conta_orfaos())
    if orfaos != TOTAL_ORFAOS_ESPERADO:
        divergencias.append(f"órfãos: esperado {TOTAL_ORFAOS_ESPERADO}, obtido {orfaos}")

    duplicados = escalar(ses, grafo.cypher_rel_ids_duplicados(), tipos=list(TIPOS_RELACAO))
    if duplicados:
        divergencias.append(f"rel_id duplicado no grafo: {duplicados} ocorrência(s)")

    fora_da_faixa = escalar(ses, grafo.cypher_peso_fora_da_faixa(), tipos=list(TIPOS_RELACAO))
    if fora_da_faixa:
        divergencias.append(f"peso fora de [0,1] ou ausente: {fora_da_faixa} aresta(s)")

    for spec_rel in RELACOES:
        violacoes = escalar(ses, grafo.cypher_viola_dominio_imagem(spec_rel.tipo))
        if violacoes:
            divergencias.append(
                f"{spec_rel.tipo}: {violacoes} aresta(s) violam rdfs:domain/rdfs:range da ontologia"
            )

    return divergencias


# =============================================================================
# CLI
# =============================================================================

def imprime_plano(plano: PlanoDeCarga, *, tamanho_lote: int) -> None:
    print("=" * 72)
    print("PLANO DE CARGA — Ordem 3 (Neo4j)")
    print("=" * 72)
    print(f"\nSchema: {len(grafo.cypher_constraints())} constraints + "
          f"{len(grafo.cypher_indices())} índices (todos IF NOT EXISTS)")

    print(f"\nNós ({plano.total_nos} de {TOTAL_NOS_ESPERADO} esperados):")
    for spec in NOS:
        obtido = len(plano.nos_por_label.get(spec.label, []))
        marca = "ok " if obtido == spec.contagem_esperada else "!! "
        lotes = -(-obtido // tamanho_lote)
        print(f"  {marca}{spec.label:<12} {obtido:>5} (esperado {spec.contagem_esperada:>5}) "
              f"— {lotes} lote(s)")

    print(f"\nArestas ({plano.total_relacoes} de {TOTAL_RELACOES_ESPERADO} esperadas):")
    for spec_rel in RELACOES:
        obtido = len(plano.relacoes_por_tipo.get(spec_rel.tipo, []))
        marca = "ok " if obtido == spec_rel.instancias_esperadas else "!! "
        origem = "|".join(spec_rel.origem) if len(spec_rel.origem) <= 2 else "ObjetoRoots"
        destino = "|".join(spec_rel.destino) if len(spec_rel.destino) <= 2 else "ObjetoRoots"
        print(f"  {marca}{spec_rel.tipo:<22} {obtido:>5} (esperado {spec_rel.instancias_esperadas:>5}) "
              f"— ({origem})-[:{spec_rel.tipo}]->({destino})")

    if plano.divergencias:
        print(f"\nDIVERGÊNCIAS ({len(plano.divergencias)}):")
        for divergencia in plano.divergencias[:50]:
            print(f"  - {divergencia}")
        if len(plano.divergencias) > 50:
            print(f"  ... e mais {len(plano.divergencias) - 50}")
    else:
        print("\nValidação offline: sem divergências contra o baseline da Auditoria Sprint 2.")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="ETL da Ordem 3 — projeta o corpus da Ordem 2 (SQLite) no Neo4j.",
    )
    parser.add_argument("--sqlite", type=Path, default=SQLITE_PADRAO,
                        help=f"banco da Ordem 2, aberto READ-ONLY (default: {SQLITE_PADRAO})")
    parser.add_argument("--executar", action="store_true",
                        help="escreve de fato no Neo4j. SEM esta flag o script é dry-run "
                             "e não abre conexão nenhuma.")
    parser.add_argument("--limpar", action="store_true",
                        help="apaga o subgrafo :ObjetoRoots antes de carregar "
                             "(exige --executar; não toca em outros nós do banco)")
    parser.add_argument("--emitir-cypher", type=Path, default=None, metavar="ARQUIVO",
                        help="grava o Cypher que seria executado, para revisão")
    parser.add_argument("--emitir-schema", type=Path, default=None, metavar="ARQUIVO",
                        help="regrava schemas/ddl_neo4j.cypher a partir de app/models/grafo.py")
    parser.add_argument("--tamanho-lote", type=int, default=TAMANHO_LOTE_PADRAO,
                        help=f"linhas por UNWIND (default: {TAMANHO_LOTE_PADRAO})")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    if args.emitir_schema is not None:
        args.emitir_schema.parent.mkdir(parents=True, exist_ok=True)
        args.emitir_schema.write_text(grafo.cypher_schema(), encoding="utf-8")
        print(f"schema do grafo escrito em {args.emitir_schema}")
        if not args.executar and args.emitir_cypher is None:
            return 0

    if args.limpar and not args.executar:
        print("--limpar só faz sentido junto com --executar. Nada foi feito.")
        return 2

    conn = abre_sqlite_somente_leitura(args.sqlite)
    try:
        plano = monta_plano(conn)
    finally:
        conn.close()

    imprime_plano(plano, tamanho_lote=args.tamanho_lote)

    if args.emitir_cypher is not None:
        emite_cypher(plano, args.emitir_cypher, tamanho_lote=args.tamanho_lote)
        print(f"\nCypher de carga escrito em {args.emitir_cypher}")

    if plano.divergencias:
        print("\nDIVERGÊNCIA DETECTADA — PARANDO CONFORME A MESMA RESTRIÇÃO DA ORDEM 2.")
        print("Nenhum dado foi enviado ao Neo4j.")
        return 1

    if not args.executar:
        print("\nDRY-RUN: nada foi enviado ao Neo4j. Para carregar de verdade, "
              "rode de novo com --executar.")
        return 0

    from app.database.neo4j import carrega_config, sessao, verifica_conectividade

    config = carrega_config()
    if not verifica_conectividade(config):
        print(f"\nNeo4j inacessível em {config.uri}. Suba o serviço "
              "(docker compose up -d neo4j) e confira NEO4J_USER/NEO4J_PASSWORD.")
        return 3

    with sessao(config) as ses:
        if args.limpar:
            ses.run(grafo.cypher_limpa_grafo())
            print("\nsubgrafo :ObjetoRoots removido")
        n_comandos = aplica_schema(ses)
        print(f"schema aplicado: {n_comandos} comandos")
        carrega(ses, plano, tamanho_lote=args.tamanho_lote)
        print("carga concluída, validando contra o baseline auditado...")
        divergencias = valida_pos_carga(ses)

    if divergencias:
        print("\nDIVERGÊNCIA PÓS-CARGA — PARANDO:")
        for divergencia in divergencias:
            print(f"  - {divergencia}")
        return 1

    print(f"\nCarga validada. Nós: {TOTAL_NOS_ESPERADO}. Arestas: {TOTAL_RELACOES_ESPERADO}. "
          f"Órfãos: {TOTAL_ORFAOS_ESPERADO}. Domain/range da ontologia: sem violações.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
