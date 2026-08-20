# CLAUDE.md

Orientações para assistentes de IA trabalhando neste repositório.

## O que é este projeto

**Roots of Brazil** é a plataforma técnica que serve o **Corpus Fundador** — um acervo de conhecimento sobre a culinária brasileira (ingredientes, receitas, técnicas, povos formadores, territórios, biomas, patrimônio imaterial) — por três caminhos complementares: uma **ontologia OWL**, um **banco relacional** e um **banco de grafo**.

O código é executado em **Ordens** numeradas, definidas no *Manual de Sprint de Implementação (Livro 2)*. Cada Ordem entrega artefatos e um relatório em `docs/relatorio_ordemN.md`. Toda a documentação, nomes de função, mensagens e comentários estão **em português** — mantenha isso.

Estado atual: **Ordens -1 a 3 entregues.** A API de domínio (Ordem 4) ainda não existe.

## A Regra Mestra

> **Nunca inventar dado. Nunca ajustar dado para bater com um número.**

É a restrição que governa tudo aqui, e a razão de várias escolhas que parecem excesso de zelo:

- Campos ainda não populados recebem **valores sentinela documentados** (`"não classificado"`, `"não informado"`), nunca um palpite.
- `LivroFonte` tem esquema definido e **0 instâncias** — o Dicionário v1.2 diz "população pendente". Nenhum ETL pode criar uma linha ali.
- Os ETLs **param com código de saída 1** quando uma contagem diverge do baseline auditado. Eles não corrigem, não arredondam, não completam.
- Se um número dado num pedido não bater com o corpus homologado, **reporte a divergência e use o número auditado** — não implemente para o número errado nem silencie a diferença.

O baseline homologado (Ata v1.1 / Relatório de Auditoria Sprint 2), que aparece em código e testes:

| | |
|---|---|
| Objetos | **381** — Ingrediente 130, Receita 136, Técnica 38, Povo 17, Território 18, Patrimônio 35, Bioma 7, LivroFonte 0 |
| Relações | **1.585** em **12 tipos** (10 com instância + 2 reservados) |
| Órfãos | **18** objetos sem nenhuma relação |
| Distribuição | USA_INGREDIENTE 895, ASSOCIADO_A_POVO 205, CULTIVADO_EM 106, UTILIZA_TECNICA 85, PREPARADO_COM 81, OCORRE_EM 77, ORIGINARIO_DE 67, PATRIMONIO_DE 38, LOCALIZADO_EM_BIOMA 24, DERIVA_DE 7 |

Se você mudar qualquer um desses números, algum teste vai falhar — e essa é a intenção.

## Estrutura

```
app/                    # aplicação FastAPI
  main.py               # esqueleto da Ordem 0: só /health. Rotas de domínio → Ordem 4
  core/logging.py       # logging JSON com nível AUDIT (25) customizado
  database/neo4j.py     # config + driver do Neo4j (Ordem 3)
  models/grafo.py       # modelo do grafo, derivado da ontologia (Ordem 3)
  api/ ai/ repositories/ schemas/ services/   # ainda vazios (Ordens 4-5)
  tests/test_health.py  # testes da própria app

schemas/                # os contratos de dado — a fonte da verdade do domínio
  ontologia.ttl         # OWL/RDF: 8 classes + 12 object properties (Ordem 1)
  shapes.shacl.ttl      # SHACL, validação
  context.jsonld        # contexto JSON-LD
  ddl_sqlite.sql        # DDL relacional dev (Ordem 2)
  ddl_postgresql.sql    # DDL relacional produção
  ddl_neo4j.cypher      # DDL do grafo — GERADO, não editar à mão (Ordem 3)

scripts/ordem2/etl.py           # xlsx → SQLite
scripts/ordem3/etl_neo4j.py     # SQLite → Neo4j (dry-run por padrão)

tests/ordem1/  ordem2/  ordem3/ # testes por Ordem, espelhando os artefatos
docs/relatorio_ordemN.md        # um relatório por Ordem
alembic/                        # migrations (target_metadata ainda None)
```

## Comandos

```bash
poetry install

pytest                     # gate de cobertura de 90% vem do pyproject (addopts)
pytest tests/ordem3 -q     # só uma Ordem
ruff check .
mypy .                     # configurado como strict
mkdocs serve

docker compose up -d       # api + postgres + neo4j
```

O CI (`.github/workflows/ci.yml`) roda ruff, mypy, bandit, safety, pytest com `--cov-fail-under=90` e um `docker build`. Rode ao menos `pytest` e `ruff check .` antes de commitar.

## Convenções que importam

**Branches e commits.** Ver `CONTRIBUTING.md`. `main` e `develop` são protegidas; features nascem de `develop`. Commits seguem Conventional Commits: `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`, `ci:`.

**Dois eixos de versionamento independentes** — nunca confunda:
- **Plataforma (código)**: SemVer `MAJOR.MINOR.PATCH`.
- **Corpus (dados)**: `v1.0`, `v1.1`, `v1.2`… política própria do Dicionário de Dados Oficial v1.2, Seção 6.

Uma mudança de schema do corpus não implica MAJOR da plataforma, nem vice-versa.

**Rastreabilidade em comentário.** Comentários no código citam a origem da regra — "Dicionário v1.2, Seção 21", "Ata de Homologação v1.1", "Relatório de Auditoria Sprint 2". Mantenha esse hábito: é o que permite auditar a decisão depois.

**Relatórios de Ordem.** Toda Ordem termina com `docs/relatorio_ordemN.md` seguindo o formato dos anteriores: o que foi entregue, decisões de modelagem numeradas e justificadas, tabela de validações com resultado, **limitações e pendências declaradas explicitamente**, e uma linha final de status. Os relatórios existentes são honestos sobre o que não foi feito — siga isso. Acrescente a entrada nova ao `nav` do `mkdocs.yml`.

## Ao mexer no modelo de dados

As três representações precisam continuar consistentes entre si:

```
ontologia.ttl  ──►  ddl_sqlite.sql / ddl_postgresql.sql  ──►  ddl_neo4j.cypher
   (classes)              (tabelas)                             (labels)
```

- `schemas/ddl_neo4j.cypher` é **gerado** a partir de `app/models/grafo.py`. Editou o modelo? Regere e commite:
  ```bash
  python -m scripts.ordem3.etl_neo4j --emitir-schema schemas/ddl_neo4j.cypher
  ```
  O teste `test_ddl_neo4j_esta_sincronizado_com_o_gerador` falha se você esquecer.
- `tests/ordem3/test_modelo_grafo.py` compara labels e tipos de aresta diretamente com o texto de `ontologia.ttl`. Adicionar uma classe OWL sem adicionar o label quebra o teste — de propósito.
- O grafo usa o label transversal `:ObjetoRoots` em todo nó (equivalente à superclasse OWL e à view `objeto_universal` do SQLite). Atributos de relação (`peso`, `confiabilidade`, `fonte`…) são **propriedades de aresta**, não nós de reificação.
- O DDL do Neo4j precisa continuar rodando em **Community**: só *node uniqueness constraints* e índices. Nada de `IS NOT NULL`, `IS NODE KEY` ou unicidade de relacionamento — há teste que barra isso.

## Ao mexer em ETL

- **A fonte é somente-leitura.** O ETL da Ordem 2 abre o `.xlsx` com `data_only=True` e nunca escreve nele; o da Ordem 3 abre o SQLite com `?mode=ro`.
- **O corpus tem uma porta de entrada só.** Ordem 2 extrai do `.xlsx`; Ordem 3 projeta o SQLite no grafo. Não reextraia do `.xlsx` na Ordem 3 — `uuid` e `slug` são gerados na carga da Ordem 2 e reextrair criaria identidades divergentes entre os dois bancos.
- **Fail-fast contra o baseline**, sempre. Compare com os números auditados e saia com código 1 na divergência.
- **`scripts/ordem3/etl_neo4j.py` é dry-run por padrão.** Sem `--executar` ele não abre conexão nenhuma. Não inverta esse default. Há um teste que substitui `cria_driver` por uma armadilha para garantir isso.

## Segurança

- **Nenhuma senha no código ou em arquivo versionado.** `carrega_config()` levanta se `NEO4J_PASSWORD` não estiver no ambiente — não assuma `neo4j/neo4j`. Use `.env` (ignorado pelo git); `.env.example` documenta as variáveis.
- **Tipos de aresta passam por whitelist, não por escaping.** O Neo4j 5 não parametriza tipo de relacionamento, então ele é interpolado literalmente no Cypher; `grafo.valida_tipo_relacao()` é a única barreira contra injeção. O mesmo vale para labels. Nunca gere Cypher com um identificador vindo de fora sem passar por essas funções.
- **Nunca `MATCH (n) DETACH DELETE n`.** A limpeza do grafo atinge só `:ObjetoRoots`.
- **Testes de integração são duplamente travados**: exigem `ROOTS_TESTE_NEO4J=1` e um `NEO4J_DATABASE` diferente do default, porque escrevem e apagam nós.

## Pegadinhas conhecidas

- **`confiabilidade` valida por prefixo de emoji, não por string exata.** Os dados reais trazem `"🔵 Inferido com cautela"`, `"🔵 Inferido (casamento textual…)"` — o Dicionário v1.2 Seção 11 já previa "enum + nota". Um `CHECK ... IN (...)` com os 4 valores literais quebra na carga real. Ver o relatório da Ordem 2.
- **`bioma` não tem coluna `confiabilidade`** — usa `fonte` e `oficial_ibge`. `livro_fonte` também não tem.
- **`logs/` está no `.gitignore`**, então não existe em clone limpo; `configure_logging()` cria o diretório antes de abrir o handler. Não remova esse `mkdir`.
- **Dados não são versionados.** `Corpus_Fundador_v1.1.xlsx` e `roots_of_brazil_dev.db` não estão no repositório. Testes que dependem de dado usam o corpus **sintético** de `tests/ordem3/conftest.py`, que reproduz as cardinalidades auditadas sem conter conteúdo real.
- **`mkdocs.yml` referencia `relatorios/ordem-2_consistencia/…`, que não existe** — inconsistência conhecida, registrada em `docs/matriz_consistencia.json`. `mkdocs build --strict` falha por causa dela.
- **Alembic ainda não tem metadata.** `alembic/env.py` tem `target_metadata = None`; os models SQLAlchemy só chegam quando alguém os escrever (o schema hoje vive em SQL puro, em `schemas/`).
