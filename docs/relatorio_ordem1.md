```
# Relatório — Ordem 1 (Implementação da Ontologia)
Data: 2026-08-19

## Executado
- `schemas/ontologia.ttl` — 8 classes (Ingrediente, Receita, Técnica, Povo, Território, Patrimônio, Bioma, LivroFonte), todas `owl:disjointWith` entre si; superclasse `roots:ObjetoRoots` carregando os blocos transversais (Metadados Universais, UUID, Slug, i18n 8 idiomas, Taxonomia 7 níveis, Geodados).
- `schemas/shapes.shacl.ttl` — SHACL Shapes para: padrão de ID por prefixo (8 shapes, um por classe), uuid v4, slug kebab-case, confiabilidade (enum de 4), tipo_relacao (enum de 12), peso (0.0–1.0), metodo_calculo_peso obrigatório.
- `schemas/context.jsonld` — mapeamento para schema.org onde há correspondência direta (Receita→schema:Recipe, Território→schema:AdministrativeArea, Bioma→schema:Place, LivroFonte→schema:Book), sem forçar mapeamento nos demais.

## Cobertura (checklist da Ordem 1)
| Critério | Status |
|---|---|
| 8 classes, nem mais nem menos | ✅ Ingrediente, Receita, Técnica, Povo, Território, Patrimônio, Bioma, LivroFonte |
| 12 tipos de relação com domain/range | ✅ 10 com domain/range específico + 2 reservados (VARIANTE_REGIONAL, SIMILAR_A) — ver nota abaixo |
| Taxonomia hierárquica (Seção 9) | ✅ macrogrupo→grupo→ordemTaxonomica→familia→classe→categoria→subcategoria como propriedades de `ObjetoRoots` |
| Blocos transversais como mixins | ✅ Modelados como data properties de `ObjetoRoots`, não como classes próprias |
| SHACL Shapes para Seção 23 | ✅ Ver `shapes.shacl.ttl` |
| Rastreabilidade (rdfs:comment → Seção do Dicionário) | ✅ Toda classe/propriedade cita a seção exata |
| Zero dados (só TBox) | ✅ Nenhuma instância de objeto real do Corpus incluída |
| Consistência lógica via reasoner (HermiT/Pellet) | ⚠️ **NÃO EXECUTADO** — sandbox sem rede/Java, sem reasoner disponível. Verificação manual: balanceamento sintático de colchetes/parênteses OK; JSON-LD validado como JSON. **Precisa ser rodado em ambiente real antes de confiar na consistência lógica.** |

## Decisões de modelagem não triviais (justificativa)

1. **`ASSOCIADO_A_POVO` e `ORIGINARIO_DE` têm domain/range em união (owl:unionOf).** O Dicionário v1.2 (Tabela de tipos de relação, Seção 21) já apresenta essas duas linhas como "Receita/Ingrediente → Povo" e "Ingrediente → Povo/Bioma" — a união reflete literalmente o que a fonte documenta, não é uma escolha de modelagem nova.
2. **`VARIANTE_REGIONAL` e `SIMILAR_A` ficaram com domain/range genéricos (`roots:ObjetoRoots`).** O Dicionário v1.2 lista os dois apenas como tipos válidos no enum de `tipo_relacao` (Seção 21/29), sem especificar domain/range granular — como são tipos reservados, sem nenhuma instância, restringir o domain/range além disso seria inventar semântica não documentada. Registrado como pendência para quando forem materializados (v1.3).
3. **`peso` e `metodo_calculo_peso` não têm domain/range fixado a uma classe.** São propriedades da aresta (RELACOES), não de uma classe de entidade — RDF/OWL padrão modela isso de forma imperfeita (uma tripla simples não carrega atributos próprios); a shape `RelacaoShape` no SHACL trata a validação via `sh:targetObjectsOf`. A Ordem 3 (Neo4j) resolve isso nativamente, já que bancos de grafo de propriedade suportam atributos de aresta diretamente.
4. **Campo "Ordem" da taxonomia renomeado para `ordemTaxonomica`** na ontologia, para não colidir semanticamente com "Ordem" no sentido das Ordens de execução deste Manual — é apenas um apelido de propriedade RDF, não uma alteração do Dicionário.

## Limitação declarada
Sem acesso à rede/Java nesta sandbox, não foi possível rodar um reasoner OWL real (HermiT/Pellet) para confirmar ausência de inconsistências e classes insatisfazíveis — critério de aceite formal da Ordem 1. A ontologia foi construída com disciplina de rastreabilidade estrita à fonte, e passou por checagem sintática manual (balanceamento, JSON válido), mas **a validação lógica formal fica pendente de execução em ambiente com as ferramentas reais**.

## Status: Ordem 1 ESCRITA (TBox completo), PENDENTE DE VALIDAÇÃO POR REASONER REAL
```
