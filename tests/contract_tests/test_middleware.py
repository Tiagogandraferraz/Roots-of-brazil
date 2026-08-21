"""Rate limiting, CORS, ETag e compressão — Ordem 4, passo 6.

Os três primeiros implementam a **decisão do fundador** que resolveu o
placeholder da Seção 6 da Especificação Conceitual: sem API Key, 100 req/min
por IP, CORS aberto. ETag e compressão vêm da Seção 8 ("cache de leitura
agressivo é apropriado — o corpus é atualizado por versão, não em tempo real").
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from app.core.middleware import LIMITE_POR_MINUTO  # noqa: E402

URL = "/v1/biomas"


# =============================================================
# Sem API Key — decisão do fundador
# =============================================================


def test_api_nao_exige_chave(client: TestClient) -> None:
    """A Especificação *recomendava* X-API-Key; a decisão foi não exigir.

    Leitura livre, sem cabeçalho de autenticação de espécie alguma.
    """
    assert client.get(URL).status_code == 200


def test_chave_invalida_nao_atrapalha(client: TestClient) -> None:
    """Um cliente que mande X-API-Key por engano não é penalizado por isso."""
    assert client.get(URL, headers={"X-API-Key": "irrelevante"}).status_code == 200


def test_contrato_nao_declara_esquema_de_seguranca(spec: dict) -> None:
    """Sem API Key também no contrato — nada de `securitySchemes` publicado."""
    assert "security" not in spec
    assert "securitySchemes" not in spec.get("components", {})


# =============================================================
# Rate limiting — 100 req/min por IP
# =============================================================


def test_cabecalhos_de_cota_em_toda_resposta(client: TestClient) -> None:
    resposta = client.get(URL)
    assert resposta.headers["X-RateLimit-Limit"] == str(LIMITE_POR_MINUTO)
    assert int(resposta.headers["X-RateLimit-Remaining"]) == LIMITE_POR_MINUTO - 1


def test_cota_decresce_a_cada_requisicao(client: TestClient) -> None:
    restantes = [int(client.get(URL).headers["X-RateLimit-Remaining"]) for _ in range(3)]
    assert restantes == [LIMITE_POR_MINUTO - 1, LIMITE_POR_MINUTO - 2, LIMITE_POR_MINUTO - 3]


def test_429_ao_estourar_o_limite(client: TestClient) -> None:
    """A 101ª requisição no minuto recebe 429, no formato de erro da Seção 5.3."""
    for _ in range(LIMITE_POR_MINUTO):
        assert client.get(URL).status_code == 200
    resposta = client.get(URL)
    assert resposta.status_code == 429
    corpo = resposta.json()
    assert corpo["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert corpo["error"]["status"] == 429
    assert int(resposta.headers["Retry-After"]) >= 1
    assert resposta.headers["X-RateLimit-Remaining"] == "0"


def test_limite_e_por_ip(client: TestClient) -> None:
    """Estourar a cota de um IP não afeta outro."""
    for _ in range(LIMITE_POR_MINUTO):
        client.get(URL, headers={"X-Forwarded-For": "203.0.113.1"})
    assert client.get(URL, headers={"X-Forwarded-For": "203.0.113.1"}).status_code == 429
    assert client.get(URL, headers={"X-Forwarded-For": "203.0.113.2"}).status_code == 200


def test_preflight_nao_consome_cota(client: TestClient) -> None:
    """OPTIONS é o navegador perguntando, não o cliente consumindo dado."""
    antes = int(client.get(URL).headers["X-RateLimit-Remaining"])
    client.options(URL, headers={"Origin": "https://exemplo.org",
                                 "Access-Control-Request-Method": "GET"})
    depois = int(client.get(URL).headers["X-RateLimit-Remaining"])
    assert antes - depois == 1  # só as duas GETs contaram


# =============================================================
# CORS aberto — decisão do fundador
# =============================================================


def test_cors_libera_qualquer_origem(client: TestClient) -> None:
    resposta = client.get(URL, headers={"Origin": "https://app.exemplo.org"})
    assert resposta.headers["access-control-allow-origin"] == "*"


def test_preflight_permite_get(client: TestClient) -> None:
    resposta = client.options(
        URL,
        headers={"Origin": "https://app.exemplo.org",
                 "Access-Control-Request-Method": "GET"},
    )
    assert resposta.status_code == 200
    assert "GET" in resposta.headers["access-control-allow-methods"]


def test_cors_expoe_etag_e_cota_ao_javascript(client: TestClient) -> None:
    """Sem `expose_headers`, o navegador esconde ETag e X-RateLimit do cliente JS."""
    expostos = client.get(URL, headers={"Origin": "https://x.org"}) \
                     .headers["access-control-expose-headers"].lower()
    for cabecalho in ("etag", "x-ratelimit-limit", "x-ratelimit-remaining"):
        assert cabecalho in expostos


def test_cors_nao_libera_credenciais(client: TestClient) -> None:
    """`Allow-Origin: *` com credenciais seria falha de segurança — e a API não usa sessão."""
    resposta = client.get(URL, headers={"Origin": "https://x.org"})
    assert "access-control-allow-credentials" not in resposta.headers


def test_429_ainda_traz_cabecalho_de_cors(client: TestClient) -> None:
    """CORS é o middleware mais externo justamente para o erro também sair navegável."""
    for _ in range(LIMITE_POR_MINUTO):
        client.get(URL)
    resposta = client.get(URL, headers={"Origin": "https://x.org"})
    assert resposta.status_code == 429
    assert resposta.headers["access-control-allow-origin"] == "*"


# =============================================================
# ETag — Seção 8
# =============================================================


def test_resposta_traz_etag_e_cache_control(client: TestClient) -> None:
    resposta = client.get(URL)
    assert resposta.headers["ETag"].startswith('"')
    assert "max-age" in resposta.headers["Cache-Control"]


def test_etag_e_estavel_para_o_mesmo_recurso(client: TestClient) -> None:
    """O corpus é um snapshot: mesma URL, mesmo corpo, mesmo ETag."""
    assert client.get(URL).headers["ETag"] == client.get(URL).headers["ETag"]


def test_etag_difere_entre_recursos(client: TestClient) -> None:
    assert client.get("/v1/biomas").headers["ETag"] != client.get("/v1/povos").headers["ETag"]


def test_if_none_match_devolve_304_sem_corpo(client: TestClient) -> None:
    etag = client.get(URL).headers["ETag"]
    resposta = client.get(URL, headers={"If-None-Match": etag})
    assert resposta.status_code == 304
    assert resposta.content == b""


def test_if_none_match_desatualizado_devolve_200(client: TestClient) -> None:
    resposta = client.get(URL, headers={"If-None-Match": '"etag-de-outra-versao"'})
    assert resposta.status_code == 200
    assert resposta.json()["total"] == 7


# =============================================================
# Compressão — Seção 8
# =============================================================


def test_resposta_grande_e_comprimida(client: TestClient) -> None:
    resposta = client.get("/v1/ingredientes", params={"page_size": 100},
                          headers={"Accept-Encoding": "gzip"})
    assert resposta.status_code == 200
    assert resposta.headers.get("content-encoding") == "gzip"


def test_cliente_sem_gzip_recebe_texto_puro(client: TestClient) -> None:
    resposta = client.get("/v1/ingredientes", params={"page_size": 100},
                          headers={"Accept-Encoding": "identity"})
    assert "content-encoding" not in resposta.headers
    assert resposta.json()["total"] == 130


def test_compressao_reduz_o_tamanho(client: TestClient) -> None:
    """Confere que a compressão é ganho real, não só um cabeçalho.

    A comparação é por `Content-Length`, que é o que trafega: o cliente HTTP
    descomprime de forma transparente, então `response.content` tem o mesmo
    tamanho nos dois casos e não serviria de medida.
    """
    comprimido = client.get("/v1/ingredientes", params={"page_size": 100},
                            headers={"Accept-Encoding": "gzip"})
    puro = client.get("/v1/ingredientes", params={"page_size": 100},
                      headers={"Accept-Encoding": "identity"})
    bytes_comprimido = int(comprimido.headers["content-length"])
    bytes_puro = int(puro.headers["content-length"])
    assert bytes_comprimido < bytes_puro / 2, (
        f"gzip rendeu pouco: {bytes_comprimido} vs {bytes_puro} bytes"
    )
    # O corpo, já descomprimido, continua íntegro nos dois casos.
    assert comprimido.json() == puro.json()
