"""
Roots of Brazil — routers dos 7 recursos de catálogo (Ordem 4).

Os 32 endpoints da Seção 2 da Especificação (7 listagens + 7 detalhes + 18
navegações) são registrados a partir de `app/models/catalogo.py`, e não escritos
sete vezes. Sete módulos quase idênticos divergiriam: um ganharia um filtro que
os outros não têm, outro esqueceria os `_links`. Aqui a forma é a mesma por
construção, e o que varia — filtros, relações, campos — está declarado no
catálogo, junto do que gera a especificação OpenAPI.

Divisão de origem, conforme o passo 3 da Ordem 4:
  - listagem e detalhe  -> banco relacional (Ordem 2)
  - navegação           -> banco de grafo   (Ordem 3)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from starlette.requests import Request

from app.api import parametros, serializacao
from app.api.erros import ErroAPI, nao_encontrado, parametro_invalido
from app.models.catalogo import RECURSOS, Navegacao, Recurso
from app.repositories import grafo, relacional

router = APIRouter()


def _expandir(request: Request, recurso: Recurso) -> list[str]:
    """Valida `?expand=` contra as relações que o recurso realmente tem."""
    bruto = request.query_params.get("expand")
    if not bruto:
        return []
    pedidos = [p.strip() for p in bruto.split(",") if p.strip()]
    disponiveis = {n.sub for n in recurso.navegacoes}
    invalidos = [p for p in pedidos if p not in disponiveis]
    if invalidos:
        raise parametro_invalido(
            f"'expand' não reconhece {', '.join(invalidos)} em /v1/{recurso.nome}. "
            f"Disponíveis: {', '.join(sorted(disponiveis))}."
        )
    return pedidos


def _hidratar(nav: Navegacao, itens: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Completa os IDs devolvidos pelo grafo com os atributos do relacional.

    O grafo responde "quem" e "com que peso"; os campos do Dicionário vêm do
    banco relacional. Uma consulta só para todos os IDs da página, não uma por
    item.
    """
    from app.models.catalogo import RECURSO_POR_NOME

    destino = RECURSO_POR_NOME[nav.recurso_destino]
    por_id = relacional.obter_varios(destino, [i["id"] for i in itens])
    completos: list[dict[str, Any]] = []
    for item in itens:
        linha = por_id.get(item["id"])
        if linha is None:
            # Aresta apontando para nó sem linha no relacional: os dois bancos
            # saíram da mesma fonte, então isso indicaria divergência entre
            # eles. Não se inventa objeto — devolve-se o ID e a aresta.
            completos.append({"id": item["id"], "_relacao": item["_relacao"]})
            continue
        objeto = serializacao.serializar(destino, linha)
        objeto["_relacao"] = item["_relacao"]
        completos.append(objeto)
    return completos


def _registrar(recurso: Recurso) -> None:
    """Cria as rotas de listagem, detalhe e navegação de um recurso."""

    # O recurso entra por fechamento léxico, não por argumento default: o
    # FastAPI inspeciona a assinatura para montar o modelo de requisição, e um
    # default extra viraria parâmetro de corpo.
    @router.get(f"/v1/{recurso.nome}", name=f"listar_{recurso.nome}")
    async def listar(request: Request) -> dict[str, Any]:
        filtros = parametros.filtros_de(request, recurso)
        page, page_size = parametros.paginacao(request)
        sort, order = parametros.ordenacao(request)
        _expandir(request, recurso)  # valida mesmo sem expandir na listagem
        try:
            total, linhas = relacional.listar(recurso, filtros, page, page_size, sort, order)
        except ValueError as erro:
            raise parametro_invalido(str(erro)) from None
        return serializacao.pagina(
            total, page, page_size,
            [serializacao.serializar(recurso, linha) for linha in linhas],
        )

    @router.get(f"/v1/{recurso.nome}/{{id_legivel}}", name=f"obter_{recurso.nome}")
    async def obter(request: Request, id_legivel: str) -> dict[str, Any]:
        pedidos = _expandir(request, recurso)
        linha = relacional.obter(recurso, id_legivel)
        if linha is None:
            raise nao_encontrado(id_legivel)
        objeto = serializacao.serializar(recurso, linha)
        for sub in pedidos:
            nav = next(n for n in recurso.navegacoes if n.sub == sub)
            _, itens = grafo.navegar(recurso, id_legivel, nav, page=1, page_size=100)
            expandido = _hidratar(nav, itens)
            objeto.setdefault("_expandido", {})[sub] = (
                expandido[0] if nav.singular and expandido else
                (None if nav.singular else expandido)
            )
        return objeto

    for navegacao in recurso.navegacoes:
        _registrar_navegacao(recurso, navegacao)


def _registrar_navegacao(recurso: Recurso, nav: Navegacao) -> None:
    @router.get(
        f"/v1/{recurso.nome}/{{id_legivel}}/{nav.sub}",
        name=f"navegar_{recurso.nome}_{nav.sub}",
    )
    async def navegar(request: Request, id_legivel: str) -> Any:
        # 404 é resolvido pelo relacional, que é barato e está sempre no ar.
        # Sem esta checagem, um ID inexistente devolveria lista vazia — o
        # cliente não distinguiria "não existe" de "existe e não tem relação".
        if relacional.obter(recurso, id_legivel) is None:
            raise nao_encontrado(id_legivel)
        page, page_size = parametros.paginacao(request)
        conf = parametros.confiabilidade(request)
        try:
            total, itens = grafo.navegar(recurso, id_legivel, nav, page, page_size, conf)
        except ValueError as erro:
            raise parametro_invalido(str(erro)) from None
        completos = _hidratar(nav, itens)
        if nav.singular:
            # /v1/receitas/{id}/territorio devolve o objeto, não uma página —
            # a Especificação o escreve no singular ("Território de origem").
            if not completos:
                raise ErroAPI(
                    "NOT_FOUND",
                    f"A receita '{id_legivel}' não tem território de origem registrado.",
                )
            return completos[0]
        return serializacao.pagina(total, page, page_size, completos)


for _recurso in RECURSOS:
    _registrar(_recurso)
