"""
Roots of Brazil — gerador da Postman Collection (Ordem 4).

Deriva `api/postman_collection.json` de `api/openapi.yaml`. Gerar a partir do
contrato, e não escrever à mão, é o que garante que a coleção não descreva uma
API diferente da publicada: um endpoint novo aparece nas duas, ou em nenhuma.

Formato: Collection v2.1.0.

Uso:
    python api/gerar_postman.py
    python api/gerar_postman.py --check   # falha se estiver desatualizada
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

RAIZ = Path(__file__).resolve().parents[1]
ENTRADA = RAIZ / "api" / "openapi.yaml"
SAIDA = RAIZ / "api" / "postman_collection.json"


def _valor_de_exemplo(parametro: dict[str, Any], spec: dict[str, Any]) -> str:
    """Valor plausível para o parâmetro, tirado do próprio contrato."""
    if "example" in parametro:
        return str(parametro["example"])
    esquema = parametro.get("schema", {})
    if "example" in esquema:
        return str(esquema["example"])
    if "default" in esquema:
        return str(esquema["default"])
    if esquema.get("enum"):
        return str(esquema["enum"][0])
    return ""


def _resolver(ref: str, spec: dict[str, Any]) -> dict[str, Any]:
    no: Any = spec
    for parte in ref.lstrip("#/").split("/"):
        no = no[parte]
    return dict(no)


def _requisicao(caminho: str, operacao: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    parametros = [
        _resolver(p["$ref"], spec) if "$ref" in p else p
        for p in operacao.get("parameters", [])
    ]

    # Parâmetros de path viram a variável do Postman e o valor de exemplo.
    caminho_final = caminho
    for p in parametros:
        if p["in"] == "path":
            caminho_final = caminho_final.replace(
                "{" + p["name"] + "}", _valor_de_exemplo(p, spec)
            )

    # Só os filtros mais úteis vêm habilitados; o resto entra desabilitado,
    # para o usuário ligar no Postman sem precisar lembrar o nome.
    sempre_ligados = {"q"}
    query = [
        {
            "key": p["name"],
            "value": _valor_de_exemplo(p, spec),
            "description": p.get("description", ""),
            "disabled": not (p.get("required") or p["name"] in sempre_ligados),
        }
        for p in parametros
        if p["in"] == "query"
    ]

    partes = [x for x in caminho_final.strip("/").split("/") if x]
    return {
        "name": operacao["summary"],
        "request": {
            "method": "GET",
            "header": [{"key": "Accept", "value": "application/json"}],
            "url": {
                "raw": "{{base_url}}" + caminho_final,
                "host": ["{{base_url}}"],
                "path": partes,
                "query": query,
            },
            "description": operacao["description"],
        },
        "response": [],
        # Um teste por requisição, executado pelo Postman/Newman: confere o
        # status e, nas listagens, o envelope de paginação da Seção 5.1.
        "event": [{
            "listen": "test",
            "script": {"type": "text/javascript", "exec": [
                "pm.test('status 200', () => pm.response.to.have.status(200));",
                "pm.test('responde JSON', () => pm.response.to.be.json);",
                "pm.test('traz ETag', () => pm.response.to.have.header('ETag'));",
                "pm.test('traz cota de uso', () =>",
                "  pm.response.to.have.header('X-RateLimit-Limit'));",
                "const corpo = pm.response.json();",
                "if ('items' in corpo) {",
                "  pm.test('envelope da Secao 5.1', () => {",
                "    pm.expect(corpo).to.have.all.keys('total','page','page_size','items');",
                "  });",
                "}",
            ]},
        }],
    }


def construir(spec: dict[str, Any]) -> dict[str, Any]:
    """Agrupa as operações por tag, na ordem em que o contrato as declara."""
    pastas: dict[str, list[dict[str, Any]]] = {t["name"]: [] for t in spec["tags"]}
    for caminho, operacoes in spec["paths"].items():
        for metodo, operacao in operacoes.items():
            if metodo != "get":
                continue
            tag = operacao.get("tags", ["Outros"])[0]
            pastas.setdefault(tag, []).append(_requisicao(caminho, operacao, spec))

    return {
        "info": {
            "name": f"{spec['info']['title']} v{spec['info']['version']}",
            "description": (
                f"{spec['info']['summary']}\n\n"
                "Gerada a partir de `api/openapi.yaml` por `api/gerar_postman.py` — "
                "não editar à mão, a edição se perde na próxima geração.\n\n"
                "Sem chave de API: a coleção não define autenticação porque a API não "
                "exige nenhuma. Limite de 100 requisições por minuto por IP."
            ),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "variable": [{
            "key": "base_url",
            "value": spec["servers"][0]["url"],
            "type": "string",
            "description": "Raiz da API. Trocar para o ambiente desejado.",
        }],
        "item": [
            {"name": nome, "item": itens,
             "description": next((t.get("description", "") for t in spec["tags"]
                                  if t["name"] == nome), "")}
            for nome, itens in pastas.items() if itens
        ],
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--check", action="store_true")
    args = p.parse_args(argv)

    if not ENTRADA.exists():
        print(f"{ENTRADA} não existe — rode `python api/gerar_openapi.py`.", file=sys.stderr)
        return 2

    spec = yaml.safe_load(ENTRADA.read_text(encoding="utf-8"))
    colecao = construir(spec)
    texto = json.dumps(colecao, indent=2, ensure_ascii=False) + "\n"

    if args.check:
        atual = SAIDA.read_text(encoding="utf-8") if SAIDA.exists() else ""
        if atual != texto:
            print("postman_collection.json DESATUALIZADA — rode `python api/gerar_postman.py`.",
                  file=sys.stderr)
            return 1
        print("postman_collection.json está em dia com o contrato.")
        return 0

    SAIDA.write_text(texto, encoding="utf-8")
    total = sum(len(pasta["item"]) for pasta in colecao["item"])
    print(f"{SAIDA.relative_to(RAIZ)}: {len(colecao['item'])} pastas, {total} requisições.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
