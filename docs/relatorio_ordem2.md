# Relatório — Ordem 2 (Implementação do Banco Relacional)
Data: 2026-08-19

## Executado e VALIDADO POR EXECUÇÃO REAL (não apenas escrito)
Diferente das Ordens 0 e 1, esta Ordem pôde ser **executada de verdade** nesta sandbox, porque SQLite e openpyxl são bibliotecas padrão/já disponíveis, sem depender de rede.

- `schemas/ddl_sqlite.sql` — DDL completo: 8 tabelas de entidade + `relacoes`, enums via CHECK (SQLite não tem `CREATE TYPE`), índices da Seção 24 (incluindo composto `origem_id, tipo_relacao`), view `objeto_universal` (resolução da FK polimórfica) e duas views `mv_estatisticas_corpus`/`mv_grafo_agregado` (materialized views reais ficam para PostgreSQL/produção — SQLite recalcula a cada consulta).
- `scripts/ordem2/etl.py` — ETL real, executado contra `Corpus_Fundador_v1.1.xlsx` (READ-ONLY, nunca escrito).
- `tests/ordem2/test_etl.py` — suite de testes (pytest não instalável nesta sandbox sem rede; as mesmas asserções foram rodadas manualmente com sucesso — ver abaixo).

## Resultado da execução real
```
ETL concluído sem divergências. Objetos: 381 (esperado 381). Relações: 1585 (esperado 1585).
Por catálogo: {'ingrediente': 130, 'receita': 136, 'tecnica': 38, 'povo': 17,
               'territorio': 18, 'patrimonio': 35, 'bioma': 7, 'livro_fonte': 0}
```

| Validação | Resultado |
|---|---|
| Contagem por catálogo (130/136/38/17/18/35/7) | ✅ bate exatamente |
| Total de objetos | ✅ 381 |
| Total de relações | ✅ 1.585 |
| `mv_grafo_agregado` vs. tabela de tipos da Ata/Auditoria | ✅ idêntico (USA_INGREDIENTE 895, ASSOCIADO_A_POVO 205, CULTIVADO_EM 106, UTILIZA_TECNICA 85, PREPARADO_COM 81, OCORRE_EM 77, ORIGINARIO_DE 67, PATRIMONIO_DE 38, LOCALIZADO_EM_BIOMA 24, DERIVA_DE 7) |
| UUIDs distintos gerados | ✅ 381 (nenhuma colisão) |
| Zero erros de FK (`origem_id`/`destino_id` resolvem para `objeto_universal`) | ✅ confirmado por query |
| Objetos órfãos | ✅ 18 (idêntico à Ata) |
| CHECK negativo (peso = 1.5, fora de [0,1]) | ✅ rejeitado, `IntegrityError` |
| CHECK positivo (peso = 0.5) | ✅ aceito |

## Achado corrigido durante a execução (não é divergência de dado — é ajuste de schema)
O primeiro `CHECK(confiabilidade IN (...))` (com os 4 valores exatos do enum) **falhou** ao carregar dados reais: o Dicionário v1.2 (Seção 11) já documenta a categoria 🔵 como "Enum + nota" (permite texto livre após o emoji), e os dados reais confirmam isso — ex.: `"🔵 Inferido com cautela"`, `"🔵 Inferido (casamento textual Aba 1 campo Derivados)"`. Corrigido o CHECK (e a SHACL Shape correspondente da Ordem 1) para validar por prefixo de emoji, não por string exata — sem alterar nenhum dado, apenas a regra de validação, para refletir corretamente o que o próprio Dicionário já especificava.

## Decisões de modelagem documentadas
1. **FK polimórfica (Seção 25.3): escolhida VIEW de união (`objeto_universal`), não trigger.** Mais simples de consultar e manter; validação de integridade é reforçada em Python no ETL (fail-fast, já testado acima). Em PostgreSQL/produção (Ordem 6), pode-se adicionar trigger real como reforço.
2. **Duas subséries de REL_ID (REL-xxxxxx e REL-Bxxxxx) preservadas como estão** — nenhuma unificação nesta carga, conforme pendência explícita de v1.3.
3. **`peso` inicializado pelo mapeamento determinístico de confiabilidade** (🟢=0.95, 🟡=0.60, 🔵=0.30, 🔴=0.10), exatamente como recomendado no Dicionário v1.2, Seção 20.2 (nota de implementação) — nenhum valor arbitrário inventado.
4. **Livro/Fonte: 0 linhas carregadas.** Consistente com o Dicionário v1.2 (Seção 19): "esquema definido, população pendente para implementação" — nenhum dado foi inventado para preencher essa tabela.

## Limitação declarada
- SQLAlchemy models (`app/models/`) e a migration inicial do Alembic **não foram gerados nesta sandbox** — dependem de `poetry install` (sem rede aqui). O DDL SQL puro foi escrito e executado com sucesso como equivalente funcional, validando a lógica do schema contra dados reais — mas o critério de aceite formal "migration do Alembic aplica limpo" fica pendente de ambiente com rede.
- Variante PostgreSQL (`schemas/ddl_postgresql.sql`, com `CREATE TYPE ENUM` nativo e `MATERIALIZED VIEW` real) **não foi escrita nesta rodada** — o DDL SQLite serviu de prova de conceito executável; adaptar para PostgreSQL é mecânico mas não foi priorizado dado o tempo, fica registrado como próximo passo.

## Status: Ordem 2 EXECUTADA E VALIDADA (SQLite) — variante PostgreSQL e models SQLAlchemy/Alembic pendentes de ambiente com rede
