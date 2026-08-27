# A suíte de `ci/tests` reprova quando rodada de DENTRO de um worktree do harness

**Sintoma:** `python -m pytest ci/tests -q` a partir de um worktree criado pelo
Claude Code (`.claude/worktrees/<nome>/`) devolve **1 falha** que não existe no CI
e não existe no clone principal:

```
FAILED ci/tests/test_contrato_check_das_celulas.py::test_o_varredor_ignora_os_worktrees_de_outras_sessoes
E   assert not ['...\.claude\worktrees\painel-vivo-admin\services\admin\Makefile', ...]
512 passed, 1 failed
```

A lista de "intrusos" são os Makefiles das **próprias** células do worktree — as
11, não as de outra sessão.

**Causa:** o guarda foi escrito contra `armadilhas/106` (um `rglob` que entrava
em `.claude/worktrees/<sessao>/services/*/Makefile` e media o trabalho alheio
junto com o seu). A regra que ele implementa é *"nenhum caminho varrido contém
`.claude` nas suas partes"* — e ela vale enquanto a raiz do repositório estiver
FORA de `.claude`. Num worktree do harness a raiz é
`<repo>/.claude/worktrees/<nome>/`, então **todo** caminho legítimo contém
`.claude`, e o guarda acusa o repositório inteiro de ser intruso.

É um falso-positivo do cenário, não do código: no CI (`actions/checkout` numa
pasta limpa) e no clone principal a condição não ocorre, e o guarda continua
fazendo exatamente o que deve.

**O que fazer:** nada, além de saber. Rodando de dentro de um worktree, esta
falha é esperada e não bloqueia nada — confira que é ELA (o nome do teste e o
caminho `.claude` nos intrusos) e siga. O `muralhas` (`python ci/ci.py --apenas
muralhas`) e a suíte da célula rodam limpos no worktree, e são eles que o
`ci-celula-gate` e o `muralhas` reproduzem no PR.

**O que NÃO fazer:** "consertar" o guarda afrouxando a regra para aceitar
`.claude` — isso reabriria `armadilhas/106`, que é justamente uma sessão medindo
o trabalho de outra. Se algum dia valer a pena, o conserto correto é ancorar a
comparação na RAIZ do repositório (caminho relativo à raiz, não partes
absolutas), não remover a proibição.

**Por que isto vale uma entrada:** o `CLAUDE.md` manda sessões paralelas
trabalharem cada uma em worktree próprio (`RUNBOOK-LOTES.md:42`, RITOS §1), e
uma sessão que obedece encontra este vermelho na primeira vez que roda a suíte
inteira. Sem esta entrada, o próximo agente gasta uma rodada investigando um
bug que não existe — ou, pior, "conserta" o guarda e reabre o `/106`.

**Origem:** despacho admin/painel-vivo-atras-da-porta, 26/08/2026 (PR #249). O
worktree tinha sido criado por outro motivo: uma segunda sessão do Claude Code
estava trabalhando na MESMA pasta ao mesmo tempo, trocou de ramo no meio do
trabalho e apagou as edições em arquivos versionados desta sessão — os arquivos
novos, não rastreados, sobreviveram. A lei já existia; a sessão é que não estava
seguindo. Ver também `RUNBOOK-LOTES.md` §"Lote 1", item 1 (a pilha de `git stash`
é única por repositório, compartilhada por todos os worktrees).
