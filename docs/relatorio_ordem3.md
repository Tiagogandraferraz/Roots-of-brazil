# Relatório — Ordem 3 (Integração com Neo4j)
Data: 2026-08-20

## Escopo desta rodada

Código **preparado e validado offline**, conforme a instrução explícita da Ordem: *"Antes de rodar qualquer ETL real no Neo4j, apenas prepare o código e me mostre o plano — não execute contra dados reais sem minha confirmação."*

Nenhuma linha foi escrita em nenhum servidor Neo4j. O ETL é **dry-run por padrão**: sem a flag `--executar` ele não abre conexão alguma — há inclusive um teste (`test_dry_run_e_o_padrao_e_nao_conecta_em_nada`) que substitui `cria_driver` por uma função que falha, para provar que o caminho de dry-run não toca o driver.

## Entregas

| Item da Ordem | Arquivo | Situação |
|---|---|---|
| 1. Driver Neo4j no `pyproject.toml` | `pyproject.toml` | **Já existia** desde a Ordem 0 (`neo4j = "^5.24"`) — nada a adicionar. Casa com a imagem `neo4j:5` do compose. |
| 2. Modelo de grafo a partir da ontologia | `app/models/grafo.py`, `schemas/ddl_neo4j.cypher` | Novo |
| 3. Script de carga (ETL) | `scripts/ordem3/etl_neo4j.py` | Novo |
| 4. Serviço Neo4j no `docker-compose.yml` | `docker-compose.yml` | Serviço **já existia**; corrigido o healthcheck e acrescentado `NEO4J_DATABASE` (ver abaixo) |
| 5. Testes de validação | `tests/ordem3/` (4 arquivos) | Novo — 61 testes offline + 23 de integração |
| 6. Relatório | `docs/relatorio_ordem3.md` | Este arquivo |
| — (extra) | `.env.example` | Novo — as variáveis que o compose e o ETL consomem |

## Correção de duas premissas do enunciado

Registrado aqui porque a Regra Mestra proíbe ajustar o dado para bater com um número dado de fora.

**1. "as 914+ relações ontológicas".** Não há 914 de nada no corpus homologado. Os números auditados são:

- **12 tipos** de relação na ontologia (`owl:ObjectProperty`) — 10 com instância + 2 reservados;
- **1.585 instâncias** de relação no corpus v1.1, distribuídas conforme a `mv_grafo_agregado` da Ordem 2.

O modelo foi construído sobre **12 tipos / 1.585 instâncias**, que é o que a Ata de Homologação v1.1 e o Relatório de Auditoria Sprint 2 registram. Nada foi inflado ou truncado para chegar a 914.

**2. "o `scripts/ordem2/etl.py` que usa SQLite" como padrão de fonte.** O padrão de *estrutura* foi seguido (fail-fast contra o baseline, sentinelas preservadas, nada inventado), mas a **fonte é outra**, deliberadamente:

```
Ordem 2:  Corpus_Fundador_v1.1.xlsx  ->  SQLite   (extração do dado bruto)
Ordem 3:  SQLite (saída da Ordem 2)  ->  Neo4j    (projeção em grafo)
```

Reextrair do `.xlsx` na Ordem 3 geraria **uuid e slug novos** (o ETL da Ordem 2 os gera na carga, porque não existem na fonte v1.1) — e o mesmo objeto teria identidades diferentes no relacional e no grafo. O corpus tem uma única porta de entrada; o grafo é uma projeção do que já foi auditado.

## Modelo de grafo

**8 labels de nó**, um por classe OWL — `Ingrediente`, `Receita`, `Tecnica`, `Povo`, `Territorio`, `Patrimonio`, `Bioma`, `LivroFonte`. Um teste compara o conjunto diretamente com os `roots:X a owl:Class` de `schemas/ontologia.ttl`: se a ontologia ganhar uma classe e o modelo não, o teste quebra.

**12 tipos de aresta**, um por `owl:ObjectProperty`, com o mesmo tipo de verificação automática contra o `.ttl`.

### Decisão 1 — label transversal `:ObjetoRoots`

Todo nó recebe, além do label específico, o label `:ObjetoRoots`. É o equivalente em grafo de duas coisas que já existiam:

- a superclasse `roots:ObjetoRoots` da ontologia (Ordem 1);
- a view de união `objeto_universal` do SQLite (Ordem 2), criada para resolver a FK polimórfica.

É o que torna a carga de arestas possível em um único `MATCH`: `origem_id`/`destino_id` podem apontar para qualquer um dos 8 catálogos.

### Decisão 2 — atributos de aresta como propriedades de relacionamento

`peso`, `confiabilidade`, `fonte`, `pagina`, `observacoes`, `data_criacao`, `metodo_calculo_peso` e `rel_id` moram **na aresta**. Isto é o cumprimento literal da pendência que a própria Ordem 1 deixou registrada em `ontologia.ttl`:

> "RELACOES tem atributos próprios que RDF/OWL simples não representa nativamente em uma tripla; SHACL Shape trata a validação, e a **Ordem 3 (Neo4j) modela isso nativamente como propriedades de aresta**."

Nenhum nó de reificação foi criado.

### Decisão 3 — nomes de propriedade em snake_case

Idênticos às colunas do DDL da Ordem 2, para que grafo e relacional falem o mesmo vocabulário. A correspondência com o termo OWL (`created_at` ↔ `roots:createdAt`, `ordem_taxonomica` ↔ `roots:ordemTaxonomica`) fica em `TERMO_OWL_POR_PROPRIEDADE`.

### Decisão 4 — `MERGE`, nunca `CREATE`

Nós casam por `id`, arestas por `rel_id`. Rodar o ETL duas vezes não duplica nada — há teste de idempotência na suíte de integração.

### Decisão 5 — só recursos do Neo4j Community

O compose sobe `neo4j:5`, que é Community. Constraints de **existência de propriedade**, `IS NODE KEY` e **unicidade de relacionamento** são exclusivas do Enterprise — se aparecessem no DDL, o `docker compose up` subiria normalmente e a carga quebraria depois. O DDL usa apenas *node uniqueness constraints* e índices; a unicidade de `rel_id` (que é PK no relacional) é verificada por query no pós-carga e por teste. Há um teste que falha se algum recurso Enterprise entrar no DDL.

### Schema gerado

`schemas/ddl_neo4j.cypher` — **10 constraints + 28 índices**, todos `IF NOT EXISTS`. É arquivo **gerado**: a fonte da verdade é `app/models/grafo.py`, e o teste `test_ddl_neo4j_esta_sincronizado_com_o_gerador` falha se os dois divergirem. Regerar com:

```
python -m scripts.ordem3.etl_neo4j --emitir-schema schemas/ddl_neo4j.cypher
```

## O que a Ordem 3 valida e a Ordem 2 não conseguia

No relacional, `relacoes` é uma tabela plana com FK polimórfica — `origem_id` e `destino_id` são `TEXT` sem FK real, e o `rdfs:domain`/`rdfs:range` da ontologia **não era verificável por constraint**. O relatório da Ordem 2 registra isso explicitamente.

No grafo isso vira uma query direta, e o ETL a executa para cada um dos 12 tipos:

```cypher
MATCH (origem)-[r:USA_INGREDIENTE]->(destino)
WHERE NOT any(l IN labels(origem)  WHERE l IN ['Receita'])
   OR NOT any(l IN labels(destino) WHERE l IN ['Ingrediente'])
RETURN count(r) AS n     // precisa ser 0
```

A mesma checagem roda **offline**, antes de qualquer escrita: uma aresta `USA_INGREDIENTE` cuja origem seja um `Povo` faz o ETL parar em dry-run, sem tocar no servidor.

## Plano de carga — saída real do dry-run

Executado contra o corpus **sintético** dos testes (o corpus real não é versionado — é dado, não código):

```
========================================================================
PLANO DE CARGA — Ordem 3 (Neo4j)
========================================================================

Schema: 10 constraints + 28 índices (todos IF NOT EXISTS)

Nós (381 de 381 esperados):
  ok Ingrediente    130 (esperado   130) — 1 lote(s)
  ok Receita        136 (esperado   136) — 1 lote(s)
  ok Tecnica         38 (esperado    38) — 1 lote(s)
  ok Povo            17 (esperado    17) — 1 lote(s)
  ok Territorio      18 (esperado    18) — 1 lote(s)
  ok Patrimonio      35 (esperado    35) — 1 lote(s)
  ok Bioma            7 (esperado     7) — 1 lote(s)
  ok LivroFonte       0 (esperado     0) — 0 lote(s)

Arestas (1585 de 1585 esperadas):
  ok USA_INGREDIENTE          895 (esperado   895) — (Receita)-[:USA_INGREDIENTE]->(Ingrediente)
  ok ASSOCIADO_A_POVO         205 (esperado   205) — (Receita|Ingrediente)-[:ASSOCIADO_A_POVO]->(Povo)
  ok CULTIVADO_EM             106 (esperado   106) — (Ingrediente)-[:CULTIVADO_EM]->(Territorio)
  ok UTILIZA_TECNICA           85 (esperado    85) — (Receita)-[:UTILIZA_TECNICA]->(Tecnica)
  ok PREPARADO_COM             81 (esperado    81) — (Tecnica)-[:PREPARADO_COM]->(Ingrediente)
  ok OCORRE_EM                 77 (esperado    77) — (Receita)-[:OCORRE_EM]->(Territorio)
  ok ORIGINARIO_DE             67 (esperado    67) — (Ingrediente)-[:ORIGINARIO_DE]->(Povo|Bioma)
  ok PATRIMONIO_DE             38 (esperado    38) — (Patrimonio)-[:PATRIMONIO_DE]->(Povo)
  ok LOCALIZADO_EM_BIOMA       24 (esperado    24) — (Territorio)-[:LOCALIZADO_EM_BIOMA]->(Bioma)
  ok DERIVA_DE                  7 (esperado     7) — (Ingrediente)-[:DERIVA_DE]->(Ingrediente)
  ok VARIANTE_REGIONAL          0 (esperado     0) — (ObjetoRoots)-[:VARIANTE_REGIONAL]->(ObjetoRoots)
  ok SIMILAR_A                  0 (esperado     0) — (ObjetoRoots)-[:SIMILAR_A]->(ObjetoRoots)

Validação offline: sem divergências contra o baseline da Auditoria Sprint 2.

DRY-RUN: nada foi enviado ao Neo4j. Para carregar de verdade, rode de novo com --executar.
```

## Sequência para a carga real (aguardando autorização)

```bash
# 0. pré-requisito: o banco da Ordem 2 precisa existir
python scripts/ordem2/etl.py Corpus_Fundador_v1.1.xlsx roots_of_brazil_dev.db

# 1. subir o Neo4j
cp .env.example .env && $EDITOR .env      # definir NEO4J_PASSWORD
docker compose up -d neo4j

# 2. dry-run contra o corpus REAL — nada é escrito, só o plano é impresso
python -m scripts.ordem3.etl_neo4j --sqlite roots_of_brazil_dev.db

# 3. revisar o Cypher exato que seria enviado
python -m scripts.ordem3.etl_neo4j --sqlite roots_of_brazil_dev.db \
    --emitir-cypher /tmp/carga_ordem3.cypher

# 4. SOMENTE APÓS AUTORIZAÇÃO — carga real
python -m scripts.ordem3.etl_neo4j --sqlite roots_of_brazil_dev.db --executar
```

O passo 4 aplica o schema, carrega em lotes de 500 via `UNWIND` e **reconsulta o servidor** para comparar com o baseline auditado (contagens por label e por tipo, órfãos, `rel_id` duplicado, `peso` fora de `[0,1]`, `domain`/`range` dos 12 tipos). Qualquer divergência: sai com código 1 e reporta. Nada é corrigido automaticamente.

## Validações executadas nesta rodada

**88 testes passando, 30 pulados, cobertura 98%** (`pytest` com o gate de 90% do `pyproject.toml`).

| Verificação | Resultado |
|---|---|
| 8 labels == as 8 `owl:Class` de `ontologia.ttl` | ✅ conferido contra o `.ttl` |
| 12 tipos de aresta == as 12 `owl:ObjectProperty` | ✅ conferido contra o `.ttl` |
| `owl:unionOf` de `ASSOCIADO_A_POVO` e `ORIGINARIO_DE` preservado | ✅ |
| Contagens por catálogo (130/136/38/17/18/35/7/0 = 381) | ✅ |
| Distribuição por tipo == `mv_grafo_agregado` da Ordem 2 (soma 1.585) | ✅ |
| 18 órfãos | ✅ |
| `LivroFonte` carrega 0 nós (nenhuma linha inventada) | ✅ |
| `schemas/ddl_neo4j.cypher` sincronizado com o gerador | ✅ |
| DDL não usa recurso Enterprise | ✅ |
| Fonte SQLite aberta READ-ONLY (`DELETE` é rejeitado) | ✅ |
| Dry-run não abre conexão (driver substituído por armadilha) | ✅ |
| Tipo de aresta passa por whitelist (tentativa de injeção em Cypher é rejeitada) | ✅ |
| `--limpar` sem `--executar` não faz nada | ✅ |
| Limpeza atinge só `:ObjetoRoots`, nunca `MATCH (n) DETACH DELETE n` | ✅ |
| **Testes negativos** — o ETL PARA quando o dado está corrompido | |
| ⤷ contagem de nós divergente | ✅ para |
| ⤷ contagem de arestas divergente | ✅ para |
| ⤷ aresta violando `rdfs:domain` | ✅ para |
| ⤷ aresta violando `rdfs:range` | ✅ para |
| ⤷ ponta de aresta apontando para ID inexistente | ✅ para |
| ⤷ número de órfãos mudou | ✅ para |
| ⤷ uuid duplicado | ✅ para |
| ⤷ `peso` fora de `[0,1]` | ✅ para |
| ⤷ `tipo_relacao` fora do enum de 12 | ✅ levanta |
| `ruff check` (regras da versão pinada) e `mypy --strict` nos módulos novos | ✅ limpo |

Os 30 testes pulados são os de integração (`test_carga_neo4j.py`): exigem servidor Neo4j, e são **duplamente travados** — `ROOTS_TESTE_NEO4J=1` e um `NEO4J_DATABASE` diferente do default `neo4j`, porque escrevem e apagam nós.

## Achados corrigidos fora do escopo da Ordem 3

Duas coisas impediam qualquer Ordem de rodar e foram corrigidas para destravar a validação:

**1. 23 arquivos versionados estavam envoltos em cercas markdown.** Todo o conteúdo do repositório havia sido commitado dentro de blocos ` ```python `, ` ```sql `, ` ``` ` — inclusive `docker-compose.yml`, `mkdocs.yml`, `ontologia.ttl`, os dois DDLs e os 7 arquivos `.py`. Nenhum `.py` importava, nenhum YAML parseava, o `.ttl` não era carregável. Apenas as cercas foram removidas; **nenhuma linha de conteúdo foi alterada**. Verificado: os 7 `.py` fazem `ast.parse`, `ddl_sqlite.sql` executa em SQLite, `context.jsonld` faz `json.loads`, os dois YAML parseiam.

**2. `import app.main` quebrava em clone limpo.** `configure_logging()` abre `logs/audit.log`, mas `logs/` está no `.gitignore` e portanto não existe em um checkout novo — `FileNotFoundError` no import. Corrigido com um `Path("logs").mkdir(exist_ok=True)` antes do handler.

## Pendências declaradas

- **A carga real não foi executada** — é exatamente o que a Ordem pediu. Aguarda autorização.
- **Não foi possível validar contra um servidor Neo4j real nesta sandbox**: não há daemon Docker disponível aqui. Os 23 testes de integração estão escritos e pulam com mensagem explícita; rodam assim que houver um servidor. O que está provado hoje é o modelo, a geração de Cypher e a validação offline — não a resposta do servidor.
- **`peso` continua sendo o valor determinístico herdado da confiabilidade** (🟢=0.95, 🟡=0.60, 🔵=0.30, 🔴=0.10), copiado da Ordem 2. Nenhum recálculo baseado em topologia do grafo foi feito — isso não estava no escopo e inventar fórmula aqui violaria a Regra Mestra.
- **Os dois tipos reservados (`VARIANTE_REGIONAL`, `SIMILAR_A`) seguem com 0 instâncias.** Têm constraint, índice e gerador de Cypher prontos; a materialização continua sendo pendência de v1.3.
- **`mkdocs.yml` referencia `docs/relatorios/ordem-2_consistencia/relatorio_ordem-2_consistencia.md`, que não existe no repositório** — a mesma inconsistência já registrada em `docs/matriz_consistencia.json`. Não foi mexida aqui por ser de outra Ordem; `mkdocs build --strict` vai falhar enquanto o arquivo não aparecer ou a entrada não sair do `nav`.

## Status: Ordem 3 PREPARADA E VALIDADA OFFLINE — carga real aguardando autorização
