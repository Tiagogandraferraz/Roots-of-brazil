"""
Roots of Brazil — camada de acesso ao Neo4j (Ordem 3).

Só a conexão: configuração por variável de ambiente, criação do driver e um
context manager de sessão. Nenhuma query de domínio mora aqui — a carga fica em
`scripts/ordem3/etl_neo4j.py` e as rotas na Ordem 4.

As variáveis de ambiente são exatamente as que o `docker-compose.yml` já injeta
no serviço `api` desde a Ordem 0 (NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Final

from neo4j import Driver, GraphDatabase, Session

#: Nome do banco padrão do Neo4j 5. Community Edition só permite um banco de
#: usuário, então isso é fixo na prática — configurável para o Enterprise.
BANCO_PADRAO: Final = "neo4j"


@dataclass(frozen=True)
class ConfiguracaoNeo4j:
    """Credenciais e endereço do Neo4j, lidos do ambiente."""

    uri: str
    usuario: str
    senha: str
    banco: str = BANCO_PADRAO

    @classmethod
    def do_ambiente(cls) -> ConfiguracaoNeo4j:
        """Monta a configuração a partir das variáveis de ambiente.

        O usuário é lido de `NEO4J_USER` ou de `NEO4J_USERNAME`: o
        docker-compose deste projeto usa a primeira, mas o arquivo de
        credenciais que o Neo4j AuraDB entrega no provisionamento usa a
        segunda. Aceitar as duas evita um erro de configuração silencioso ao
        colar as credenciais da nuvem direto no `.env`.

        Levanta RuntimeError com mensagem explícita se faltar alguma — falha na
        largada é melhor do que um driver que só quebra na primeira query.
        A senha nunca é impressa nem incluída em mensagens de erro.
        """
        usuario = os.getenv("NEO4J_USER") or os.getenv("NEO4J_USERNAME") or ""
        faltando = [v for v in ("NEO4J_URI", "NEO4J_PASSWORD") if not os.getenv(v)]
        if not usuario:
            faltando.insert(1, "NEO4J_USER (ou NEO4J_USERNAME)")
        if faltando:
            raise RuntimeError(
                f"Variáveis de ambiente do Neo4j ausentes: {', '.join(faltando)}. "
                "Defina-as no .env (ver docker-compose.yml) antes de conectar."
            )
        return cls(
            uri=os.environ["NEO4J_URI"],
            usuario=usuario,
            senha=os.environ["NEO4J_PASSWORD"],
            banco=os.getenv("NEO4J_DATABASE", BANCO_PADRAO),
        )


def cria_driver(config: ConfiguracaoNeo4j | None = None) -> Driver:
    """Cria o driver do Neo4j. O chamador é dono do fechamento (`driver.close()`)."""
    cfg = config or ConfiguracaoNeo4j.do_ambiente()
    return GraphDatabase.driver(cfg.uri, auth=(cfg.usuario, cfg.senha))


@contextmanager
def sessao(config: ConfiguracaoNeo4j | None = None) -> Iterator[Session]:
    """Abre driver e sessão, fechando os dois ao sair do bloco.

    Uso:
        with sessao() as s:
            s.run("MATCH (n:ObjetoRoots) RETURN count(n)")
    """
    cfg = config or ConfiguracaoNeo4j.do_ambiente()
    driver = cria_driver(cfg)
    try:
        with driver.session(database=cfg.banco) as s:
            yield s
    finally:
        driver.close()


def verifica_conectividade(config: ConfiguracaoNeo4j | None = None) -> bool:
    """True se o Neo4j responde ao handshake, False se não. Não levanta.

    Usada pelos testes de integração da Ordem 3 para decidir entre rodar ou
    pular (`pytest.skip`) — sem Neo4j no ar, os testes não devem falhar, devem
    declarar que não rodaram.
    """
    try:
        cfg = config or ConfiguracaoNeo4j.do_ambiente()
        driver = cria_driver(cfg)
    except Exception:
        return False
    try:
        driver.verify_connectivity()
        return True
    except Exception:
        return False
    finally:
        driver.close()
