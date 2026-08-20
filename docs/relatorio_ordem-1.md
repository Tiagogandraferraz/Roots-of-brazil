```
# Relatório — Ordem -1 (Governança do Repositório)
Data: 2026-08-19

## Executado
- Repositório Git local inicializado; branches `main` e `develop` criadas.
- `CONTRIBUTING.md` na raiz: Git Flow simplificado, padrão de branches efêmeras, Conventional Commits, e a distinção explícita entre SemVer (plataforma) e versionamento do corpus (v1.x).
- `.github/branch-protection.yml`: regras declarativas de proteção de branch (PR obrigatório, CI verde obrigatório, sem force-push, sem deleção).

## Limitação declarada
A proteção de branch real (bloqueio de push direto no servidor) depende de um provedor Git remoto (GitHub/GitLab) com API/admin — não aplicável dentro deste ambiente sandbox local, sem repositório remoto configurado. O arquivo `.github/branch-protection.yml` documenta a intenção; precisa ser aplicado manualmente (ou via CLI autenticado) quando o repositório for hospedado.

## Restrições respeitadas
Nenhum código de domínio foi escrito nesta Ordem. `main` não recebeu nenhum commit direto além do commit inicial de inicialização (`chore: init repository`), antes da criação de `develop` — consistente com a regra de que `main` só recebe merge de `release/*` ou `fix/*` dali em diante.

## Critérios de aceite
- [x] Branches `main` e `develop` existem.
- [x] Regras de proteção declaradas (aplicação real pendente de hospedagem remota — ver Limitação acima).
- [x] `CONTRIBUTING.md` documenta Git Flow, Conventional Commits e a distinção de versionamento.

## Status: Ordem -1 CONCLUÍDA (com limitação de infraestrutura declarada, não bloqueante para prosseguir)
```
