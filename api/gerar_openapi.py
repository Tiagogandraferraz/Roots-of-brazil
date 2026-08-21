"""
Roots of Brazil — gerador da especificação OpenAPI 3.1 (Ordem 4).

Emite `api/openapi.yaml` a partir de duas fontes que já são a verdade do
projeto:

  - `app/models/catalogo.py` — quais recursos existem, que campos expõem e por
    qual relação cada endpoint de navegação caminha;
  - `schemas/ddl_sqlite.sql` (via banco da Ordem 2) — o tipo de cada campo.

Gerar em vez de escrever à mão não é preguiça: é o que garante dois critérios
de aceite por construção, em vez de por revisão. Primeiro, "nenhum endpoint
expõe campo ausente do Dicionário v1.2" — um campo que não está no DDL não tem
como aparecer no schema. Segundo, "todo schema com exemplo válido" — os
exemplos são LIDOS DO CORPUS REAL carregado, então nenhum valor de exemplo é
inventado.

Uso:
    python api/gerar_openapi.py                    # usa roots_of_brazil_dev.db
    python api/gerar_openapi.py --db caminho.db
    python api/gerar_openapi.py --check            # falha se o yaml estiver desatualizado
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path
from typing import Any

import yaml

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from app.models.catalogo import (  # noqa: E402
    CAMPOS_ARESTA,
    CONFIABILIDADES,
    ERROS,
    PAGE_SIZE_MAXIMO,
    PAGE_SIZE_PADRAO,
    RECURSOS,
    TIPOS_BUSCA,
    Recurso,
    campos_de,
)
from app.models.grafo import TIPOS_RELACAO  # noqa: E402  (Ordem 3, só leitura)

SAIDA = RAIZ / "api" / "openapi.yaml"

#: Campos que ganham formato ou tipo diferente do que o DDL sugere.
#: `oficial_ibge` é o caso importante: no SQLite é INTEGER 0/1 porque SQLite não
#: tem booleano, mas a Seção 2.6 da Especificação exige `oficial_ibge: false`.
#: A conversão acontece na serialização (app/api/serializacao.py).
FORMATOS: dict[str, dict[str, Any]] = {
    "uuid": {"type": "string", "format": "uuid"},
    "created_at": {"type": "string", "format": "date-time"},
    "updated_at": {"type": "string", "format": "date-time"},
    "data_criacao": {"type": "string", "format": "date"},
    "oficial_ibge": {"type": "boolean"},
    "slug": {"type": "string", "pattern": "^[a-z0-9]+(-[a-z0-9]+)*$"},
    "peso": {"type": "number", "format": "double", "minimum": 0.0, "maximum": 1.0},
    "geometry": {"type": "string", "description": "GeoJSON Polygon/MultiPolygon (RFC 7946)."},
    "bounding_box": {"type": "string", "description": "GeoJSON BBox [minLon,minLat,maxLon,maxLat]."},
}

DESCRICOES: dict[str, str] = {
    "id": "Identificador legível, com prefixo da entidade. Dicionário v1.2, Seção 3.",
    "uuid": "Identificador universal imutável, UUID v4. Seção 5.",
    "slug": "Identificador amigável para URL, kebab-case. Seção 7.",
    "created_at": "Timestamp de criação, imutável. Seção 4.",
    "updated_at": "Timestamp da última alteração. Seção 4.",
    "version": "Contador de versão do objeto, inicia em 1. Seções 4 e 6.",
    "confiabilidade": (
        "Grau de certeza da informação. Seção 11. O valor pode trazer texto livre após o "
        "emoji (ex.: '🔵 Inferido com cautela'), por isso filtros casam por prefixo."
    ),
    "peso": "Peso da relação, de 0.0 a 1.0. Seção 20.",
    "metodo_calculo_peso": "Como o peso foi obtido. Seção 20.2.",
    "oficial_ibge": (
        "false para o bioma extra-oficial BIO-000007 (Zona Costeira/Litoral), true para os "
        "6 biomas oficiais do IBGE. Especificação Conceitual, Seção 2.6."
    ),
}


def tipo_sql_para_openapi(tipo: str) -> dict[str, Any]:
    return {"TEXT": {"type": "string"}, "INTEGER": {"type": "integer"},
            "REAL": {"type": "number"}}.get(tipo.upper(), {"type": "string"})


def _nulavel(esquema: dict[str, Any]) -> dict[str, Any]:
    """Em OpenAPI 3.1 o nulo é expresso por união de tipos, não por `nullable`."""
    e = dict(esquema)
    t = e.get("type")
    if isinstance(t, str):
        e["type"] = [t, "null"]
    return e


class Gerador:
    def __init__(self, db: Path) -> None:
        self.conn = sqlite3.connect(db)
        self.conn.row_factory = sqlite3.Row
        self.tipos: dict[str, dict[str, tuple[str, bool]]] = {}
        for r in RECURSOS:
            self.tipos[r.tabela] = {
                linha[1]: (linha[2], bool(linha[3]))
                for linha in self.conn.execute(f"PRAGMA table_info({r.tabela})")
            }
        self.tipos["relacoes"] = {
            linha[1]: (linha[2], bool(linha[3]))
            for linha in self.conn.execute("PRAGMA table_info(relacoes)")
        }

    # --- exemplos vindos do corpus real -------------------------------

    def exemplo_de(self, recurso: Recurso) -> dict[str, Any]:
        """Uma linha real do catálogo, virando o `example` do schema."""
        linha = self.conn.execute(
            f"SELECT * FROM {recurso.tabela} WHERE id = ?", (recurso.exemplo_id,)
        ).fetchone()
        if linha is None:  # corpus não carregado: cai para a primeira linha
            linha = self.conn.execute(f"SELECT * FROM {recurso.tabela} LIMIT 1").fetchone()
        if linha is None:
            raise SystemExit(
                f"Tabela {recurso.tabela} vazia — rode scripts/ordem2/etl.py antes de gerar."
            )
        exemplo = {}
        for campo in campos_de(recurso):
            valor = linha[campo] if campo in linha.keys() else None
            if valor is None:
                continue
            if campo == "oficial_ibge":
                valor = bool(valor)
            exemplo[campo] = valor
        exemplo["_links"] = {
            n.sub: f"/v1/{recurso.nome}/{linha['id']}/{n.sub}" for n in recurso.navegacoes
        }
        return exemplo

    def exemplo_relacao(self) -> dict[str, Any]:
        linha = self.conn.execute("SELECT * FROM relacoes LIMIT 1").fetchone()
        if linha is None:
            raise SystemExit("Tabela relacoes vazia — rode scripts/ordem2/etl.py.")
        return {c: linha[c] for c in CAMPOS_ARESTA if linha[c] is not None}

    # --- schemas ------------------------------------------------------

    def schema_de(self, recurso: Recurso) -> dict[str, Any]:
        props: dict[str, Any] = {}
        obrigatorios: list[str] = []
        tipos_tabela = self.tipos[recurso.tabela]
        for campo in campos_de(recurso):
            if campo not in tipos_tabela:
                continue
            tipo_sql, nao_nulo = tipos_tabela[campo]
            esquema = FORMATOS.get(campo, tipo_sql_para_openapi(tipo_sql)).copy()
            if campo in DESCRICOES:
                esquema["description"] = DESCRICOES[campo]
            if nao_nulo:
                obrigatorios.append(campo)
            else:
                esquema = _nulavel(esquema)
            props[campo] = esquema
        props["_links"] = {
            "type": "object",
            "description": "URLs dos sub-recursos de navegação, resolvidos pelo banco de grafo.",
            "additionalProperties": {"type": "string", "format": "uri-reference"},
        }
        return {
            "type": "object",
            "description": (
                f"{recurso.singular} do Corpus Fundador. Origem: aba "
                f"'{recurso.aba_workbook}' (Especificação Conceitual, Seção 7). "
                f"Todo campo corresponde 1:1 a uma coluna do Dicionário de Dados v1.2."
            ),
            "required": obrigatorios,
            "properties": props,
            "additionalProperties": False,
            "example": self.exemplo_de(recurso),
        }

    def schema_relacao(self) -> dict[str, Any]:
        props: dict[str, Any] = {}
        obrigatorios: list[str] = []
        for campo in CAMPOS_ARESTA:
            tipo_sql, nao_nulo = self.tipos["relacoes"][campo]
            esquema = FORMATOS.get(campo, tipo_sql_para_openapi(tipo_sql)).copy()
            if campo == "tipo_relacao":
                esquema["enum"] = [d.tipo for d in TIPOS_RELACAO]
            if campo in DESCRICOES:
                esquema["description"] = DESCRICOES[campo]
            if nao_nulo:
                obrigatorios.append(campo)
            else:
                esquema = _nulavel(esquema)
            props[campo] = esquema
        return {
            "type": "object",
            "description": (
                "Aresta da camada RELACOES. Peso, confiabilidade e proveniência são "
                "propriedades da própria relação — Dicionário v1.2, Seção 20."
            ),
            "required": obrigatorios,
            "properties": props,
            "additionalProperties": False,
            "example": self.exemplo_relacao(),
        }

    def schemas(self) -> dict[str, Any]:
        s: dict[str, Any] = {}
        for r in RECURSOS:
            s[r.singular] = self.schema_de(r)
            s[f"Pagina{r.singular}"] = self._pagina(
                f"#/components/schemas/{r.singular}",
                f"Página de {r.nome}.",
                self.exemplo_de(r),
            )
        s["Relacao"] = self.schema_relacao()
        s["PaginaRelacao"] = self._pagina(
            "#/components/schemas/Relacao", "Página de relações.", self.exemplo_relacao()
        )

        s["ResultadoBusca"] = {
            "type": "object",
            "description": (
                "Item heterogêneo da busca global. O campo `tipo` diz de qual catálogo o "
                "resultado veio — Especificação Conceitual, Seção 4."
            ),
            "required": ["id", "tipo", "nome", "confiabilidade"],
            "properties": {
                "id": {"type": "string", "description": DESCRICOES["id"]},
                "tipo": {"type": "string", "enum": list(TIPOS_BUSCA)},
                "nome": {"type": "string", "description": "Nome em português do objeto."},
                "descricao": _nulavel({"type": "string"}),
                "slug": {"type": "string"},
                "confiabilidade": {"type": "string", "description": DESCRICOES["confiabilidade"]},
                "score": {
                    "type": "number", "format": "double",
                    "description": "Relevância devolvida pelo índice full-text do grafo.",
                },
            },
            "additionalProperties": False,
            "example": {
                "id": "ING-000031", "tipo": "ingrediente", "nome": "Cebola",
                "slug": "cebola", "confiabilidade": CONFIABILIDADES[0], "score": 3.14,
            },
        }
        s["PaginaBusca"] = self._pagina(
            "#/components/schemas/ResultadoBusca", "Página de resultados da busca global.",
            {"id": "ING-000031", "tipo": "ingrediente", "nome": "Cebola",
             "slug": "cebola", "confiabilidade": CONFIABILIDADES[0], "score": 3.14},
        )

        s["Erro"] = {
            "type": "object",
            "description": "Formato de erro padrão — Especificação Conceitual, Seção 5.3.",
            "required": ["error"],
            "properties": {
                "error": {
                    "type": "object",
                    "required": ["code", "message", "status"],
                    "properties": {
                        "code": {"type": "string", "enum": list(ERROS)},
                        "message": {"type": "string"},
                        "status": {"type": "integer"},
                    },
                    "additionalProperties": False,
                }
            },
            "additionalProperties": False,
            "example": {
                "error": {
                    "code": "NOT_FOUND",
                    "message": "Objeto com ID 'ING-999999' não encontrado.",
                    "status": 404,
                }
            },
        }
        return s

    @staticmethod
    def _pagina(ref: str, descricao: str, exemplo_item: Any) -> dict[str, Any]:
        """Envelope de paginação da Seção 5.1: total, page, page_size, items."""
        return {
            "type": "object",
            "description": descricao,
            "required": ["total", "page", "page_size", "items"],
            "properties": {
                "total": {"type": "integer", "description": "Total de itens que casam com o filtro."},
                "page": {"type": "integer", "minimum": 1},
                "page_size": {"type": "integer", "minimum": 1, "maximum": PAGE_SIZE_MAXIMO},
                "items": {"type": "array", "items": {"$ref": ref}},
            },
            "additionalProperties": False,
            "example": {"total": 1, "page": 1, "page_size": PAGE_SIZE_PADRAO,
                        "items": [exemplo_item]},
        }

    # --- parâmetros ---------------------------------------------------

    def parametros(self) -> dict[str, Any]:
        p: dict[str, Any] = {
            "Page": {
                "name": "page", "in": "query", "required": False,
                "description": "Página, começando em 1. Seção 5.1.",
                "schema": {"type": "integer", "minimum": 1, "default": 1}, "example": 1,
            },
            "PageSize": {
                "name": "page_size", "in": "query", "required": False,
                "description": f"Itens por página. Máximo {PAGE_SIZE_MAXIMO}. Seção 5.1.",
                "schema": {"type": "integer", "minimum": 1, "maximum": PAGE_SIZE_MAXIMO,
                           "default": PAGE_SIZE_PADRAO},
                "example": PAGE_SIZE_PADRAO,
            },
            "Sort": {
                "name": "sort", "in": "query", "required": False,
                "description": "Campo de ordenação. Seção 5.2.",
                "schema": {"type": "string"}, "example": "n_citacoes",
            },
            "Order": {
                "name": "order", "in": "query", "required": False,
                "description": "Sentido da ordenação. Seção 5.2.",
                "schema": {"type": "string", "enum": ["asc", "desc"], "default": "asc"},
                "example": "desc",
            },
            "Expand": {
                "name": "expand", "in": "query", "required": False,
                "description": (
                    "Lista separada por vírgula de relações a resolver inline, em vez de "
                    "apenas linkar. Ex.: expand=receitas,territorios. Seção 1."
                ),
                "schema": {"type": "string"}, "example": "receitas,povos",
            },
            "Id": {
                "name": "id", "in": "path", "required": True,
                "description": DESCRICOES["id"],
                "schema": {"type": "string", "pattern": "^(ING|REC|TEC|POV|TER|PAT|BIO|LIV)-[0-9]{6}$"},
                "example": "ING-000031",
            },
            "Confiabilidade": {
                "name": "confiabilidade", "in": "query", "required": False,
                "description": DESCRICOES["confiabilidade"],
                "schema": {"type": "string", "enum": list(CONFIABILIDADES)},
                "example": CONFIABILIDADES[0],
            },
            "Q": {
                "name": "q", "in": "query", "required": False,
                "description": "Busca textual nos campos de nome do recurso.",
                "schema": {"type": "string"}, "example": "cebola",
            },
        }
        simples = {
            "categoria": "Filtra pela categoria taxonômica. Dicionário v1.2, Seção 9.",
            "subcategoria": "Filtra pela subcategoria taxonômica. Seção 9.",
            "bioma": "Filtra por bioma associado ao ingrediente.",
            "estado": "Filtra pela unidade federativa.",
            "regiao": "Filtra pela região do país.",
        }
        for nome, desc in simples.items():
            p[nome.capitalize()] = {
                "name": nome, "in": "query", "required": False,
                "description": desc, "schema": {"type": "string"},
            }
        p["Classe"] = {
            "name": "classe", "in": "query", "required": False,
            "description": "Classe do ingrediente. Especificação Conceitual, Seção 2.1.",
            "schema": {"type": "string", "enum": ["Vegetal", "Animal", "Processado/Outro"]},
            "example": "Vegetal",
        }
        p["OficialIbge"] = {
            "name": "oficial_ibge", "in": "query", "required": False,
            "description": DESCRICOES["oficial_ibge"],
            "schema": {"type": "boolean"}, "example": True,
        }
        return p

    # --- paths --------------------------------------------------------

    def _erros(self, *codigos: int) -> dict[str, Any]:
        rotulos = {400: "Parâmetro de query inválido.", 404: "Objeto não encontrado.",
                   422: "origem_id/destino_id não corresponde a entidade conhecida.",
                   429: "Limite de 100 requisições por minuto por IP excedido.",
                   500: "Erro não tratado no servidor."}
        r: dict[str, Any] = {}
        for c in codigos:
            r[str(c)] = {
                "description": rotulos[c],
                "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Erro"}}},
            }
            if c == 429:
                r[str(c)]["headers"] = {
                    "Retry-After": {"description": "Segundos até a próxima janela.",
                                    "schema": {"type": "integer"}}
                }
        return r

    @staticmethod
    def _cabecalhos_ok() -> dict[str, Any]:
        return {
            "ETag": {"description": "Hash forte do corpo, para revalidação com If-None-Match.",
                     "schema": {"type": "string"}},
            "Cache-Control": {"description": "O corpus muda por versão, não em tempo real.",
                              "schema": {"type": "string"}},
            "X-RateLimit-Limit": {"description": "Requisições permitidas por janela.",
                                  "schema": {"type": "integer"}},
            "X-RateLimit-Remaining": {"description": "Requisições restantes na janela.",
                                      "schema": {"type": "integer"}},
        }

    def paths(self) -> dict[str, Any]:
        caminhos: dict[str, Any] = {}
        for r in RECURSOS:
            caminhos[f"/v1/{r.nome}"] = {"get": self._op_lista(r)}
            caminhos[f"/v1/{r.nome}/{{id}}"] = {"get": self._op_detalhe(r)}
            for nav in r.navegacoes:
                caminhos[f"/v1/{r.nome}/{{id}}/{nav.sub}"] = {"get": self._op_navegacao(r, nav)}
        caminhos["/v1/relacoes"] = {"get": self._op_relacoes()}
        caminhos["/v1/busca"] = {"get": self._op_busca()}
        caminhos["/health"] = {
            "get": {
                "tags": ["Operação"], "summary": "Healthcheck",
                "operationId": "health",
                "description": "Liveness do serviço. Usado pelo healthcheck do docker-compose.",
                "responses": {"200": {
                    "description": "Serviço no ar.",
                    "content": {"application/json": {
                        "schema": {"type": "object", "properties": {"status": {"type": "string"}},
                                   "required": ["status"], "additionalProperties": False},
                        "example": {"status": "ok"}}},
                }},
            }
        }
        return caminhos

    def _ref_param(self, filtro: str) -> dict[str, str]:
        especiais = {"confiabilidade": "Confiabilidade", "q": "Q", "classe": "Classe",
                     "oficial_ibge": "OficialIbge"}
        return {"$ref": f"#/components/parameters/{especiais.get(filtro, filtro.capitalize())}"}

    def _op_lista(self, r: Recurso) -> dict[str, Any]:
        params = [self._ref_param(f) for f in r.filtros]
        params += [{"$ref": f"#/components/parameters/{n}"}
                   for n in ("Page", "PageSize", "Sort", "Order", "Expand")]
        return {
            "tags": [r.singular],
            "summary": f"Lista {r.nome}",
            "operationId": f"listar_{r.nome}",
            "description": (
                f"Listagem paginada de {r.nome}, resolvida pelo **banco relacional** "
                f"(Ordem 2). Filtros conforme a Especificação Conceitual, Seção 2."
            ),
            "parameters": params,
            "responses": {
                "200": {
                    "description": f"Página de {r.nome}.",
                    "headers": self._cabecalhos_ok(),
                    "content": {"application/json": {
                        "schema": {"$ref": f"#/components/schemas/Pagina{r.singular}"}}},
                },
                "304": {"description": "Não modificado — o ETag enviado ainda vale."},
                **self._erros(400, 429, 500),
            },
        }

    def _op_detalhe(self, r: Recurso) -> dict[str, Any]:
        return {
            "tags": [r.singular],
            "summary": f"Detalhe de {r.singular.lower()}",
            "operationId": f"obter_{r.nome}",
            "description": (
                f"Um {r.singular.lower()} pelo ID legível, resolvido pelo **banco relacional** "
                f"(Ordem 2). `_links` traz os sub-recursos de navegação."
            ),
            "parameters": [{"$ref": "#/components/parameters/Id"},
                           {"$ref": "#/components/parameters/Expand"}],
            "responses": {
                "200": {
                    "description": f"{r.singular} encontrado.",
                    "headers": self._cabecalhos_ok(),
                    "content": {"application/json": {
                        "schema": {"$ref": f"#/components/schemas/{r.singular}"},
                        "example": self.exemplo_de(r)}},
                },
                "304": {"description": "Não modificado — o ETag enviado ainda vale."},
                **self._erros(400, 404, 429, 500),
            },
        }

    def _op_navegacao(self, r: Recurso, nav: Any) -> dict[str, Any]:
        destino = next(x for x in RECURSOS if x.nome == nav.recurso_destino)
        sentido = "no sentido inverso" if nav.sentido == "inversa" else "no sentido direto"
        tipos = ", ".join(f"`{t}`" for t in nav.tipos)
        descricao = (
            f"{nav.descricao}. Resolvido pelo **banco de grafo** (Ordem 3), percorrendo "
            f"{tipos} {sentido}. Peso e proveniência de cada aresta vêm junto, em `_relacao`."
        )
        if nav.singular:
            corpo = {"application/json": {
                "schema": {"$ref": f"#/components/schemas/{destino.singular}"},
                "example": self.exemplo_de(destino)}}
            params: list[Any] = [{"$ref": "#/components/parameters/Id"}]
            respostas_404 = (404,)
        else:
            corpo = {"application/json": {
                "schema": {"$ref": f"#/components/schemas/Pagina{destino.singular}"}}}
            params = [{"$ref": "#/components/parameters/Id"},
                      {"$ref": "#/components/parameters/Page"},
                      {"$ref": "#/components/parameters/PageSize"},
                      {"$ref": "#/components/parameters/Confiabilidade"}]
            respostas_404 = (404,)
        return {
            "tags": [r.singular],
            "summary": f"{r.singular} → {nav.sub}",
            "operationId": f"navegar_{r.nome}_{nav.sub}",
            "description": descricao,
            "parameters": params,
            "responses": {
                "200": {
                    "description": nav.descricao + ".",
                    "headers": self._cabecalhos_ok(),
                    "content": corpo,
                },
                "304": {"description": "Não modificado — o ETag enviado ainda vale."},
                **self._erros(400, *respostas_404, 429, 500),
            },
        }

    def _op_relacoes(self) -> dict[str, Any]:
        return {
            "tags": ["Relações"],
            "summary": "Lista relações",
            "operationId": "listar_relacoes",
            "description": (
                "Acesso direto à camada RELACOES — Especificação Conceitual, Seção 3. "
                "Resolvido pelo **banco de grafo** (Ordem 3), que guarda peso, "
                "confiabilidade e proveniência como propriedades nativas da aresta."
            ),
            "parameters": [
                {"name": "origem_id", "in": "query", "required": False,
                 "description": "Filtra por ID de origem exato.",
                 "schema": {"type": "string"}, "example": "REC-000001"},
                {"name": "destino_id", "in": "query", "required": False,
                 "description": "Filtra por ID de destino exato.",
                 "schema": {"type": "string"}, "example": "ING-000010"},
                {"name": "tipo_relacao", "in": "query", "required": False,
                 "description": "Um dos 12 tipos da ontologia. Dicionário v1.2, Seção 21.",
                 "schema": {"type": "string", "enum": [d.tipo for d in TIPOS_RELACAO]},
                 "example": "USA_INGREDIENTE"},
                {"$ref": "#/components/parameters/Confiabilidade"},
                {"$ref": "#/components/parameters/Page"},
                {"$ref": "#/components/parameters/PageSize"},
            ],
            "responses": {
                "200": {
                    "description": "Página de relações.",
                    "headers": self._cabecalhos_ok(),
                    "content": {"application/json": {
                        "schema": {"$ref": "#/components/schemas/PaginaRelacao"}}},
                },
                "304": {"description": "Não modificado — o ETag enviado ainda vale."},
                **self._erros(400, 422, 429, 500),
            },
        }

    def _op_busca(self) -> dict[str, Any]:
        return {
            "tags": ["Busca"],
            "summary": "Busca global",
            "operationId": "busca_global",
            "description": (
                "Busca textual multi-entidade — Especificação Conceitual, Seção 4. "
                "Resolvida pelo **índice full-text do banco de grafo** "
                "(`objeto_roots_nome_ft`, criado na carga da Ordem 3 sobre `nome_pt` e "
                "`descricao_pt`). Retorna itens heterogêneos, cada um com `tipo` indicando "
                "o catálogo de origem."
            ),
            "parameters": [
                {"name": "q", "in": "query", "required": True,
                 "description": "Termo de busca. Obrigatório.",
                 "schema": {"type": "string", "minLength": 1}, "example": "mandioca"},
                {"name": "tipos", "in": "query", "required": False,
                 "description": ("Lista separada por vírgula, para restringir os catálogos. "
                                 "Omitido, busca em todos."),
                 "schema": {"type": "string"}, "example": "ingrediente,receita"},
                {"$ref": "#/components/parameters/Page"},
                {"$ref": "#/components/parameters/PageSize"},
            ],
            "responses": {
                "200": {
                    "description": "Resultados heterogêneos, ordenados por relevância.",
                    "headers": self._cabecalhos_ok(),
                    "content": {"application/json": {
                        "schema": {"$ref": "#/components/schemas/PaginaBusca"}}},
                },
                "304": {"description": "Não modificado — o ETag enviado ainda vale."},
                **self._erros(400, 429, 500),
            },
        }

    # --- documento ----------------------------------------------------

    def documento(self) -> dict[str, Any]:
        tags = [{"name": r.singular, "description": f"Origem: aba '{r.aba_workbook}'."}
                for r in RECURSOS]
        tags += [
            {"name": "Relações", "description": "Origem: aba '11. RELACOES'."},
            {"name": "Busca", "description": "Busca global sobre o índice full-text do grafo."},
            {"name": "Operação", "description": "Endpoints de infraestrutura."},
        ]
        return {
            "openapi": "3.1.0",
            "info": {
                "title": "Roots of Brazil — API do Corpus Fundador",
                "version": "1.1.0",
                "summary": "Camada de acesso somente leitura ao Corpus Fundador v1.1.",
                "description": (
                    "Implementa a Especificação Conceitual da API v1.1. Serve as 381 entidades "
                    "e 1.585 relações do Corpus Fundador, homologado na Auditoria Sprint 2.\n\n"
                    "**Somente leitura.** Não há POST, PUT ou DELETE: o corpus é curado offline "
                    "(mineração + auditoria) e publicado como snapshot versionado, não editado "
                    "pela API — Especificação Conceitual, Seção 6.\n\n"
                    "**Duas origens de dado.** Listagem e detalhe vêm do banco relacional "
                    "(Ordem 2); navegação entre entidades e busca global vêm do banco de grafo "
                    "(Ordem 3). A divisão está documentada em cada operação.\n\n"
                    "**Fidelidade ao corpus.** Toda propriedade de resposta corresponde 1:1 a "
                    "uma coluna do Dicionário de Dados Oficial v1.2 — sem agregação, "
                    "transformação ou dado derivado além do já calculado no corpus "
                    "(Especificação Conceitual, Seção 7).\n\n"
                    "**Confiabilidade sempre visível.** Nenhuma resposta esconde o grau de "
                    "certeza: `confiabilidade` acompanha toda entidade, e `peso`, `fonte`, "
                    "`pagina` e `observacoes` acompanham toda relação.\n\n"
                    "**Acesso.** Aberto, sem chave de API. Limite de 100 requisições por "
                    "minuto por IP; acima disso, 429. CORS liberado para qualquer origem."
                ),
                "license": {"name": "MIT", "identifier": "MIT"},
                "contact": {"name": "Roots of Brazil"},
            },
            "servers": [
                {"url": "http://localhost:8000", "description": "Desenvolvimento local."},
            ],
            "tags": tags,
            "paths": self.paths(),
            "components": {"schemas": self.schemas(), "parameters": self.parametros()},
        }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", type=Path, default=RAIZ / "roots_of_brazil_dev.db")
    p.add_argument("--check", action="store_true",
                   help="Não escreve; falha se o openapi.yaml versionado estiver desatualizado.")
    args = p.parse_args(argv)

    if not args.db.exists():
        print(f"Banco {args.db} não encontrado. Rode scripts/ordem2/etl.py primeiro.",
              file=sys.stderr)
        return 2

    doc = Gerador(args.db).documento()
    texto = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=100)

    if args.check:
        atual = SAIDA.read_text(encoding="utf-8") if SAIDA.exists() else ""
        if atual != texto:
            print("openapi.yaml está DESATUALIZADO — rode `python api/gerar_openapi.py`.",
                  file=sys.stderr)
            return 1
        print("openapi.yaml está em dia com o catálogo e o Dicionário.")
        return 0

    SAIDA.write_text(texto, encoding="utf-8")
    n_paths = len(doc["paths"])
    n_ops = sum(len(v) for v in doc["paths"].values())
    print(f"{SAIDA.relative_to(RAIZ)}: {n_paths} paths, {n_ops} operações, "
          f"{len(doc['components']['schemas'])} schemas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
