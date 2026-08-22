"""
Roots of Brazil — middlewares da API (Ordem 4).

Implementa a **decisão do fundador** que resolveu o placeholder da Seção 6 da
Especificação Conceitual. A decisão é externa a este código e está registrada
como tal no relatório da Ordem 4:

  - **Sem API Key.** A Especificação *recomendava* `X-API-Key`; o fundador
    decidiu o contrário — API pública de catalogação cultural, leitura livre.
    Nenhum endpoint exige autenticação.
  - **Rate limiting por IP:** 100 requisições por minuto, 429 acima disso.
  - **CORS aberto:** `Access-Control-Allow-Origin: *`.

Mais dois middlewares que não vêm da Seção 6, e sim da Seção 8 ("cache de
leitura agressivo é apropriado — o corpus é atualizado por versão, não em
tempo real"): ETag para revalidação condicional e compressão gzip.
"""

from __future__ import annotations

import hashlib
import time
from collections import deque
from threading import Lock
from typing import Final

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.api.erros import ErroAPI

#: Decisão do fundador: 100 req/min por IP.
LIMITE_POR_MINUTO: Final = 100
JANELA_SEGUNDOS: Final = 60

#: Seção 8: o corpus muda por versão, não em tempo real — cache longo é seguro.
CACHE_CONTROL: Final = "public, max-age=300, stale-while-revalidate=3600"


class LimitadorDeTaxa:
    """Janela deslizante por IP, em memória.

    Janela deslizante e não contador por minuto cheio: com contador fixo, um
    cliente pode mandar 100 requisições no fim de um minuto e mais 100 no
    começo do seguinte — 200 em dois segundos, respeitando o limite no papel.

    Guardar em memória significa que o limite é **por processo**. Com várias
    réplicas, cada uma conta o seu, e o limite efetivo é 100 × réplicas. Para
    valer de verdade em produção, o contador precisa ser compartilhado (Redis).
    Registrado no backlog da Ordem 4 — não é um detalhe a descobrir depois.
    """

    def __init__(self, limite: int = LIMITE_POR_MINUTO, janela: int = JANELA_SEGUNDOS) -> None:
        self.limite = limite
        self.janela = janela
        self._batidas: dict[str, deque[float]] = {}
        self._trava = Lock()

    def registrar(self, chave: str) -> tuple[bool, int, int]:
        """Registra uma batida. Devolve (permitido, restantes, segundos_para_liberar)."""
        agora = time.monotonic()
        with self._trava:
            fila = self._batidas.setdefault(chave, deque())
            corte = agora - self.janela
            while fila and fila[0] <= corte:
                fila.popleft()
            if len(fila) >= self.limite:
                espera = max(1, int(fila[0] + self.janela - agora) + 1)
                return False, 0, espera
            fila.append(agora)
            return True, self.limite - len(fila), 0

    def limpar(self) -> None:
        """Zera o estado. Só para os testes — nunca chamado em runtime."""
        with self._trava:
            self._batidas.clear()


limitador = LimitadorDeTaxa()


def _ip_do_cliente(request: Request) -> str:
    """IP de origem, respeitando o proxy à frente quando houver.

    `X-Forwarded-For` só é considerado porque a API é pensada para rodar atrás
    de um proxy reverso. Exposta direto, um cliente poderia forjar o header e
    escapar do limite — por isso o fallback é sempre o IP do socket.
    """
    encaminhado: str | None = request.headers.get("x-forwarded-for")
    if encaminhado:
        return encaminhado.split(",")[0].strip()
    return request.client.host if request.client else "desconhecido"


class MiddlewareLimiteDeTaxa(BaseHTTPMiddleware):
    """429 quando o IP passa de 100 req/min, com os headers de cortesia."""

    def __init__(self, app: ASGIApp, limitador_: LimitadorDeTaxa | None = None) -> None:
        super().__init__(app)
        self.limitador = limitador_ or limitador

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Preflight de CORS não consome cota: é o navegador perguntando, não o
        # cliente consumindo dado.
        if request.method == "OPTIONS":
            return await call_next(request)

        permitido, restantes, espera = self.limitador.registrar(_ip_do_cliente(request))
        if not permitido:
            erro = ErroAPI(
                "RATE_LIMIT_EXCEEDED",
                f"Limite de {self.limitador.limite} requisições por minuto por IP excedido.",
            )
            # Variável própria para a resposta de recusa: reusar o mesmo nome da
            # resposta do `call_next` fazia o mypy inferir `JSONResponse` para
            # ela e recusar a atribuição seguinte, que é um `Response`.
            recusada = JSONResponse(status_code=429, content=erro.corpo())
            recusada.headers["Retry-After"] = str(espera)
            recusada.headers["X-RateLimit-Limit"] = str(self.limitador.limite)
            recusada.headers["X-RateLimit-Remaining"] = "0"
            return recusada

        resposta = await call_next(request)
        resposta.headers["X-RateLimit-Limit"] = str(self.limitador.limite)
        resposta.headers["X-RateLimit-Remaining"] = str(restantes)
        return resposta


class MiddlewareETag(BaseHTTPMiddleware):
    """ETag forte e resposta 304 para `If-None-Match`.

    O corpus é um snapshot versionado: a mesma URL devolve o mesmo corpo até a
    próxima versão do corpus. Isso torna a revalidação condicional
    especialmente eficaz — o cliente reconsulta e recebe 304 sem corpo.

    O ETag é o hash do corpo já serializado, então é sempre coerente com o que
    foi enviado, sem depender de o servidor saber quando o dado mudou.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        resposta = await call_next(request)
        if request.method != "GET" or resposta.status_code != 200:
            return resposta

        # `body_iterator` só existe em StreamingResponse, que é o que o
        # BaseHTTPMiddleware entrega aqui; `getattr` evita depender de um
        # atributo que a classe base não declara.
        fluxo = getattr(resposta, "body_iterator")
        corpo = b"".join([secao async for secao in fluxo])
        etag = '"' + hashlib.sha256(corpo).hexdigest()[:32] + '"'

        cabecalhos = dict(resposta.headers)
        cabecalhos["ETag"] = etag
        cabecalhos["Cache-Control"] = CACHE_CONTROL

        if request.headers.get("if-none-match") == etag:
            cabecalhos.pop("content-length", None)
            return Response(status_code=304, headers=cabecalhos)

        cabecalhos["content-length"] = str(len(corpo))
        return Response(content=corpo, status_code=200, headers=cabecalhos,
                        media_type=resposta.media_type)
