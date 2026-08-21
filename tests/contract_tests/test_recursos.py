"""Testes de contrato por recurso — Seção 2 da Especificação Conceitual.

Um teste de listagem e um de detalhe para cada um dos 7 recursos, com a
resposta real validada contra o schema publicado. Cobre o critério "≥1 teste de
contrato por recurso".

Resolvidos pelo banco relacional (Ordem 2); a navegação, que depende do grafo,
está em `test_grafo.py`.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from app.models.catalogo import RECURSOS, Recurso  # noqa: E402
from tests.contract_tests.test_contrato_openapi import valida  # noqa: E402

#: Contagens do baseline da Auditoria Sprint 2, conferidas na Ordem 2 e na
#: carga da Ordem 3. Se a API devolver outro total, ou o corpus mudou sem
#: nova homologação, ou o filtro está errado.
TOTAIS = {"ingredientes": 130, "receitas": 136, "tecnicas": 38, "povos": 17,
          "territorios": 18, "biomas": 7, "patrimonio": 35}


@pytest.mark.parametrize("recurso", RECURSOS, ids=lambda r: r.nome)
def test_listagem_bate_com_o_baseline(
    client: TestClient, spec: dict[str, Any], recurso: Recurso
) -> None:
    """A listagem devolve o total homologado e valida contra o schema de página."""
    resposta = client.get(f"/v1/{recurso.nome}", params={"page_size": 5})
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["total"] == TOTAIS[recurso.nome]
    assert len(corpo["items"]) == min(5, TOTAIS[recurso.nome])
    valida(spec, f"Pagina{recurso.singular}", corpo)


@pytest.mark.parametrize("recurso", RECURSOS, ids=lambda r: r.nome)
def test_detalhe_valida_contra_o_schema(
    client: TestClient, spec: dict[str, Any], recurso: Recurso
) -> None:
    """O detalhe do exemplo do contrato existe e casa com o schema publicado."""
    resposta = client.get(f"/v1/{recurso.nome}/{recurso.exemplo_id}")
    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["id"] == recurso.exemplo_id
    valida(spec, recurso.singular, corpo)


@pytest.mark.parametrize("recurso", RECURSOS, ids=lambda r: r.nome)
def test_detalhe_traz_links_de_navegacao(client: TestClient, recurso: Recurso) -> None:
    """Seção 1: a resposta oferece os caminhos de navegação, sem o cliente montar."""
    corpo = client.get(f"/v1/{recurso.nome}/{recurso.exemplo_id}").json()
    assert set(corpo["_links"]) == {n.sub for n in recurso.navegacoes}
    for sub, url in corpo["_links"].items():
        assert url == f"/v1/{recurso.nome}/{recurso.exemplo_id}/{sub}"


@pytest.mark.parametrize("recurso", RECURSOS, ids=lambda r: r.nome)
def test_confiabilidade_sempre_presente(client: TestClient, recurso: Recurso) -> None:
    """Seção 1: "a API nunca esconde o grau de certeza de uma informação"."""
    if recurso.nome == "biomas":
        pytest.skip("Bioma não tem coluna confiabilidade no Dicionário v1.2 (Seção 24).")
    corpo = client.get(f"/v1/{recurso.nome}", params={"page_size": 5}).json()
    for item in corpo["items"]:
        assert item["confiabilidade"].startswith(("🟢", "🟡", "🔵", "🔴"))


# =============================================================
# Filtros da Seção 2
# =============================================================


def test_filtro_classe_de_ingrediente(client: TestClient) -> None:
    """Seção 2.1: classe ∈ {Vegetal, Animal, Processado/Outro}."""
    corpo = client.get("/v1/ingredientes", params={"classe": "Vegetal", "page_size": 100}).json()
    assert corpo["total"] > 0
    assert all(i["classe"] == "Vegetal" for i in corpo["items"])


def test_filtro_classe_invalida_e_400(client: TestClient) -> None:
    corpo = client.get("/v1/ingredientes", params={"classe": "Mineral"}).json()
    assert corpo["total"] == 0  # valor fora do domínio simplesmente não casa


def test_filtro_q_busca_em_nome_e_nomes_regionais(client: TestClient) -> None:
    """Seção 2.1: q busca em 'Nome principal' e 'Nomes regionais'."""
    corpo = client.get("/v1/ingredientes", params={"q": "mandioca", "page_size": 100}).json()
    assert corpo["total"] > 0
    for item in corpo["items"]:
        alvo = (item.get("nome_principal", "") + " " + (item.get("nomes_regionais") or "")).lower()
        assert "mandioca" in alvo


def test_filtro_confiabilidade_casa_por_prefixo(client: TestClient) -> None:
    """O Dicionário permite texto livre após o emoji — o filtro casa o prefixo.

    A Ordem 2 encontrou '🔵 Inferido com cautela' no corpus real; um filtro por
    igualdade exata perderia essas linhas.
    """
    corpo = client.get("/v1/ingredientes",
                       params={"confiabilidade": "🟢 Confirmado em várias fontes",
                               "page_size": 100}).json()
    assert corpo["total"] > 0
    assert all(i["confiabilidade"].startswith("🟢") for i in corpo["items"])


def test_confiabilidade_fora_do_dominio_e_400(client: TestClient) -> None:
    resposta = client.get("/v1/ingredientes", params={"confiabilidade": "🟣 Inventado"})
    assert resposta.status_code == 400
    assert resposta.json()["error"]["code"] == "INVALID_PARAMETER"


def test_filtro_estado_e_regiao_de_receita(client: TestClient) -> None:
    """Seção 2.2: receitas filtram por estado e região."""
    corpo = client.get("/v1/receitas", params={"regiao": "Norte", "page_size": 100}).json()
    assert corpo["total"] > 0
    assert all(i["regiao"] == "Norte" for i in corpo["items"])


def test_filtro_oficial_ibge_separa_o_bioma_extraoficial(client: TestClient) -> None:
    """Seção 2.6: BIO-000007 (Zona Costeira) não pode se confundir com os 6 do IBGE."""
    oficiais = client.get("/v1/biomas", params={"oficial_ibge": "true"}).json()
    extras = client.get("/v1/biomas", params={"oficial_ibge": "false"}).json()
    assert oficiais["total"] == 6
    assert extras["total"] == 1
    assert extras["items"][0]["id"] == "BIO-000007"
    assert extras["items"][0]["oficial_ibge"] is False


def test_oficial_ibge_e_booleano_no_json(client: TestClient) -> None:
    """No banco é INTEGER 0/1; o contrato promete booleano."""
    corpo = client.get("/v1/biomas/BIO-000001").json()
    assert isinstance(corpo["oficial_ibge"], bool)


def test_parametro_desconhecido_e_recusado(client: TestClient) -> None:
    """Erro de digitação em filtro não pode devolver a lista inteira em silêncio."""
    resposta = client.get("/v1/receitas", params={"categora": "Prato"})
    assert resposta.status_code == 400
    assert "categora" in resposta.json()["error"]["message"]


def test_filtro_de_outro_recurso_e_recusado(client: TestClient) -> None:
    """`classe` existe em /v1/ingredientes, não em /v1/biomas."""
    assert client.get("/v1/biomas", params={"classe": "Vegetal"}).status_code == 400
