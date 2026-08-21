"""Paridade entre a especificação publicada e a API que roda.

Estes testes são o coração da Ordem 4: garantem que `api/openapi.yaml` não é
documentação decorativa, e sim uma descrição verificada do serviço. Cobrem os
dois sentidos da paridade — nenhum endpoint da Especificação Conceitual falta,
e nenhum endpoint servido está fora do contrato.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from app.models.catalogo import ERROS, RECURSOS, campos_de  # noqa: E402


def valida(spec: dict[str, Any], nome_schema: str, corpo: Any) -> None:
    """Valida um corpo contra um schema do `components/schemas`, resolvendo $ref."""
    esquema = {"$ref": f"#/components/schemas/{nome_schema}", "components": spec["components"]}
    Draft202012Validator(esquema).validate(corpo)


# =============================================================
# Cobertura: 100% dos endpoints da Especificação Conceitual
# =============================================================


def test_todos_os_endpoints_da_especificacao_estao_no_contrato(spec: dict[str, Any]) -> None:
    """Os 34 endpoints das Seções 2-4, mais /health.

    7 listagens + 7 detalhes + 18 navegações + /v1/relacoes + /v1/busca.
    """
    paths = set(spec["paths"])
    esperados: set[str] = {"/health", "/v1/relacoes", "/v1/busca"}
    for r in RECURSOS:
        esperados.add(f"/v1/{r.nome}")
        esperados.add(f"/v1/{r.nome}/{{id}}")
        for nav in r.navegacoes:
            esperados.add(f"/v1/{r.nome}/{{id}}/{nav.sub}")
    assert esperados <= paths, f"faltam no contrato: {sorted(esperados - paths)}"
    assert len(esperados) == 35, f"esperados 35 paths, enumerados {len(esperados)}"


def test_contrato_nao_tem_endpoint_alem_da_especificacao(spec: dict[str, Any]) -> None:
    """Nada foi inventado: o contrato não publica endpoint que a Especificação não define."""
    permitidos: set[str] = {"/health", "/v1/relacoes", "/v1/busca"}
    for r in RECURSOS:
        permitidos.add(f"/v1/{r.nome}")
        permitidos.add(f"/v1/{r.nome}/{{id}}")
        permitidos.update(f"/v1/{r.nome}/{{id}}/{nav.sub}" for nav in r.navegacoes)
    assert set(spec["paths"]) <= permitidos, f"a mais: {sorted(set(spec['paths']) - permitidos)}"


def test_toda_rota_servida_esta_no_contrato(client: TestClient, spec: dict[str, Any]) -> None:
    """O outro sentido: nada é servido em /v1 sem estar documentado."""
    from app.main import app

    servidas: set[str] = set()

    def coletar(rotas: Any) -> None:
        # O FastAPI 0.141 não achata as rotas incluídas em `app.routes`: agrupa
        # cada `include_router` em um `_IncludedRouter`, cujo router original
        # guarda as rotas de verdade. Por isso a coleta desce um nível.
        for rota in rotas:
            caminho = getattr(rota, "path", None)
            if caminho and caminho.startswith("/v1/"):
                if getattr(rota, "include_in_schema", True):
                    servidas.add(caminho.replace("{id_legivel}", "{id}"))
            interno = getattr(rota, "original_router", None)
            if interno is not None:
                coletar(interno.routes)
            elif isinstance(getattr(rota, "routes", None), list):
                coletar(rota.routes)

    coletar(app.routes)
    assert servidas, "nenhuma rota /v1 encontrada — a coleta de rotas falhou"
    assert servidas <= set(spec["paths"]), (
        f"servidas sem contrato: {sorted(servidas - set(spec['paths']))}"
    )


def test_somente_leitura(spec: dict[str, Any]) -> None:
    """Restrição da Ordem 4 e da Seção 6: nenhum POST, PUT, PATCH ou DELETE."""
    for caminho, operacoes in spec["paths"].items():
        metodos = set(operacoes) - {"parameters", "summary", "description"}
        assert metodos == {"get"}, f"{caminho} expõe {sorted(metodos - {'get'})}"


# =============================================================
# Schemas: exemplos e fidelidade ao Dicionário v1.2
# =============================================================


def test_todo_schema_tem_exemplo(spec: dict[str, Any]) -> None:
    """Critério de aceite: todo schema traz exemplo."""
    sem_exemplo = [n for n, s in spec["components"]["schemas"].items() if "example" not in s]
    assert sem_exemplo == [], f"schemas sem exemplo: {sem_exemplo}"


def test_todo_exemplo_valida_contra_o_proprio_schema(spec: dict[str, Any]) -> None:
    """Exemplo que não passa no próprio schema é pior que exemplo nenhum."""
    for nome, esquema in spec["components"]["schemas"].items():
        valida(spec, nome, esquema["example"])


@pytest.mark.parametrize("recurso", RECURSOS, ids=lambda r: r.nome)
def test_schema_nao_expoe_campo_fora_do_dicionario(spec: dict[str, Any], recurso: Any) -> None:
    """Restrição da Ordem 4: nenhum campo além dos do Dicionário v1.2.

    `_links` é a única propriedade construída pela API, e é navegação, não dado
    do corpus — a Seção 1 da Especificação a prevê explicitamente.
    """
    propriedades = set(spec["components"]["schemas"][recurso.singular]["properties"])
    permitidos = set(campos_de(recurso)) | {"_links"}
    assert propriedades <= permitidos, f"a mais: {sorted(propriedades - permitidos)}"


@pytest.mark.parametrize("recurso", RECURSOS, ids=lambda r: r.nome)
def test_schema_traz_os_blocos_transversais(spec: dict[str, Any], recurso: Any) -> None:
    """Passo 2 da Ordem 4: identidade, versionamento e i18n em todo recurso."""
    props = set(spec["components"]["schemas"][recurso.singular]["properties"])
    for campo in ("uuid", "slug", "created_at", "updated_at", "version",
                  "nome_pt", "nome_en", "nome_es", "nome_fr", "nome_it",
                  "nome_de", "nome_ja", "nome_zh",
                  "descricao_pt", "descricao_en", "descricao_es"):
        assert campo in props, f"{recurso.singular} não expõe {campo}"


def test_schema_de_relacao_traz_peso_e_metodo(spec: dict[str, Any]) -> None:
    """Passo 2: peso e metodo_calculo_peso, as propriedades de aresta da Seção 20."""
    props = spec["components"]["schemas"]["Relacao"]["properties"]
    assert "peso" in props and "metodo_calculo_peso" in props
    assert props["peso"]["minimum"] == 0.0 and props["peso"]["maximum"] == 1.0


def test_bioma_expoe_oficial_ibge_como_booleano(spec: dict[str, Any]) -> None:
    """Seção 2.6: o cliente precisa distinguir BIO-000007 dos 6 oficiais."""
    assert spec["components"]["schemas"]["Bioma"]["properties"]["oficial_ibge"]["type"] == "boolean"


# =============================================================
# Erros — Seção 5.3
# =============================================================


def test_schema_de_erro_cobre_os_codigos_da_secao_5_3(spec: dict[str, Any]) -> None:
    codigos = spec["components"]["schemas"]["Erro"]["properties"]["error"]["properties"]["code"]
    assert set(codigos["enum"]) == set(ERROS)


def test_operacoes_declaram_400_429_500(spec: dict[str, Any]) -> None:
    """Todo endpoint pode receber parâmetro inválido, estourar cota ou falhar."""
    for caminho, operacoes in spec["paths"].items():
        if caminho == "/health":
            continue
        respostas = set(operacoes["get"]["responses"])
        assert {"400", "429", "500"} <= respostas, f"{caminho}: faltam {respostas}"


def test_endpoints_de_detalhe_declaram_404(spec: dict[str, Any]) -> None:
    for r in RECURSOS:
        assert "404" in spec["paths"][f"/v1/{r.nome}/{{id}}"]["get"]["responses"]


def test_relacoes_declara_422(spec: dict[str, Any]) -> None:
    """Seção 5.3 reserva 422 para origem_id/destino_id sem entidade correspondente."""
    assert "422" in spec["paths"]["/v1/relacoes"]["get"]["responses"]


# =============================================================
# Metadados
# =============================================================


def test_operacoes_tem_operationid_unico(spec: dict[str, Any]) -> None:
    ids = [op["operationId"] for ops in spec["paths"].values() for op in ops.values()]
    assert len(ids) == len(set(ids)), "operationId duplicado no contrato"


def test_toda_operacao_documenta_a_origem_do_dado(spec: dict[str, Any]) -> None:
    """Passo 3 da Ordem 4: a divisão relacional/grafo tem de estar no contrato."""
    for caminho, operacoes in spec["paths"].items():
        if caminho == "/health":
            continue
        descricao = operacoes["get"]["description"]
        assert "banco relacional" in descricao or "banco de grafo" in descricao or \
               "índice full-text" in descricao, f"{caminho} não diz de onde vem o dado"
