"""Latência p95 — critérios de aceite da Ordem 4.

    GET simples (detalhe)  < 100 ms
    listagem               < 200 ms
    navegação (grafo)      < 300 ms
    busca global           < 500 ms

Medido pelo `TestClient`, ou seja, **sem rede**: o número reflete o custo de
consulta e serialização, não o de transporte. É o que dá para medir de forma
reprodutível em CI; latência ponta a ponta depende do enlace até o AuraDB e da
máquina, e seria um teste instável.

Os alvos de navegação e busca só são exercidos quando há grafo alcançável; sem
ele, os testes se pulam como os demais.
"""

from __future__ import annotations

import statistics
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

#: Repetições por medição. 40 dá um p95 estável sem deixar a suíte lenta.
AMOSTRAS = 40


def p95(client: TestClient, url: str, params: dict[str, Any] | None = None) -> float:
    """Percentil 95 em milissegundos, descartando a primeira chamada.

    A primeira paga o custo de abrir conexão e aquecer cache; incluí-la mediria
    inicialização, não o regime de operação.
    """
    client.get(url, params=params)
    tempos: list[float] = []
    for _ in range(AMOSTRAS):
        inicio = time.perf_counter()
        resposta = client.get(url, params=params)
        tempos.append((time.perf_counter() - inicio) * 1000)
        assert resposta.status_code == 200, resposta.text
    return statistics.quantiles(tempos, n=20)[-1]


def test_p95_detalhe_abaixo_de_100ms(client: TestClient) -> None:
    medido = p95(client, "/v1/ingredientes/ING-000031")
    assert medido < 100, f"p95 do detalhe: {medido:.1f} ms (alvo < 100 ms)"


def test_p95_listagem_abaixo_de_200ms(client: TestClient) -> None:
    medido = p95(client, "/v1/ingredientes", {"page_size": 20})
    assert medido < 200, f"p95 da listagem: {medido:.1f} ms (alvo < 200 ms)"


def test_p95_listagem_cheia_abaixo_de_200ms(client: TestClient) -> None:
    """Pior caso da listagem: página cheia, no teto de 100 itens."""
    medido = p95(client, "/v1/receitas", {"page_size": 100})
    assert medido < 200, f"p95 da listagem cheia: {medido:.1f} ms (alvo < 200 ms)"


def test_p95_listagem_filtrada_abaixo_de_200ms(client: TestClient) -> None:
    medido = p95(client, "/v1/ingredientes", {"classe": "Vegetal", "sort": "n_citacoes",
                                              "order": "desc", "page_size": 50})
    assert medido < 200, f"p95 da listagem filtrada: {medido:.1f} ms (alvo < 200 ms)"


@pytest.mark.usefixtures("exige_grafo")
def test_p95_navegacao_abaixo_de_300ms(client: TestClient) -> None:
    medido = p95(client, "/v1/receitas/REC-000001/ingredientes")
    assert medido < 300, f"p95 da navegação: {medido:.1f} ms (alvo < 300 ms)"


@pytest.mark.usefixtures("exige_grafo")
def test_p95_busca_abaixo_de_500ms(client: TestClient) -> None:
    medido = p95(client, "/v1/busca", {"q": "mandioca"})
    assert medido < 500, f"p95 da busca: {medido:.1f} ms (alvo < 500 ms)"
