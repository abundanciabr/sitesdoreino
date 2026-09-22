# Fotografia dos workflows e do site

Medição executada em **21/09/2026 19:20:19 BRT**. Esta fotografia complementa, sem alterar, `fotografia-oficial-fase-1-2026-09-21.md`.

## Resultado remoto

| Workflow | Último run | Início informado pelo GitHub | Conclusão | Gatilho |
|---|---:|---|---|---|
| `deploy-celula.yml` | [35647040827](https://github.com/abundanciabr/sitesdoreino/actions/runs/35647040827) | 21/09/2026 19:47:41 UTC | sucesso | push em `main` |
| `deploy-infra.yml` | [35547249078](https://github.com/abundanciabr/sitesdoreino/actions/runs/35547249078) | 21/09/2026 00:17:43 UTC | sucesso | push em `main` |
| `rollback.yml` | [35450057117](https://github.com/abundanciabr/sitesdoreino/actions/runs/35450057117) | 19/09/2026 14:52:27 UTC | sucesso | disparo manual em `main` |
| `vigia-do-site.yml` | [35655041426](https://github.com/abundanciabr/sitesdoreino/actions/runs/35655041426) | 21/09/2026 21:04:58 UTC | sucesso | agendamento |
| `vigia-do-pouso.yml` | [35643097856](https://github.com/abundanciabr/sitesdoreino/actions/runs/35643097856) | 21/09/2026 19:10:05 UTC | sucesso | agendamento |
| `vigia-do-cadeado.yml` | [35628043454](https://github.com/abundanciabr/sitesdoreino/actions/runs/35628043454) | 21/09/2026 16:49:18 UTC | sucesso | agendamento |
| `alarme-main.yml` | [35647040958](https://github.com/abundanciabr/sitesdoreino/actions/runs/35647040958) | 21/09/2026 19:47:41 UTC | sucesso | push em `main` |
| `vacina-do-deploy.yml` | [35647540798](https://github.com/abundanciabr/sitesdoreino/actions/runs/35647540798) | 21/09/2026 19:52:31 UTC | sucesso | conclusão de workflow |

Todos os oito runs consultados estavam com estado `completed` e conclusão `success`.

## Estado HTTP

`curl.exe --silent --show-error --location --output NUL --write-out "HTTP %{http_code}; URL %{url_effective}; tempo %{time_total}s" --max-time 30 https://meshcraft.top` retornou **HTTP 200**, URL final `https://meshcraft.top/` e tempo de **0,554983 s**.

## Fonte e limite temporal

Os dados de workflows foram coletados com `gh run list --repo abundanciabr/sitesdoreino --workflow <arquivo> --limit 1 --json databaseId,workflowName,status,conclusion,startedAt,updatedAt,event,headBranch,url`.

O relógio local da coleta marcou 19:20:19 BRT, mas o GitHub devolveu horários de início posteriores para parte dos runs. Esta fotografia preserva os horários brutos de cada fonte e não infere uma ordem entre os relógios.
