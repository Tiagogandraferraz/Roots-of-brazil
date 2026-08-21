"""Fixtures dos testes de contrato da Ordem 4.

Os testes validam a API **contra `api/openapi.yaml`**, não contra o que o
código devolve. É a diferença entre um teste de contrato e um teste de
regressão: aqui, se a implementação mudar de forma que o contrato publicado
deixe de descrevê-la, o teste quebra — mesmo que a resposta nova seja
"melhor".
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

BANCO = RAIZ / "roots_of_brazil_dev.db"
OPENAPI = RAIZ / "api" / "openapi.yaml"


def pytest_collection_modifyitems(items: list[Any]) -> None:
    """Pula a suíte inteira, com razão clara, se o corpus não foi gerado."""
    if BANCO.exists():
        return
    marca = pytest.mark.skip(
        reason="roots_of_brazil_dev.db ausente — rode `python scripts/ordem2/etl.py "
               "Corpus_Fundador_v1.1.xlsx` antes dos testes de contrato."
    )
    for item in items:
        item.add_marker(marca)


@pytest.fixture(scope="session")
def spec() -> dict[str, Any]:
    """A especificação OpenAPI publicada — a fonte da verdade destes testes."""
    return yaml.safe_load(OPENAPI.read_text(encoding="utf-8"))


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Cliente HTTP com o limitador de taxa zerado.

    Zerar entre testes é necessário porque o limitador é global ao processo:
    sem isso, o 51º teste começaria a receber 429 por causa dos anteriores.
    """
    from app.core.middleware import limitador

    limitador.limpar()
    from app.main import app

    with TestClient(app) as c:
        yield c
    limitador.limpar()


@pytest.fixture(scope="session")
def grafo_disponivel() -> bool:
    """True se o Neo4j responde — os testes de navegação e busca dependem dele."""
    try:
        from app.database.neo4j import verifica_conectividade

        return verifica_conectividade()
    except Exception:
        return False


@pytest.fixture
def exige_grafo(grafo_disponivel: bool) -> None:
    """Pula o teste, declarando o motivo, quando não há Neo4j alcançável.

    Pular em vez de falhar: um ambiente sem banco de grafo deve declarar que
    não validou, não fingir que validou. No GitHub Actions, com os secrets
    cadastrados, estes testes rodam de verdade.
    """
    if not grafo_disponivel:
        pytest.skip(
            "Neo4j não alcançável — defina NEO4J_URI/NEO4J_USERNAME/NEO4J_PASSWORD. "
            "Navegação (Seção 2) e busca global (Seção 4) dependem do grafo."
        )
