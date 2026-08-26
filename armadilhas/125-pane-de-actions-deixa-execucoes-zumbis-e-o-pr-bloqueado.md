# Pane do GitHub Actions: as execuções viram zumbis, os gatilhos normais somem, e o PR fica `BLOCKED` sem nenhum check no `head`

**Sintoma:** durante uma pane declarada de Actions (`githubstatus.com` →
*Actions: major_outage*), um PR fica sem veredito e **nenhuma das saídas normais
funciona**. Tudo ao mesmo tempo, e cada uma mentindo de um jeito diferente:

| você faz | o que aparece | o que é |
|---|---|---|
| `gh run list` | `queued` há mais de uma hora | a execução nunca vai começar |
| `gh run rerun <id>` | sai sem erro nenhum | `run_attempt` continua 1 — não re-disparou |
| `gh run cancel <id>` | `Cannot cancel a workflow run that is completed` | a MESMA execução que a lista diz estar `queued` |
| `gh pr checks <N>` | `no checks reported on the branch` | os check-runs se soltaram do PR |
| `git push` (commit novo) | push OK | **nenhuma execução é criada** — o evento é engolido |
| `gh pr close` + `reopen` | OK | funciona, mas o evento leva ~7 minutos para ser processado |

**Causa:** na pane, a entrega de eventos (`push`, `pull_request`) e a fila de
execução se degradam separadamente do resto do GitHub — Git, API e PRs seguem
`operational`. As execuções criadas antes ficam num estado inconsistente: a
listagem serve um cache que diz `queued`, e o banco por trás já as considera
terminadas. Nada disso é sinal sobre o seu código.

**A armadilha de verdade, e é ela que custa caro:** quando o evento finalmente
chega, ele é processado **com o `head` que o PR tinha no momento do gatilho** —
não o de agora. Se você, no meio da espera, empurrou um commit (por exemplo, um
commit vazio para "forçar" a esteira), o resultado é o pior dos mundos:

- as execuções ficam **verdes**, mas presas ao commit ANTERIOR;
- o `head` do PR é o commit novo, **sem check nenhum**;
- o PR fica `mergeStateStatus: BLOCKED` com a tela mostrando verde em volta;
- e a trava de branch recusa o merge, corretamente, porque os checks
  obrigatórios não existem *naquele* commit.

**Solução:**

1. **Antes de qualquer coisa, confirme a pane:**
   `curl -s https://www.githubstatus.com/api/v2/summary.json` e leia o
   componente `Actions`. Se for `major_outage`, pare de diagnosticar o
   repositório — não há nada errado com ele.
2. **Não empurre commit para "forçar" a esteira durante a pane.** É o gesto que
   cria o descasamento acima. Se já empurrou, o conserto é gerar execução para o
   `head` ATUAL (outro gatilho depois que os eventos voltarem), ou descartar o
   commit — force-push, que pode estar bloqueado no harness do agente.
3. **Confira sempre em qual commit o verde está**, nunca só que "ficou verde":
   ```bash
   gh pr view <N> --json headRefOid,mergeStateStatus
   gh api repos/<owner>/<repo>/commits/<sha>/check-runs -q '.check_runs[] | "\(.name) \(.conclusion)"'
   ```
   Verde no commit errado é verde legítimo respondendo à pergunta errada — a
   mesma família do falso-verde nº 1 (`RETROSPECTIVA-FASE-D.md` §1).
4. **Não aproveite o verde de um PR empilhado para mergear o de baixo.** Se o
   PR B sai do PR A, o verde de B foi medido com **A como base** — a cerca de
   célula e o orçamento conferiram um recorte menor do que entraria na `main`.
   Tentador durante a pane; é um verde que responde outra pergunta.
5. **Paciência é a saída certa.** Vermelho, pendente ou ausente não se mergeia
   (CLAUDE.md), e "ausente por pane do provedor" é ausente. Deixe um vigia
   acompanhando e reporte ao mantenedor em texto claro que o bloqueio é externo.

**Origem:** 26/08/2026, PRs #227 e #228. A pane durou mais de duas horas. O #228
(aberto depois) pegou uma janela boa e fechou verde em 30s; o #227 (aberto no
pico) acumulou três execuções zumbis, resistiu a rerun, a cancel e a
close/reopen, e terminou com verde no commit anterior ao `head`. Uma hora de
diagnóstico que este arquivo faz caber em dois minutos.
