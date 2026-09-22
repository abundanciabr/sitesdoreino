# Fotografia oficial da plataforma

Medição realizada em **22/09/2026 07:24:24 BRT** (**10:24:24 UTC**), na bancada `wt-admin-fotografia-oficial-fase-1-2026-09-22`.

## Linha de base

| Item | Medição | Fonte e prova |
|---|---:|---|
| `origin/main` | `db55622c5ddc6b711a9a34fb3496d176644560dd`, commit em 22/09/2026 01:48:13 BRT | `git rev-parse origin/main`; `git show -s --format='%H|%cI|%s' origin/main` |
| Divergência do clone principal | 25 commits atrás; 0 à frente | `git rev-list --left-right --count origin/main...main` |
| Árvore do clone principal | 9 arquivos alterados ou não rastreados | `git status --short --branch`; a árvore principal permaneceu intacta |
| Remote | `origin` em `https://github.com/abundanciabr/sitesdoreino.git` | `git remote -v` |
| Worktrees | 77 | `git worktree list` |
| Branches locais | 221 | `git for-each-ref refs/heads` |
| Referências remotas | 3.550, excluindo `origin/HEAD` | `git for-each-ref refs/remotes` |
| Fichas Codex | 5 TOML | `.codex/agents/` |
| Fichas Claude | 8 fichas, excluindo `LEIA-ME.md` | `.claude/agents/` |
| Workflows | 28 arquivos | `.github/workflows/` |
| Contratos OpenAPI | 16 YAML | `contracts/**/*.yaml` |
| Eventos versionados | 53 JSON | `contracts/eventos/**/*.json` |
| Mandato por CODEOWNERS | 16 padrões nominais, todos com `@abundanciabr` | `.github/CODEOWNERS` |
| Livro de ocorrências | 1.764 registros; último `20260922-006-fila-retirar-cartoes-cancelados-pelo-mantenedor.js` | `painel/registros/` |

## PRs e checks

| Estado | Quantidade |
|---|---:|
| Abertos | 5 |
| Abertos em rascunho | 3 |
| Abertos prontos | 2 |
| Fechados | 1.870 |
| Fechados sem merge | 97 |
| Fechados com merge | 1.773 |

Fonte: `gh pr list --state open/closed --limit 10000`. Os cinco PRs abertos foram consultados com `gh pr view <N> --json statusCheckRollup`:

| PR | Situação | Checks |
|---:|---|---|
| #1884 | rascunho | 8: 5 sucesso, 1 ignorado, 2 em andamento |
| #1883 | rascunho | 8: 7 sucesso, 1 ignorado |
| #1882 | rascunho | 8: 7 sucesso, 1 ignorado |
| #1881 | aberto | 8: 6 sucesso, 1 ignorado, 1 falha |
| #1880 | aberto | 8: 8 sucesso |

## Runs, pousos, vigias e alarmes

O recorte consultado foi de **1.000 runs mais recentes**, por `gh run list --limit 1000`; não é uma contagem histórica total.

| Estado | Quantidade |
|---|---:|
| Em andamento | 1 |
| Concluídos | 999 |
| Sucesso | 934 |
| Falha | 50 |
| Cancelados | 15 |
| Sem conclusão no retorno | 1 |

Últimos runs por família no mesmo comando:

| Família | Run mais recente | Resultado |
|---|---:|---|
| Pouso | `35715485467` | sucesso, 22/09/2026 07:21:01 BRT |
| Vigia do site | `35711234372` | sucesso, 22/09/2026 06:35:19 BRT |
| Vigia do pouso | `35685904500` | sucesso, 22/09/2026 01:10:56 BRT |
| Vigia do cadeado | `35628043454` | sucesso, 21/09/2026 13:49:18 BRT |
| Alarme da main | `35677122277` | sucesso, 21/09/2026 22:48:16 BRT |

## Últimos deploys por célula

Fonte: `gh run list --workflow deploy-celula.yml --limit 30`, complementado por `gh run view <run> --json jobs`. O campo abaixo é o último job `deploy (<célula>)` concluído com sucesso dentro da janela consultada.

| Célula | Run | Horário BRT | SHA |
|---|---:|---|---|
| admin | `35675447007` | 22/09/2026 01:21:25 | `4185469d9910027e11bafdb39103149c211465c1` |
| quiz | `35674998337` | 22/09/2026 01:14:00 | `7b84a5d520249e2389ece0664faad47e6bdcc072` |
| cursos | `35673226723` | 22/09/2026 00:45:06 | `4a1b84e7fa431b057a5cd8d504d2a307e3e39a6a` |
| pagamentos | `35613417997` | 21/09/2026 14:37:36 | `073b0bbc49acaa7736429e55a57f0118a2050ac1` |
| checkout | `35612177836` | 21/09/2026 14:26:29 | `4b9c981bbd494e5c4a28bd07257ba1b00a72d6b9` |
| demais 13 células | não localizado na janela de 30 runs | consultar runs anteriores da mesma workflow | não inferido |

## Estado atual do site

`curl.exe --silent --show-error --location --output NUL --write-out "HTTP %{http_code}; URL %{url_effective}; tempo %{time_total}s" --max-time 30 https://meshcraft.top` retornou **HTTP 200**, URL final `https://meshcraft.top/` e tempo **0,809407 s**.

Esse resultado comprova disponibilidade HTTP da página inicial; não comprova login, compra ou todas as rotas internas.

## Veredito da fase

**NÃO PRONTO como fotografia completa.** A linha de base Git, PRs, checks, mandato, runs, site, worktrees, branches, remotes e fichas está medida com fonte e horário. A fotografia ainda não fecha o último deploy de cada uma das 18 células, pois a consulta apresentada cobre os 30 runs de deploy mais recentes e 13 células não apareceram com job de deploy bem-sucedido nesse recorte.

Para fechar a fase, ampliar a leitura histórica de `deploy-celula.yml` até encontrar o último job bem-sucedido das 13 células restantes e registrar run, horário, SHA e URL para cada uma.
