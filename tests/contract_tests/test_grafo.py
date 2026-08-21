"""Navegação e busca global — os endpoints servidos pelo grafo da Ordem 3.

Exigem um Neo4j alcançável com o corpus carregado (381 nós / 1.585 arestas).
Sem ele, cada teste se pula declarando o motivo, em vez de falhar — um
ambiente sem banco de grafo deve dizer que não validou, não fingir que validou.

No GitHub Actions, com os secrets cadastrados, estes testes rodam de verdade
contra o AuraDB.
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

pytestmark = pytest.mark.usefixtures("exige_grafo")

#: Todas as 18 navegações da Seção 2, achatadas para parametrizar.
NAVEGACOES = [(r, n) for r in RECURSOS for n in r.navegacoes]


@pytest.mark.parametrize(
    ("recurso", "nav"), NAVEGACOES, ids=[f"{r.nome}-{n.sub}" for r, n in NAVEGACOES]
)
def test_toda_navegacao_responde(
    client: TestClient, spec: dict[str, Any], recurso: Recurso, nav: Any
) -> None:
    """Os 18 endpoints de navegação respondem e casam com o schema publicado.

    Lista vazia é resultado legítimo — nem todo objeto tem toda relação. O que
    se verifica é que o endpoint existe, resolve pelo grafo e devolve a forma
    prometida.
    """
    resposta = client.get(f"/v1/{recurso.nome}/{recurso.exemplo_id}/{nav.sub}")
    assert resposta.status_code in (200, 404), resposta.text
    if resposta.status_code == 404:
        # Só o sub-recurso singular pode dar 404 por ausência de relação.
        assert nav.singular, f"{recurso.nome}/{nav.sub} devolveu 404 sem ser singular"
        return
    corpo = resposta.json()
    if nav.singular:
        from app.models.catalogo import RECURSO_POR_NOME
        valida(spec, RECURSO_POR_NOME[nav.recurso_destino].singular,
               {k: v for k, v in corpo.items() if k != "_relacao"})
    else:
        assert set(corpo) == {"total", "page", "page_size", "items"}


def test_navegacao_traz_a_proveniencia_da_aresta(client: TestClient) -> None:
    """Seção 1: a API nunca esconde o grau de certeza.

    O ganho concreto do property graph da Ordem 3: peso, fonte e confiabilidade
    são propriedades da aresta e vêm junto, sem reificação.
    """
    corpo = client.get("/v1/receitas/REC-000001/ingredientes").json()
    assert corpo["total"] > 0, "REC-000001 deveria ter ingredientes (USA_INGREDIENTE)"
    item = corpo["items"][0]
    relacao = item["_relacao"]
    assert relacao["tipo_relacao"] == "USA_INGREDIENTE"
    assert 0.0 <= relacao["peso"] <= 1.0
    assert relacao["confiabilidade"].startswith(("🟢", "🟡", "🔵", "🔴"))
    assert item["id"].startswith("ING-")


def test_navegacao_hidrata_com_campos_do_dicionario(client: TestClient) -> None:
    """O grafo dá o ID e a aresta; os campos vêm do relacional."""
    item = client.get("/v1/receitas/REC-000001/ingredientes").json()["items"][0]
    for campo in ("uuid", "slug", "created_at", "version", "nome_pt", "confiabilidade"):
        assert campo in item, f"faltou {campo} na hidratação"


def test_navegacao_inversa_e_simetrica(client: TestClient) -> None:
    """Se a receita usa o ingrediente, o ingrediente é usado pela receita.

    Testa os dois sentidos da mesma aresta: USA_INGREDIENTE direto em
    /receitas/{id}/ingredientes e inverso em /ingredientes/{id}/receitas.
    """
    ingredientes = client.get("/v1/receitas/REC-000001/ingredientes").json()["items"]
    assert ingredientes
    alvo = ingredientes[0]["id"]
    receitas = client.get(f"/v1/ingredientes/{alvo}/receitas",
                          params={"page_size": 100}).json()["items"]
    assert "REC-000001" in {r["id"] for r in receitas}


def test_navegacao_com_uniao_de_relacoes(client: TestClient) -> None:
    """/v1/povos/{id}/ingredientes junta ASSOCIADO_A_POVO e ORIGINARIO_DE.

    A Seção 2.4 descreve as duas; achatar para uma só perderia arestas.
    """
    corpo = client.get("/v1/povos/POV-000001/ingredientes", params={"page_size": 100}).json()
    assert corpo["total"] >= 0
    tipos = {i["_relacao"].get("tipo_relacao") for i in corpo["items"]}
    assert tipos <= {"ASSOCIADO_A_POVO", "ORIGINARIO_DE", None}


def test_navegacao_de_id_inexistente_e_404(client: TestClient) -> None:
    """404 distingue "não existe" de "existe e não tem relação" (lista vazia)."""
    resposta = client.get("/v1/ingredientes/ING-999999/receitas")
    assert resposta.status_code == 404
    assert resposta.json()["error"]["code"] == "NOT_FOUND"


def test_navegacao_pagina(client: TestClient) -> None:
    p1 = client.get("/v1/receitas/REC-000001/ingredientes",
                    params={"page": 1, "page_size": 2}).json()
    if p1["total"] > 2:
        p2 = client.get("/v1/receitas/REC-000001/ingredientes",
                        params={"page": 2, "page_size": 2}).json()
        assert {i["id"] for i in p1["items"]}.isdisjoint({i["id"] for i in p2["items"]})


# =============================================================
# /v1/relacoes — Seção 3
# =============================================================


def test_relacoes_devolve_o_total_do_baseline(client: TestClient, spec: dict[str, Any]) -> None:
    """1.585 arestas — o número homologado na Auditoria Sprint 2."""
    corpo = client.get("/v1/relacoes", params={"page_size": 5}).json()
    assert corpo["total"] == 1585
    valida(spec, "PaginaRelacao", corpo)


@pytest.mark.parametrize(
    ("tipo", "esperado"),
    [("USA_INGREDIENTE", 895), ("ASSOCIADO_A_POVO", 205), ("CULTIVADO_EM", 106),
     ("UTILIZA_TECNICA", 85), ("PREPARADO_COM", 81), ("OCORRE_EM", 77),
     ("ORIGINARIO_DE", 67), ("PATRIMONIO_DE", 38), ("LOCALIZADO_EM_BIOMA", 24),
     ("DERIVA_DE", 7), ("VARIANTE_REGIONAL", 0), ("SIMILAR_A", 0)],
)
def test_relacoes_por_tipo_bate_com_a_auditoria(
    client: TestClient, tipo: str, esperado: int
) -> None:
    """Os 12 contadores por tipo, iguais aos verificados na carga da Ordem 3."""
    corpo = client.get("/v1/relacoes", params={"tipo_relacao": tipo, "page_size": 1}).json()
    assert corpo["total"] == esperado


def test_relacoes_filtra_por_origem(client: TestClient) -> None:
    """Exemplo literal da Seção 3: ?origem_id=REC-000001&tipo_relacao=USA_INGREDIENTE."""
    corpo = client.get("/v1/relacoes", params={"origem_id": "REC-000001",
                                               "tipo_relacao": "USA_INGREDIENTE"}).json()
    assert corpo["total"] > 0
    for item in corpo["items"]:
        assert item["origem_id"] == "REC-000001"
        assert item["tipo_relacao"] == "USA_INGREDIENTE"
        assert item["destino_id"].startswith("ING-")


def test_relacao_traz_peso_e_metodo(client: TestClient) -> None:
    """Passo 2 da Ordem 4: peso e metodo_calculo_peso na resposta."""
    item = client.get("/v1/relacoes", params={"page_size": 1}).json()["items"][0]
    assert 0.0 <= item["peso"] <= 1.0
    assert item["metodo_calculo_peso"]


# =============================================================
# /v1/busca — Seção 4, índice full-text
# =============================================================


def test_busca_encontra_pelo_indice_fulltext(client: TestClient, spec: dict[str, Any]) -> None:
    """Usa `objeto_roots_nome_ft`, criado na carga da Ordem 3."""
    corpo = client.get("/v1/busca", params={"q": "mandioca", "page_size": 20}).json()
    assert corpo["total"] > 0
    valida(spec, "PaginaBusca", corpo)


def test_busca_e_heterogenea_e_marca_o_tipo(client: TestClient) -> None:
    """Seção 4: cada item diz de qual catálogo veio."""
    from app.models.catalogo import TIPOS_BUSCA

    corpo = client.get("/v1/busca", params={"q": "mandioca", "page_size": 50}).json()
    assert all(i["tipo"] in TIPOS_BUSCA for i in corpo["items"])


def test_busca_restringe_por_tipos(client: TestClient) -> None:
    corpo = client.get("/v1/busca",
                       params={"q": "mandioca", "tipos": "ingrediente", "page_size": 50}).json()
    assert all(i["tipo"] == "ingrediente" for i in corpo["items"])


def test_busca_vem_ordenada_por_relevancia(client: TestClient) -> None:
    """O `score` vem do índice full-text, não de ordenação nossa."""
    itens = client.get("/v1/busca", params={"q": "mandioca", "page_size": 20}).json()["items"]
    scores = [i["score"] for i in itens]
    assert scores == sorted(scores, reverse=True)


def test_busca_sem_resultado_devolve_pagina_vazia(client: TestClient) -> None:
    corpo = client.get("/v1/busca", params={"q": "xyzzyxyzzy"}).json()
    assert corpo["total"] == 0 and corpo["items"] == []
