```
# Contribuindo — Roots of Brazil (Plataforma)

## Branches permanentes
- `main` — reflete exatamente o que está em produção (Ordem 6). Nunca recebe commit direto.
- `develop` — integração contínua das Ordens em andamento.

## Branches efêmeras
- `feature/<ordem>-<descricao-curta>` — ex.: `feature/ordem2-schema-sql`
- `fix/<descricao-curta>`
- `release/<versao>`

## Fluxo (Git Flow simplificado)
- Toda `feature/*` nasce de `develop` e volta para `develop` via Pull Request.
- `release/*` nasce de `develop` e vai para `main`.
- `fix/*` pode nascer de `main` para hotfix urgente, depois é mesclado de volta em `develop`.

## Dois eixos de versionamento — NUNCA confundir
1. **Plataforma (código)** — Versionamento Semântico (SemVer): `MAJOR.MINOR.PATCH`. Releases da plataforma técnica (API, frontend, infraestrutura).
2. **Corpus (dados)** — Política de Versionamento própria, definida no Dicionário de Dados Oficial v1.2 (Seção 6): `v1.0`, `v1.1`, `v1.2`... Versiona o *conteúdo* do conhecimento, não o código.

Estes dois eixos são **independentes**. Uma mudança de schema do corpus (v1.2 → v1.3) não implica necessariamente um MAJOR da plataforma, e vice-versa.

## Conventional Commits
Todo commit segue o padrão:
```
<tipo>: <descrição curta>
```
Tipos: `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`, `ci:`

## Proteção de branch
`main` e `develop` são protegidas: Pull Request obrigatório, pipeline de CI (Ordem 0) verde obrigatório antes de merge. Ver `.github/branch-protection.yml`.

> **Nota de implementação:** a proteção de branch real (bloqueio de push direto) é aplicada nas configurações do provedor Git (GitHub/GitLab) quando o repositório for hospedado remotamente — o arquivo `.github/branch-protection.yml` documenta a regra pretendida; não é executável localmente sem uma conta/API do provedor.
```
