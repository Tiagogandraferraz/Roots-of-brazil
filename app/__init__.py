"""Roots of Brazil — pacote da aplicação.

Marcado como pacote regular na Ordem 4. Sem este arquivo, `app/` era um
namespace package e o mypy resolvia `app/api/parametros.py` sob dois nomes de
módulo — `api.parametros` e `app.api.parametros` —, o que impedia a checagem de
tipos de rodar. Todos os subpacotes já tinham `__init__.py`; só a raiz faltava.
"""
