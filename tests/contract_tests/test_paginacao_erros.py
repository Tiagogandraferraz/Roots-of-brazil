"""Paginação, ordenação e formato de erro — Seção 5 da Especificação Conceitual."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from app.models.catalogo import PAGE_SIZE_MAXIMO, PAGE_SIZE_PADRAO  # noqa: E402
from tests.contract_tests.test_contrato_openapi import valida  # noqa: E402


# =============================================================
# 5.1 Paginação
# =============================================================


def test_envelope_tem_os_quatro_campos(client: TestClient) -> None:
    """Seção 5.1: "Resposta inclui total, page, page_size, items"."""
    corpo = client.get("/v1/receitas").json()
    assert set(corpo) == {"total", "page", "page_size", "items"}


def test_page_size_padrao(client: TestClient) -> None:
    corpo = client.get("/v1/receitas").json()
    assert corpo["page_size"] == PAGE_SIZE_PADRAO
    assert len(corpo["items"]) == PAGE_SIZE_PADRAO


def test_paginas_nao_se_sobrepoem(client: TestClient) -> None:
    p1 = client.get("/v1/receitas", params={"page": 1, "page_size": 10}).json()
    p2 = client.get("/v1/receitas", params={"page": 2, "page_size": 10}).json()
    assert {i["id"] for i in p1["items"]}.isdisjoint({i["id"] for i in p2["items"]})
    assert p1["total"] == p2["total"] == 136


def test_pagina_alem_do_fim_vem_vazia_mas_com_total(client: TestClient) -> None:
    """Página inexistente não é erro — é uma página vazia, com o total correto."""
    corpo = client.get("/v1/receitas", params={"page": 999}).json()
    assert corpo["items"] == []
    assert corpo["total"] == 136


def test_page_size_acima_do_maximo_e_400(client: TestClient) -> None:
    """Seção 5.1: "page_size máximo sugerido: 100"."""
    resposta = client.get("/v1/receitas", params={"page_size": PAGE_SIZE_MAXIMO + 1})
    assert resposta.status_code == 400
    assert resposta.json()["error"]["code"] == "INVALID_PARAMETER"


def test_page_size_no_maximo_e_aceito(client: TestClient) -> None:
    corpo = client.get("/v1/receitas", params={"page_size": PAGE_SIZE_MAXIMO}).json()
    assert len(corpo["items"]) == PAGE_SIZE_MAXIMO


@pytest.mark.parametrize("valor", ["0", "-1", "abc", "1.5"])
def test_page_invalido_e_400(client: TestClient, valor: str) -> None:
    assert client.get("/v1/receitas", params={"page": valor}).status_code == 400


# =============================================================
# 5.2 Ordenação
# =============================================================


def test_ordenacao_descendente(client: TestClient) -> None:
    """Exemplo literal da Seção 5.2: ?sort=n_citacoes&order=desc."""
    corpo = client.get("/v1/ingredientes",
                       params={"sort": "n_citacoes", "order": "desc", "page_size": 20}).json()
    citacoes = [i["n_citacoes"] for i in corpo["items"] if i.get("n_citacoes") is not None]
    assert citacoes == sorted(citacoes, reverse=True)


def test_ordenacao_ascendente_inverte(client: TestClient) -> None:
    asc = client.get("/v1/ingredientes",
                     params={"sort": "n_citacoes", "order": "asc", "page_size": 5}).json()
    desc = client.get("/v1/ingredientes",
                      params={"sort": "n_citacoes", "order": "desc", "page_size": 5}).json()
    assert asc["items"][0]["id"] != desc["items"][0]["id"]


def test_order_invalido_e_400(client: TestClient) -> None:
    resposta = client.get("/v1/receitas", params={"order": "aleatorio"})
    assert resposta.status_code == 400
    assert "asc" in resposta.json()["error"]["message"]


def test_sort_por_campo_inexistente_e_400(client: TestClient) -> None:
    """Campo de ordenação vem do cliente; recusar é o que evita SQL inválido."""
    resposta = client.get("/v1/receitas", params={"sort": "coluna_que_nao_existe"})
    assert resposta.status_code == 400
    assert resposta.json()["error"]["code"] == "INVALID_PARAMETER"


def test_sort_nao_permite_injecao(client: TestClient) -> None:
    """`sort` é validado contra a lista de colunas, então não vira SQL."""
    resposta = client.get("/v1/receitas", params={"sort": "id; DROP TABLE receita"})
    assert resposta.status_code == 400
    assert client.get("/v1/receitas").json()["total"] == 136  # tabela intacta


# =============================================================
# 5.3 Formato de erro
# =============================================================


def test_erro_404_tem_o_formato_literal_da_especificacao(
    client: TestClient, spec: dict[str, Any]
) -> None:
    """A Seção 5.3 mostra o corpo exato; a API devolve esse corpo."""
    resposta = client.get("/v1/ingredientes/ING-999999")
    assert resposta.status_code == 404
    corpo = resposta.json()
    assert corpo == {
        "error": {
            "code": "NOT_FOUND",
            "message": "Objeto com ID 'ING-999999' não encontrado.",
            "status": 404,
        }
    }
    valida(spec, "Erro", corpo)


def test_erro_400_valida_contra_o_schema(client: TestClient, spec: dict[str, Any]) -> None:
    resposta = client.get("/v1/receitas", params={"order": "invalido"})
    assert resposta.status_code == 400
    valida(spec, "Erro", resposta.json())


def test_status_no_corpo_bate_com_o_http(client: TestClient) -> None:
    """O campo `status` do corpo não pode divergir do código HTTP."""
    for url, params in [("/v1/ingredientes/ING-999999", {}),
                        ("/v1/receitas", {"order": "x"})]:
        resposta = client.get(url, params=params)
        assert resposta.json()["error"]["status"] == resposta.status_code


def test_erro_422_de_integridade_referencial(client: TestClient, spec: dict[str, Any]) -> None:
    """Seção 5.3: 422 quando origem_id não corresponde a entidade conhecida.

    Diferente de 404: o ID tem forma válida, mas não existe no corpus. É a
    distinção que a própria Seção 5.3 faz entre os dois códigos.
    """
    resposta = client.get("/v1/relacoes", params={"origem_id": "REC-999999"})
    assert resposta.status_code == 422
    corpo = resposta.json()
    assert corpo["error"]["code"] == "REFERENTIAL_INTEGRITY_ERROR"
    valida(spec, "Erro", corpo)


def test_tipo_relacao_fora_do_dominio_e_400(client: TestClient) -> None:
    """Exemplo citado na própria tabela da Seção 5.3."""
    resposta = client.get("/v1/relacoes", params={"tipo_relacao": "INVENTADA"})
    assert resposta.status_code == 400
    assert resposta.json()["error"]["code"] == "INVALID_PARAMETER"


def test_busca_sem_q_e_400(client: TestClient) -> None:
    """`q` é obrigatório na Seção 4; sem ele o pedido não faz sentido."""
    resposta = client.get("/v1/busca")
    assert resposta.status_code == 400
    assert "q" in resposta.json()["error"]["message"]


def test_tipo_de_busca_desconhecido_e_400(client: TestClient) -> None:
    resposta = client.get("/v1/busca", params={"q": "x", "tipos": "receita,planeta"})
    assert resposta.status_code == 400
    assert "planeta" in resposta.json()["error"]["message"]


def test_expand_invalido_e_400(client: TestClient) -> None:
    resposta = client.get("/v1/ingredientes/ING-000031", params={"expand": "planetas"})
    assert resposta.status_code == 400
    assert "planetas" in resposta.json()["error"]["message"]
