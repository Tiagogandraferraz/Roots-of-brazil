"""Testes da camada de conexão da Ordem 3 — rodam offline, sem Neo4j.

Cobrem a leitura de configuração e a construção do driver. Abrir sessão e
consultar exige servidor e fica em `test_carga_neo4j.py`.
"""

from __future__ import annotations

import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

pytest.importorskip("neo4j", reason="driver neo4j não instalado")

from app.database.neo4j import (  # noqa: E402
    BANCO_PADRAO,
    ConfiguracaoNeo4j,
    cria_driver,
    verifica_conectividade,
)

VARIAVEIS = ("NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD", "NEO4J_DATABASE")


@pytest.fixture
def ambiente_limpo(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    for var in VARIAVEIS:
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


def test_le_as_variaveis_do_docker_compose(ambiente_limpo: pytest.MonkeyPatch) -> None:
    """São as mesmas três variáveis que o compose injeta no serviço `api`."""
    ambiente_limpo.setenv("NEO4J_URI", "bolt://localhost:7687")
    ambiente_limpo.setenv("NEO4J_USER", "neo4j")
    ambiente_limpo.setenv("NEO4J_PASSWORD", "segredo")

    config = ConfiguracaoNeo4j.do_ambiente()
    assert config.uri == "bolt://localhost:7687"
    assert config.usuario == "neo4j"
    assert config.senha == "segredo"
    assert config.banco == BANCO_PADRAO  # NEO4J_DATABASE é opcional


def test_banco_configuravel(ambiente_limpo: pytest.MonkeyPatch) -> None:
    """NEO4J_DATABASE só faz diferença no Enterprise, mas é respeitado."""
    for var, valor in (("NEO4J_URI", "bolt://x"), ("NEO4J_USER", "u"), ("NEO4J_PASSWORD", "p")):
        ambiente_limpo.setenv(var, valor)
    ambiente_limpo.setenv("NEO4J_DATABASE", "corpus")
    assert ConfiguracaoNeo4j.do_ambiente().banco == "corpus"


def test_variavel_ausente_falha_na_largada(ambiente_limpo: pytest.MonkeyPatch) -> None:
    """Faltando configuração, o erro é imediato e nomeia o que falta.

    Melhor do que um driver que só quebra na primeira query, longe da causa.
    """
    ambiente_limpo.setenv("NEO4J_URI", "bolt://localhost:7687")
    with pytest.raises(RuntimeError) as excinfo:
        ConfiguracaoNeo4j.do_ambiente()
    mensagem = str(excinfo.value)
    assert "NEO4J_USER" in mensagem
    assert "NEO4J_PASSWORD" in mensagem
    assert "NEO4J_URI" not in mensagem  # essa estava definida


def test_erro_de_configuracao_nao_vaza_a_senha(ambiente_limpo: pytest.MonkeyPatch) -> None:
    """A mensagem lista nomes de variáveis, nunca valores."""
    ambiente_limpo.setenv("NEO4J_PASSWORD", "senha-secreta")
    with pytest.raises(RuntimeError) as excinfo:
        ConfiguracaoNeo4j.do_ambiente()
    assert "senha-secreta" not in str(excinfo.value)


def test_configuracao_e_imutavel() -> None:
    """Frozen dataclass: ninguém reaponta a conexão em runtime por engano."""
    config = ConfiguracaoNeo4j(uri="bolt://x", usuario="u", senha="p")
    with pytest.raises(FrozenInstanceError):
        config.uri = "bolt://outro"  # type: ignore[misc]


def test_cria_driver_nao_conecta_na_construcao() -> None:
    """O driver do Neo4j é preguiçoso: construir não abre socket.

    Por isso `verifica_conectividade` existe — só ela força o handshake.
    """
    driver = cria_driver(ConfiguracaoNeo4j(uri="bolt://localhost:7687", usuario="u", senha="p"))
    try:
        assert driver is not None
    finally:
        driver.close()


def test_verifica_conectividade_devolve_false_sem_configuracao(
    ambiente_limpo: pytest.MonkeyPatch,
) -> None:
    """Sem servidor nem configuração, responde False em vez de levantar.

    É o que permite aos testes de integração se pularem em vez de quebrar a
    suíte num ambiente sem banco de grafo.
    """
    assert verifica_conectividade() is False
