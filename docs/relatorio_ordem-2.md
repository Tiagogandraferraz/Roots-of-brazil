# Relatório — Ordem -2 (Auditoria Documental de Consistência)
Data: 2026-08-20

## Executado
Auditoria de consistência documental sobre o conjunto de documentos técnicos do repositório. O resultado bruto está registrado em `docs/matriz_consistencia.json`, que é o artefato primário desta Ordem — este relatório o narra, não o substitui.

Foram auditados **6 documentos**, cruzando cada um com as referências que outros arquivos fazem a ele.

## Resultado da auditoria
| Documento | Caminho | Status | Inconsistências |
|---|---|---|---|
| `index.md` | `docs/index.md` | corrente | nenhuma |
| `relatorio_ordem-1.md` | `docs/relatorio_ordem-1.md` | corrente | nenhuma |
| `relatorio_ordem0.md` | `docs/relatorio_ordem0.md` | corrente | nenhuma |
| `relatorio_ordem1.md` | `docs/relatorio_ordem1.md` | corrente | nenhuma |
| `relatorio_ordem2.md` | `docs/relatorio_ordem2.md` | corrente | nenhuma |
| `relatorio_ordem-2_consistencia.md` | `docs/relatorios/ordem-2_consistencia/…` | N/A | **1** — referenciado no `nav` do `mkdocs.yml`, mas o arquivo não existe no repositório |

**Zero issues bloqueantes.** A única inconsistência encontrada é uma referência órfã na navegação da documentação: o `mkdocs.yml` aponta para um relatório desta própria Ordem em um caminho que nunca foi criado. Não afeta código, schema, dado ou build da aplicação — apenas quebra um link no portal de documentação.

## Resolução da inconsistência encontrada
A referência órfã foi resolvida ao escrever **este** arquivo: o relatório da Ordem -2 passou a existir, em `docs/relatorio_ordem-2.md`, seguindo a convenção de nomes já usada pelos demais (`relatorio_ordem-1.md`, `relatorio_ordem0.md`, `relatorio_ordem1.md`, …) em vez do caminho aninhado `docs/relatorios/ordem-2_consistencia/` que o `nav` presumia e que não correspondia à estrutura real de `docs/`. O `nav` do `mkdocs.yml` foi corrigido para o caminho correto, e as entradas que faltavam — Ordens 1, 2 e 3 — foram acrescentadas na mesma passagem.

`docs/matriz_consistencia.json` foi deixado **como está**: ele é o registro da auditoria como executada em 2026-08-20, e reescrever a linha para "nenhuma inconsistência" apagaria o achado. A resolução é registrada aqui e no histórico do repositório; a matriz continua sendo o retrato do que a auditoria encontrou.

## Limitações declaradas
- **O escopo foi consistência documental, não sintaxe de arquivo.** A auditoria cruzou referências entre documentos e conferiu se cada um existia e estava corrente; não validou se os arquivos eram sintaticamente válidos em seus formatos. Por isso ela **não detectou** o defeito de cercas markdown residuais (```` ``` ```` na primeira e na última linha) que afetava 23 arquivos versionados na mesma data desta auditoria — inclusive quatro dos seis documentos aqui listados como "corrente, nenhuma inconsistência". Esse defeito só foi encontrado durante a Ordem 3 e corrigido em commit próprio; está documentado em `relatorio_ordem3.md`. Uma futura rodada desta Ordem deve incluir validação sintática por tipo de arquivo, não apenas checagem de referências cruzadas.
- **Nenhum documento carrega metadado de versão.** Todos os 6 registros da matriz têm `versao: "N/A"`. A auditoria conferiu a existência e o status ("corrente"), mas não teve como verificar defasagem de versão entre documentos, porque não há campo de versão a comparar. Adotar cabeçalho de versão nos relatórios tornaria a próxima auditoria mais forte.
- **A auditoria cobriu `docs/` apenas.** Os artefatos técnicos fora dessa pasta (`schemas/`, `CONTRIBUTING.md`, `README.md`, `mkdocs.yml`) não entraram na matriz, embora o `mkdocs.yml` tenha sido lido para localizar a referência órfã.

## Critérios de aceite
- [x] Matriz de consistência gerada e versionada (`docs/matriz_consistencia.json`).
- [x] Todos os documentos de `docs/` auditados (6 de 6).
- [x] Zero issues bloqueantes.
- [x] Única inconsistência encontrada documentada e resolvida (ver acima).
- [ ] Validação sintática por tipo de arquivo — fora do escopo desta rodada, registrado como limitação.

## Status: Ordem -2 CONCLUÍDA — zero issues bloqueantes; a única inconsistência não-bloqueante encontrada foi resolvida
