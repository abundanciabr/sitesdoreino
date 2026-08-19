# KIT FUNDADOR — Plataforma de Células Isoladas

> "Quanto mais poderosa a IA, menores devem ser as fronteiras dentro das quais lhe damos liberdade."

Este kit é a Fase 0 completa da plataforma nova (domínio novo, VPS nova, tudo novo).
Ele não é um plano que pede confiança: cada alegação estrutural vem com um teste que a
falsificaria. A Fase 0 só termina quando o **red-team** (02-RED-TEAM.md) falha em matá-la.

## Mapa do kit

| Caminho | O que é |
|---|---|
| `00-LEIA-PRIMEIRO.md` | Este arquivo. |
| `01-BRIEF-FASE-0.md` | O brief de despacho da Fase 0 (formato de despacho para agentes). |
| `PROMPTS-INICIAIS.md` | A sequência de despachos prontos: do repo vazio ao esqueleto que anda. |
| `02-RED-TEAM.md` | O rito de graduação: tentativas deliberadas de matar cada muralha. |
| `CONSTITUICAO.md` | A lei da plataforma (herda para todas as células). |
| `RITOS.md` | Abertura de sessão, catraca verde/anti-thrashing, mudança de contrato, emergência 2h. |
| `INVARIANTES.md` | Jurisprudência pré-paga: os invariantes de dinheiro, com teste-guarda ANTES da primeira feature. |
| `ESQUELETO-QUE-ANDA.md` | Marco zero: uma transação sandbox atravessando todas as células. |
| `CAMINHO-DOURADO.md` | As receitas canônicas: o despacho cita por número, o agente cola — velocidade sem divergência. |
| `ARMADILHAS.md` | **Memória de campo — leia antes de cada sessão.** O que já custou tempo aqui (sintoma → causa → solução) + a tabela `PRECISA DE VOCÊ`, com os atritos que só o mantenedor resolve de vez. |
| `services/<celula>/LICOES.md` | O mesmo, restrito a uma célula: decisões e armadilhas de quem já trabalhou nela. |
| `ARMADILHAS.md` | **Leia antes de cada sessão.** Memória de campo: o que já custou tempo, com sintoma → causa → solução. |
| `constituicoes/AGENTS.<celula>.md` | Constituição de 1 página por célula (a lei espacial). |
| `contracts/` | OpenAPI por célula + eventos versionados. CONGELADOS após ratificação. |
| `infra/` | Provisionamento da VPS, Postgres por célula, Traefik (file provider), compose, envs. |
| `ci/` | As muralhas mecânicas: cercas, orçamento, freeze, cross-smoke, workflows, CODEOWNERS. |
| `celula-template/` | Esqueleto de cada célula Django (Makefile, Dockerfile, compose.dev, import-linter). |

## Ordem de execução (espelha o brief)

1. **Etapa A — Impossibilidades** (VOCÊ, não agente): `infra/provisionamento-vps.sh`,
   `infra/provisionamento-postgres.sql`, secrets, branch protection (checklist abaixo).
2. **Etapa B — Jaula verde vazia** (agente): repo com `ci/` inteiro passando ANTES de existir feature.
3. **Etapa C — Constituições + contratos + invariantes** (agente + você nos portões):
   ratificar `contracts/`, semear os testes-guarda de `INVARIANTES.md`.
4. **Etapa D — Esqueleto que anda** (agente): `ESQUELETO-QUE-ANDA.md` verde no CI e na VPS.
5. **Etapa E — Red-team** (você + agente): `02-RED-TEAM.md` com evidência de cada golpe bloqueado.

## Placeholders a substituir (grep por `TROQUE`)

- `basileiatoutheou.org` — o domínio novo
- `abundanciabr` / `abundanciabr` — dono do repo e do GHCR
- `TROQUE_*` — senhas Postgres (gere com `openssl rand -hex 24`)
- `IP-DA-VPS-NOVA`, e-mail do ACME (se não usar Cloudflare na frente)

## Branch protection (GitHub → Settings → Branches → `main`) — não é arquivo, é checklist

- [ ] Require a pull request before merging
- [ ] Require review from Code Owners (ativa o CODEOWNERS)
- [ ] Require status checks: `muralhas`, `ci-celula-gate`
- [ ] Require branches to be up to date
- [ ] Do not allow force pushes / deletions
- [ ] Restrict who can push to matching branches (só você + CI)

## As três alegações mensuráveis desta arquitetura

1. Raio de explosão de qualquer falha = **1 célula**.
2. Reversão de qualquer deploy = **minutos** (rollback por tag de imagem).
3. Regressão cruzada chegando a produção = **zero** (cross-smoke + cercas bloqueiam antes).

Quando alguma falhar, você saberá — e é isso que separa este kit dos planos que "garantiram que tudo daria certo".
