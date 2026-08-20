# Relatório — Ordem 3 (Integração com Neo4j)
Data: 2026-08-20

## Escopo e restrição respeitada
A Ordem foi pedida com uma restrição explícita: **preparar o código e apresentar o plano, sem rodar ETL contra dados reais sem confirmação.** Nenhuma carga real foi executada. A restrição não ficou só no procedimento — ela foi codificada: `scripts/ordem3/etl_neo4j.py` roda em **dry-run por padrão** e só escreve com o flag `--execute`. Em dry-run o script sequer importa o driver do Neo4j (ver `test_cli_sem_execute_nao_conecta_no_neo4j`).

## Entregue
| Item da Ordem | Arquivo | Situação |
|---|---|---|
| 1. Driver Neo4j (dependência) | `pyproject.toml` | **Já existia** desde a Ordem 0 (`neo4j = "^5.24"`). Nenhuma alteração necessária — validado com 5.28.4. |
| 2. Modelo de grafo da ontologia | `app/models/grafo.py` | Novo — 8 labels, 12 tipos de relação, constraints e índices. |
| — camada de conexão | `app/database/neo4j.py` | Novo — configuração por env, driver, sessão. |
| 3. Script de carga (ETL) | `scripts/ordem3/etl_neo4j.py` | Novo — dry-run padrão, `--execute` explícito. |
| 4. Serviço Neo4j no compose | `docker-compose.yml` | **Já existia** o esboço; corrigido e configurado (ver "Achados" abaixo). |
| 5. Testes de validação | `tests/ordem3/` | Novo — 54 testes offline + 12 de integração. |
| 6. Relatório | `docs/relatorio_ordem3.md` | Este arquivo. |

## Modelo de grafo — a tradução OWL → property graph
| Ontologia (Ordem 1) | Neo4j (Ordem 3) |
|---|---|
| `roots:Ingrediente` (`owl:Class`) | label `:Ingrediente` |
| `roots:ObjetoRoots` (superclasse) | label adicional `:ObjetoRoots` em **todo** nó |
| `rdfs:subClassOf` | multi-label (o nó carrega os dois) |
| `roots:USA_INGREDIENTE` (`owl:ObjectProperty`) | tipo de relação `[:USA_INGREDIENTE]` |
| `rdfs:domain` / `rdfs:range` | `dominio` / `alcance` em `TipoRelacao`, validados no ETL |
| `owl:unionOf` (2 casos) | conjunto de labels aceitos, sem achatar |
| reificação de aresta (nota da Ordem 1) | **propriedades nativas de aresta** |

A última linha é o ponto da Ordem. `schemas/ontologia.ttl` (linhas 183-186) registra que RDF/OWL simples não representa em uma tripla os atributos próprios de `RELACOES` — peso, confiabilidade, proveniência — e **delega explicitamente essa modelagem à Ordem 3**. No property graph elas são propriedades da aresta (`rel_id`, `fonte`, `pagina`, `confiabilidade`, `observacoes`, `data_criacao`, `peso`, `metodo_calculo_peso`), sem nó intermediário. É a dívida de modelagem da Ordem 1 sendo quitada aqui.

O label `:ObjetoRoots` cumpre no grafo o mesmo papel que a view `objeto_universal` cumpre no SQLite: dá alvo único para resolver as pontas polimórficas de `relacoes` e ancora as constraints de unicidade de `id` e `uuid` sobre **todo** o corpus, não por catálogo.

## Fonte da carga: o SQLite da Ordem 2, não a planilha
```
Corpus_Fundador_v1.1.xlsx  --Ordem 2-->  SQLite  --Ordem 3-->  Neo4j
         (read-only)                   (canônico)             (grafo)
```
Reler o `.xlsx` aqui criaria um segundo caminho de normalização e, com ele, a possibilidade de os dois bancos divergirem em silêncio. O SQLite já é o conteúdo normalizado, deduplicado e validado uma vez; a Ordem 3 projeta esse mesmo conteúdo no grafo.

## Baseline e disciplina fail-fast (herdada da Ordem 2)
Antes de qualquer escrita, o ETL confere contra o Relatório de Auditoria Sprint 2 — o mesmo baseline que a Ordem 2 usa:

| Verificação | Regra |
|---|---|
| Nós por label | 130/136/38/17/18/35/7/0 = **381** |
| Arestas por tipo | 895/205/106/85/81/77/67/38/24/7 + 2 reservados = **1.585** |
| `id` único em todo o corpus | sem colisão entre catálogos |
| `uuid` único em todo o corpus | sem colisão entre catálogos |
| `rel_id` único | sem colisão entre as subséries `REL-` e `REL-B` |
| Pontas resolvem para nó existente | FK polimórfica da Seção 25.3 |
| Aresta respeita `rdfs:domain`/`rdfs:range` | validada contra a ontologia, aresta a aresta |
| `peso` em [0,1] | replica o CHECK do DDL |
| Órfãos (pós-carga) | 18, idêntico à Ata |

Divergindo qualquer uma, o script **para e reporta** — não ajusta dado para bater número. Em modo `--execute`, a validação roda **antes** de abrir a conexão: uma fonte divergente nunca chega a escrever parcialmente no grafo. Depois da carga, tudo é recontado **consultando o Neo4j** (não a fonte) e comparado de novo.

## Executado e validado nesta rodada
| Validação | Resultado |
|---|---|
| `pytest tests/ordem3` | ✅ **54 passaram**, 12 puladas (integração, sem Neo4j no ar) |
| `ruff check` (código novo) | ✅ limpo |
| `mypy --strict` (3 módulos novos) | ✅ `Success: no issues found` |
| Cobertura `app/models/grafo.py` | ✅ 100% |
| Cobertura `app/database/neo4j.py` | 70% — as linhas restantes são exatamente as que exigem servidor |
| `docker compose config` | ✅ YAML válido, variáveis resolvem |
| Dry-run do ETL ponta a ponta | ✅ executado contra SQLite sintético: leu, validou, imprimiu o plano, **bloqueou a carga** por divergência de baseline e saiu com código 1 |

Os testes offline não são de fachada: eles **releem `schemas/ontologia.ttl`** e comparam com `app/models/grafo.py`. Se alguém acrescentar uma `owl:Class` ou um `owl:ObjectProperty` na ontologia sem refletir no modelo do grafo, `test_todo_owl_class_do_corpus_virou_label` e `test_todo_object_property_virou_tipo_de_relacao` quebram. Uma tradução que sai de sincronia em silêncio é pior do que não ter tradução.

## Achados durante a execução
### 1. `docker-compose.yml` estava com o YAML inválido
O arquivo commitado começa com uma cerca markdown (```` ``` ````) e termina com outra. Como YAML, isso não sobe: `docker compose up` falha na leitura. Corrigido nesta Ordem, junto com a configuração do serviço.

**Este não era um caso isolado — ver "Defeito das Ordens 0-2" no fim do relatório.**

### 2. Serviço `neo4j`: healthcheck media a coisa errada
O healthcheck original era `wget --spider http://localhost:7474`. O servidor responde na porta HTTP **antes** de aceitar Cypher, então `depends_on: condition: service_healthy` liberava a API contra um banco que ainda não consultava. Trocado por uma consulta real via Bolt (`cypher-shell 'RETURN 1'`), com `start_period: 60s` para cobrir a criação dos stores na primeira subida.

### 3. Imagem `neo4j:5` flutuava; edição Community limita as constraints
Fixada em `neo4j:5.26-community` (linha LTS): `neo4j:5` traria mudança de minor sem aviso sob um serviço que a carga e os testes de integração assumem estável.

Escolhida a Community, apenas **constraints de unicidade de nó** são aplicáveis. Constraints de existência (`IS NOT NULL`), node key e qualquer constraint de **relação** são exclusivas do Enterprise. Então:
- o que o banco garante: `id` e `uuid` únicos em `:ObjetoRoots`;
- o que o **ETL** garante (fail-fast em Python): unicidade de `rel_id`, faixa de `peso`, obrigatoriedade de `nome_pt`, domain/range das arestas.

O Cypher equivalente do Enterprise fica registrado em `CONSTRAINTS_ENTERPRISE`, **não executado** — emitir um comando que a edição em uso rejeita daria a falsa impressão de que a regra está sendo aplicada pelo banco. Mesma estratégia que a Ordem 2 adotou para a FK polimórfica.

### 4. "914+ relações ontológicas" — divergência levantada e RESOLVIDA
A Ordem foi pedida citando "as 914+ relações ontológicas". Nenhum artefato do projeto tem esse número, e o modelo foi construído sobre os documentados: **1.585 relações** (instâncias, Relatório de Auditoria Sprint 2, conferidas por `mv_grafo_agregado` na Ordem 2) e **12 tipos** de relação (`owl:ObjectProperty` na ontologia, 10 com instância + 2 reservados). Nada foi ajustado para chegar a 914.

**Resolução:** confirmado pelo responsável do projeto que 1.585 é o número correto e oficial (baseline da Auditoria Sprint 2, documentado no Manual de Sprint — Livro 2, Ordens 0-2) e que "914+" foi erro de redação do pedido, sem lastro em nenhum documento. Descartado. O baseline em `app/models/grafo.py` já era o correto e permanece inalterado.

## Decisões de modelagem documentadas
1. **`MERGE`, nunca `CREATE`.** A carga é idempotente: rodar duas vezes não duplica nó nem aresta. Nós entram por `MERGE (n:ObjetoRoots {id})`; arestas por `MERGE (o)-[r:TIPO {rel_id}]->(d)`. Testado em `test_carga_e_idempotente`.
2. **`rel_id` na chave do MERGE da aresta**, não o par (origem, destino). É o que dá identidade à aresta na fonte e o que permite duas arestas do mesmo tipo entre o mesmo par de nós — necessário porque a v1.1 mantém duas subséries de `REL_ID` (`REL-xxxxxx` e `REL-Bxxxxx`), preservadas como estão conforme pendência de v1.3.
3. **Todas as colunas do SQLite viram propriedades do nó**, em vez de uma lista escrita à mão. Garante que o grafo carregue exatamente os campos do Dicionário v1.2 que a Ordem 2 materializou, sem uma segunda lista para sair de sincronia com o DDL. `NULL` é descartado: no Neo4j, gravar `None` e não gravar são a mesma coisa.
4. **Uniões OWL preservadas como conjunto de labels.** `ASSOCIADO_A_POVO` aceita domain `{Receita, Ingrediente}` e `ORIGINARIO_DE` aceita range `{Povo, Bioma}`. Achatar qualquer uma para um único label rejeitaria arestas legítimas do corpus (205 e 67 instâncias respectivamente).
5. **Reservados mantidos com domain/range amplos.** `VARIANTE_REGIONAL` e `SIMILAR_A` continuam sobre `ObjetoRoots`/`ObjetoRoots`, exatamente como a ontologia — que registra não haver base documental para restringir mais. Nenhuma semântica foi inventada aqui.
6. **Sem equivalente do índice composto `(origem_id, tipo_relacao)`.** Ele existia na Ordem 2 para compensar o modelo relacional; no property graph a travessia por tipo a partir de um nó já é O(1). Os demais índices da Seção 24 têm equivalente: `slug`, `categoria`/`classe` por label, `confiabilidade` por tipo de relação, mais um full-text sobre `nome_pt`/`descricao_pt` (base da busca semântica da Ordem 5).
7. **Labels e tipos de relação nunca vêm de dado de entrada.** Cypher não parametriza label nem tipo de relação, então eles são interpolados — sempre a partir da lista fechada de `app/models/grafo.py`, com rejeição explícita de qualquer valor fora dela. Testado com uma tentativa de injeção (`test_merge_de_no_rejeita_label_fora_da_ontologia`).
8. **`--limpar` restrito a `:ObjetoRoots`**, nunca `MATCH (n) DETACH DELETE n`. Um DELETE cego apagaria qualquer outra coisa que estivesse no mesmo banco. Exige `--execute` junto; sozinho é erro de uso, não limpeza silenciosa.

## Limitações declaradas
- **A carga real não foi executada** — é a restrição da Ordem, e ela foi respeitada. O plano está pronto e é reproduzível (comandos abaixo).
- **Os 12 testes de integração foram PULADOS, não executados.** Não há daemon Docker nesta sandbox, logo não há Neo4j alcançável. Eles se pulam sozinhos com a razão impressa (`pytest -rs`), em vez de falhar ou de fingir sucesso. Tudo que depende do servidor — sintaxe do Cypher aceita pelo motor, disponibilidade das constraints na Community, carga, travessia multi-hop, full-text — está **coberto por teste escrito mas ainda não verificado em execução.**
- **`Corpus_Fundador_v1.1.xlsx` e `roots_of_brazil_dev.db` não estão no repositório** (o `.gitignore` exclui `*.db`). Os testes offline usam uma fixture sintética montada com o DDL real da Ordem 2.
- **Python 3.11 nesta sandbox**, contra `^3.13` no `pyproject.toml`. `mypy --strict` foi rodado com `--python-version 3.11`; nada no código novo usa sintaxe posterior a 3.10.

## Como executar a carga real (aguardando confirmação)
```bash
# 1. Subir o Neo4j e conferir que ele aceita Cypher, não só HTTP
docker compose up -d neo4j
docker compose ps neo4j          # deve chegar a (healthy)

export NEO4J_URI=bolt://localhost:7687 NEO4J_USER=neo4j NEO4J_PASSWORD=<senha>

# 2. Regenerar o SQLite da Ordem 2 (fonte da carga)
python scripts/ordem2/etl.py Corpus_Fundador_v1.1.xlsx

# 3. DRY-RUN — lê, valida contra ontologia e baseline, imprime o plano.
#    Não escreve nada. Só prosseguir se sair com código 0.
python scripts/ordem3/etl_neo4j.py

# 4. Carga real (só depois do dry-run limpo)
python scripts/ordem3/etl_neo4j.py --execute

# 5. Rodar os 12 testes de integração, agora com o banco no ar
pytest tests/ordem3/test_carga_neo4j.py -v
```

## Defeito das Ordens 0-2 — detectado aqui, corrigido em commit separado
**23 dos arquivos versionados estavam com cercas de bloco markdown (```` ``` ````) na primeira e na última linha**, incluindo todo o código Python das Ordens 0 a 2, os schemas, o `mkdocs.yml`, o `alembic.ini` e os relatórios anteriores. Consequências reais:

- nenhum módulo afetado importava (`SyntaxError` na linha 1) — `app/main.py`, `app/core/logging.py`, `alembic/env.py`, `scripts/ordem2/etl.py`;
- `tests/ordem1/` e `tests/ordem2/` não eram sequer coletados pelo pytest;
- o build da imagem e o workflow de CI (`.github/workflows/ci.yml`) não tinham como passar.

O `docker-compose.yml` foi corrigido dentro da Ordem 3, por ser item explícito do escopo (4). Os **22 restantes foram corrigidos em commit separado**, marcado como correção de defeito das Ordens 0-2 — não como parte do escopo desta Ordem. Com o defeito sanado, o contorno que `tests/ordem3/conftest.py` mantinha para ler `schemas/ddl_sqlite.sql` foi removido no mesmo commit.

Validação da correção, por tipo de arquivo:

| Tipo | Verificação | Resultado |
|---|---|---|
| Python (7 arquivos) | `py_compile` | ✅ todos compilam |
| YAML (`mkdocs.yml`) | `yaml.safe_load` | ✅ parseia |
| JSON-LD (`context.jsonld`) | `json.load` | ✅ parseia |
| INI (`alembic.ini`) | `configparser` | ✅ parseia, 3+ seções |
| SQL (`ddl_sqlite.sql`) | `executescript` em SQLite | ✅ 9 tabelas + 3 views criadas |
| Suíte completa | `pytest tests/` | ✅ 59 passaram, 19 puladas |
| `tests/ordem1/` (antes: não coletado) | `pytest` | ✅ 5 passaram |
| Repositório inteiro | `ruff check .` | ✅ limpo (antes nem parseava) |

Nenhum conteúdo foi alterado além da remoção das duas linhas de cerca por arquivo. As cercas internas legítimas (blocos de código dentro de `CONTRIBUTING.md` e `docs/relatorio_ordem2.md`) foram preservadas — conferido antes da edição que só havia pares balanceados.

## Pendência que permanece aberta
O `nav` do `mkdocs.yml` está defasado desde a Ordem 1: lista até a Ordem 0, não inclui os relatórios das Ordens 1, 2 e 3, e aponta para `relatorios/ordem-2_consistencia/relatorio_ordem-2_consistencia.md`, que não existe no repositório. O arquivo agora é YAML válido, mas a navegação continua quebrada. Não foi corrigido aqui porque resolver a entrada órfã exige decidir entre criar o relatório da Ordem -2 ou remover a linha — decisão de conteúdo, não de sintaxe.

## Status: Ordem 3 IMPLEMENTADA E VALIDADA OFFLINE — carga real e testes de integração aguardando confirmação e um Neo4j no ar
