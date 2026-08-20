"""
Roots of Brazil — conexão com o Neo4j (Ordem 3).

Camada fina sobre o driver oficial `neo4j`. Só cuida de configuração,
ciclo de vida do driver e verificação de conectividade; nenhuma regra de
domínio mora aqui (o modelo está em `app/models/grafo.py`, a carga em
`scripts/ordem3/etl_neo4j.py`).

Configuração exclusivamente por variável de ambiente, como no `docker-compose.yml`:

    NEO4J_URI       (default: bolt://localhost:7687)
    NEO4J_USER      (default: neo4j)
    NEO4J_PASSWORD  (sem default — obrigatória; nunca embutir senha no código)
    NEO4J_DATABASE  (default: neo4j)

O import do driver é preguiçoso (dentro das funções) para que `app/models/grafo.py`
e os testes de modelo continuem importáveis em ambiente sem o pacote instalado.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.core.logging import get_logger

if TYPE_CHECKING:  # pragma: no cover - apenas para tipagem
    from neo4j import Driver, Session

logger = get_logger(__name__)

URI_PADRAO = "bolt://localhost:7687"
USUARIO_PADRAO = "neo4j"
DATABASE_PADRAO = "neo4j"


class ConfiguracaoNeo4jAusente(RuntimeError):
    """Falta variável de ambiente obrigatória para conectar ao Neo4j."""


@dataclass(frozen=True)
class ConfigNeo4j:
    uri: str
    usuario: str
    senha: str
    database: str

    @property
    def uri_sem_credenciais(self) -> str:
        """URI segura para log — o driver nunca loga a senha, e nós também não."""
        return self.uri


def carrega_config(*, ambiente: dict[str, str] | None = None) -> ConfigNeo4j:
    """Lê a configuração do ambiente. Levanta se `NEO4J_PASSWORD` não estiver definida."""
    env = os.environ if ambiente is None else ambiente
    senha = env.get("NEO4J_PASSWORD", "")
    if not senha:
        raise ConfiguracaoNeo4jAusente(
            "NEO4J_PASSWORD não definida. Defina-a no ambiente (ou no .env usado pelo "
            "docker-compose) antes de conectar — nenhuma senha padrão é assumida."
        )
    return ConfigNeo4j(
        uri=env.get("NEO4J_URI", URI_PADRAO),
        usuario=env.get("NEO4J_USER", USUARIO_PADRAO),
        senha=senha,
        database=env.get("NEO4J_DATABASE", DATABASE_PADRAO),
    )


def cria_driver(config: ConfigNeo4j | None = None) -> Driver:
    """Instancia o driver. Quem chama é responsável por fechá-lo (ou usar `sessao()`)."""
    from neo4j import GraphDatabase

    cfg = config or carrega_config()
    logger.info("abrindo driver neo4j em %s (database=%s)", cfg.uri_sem_credenciais, cfg.database)
    return GraphDatabase.driver(cfg.uri, auth=(cfg.usuario, cfg.senha))


@contextmanager
def sessao(config: ConfigNeo4j | None = None) -> Iterator[Session]:
    """Context manager que abre driver + sessão e fecha ambos ao sair."""
    cfg = config or carrega_config()
    driver = cria_driver(cfg)
    try:
        with driver.session(database=cfg.database) as ses:
            yield ses
    finally:
        driver.close()


def verifica_conectividade(config: ConfigNeo4j | None = None) -> bool:
    """`True` se o servidor responde e autentica; `False` em qualquer falha.

    Não propaga a exceção de propósito: é usada por testes de integração para
    decidir entre rodar e pular (`skip`), e pelo ETL para falhar com mensagem
    própria em vez de um traceback do driver.
    """
    try:
        driver = cria_driver(config)
    except Exception as exc:  # noqa: BLE001 - qualquer falha aqui significa "indisponível"
        logger.warning("neo4j indisponível ao criar driver: %s", exc)
        return False
    try:
        driver.verify_connectivity()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("neo4j indisponível: %s", exc)
        return False
    finally:
        driver.close()


def escalar(ses: Session, cypher: str, **params: Any) -> Any:
    """Roda uma query que devolve uma única linha/coluna e retorna esse valor."""
    registro = ses.run(cypher, **params).single()
    return None if registro is None else registro.value()
