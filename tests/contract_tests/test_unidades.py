"""Testes de unidade das peças que os testes de contrato exercitam só de raspão.

Cobrem os caminhos de erro e as conversões que uma requisição feliz não passa:
handlers de exceção, o limitador de taxa isolado e a serialização.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from app.api.erros import (  # noqa: E402
    ErroAPI,
    integridade_referencial,
    nao_encontrado,
    parametro_invalido,
)
from app.api.serializacao import links_de, pagina, serializar  # noqa: E402
from app.core.middleware import LimitadorDeTaxa  # noqa: E402
from app.models.catalogo import ERROS, RECURSO_POR_NOME  # noqa: E402


# =============================================================
# Erros — Seção 5.3
# =============================================================


def test_erro_desconhecido_e_recusado_na_construcao() -> None:
    """Um código fora da Seção 5.3 não pode chegar ao cliente.

    Falhar na construção, e não na serialização, é o que impede a API de
    publicar um código que o `openapi.yaml` não documenta.
    """
    with pytest.raises(ValueError, match="não está na Seção 5.3"):
        ErroAPI("CODIGO_INVENTADO", "qualquer coisa")


@pytest.mark.parametrize(("code", "status"), list(ERROS.items()))
def test_cada_codigo_carrega_o_status_certo(code: str, status: int) -> None:
    assert ErroAPI(code, "mensagem").status == status


def test_corpo_do_erro_tem_a_forma_da_especificacao() -> None:
    corpo = ErroAPI("NOT_FOUND", "sumiu").corpo()
    assert corpo == {"error": {"code": "NOT_FOUND", "message": "sumiu", "status": 404}}


def test_atalhos_de_erro() -> None:
    assert nao_encontrado("ING-000001").code == "NOT_FOUND"
    assert parametro_invalido("x").code == "INVALID_PARAMETER"
    assert integridade_referencial("REC-999999").code == "REFERENTIAL_INTEGRITY_ERROR"


def test_mensagem_de_404_cita_o_id() -> None:
    assert "'ING-000001'" in nao_encontrado("ING-000001").message


# =============================================================
# Limitador de taxa
# =============================================================


def test_limitador_permite_ate_o_limite() -> None:
    limitador = LimitadorDeTaxa(limite=3, janela=60)
    assert [limitador.registrar("ip")[0] for _ in range(3)] == [True, True, True]
    assert limitador.registrar("ip")[0] is False


def test_limitador_conta_restantes_corretamente() -> None:
    limitador = LimitadorDeTaxa(limite=3, janela=60)
    assert [limitador.registrar("ip")[1] for _ in range(3)] == [2, 1, 0]


def test_limitador_separa_por_chave() -> None:
    limitador = LimitadorDeTaxa(limite=1, janela=60)
    assert limitador.registrar("a")[0] is True
    assert limitador.registrar("b")[0] is True
    assert limitador.registrar("a")[0] is False


def test_limitador_informa_a_espera() -> None:
    limitador = LimitadorDeTaxa(limite=1, janela=60)
    limitador.registrar("ip")
    permitido, restantes, espera = limitador.registrar("ip")
    assert (permitido, restantes) == (False, 0)
    assert 1 <= espera <= 61


def test_janela_deslizante_libera_apos_expirar() -> None:
    """Janela de 0 s: a batida anterior já saiu da janela na chamada seguinte.

    É o comportamento que diferencia janela deslizante de contador fixo — e o
    motivo de a implementação limpar a fila pelo tempo, não pelo minuto cheio.
    """
    limitador = LimitadorDeTaxa(limite=1, janela=0)
    assert limitador.registrar("ip")[0] is True
    assert limitador.registrar("ip")[0] is True


def test_limpar_zera_o_estado() -> None:
    limitador = LimitadorDeTaxa(limite=1, janela=60)
    limitador.registrar("ip")
    limitador.limpar()
    assert limitador.registrar("ip")[0] is True


# =============================================================
# Serialização
# =============================================================


def test_serializar_descarta_nulos() -> None:
    recurso = RECURSO_POR_NOME["biomas"]
    saida = serializar(recurso, {"id": "BIO-000001", "nome": "Amazônia", "nome_en": None})
    assert "nome_en" not in saida
    assert saida["nome"] == "Amazônia"


def test_serializar_descarta_campo_fora_do_dicionario() -> None:
    """Última barreira da restrição da Ordem 4.

    Se uma coluna nova aparecer no banco sem entrar no catálogo, ela não vaza
    para a resposta — e o teste de contrato acusa a diferença.
    """
    recurso = RECURSO_POR_NOME["biomas"]
    saida = serializar(recurso, {"id": "BIO-000001", "coluna_intrusa": "vazou"})
    assert "coluna_intrusa" not in saida


def test_serializar_converte_oficial_ibge_para_booleano() -> None:
    """No SQLite é 0/1; a Seção 2.6 exige booleano."""
    recurso = RECURSO_POR_NOME["biomas"]
    assert serializar(recurso, {"id": "BIO-000007", "oficial_ibge": 0})["oficial_ibge"] is False
    assert serializar(recurso, {"id": "BIO-000001", "oficial_ibge": 1})["oficial_ibge"] is True


def test_links_derivam_do_catalogo() -> None:
    links = links_de(RECURSO_POR_NOME["receitas"], "REC-000001")
    assert links == {
        "ingredientes": "/v1/receitas/REC-000001/ingredientes",
        "tecnicas": "/v1/receitas/REC-000001/tecnicas",
        "territorio": "/v1/receitas/REC-000001/territorio",
        "povos": "/v1/receitas/REC-000001/povos",
    }


def test_envelope_de_pagina() -> None:
    assert pagina(7, 1, 20, [{"id": "x"}]) == {
        "total": 7, "page": 1, "page_size": 20, "items": [{"id": "x"}]
    }
