# PROJETO — Portão de Deploy (o required check que o GitHub não vende)

> ## ✅ EXECUTADO E PROVADO — PR #54, 22/08/2026. NÃO redespache.
> **Nível A:** 25 testes adversariais (`ci/tests/test_portao_de_deploy.py`) — a
> tabela de estados completa + homônimo + exclusão do próprio run + teste de
> forma dos YAMLs, rodando em `muralhas` e `alarme-main`.
> **Nível B (ao vivo, mesmo dia):** PR #55 vermelho de propósito, mergeado sem
> guarda ⇒ run 32567765127: `portao-de-deploy: failure`, `deploy: skipped`;
> revert #56 verde ⇒ run 32567900961: portão `success`, quiz deployado e
> `healthy` na VPS. Estreia verde do modo infra: run 32567326357.
> **Reconciliações honestas com esta especificação:** F5 (sonda pós-deploy) é
> atendida pelos healthchecks + `up -d --wait` que o PR #45 entregou; o portão
> foi ESTENDIDO ao `deploy-infra` (modo `infra`: o `rodar` pode pular, o gate
> não) — pedido do handoff do despacho 04; a checagem de `updated_at` do
> package não rodou (token `gh` sem `read:packages`) — a prova de imagem
> intocada veio do próprio `deploy: skipped`, que contém o build.

> **Origem:** relatório da auditoria de portões de CI (agente Opus, 21/08/2026),
> preservado aqui porque o projeto completo existia só no contexto da sessão.
> **Para quem:** o agente que receber o despacho B1 do painel 10X. Este arquivo é a
> especificação; o despacho define escopo, DoD e evidência.
> **Contexto:** não há branch protection e NÃO PODE haver (ARMADILHAS-OPERACAO.md §1 H3 — sem
> forma de pagamento aceita). Todo portão pode estar vermelho e o merge acontece.
> O que não pode acontecer é o DEPLOY — e é o deploy que alcança cliente.

## Fatos medidos que moldam o desenho (verificados em 21/08/2026)

- **F1** — `muralhas` NUNCA roda no commit que dispara o deploy (`muralhas.yml` só tem
  `on: pull_request`). A evidência dele mora no **head do PR de origem**, recuperável:
  `gh api repos/<owner>/<repo>/commits/<sha>/pulls` → `head.sha`.
- **F2** — o nome `detectar` COLIDE: existem DOIS check-runs com esse nome no mesmo
  SHA (um do `ci-celula`, um do `deploy-celula`). Por isso o portão é chaveado por
  **path de workflow**, nunca por nome de check.
- **F3** — `ci-celula: skipped` é ambíguo (legítimo em PR de docs); **`ci-celula-gate`
  não é**: roda com `if: always()`, nunca é skipped, e carimba a tabela-verdade
  (detecção falhou ⇒ exit 1; célula detectada mas `rodar` pulado ⇒ exit 1). O portão
  exige `ci-celula-gate == success` — e, como o deploy só dispara quando `services/**`
  mudou, exige também `ci-celula == success` (nunca skipped) nesse caso.
- **F4** — a corrida é real: medido, o deploy começa ~55s ANTES de `ci-celula-gate`
  concluir. `ci-celula` leva 18–70s. O portão espera com polling.
- **F5** — o deploy atual declara sucesso sem verificar nada: `docker compose ps`
  retorna 0 com container em crash-loop. A sonda pós-deploy fecha isso.

## Decisões de arquitetura

1. **Lógica em Python (`ci/portao_de_deploy.py`), YAML só faz fiação** — doutrina do
   próprio repo, e é o que torna o portão testável adversarialmente em `ci/tests/`
   (que roda no `muralhas` E no `alarme-main`).
2. Usa `_nucleo.py` (Estado, Resultado, Relatorio, ErroDeInstrumentacao, executar):
   herda INV-CI01 de graça.
3. **O portão roda ANTES do build**: `docker push :main` já arma o próximo `compose
   up` na VPS (tags `${X_TAG:-main}`) — gatear só o SSH deixaria a imagem ruim
   publicada e pronta.
4. **Polling com `gh api`, sem action de terceiro** — dependência de supply chain no
   portão de segurança é o oposto do objetivo. Intervalo 15s; graça de 5min para o
   run APARECER (distingue "fila do GitHub" de "workflow deletado"); timeout total
   20min ⇒ ERROR ⇒ deploy abortado; recuperação: re-run do workflow (reavalia do zero).
5. Detecção de escopo usa `github.event.before` (não `HEAD^`: push com vários commits
   perderia célula tocada em commit anterior) e o runner canônico
   (`python ci/ci.py --detectar-celulas --base <sha>`) — mesma semântica do ci-celula.
6. Sem `workflow_dispatch` — seria deploy que ninguém amarra a commit revisado; o
   portão recusa `event_name != 'push'` explicitamente.
7. **Least privilege**: o job do portão NÃO recebe `packages: write` — só
   `contents/actions/checks/pull-requests: read`.
8. `vermelhos_nao_previstos`: workflow novo e vermelho no mesmo SHA também barra —
   senão todo check novo nasceria fora do portão sem ninguém decidir isso.

## Estrutura do workflow (deploy-celula.yml revisado)

```yaml
jobs:
  detectar:            # escopo via ci/ci.py --detectar-celulas --base $EVENT_BEFORE
    # before vazio/zeros => ERROR exit 1 (força de push/branch nova NÃO é "nenhuma célula")
    # deteccao falhou => ERROR exit 1 (a versão antiga: git diff|grep|jq — falha virava [])
    outputs: celulas (json), n, deteccao=ok

  portao:              # roda ANTES do build
    name: portao-de-deploy
    needs: detectar
    timeout-minutes: 25
    permissions: {contents: read, actions: read, checks: read, pull-requests: read}
    env: GH_TOKEN, REPO, SHA, CELULAS, RUN_ID (para excluir a si mesmo),
         EVENTO, PORTAO_TIMEOUT=1200, PORTAO_GRACA=300, PORTAO_INTERVALO=15
    run: python ci/portao_de_deploy.py

  deploy:
    needs: [detectar, portao]
    if: >-                        # explícito de propósito; NUNCA always()/failure()
      needs.portao.result == 'success' &&
      needs.detectar.result == 'success' &&
      needs.detectar.outputs.deteccao == 'ok' &&
      needs.detectar.outputs.celulas != '[]'
    # ... build+push igual, e o passo de VPS que já descobre os auxiliares ...
    # + SONDA PÓS-DEPLOY (F5): loop de até 60s batendo /healthz DENTRO do container
    #   (compose exec <celula> python -c urlopen('http://localhost:8000/healthz'));
    #   falhou => exit 1 + logs --tail 80 + instrução de rollback (RITOS §4).
    #   Exceção: checkout usa sonda TCP enquanto o remendo H10 existir.
```

## `ci/portao_de_deploy.py` — contrato de comportamento

```
PASS  (0) medi e está tudo verde        -> deploy roda
FAIL  (1) medi e algo reprovou          -> deploy pulado
ERROR (2) não consegui medir            -> deploy pulado
SKIP  (0) nenhuma célula no diff        -> não há o que deployar
```

Constantes:
```python
EXIGIDOS_NO_COMMIT = {
    ".github/workflows/ci-celula.yml": ("ci-celula-gate", "ci-celula"),
    ".github/workflows/alarme-main.yml": ("guardas do repositório",),
}
EXIGIDO_NO_PR = {".github/workflows/muralhas.yml": ("muralhas",)}
REPROVA = {"failure","timed_out","startup_failure","action_required","neutral","stale"}
```

> **Emenda de 05/09/2026 (alavanca 2 das alavancas de 10x da fábrica):** o
> `alarme-main` saiu de `EXIGIDOS_NO_COMMIT` e passou a `conhecidos`. A `main`
> tem política estrita, então ele media o mesmo conteúdo que o `muralhas` do PR
> de origem (que continua exigido) já tinha medido; esperá-lo custava 1min18s
> por deploy. O raciocínio inteiro está ao lado da constante `ALARME_MAIN` em
> `ci/portao_de_deploy.py`.

Funções (a implementação segue o relatório; o agente reescreve com liberdade desde
que preserve ESTA semântica):
- `gh(caminho)` — `gh api --paginate`, JSON inválido ⇒ ErroDeInstrumentacao.
- `runs_do_sha(sha, excluir_id=RUN_ID)` — lista runs por `head_sha`, chaveia por
  `run["path"]`.
- `veredito_do_run(run, jobs_exigidos)` — run não-success ⇒ ERROR (cancelled/skipped
  NÃO é verde); job exigido ausente ⇒ ERROR com a lista dos jobs vistos; job skipped
  quando `services/**` mudou ⇒ ERROR ("pulo aqui é instrumentação quebrada, não pulo
  declarado").
- `esperar(...)` — polling; 5 falhas seguidas da API ⇒ ERROR; graça vencida com run
  ausente ⇒ ERROR; timeout ⇒ ERROR com instrução de re-run.
- `evidencia_das_muralhas(sha)` — acha o PR de origem via `commits/<sha>/pulls`
  (prefere `merge_commit_sha == sha`; 0 PRs ⇒ ERROR "push direto na main não vira
  deploy"; >1 ambíguo ⇒ ERROR); avalia o run de `muralhas` no head do PR.
- `vermelhos_nao_previstos(runs)` — workflow fora da lista com conclusion em REPROVA
  ⇒ FAIL, com instrução de declará-lo por escrito.
- `main()` — recusa `EVENTO != push`; `len(celulas) > 1` ⇒ FAIL (1 PR = 1 célula);
  `_blindar` no `__main__`: exceção interna ⇒ 2, nunca 1 (padrão de `ci/ci.py`).

## Tabela de estados (a prova de completude — o teste-guarda cobre TODOS)

| Situação | Estado | Deploy |
|---|---|---|
| tudo verde (gate ✔, ci-celula ✔, guardas ✔, muralhas ✔ no head do PR) | PASS | roda |
| teste da célula quebrou | FAIL | pulado |
| PR de docs (nenhuma célula) | SKIP declarado | não há o quê |
| ci-celula skipped com services/** tocado | ERROR | pulado |
| workflow exigido desabilitado/renomeado/deletado | ERROR (após graça) | pulado |
| checks ainda rodando após timeout | ERROR | pulado |
| gh api fora do ar 5× / JSON inválido / job cancelled | ERROR | pulado |
| push direto na main (sem PR) | ERROR | pulado |
| muralhas vermelho no PR, mergeado pelo botão | FAIL | pulado |
| push toca 2 células | FAIL | pulado |
| workflow novo e vermelho no mesmo SHA | FAIL | pulado |
| bug dentro do próprio portão | ERROR (blindado) | pulado |

## Vetores de burla (e por que não passam)

- Re-run do deploy: reavalia os mesmos checks — só passa se verdes de verdade.
- Check-run falso com nome `ci-celula-gate` em outro workflow: chaveamento por PATH.
- Deletar `ci-celula.yml` no mesmo push: o run não existe para o SHA ⇒ ERROR.
- Desabilitar workflow no painel: run ausente ⇒ ERROR na graça.
- **Editar o YAML e remover o job `portao`: detectado, não impedido** — teto honesto.
  Mitigação obrigatória: `ci/tests/test_portao_de_deploy.py::test_workflow_de_deploy_
  exige_o_portao` lê o YAML e afirma a forma (needs, if, ausência de
  workflow_dispatch); roda no `muralhas` (PR) e no `alarme-main` (push na main).

## Prova exigida (Lei 6 — sem isto o despacho NÃO está pronto)

**Nível A — suíte adversarial** (`ci/tests/test_portao_de_deploy.py`, com um `gh`
falso no PATH devolvendo JSON canned — padrão já existente no conftest de ci/tests):
os 14 casos da tabela acima, cada um afirmando o exit code exato. Incluir o caso 12
(check-run homônimo de outro path + o verdadeiro vermelho ⇒ 1).

**Nível B — ao vivo** (com o mantenedor):
1. Branch numa célula com um assert falso; mergear PELO BOTÃO do site.
2. `gh run view <run> --json jobs` ⇒ `portao-de-deploy: failure`, `deploy: skipped`.
3. Provar que a imagem NÃO mudou: `gh api /user/packages/container/plataforma-
   <celula>/versions --jq '.[0].metadata.container.tags + [.updated_at]'` com
   `updated_at` ANTERIOR ao merge.
4. Reverter, mergear de novo ⇒ portao success, deploy success, updated_at novo.
   **Vermelho→verde, medido — colar as quatro saídas cruas no PR.**

## Custos e riscos

Caminho feliz: ~1 min de runner por deploy (~80 chamadas de API no pior caso; limite
5000/h). Modo de falha: "abortar quando não devia" — lado seguro, recuperável por
re-run. Não exercite confiança antes do Nível B rodar.
