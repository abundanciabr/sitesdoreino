# Clone local desatualizado faz um revisor confirmar um bug que já foi corrigido — merge remoto não sincroniza o `main` local sozinho

**Sintoma:** durante uma auditoria/code-review de uma mudança já mergeada, você lê
um arquivo pelo caminho normal do repositório (`Read`, `grep`, `sed`), encontra um
defeito, e ele parece real e presente — mas na verdade **já foi corrigido em outro
PR, mergeado minutos antes, que o seu clone local nunca baixou**. O relatório sai
errado, com um bug "confirmado" que não existe mais.

**Causa:** `python ci/mergear.py <N> --confirmo <N>` mergeia no GitHub (Lei 4) —
isso é real, medido, confirmado por `state: MERGED`. Mas **não avança o `HEAD` do
clone local que está rodando a sessão**. Se a mesma sessão (ou uma auditoria que
comece depois, no mesmo clone) não roda `git fetch && git pull --ff-only` antes de
ler código "para conferir", ela está lendo o `main` de um instante atrás — e, pior,
se OUTRAS sessões mergearam PRs não-relacionados nesse intervalo (comum em lote —
RETROSPECTIVA-FASE-D §7), o clone local pode ficar **vários commits** atrás sem
nenhum aviso: não há erro, não há mensagem, `git log` local simplesmente mostra
menos história do que existe no GitHub.

O caso medido: uma sessão implementou e mergeou um PR (`#158`), encontrou e
mergeou um conserto de acompanhamento (`#159`, ~15 min depois), e então — no
MESMO clone, sem `git pull` no meio — pediu uma auditoria formal (`/code-review
158 max` + agentes independentes). Um dos agentes leu o arquivo já corrigido pelo
`#159` diretamente do disco do clone e encontrou a versão **antiga** (o bug do
`#159`, sem `#159`), porque nesse meio-tempo TRÊS OUTROS PRs de sessões diferentes
(`#160`, `#161`, `#162`, mais um `#163` de sincronização) também tinham mergeado —
o clone estava 9 commits atrás do `origin/main` real, sem que nada tivesse avisado.

**Por que escapou:** o merge acontece de verdade — `--conferir` e `--confirmo`
consultam o GitHub, não o disco local, então TUDO que o `mergear.py` verifica
continua correto. O gap é especificamente entre "o GitHub tem o commit" e "este
clone específico tem o commit" — duas coisas que parecem a mesma e não são.

**Solução:**
1. **Antes de qualquer leitura de código com intenção de auditar/revisar/confirmar
   um estado** (não antes de cada edição isolada — antes de "vou conferir se X está
   certo"): `git fetch origin && git status` e confira se `HEAD` é ancestral de
   `origin/main`. Se não for, é fast-forward puro na maioria dos casos —
   `git merge-base --is-ancestor HEAD origin/main && git pull --ff-only` — e é
   seguro porque não reescreve história, só avança.
2. **Rode a suíte de testes depois de sincronizar, não antes**, se o número de
   testes for parte do que você vai reportar — contar "262 testes" quando o real
   é "271" é exatamente este bug se manifestando num número, não só num código-fonte.
3. **Um agente de auditoria independente que só lê arquivo por caminho (sem `git
   log`/`git fetch` primeiro) herda a mesma cegueira do clone que o invocou** —
   se o despacho pede rigor, o primeiro passo do agente tem de ser confirmar que
   está vendo o estado real, não assumir que o disco está atualizado.

**Vale para qualquer clone de longa duração** (a raiz do repositório, não um
worktree efêmero que nasce de `origin/main` na hora) que permaneça aberto por uma
sessão inteira enquanto outros PRs (do próprio despacho ou de despachos paralelos)
vão sendo mergeados — é exatamente o padrão de "sessão raiz orquestrando lote" do
`RUNBOOK-LOTES.md`.

**Origem:** auditoria formal (code-review + 3 agentes independentes) da mudança
"o idioma padrão mora na raiz" (PRs #157-#159), 25/08/2026 — um agente de correção
independente encontrou o clone desatualizado ANTES de eu detectar sozinho, e a
sincronização (`git pull --ff-only`, fast-forward de 9 commits) foi o que revelou
que o "bug" que eu mesmo ia reportar via `/code-review 158 max` já não existia.
