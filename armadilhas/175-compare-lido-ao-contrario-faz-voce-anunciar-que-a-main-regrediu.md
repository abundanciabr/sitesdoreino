# `compare/A...B` lido ao contrário faz você anunciar que a `main` REGREDIU — e quase alarmar o mantenedor

**Sintoma:** você confere a `main` depois de mergear, e o commit do topo tem um
título de um PR **muito antigo**:

```
$ git log --oneline -1 origin/main
e35a055 Merge pull request #426 from abundanciabr/agent/admin/livro-da-caixa
```

Você acabou de mergear os PRs #465, #466 e #467. O servidor concorda com o
clone (`git ls-remote`, `gh api .../commits/main` — os três dizem `e35a055`),
então não é espelho desatualizado (`armadilhas/148`), não é clone raso
(`armadilhas/159`) e não é cache. Parece force-push: a `main` andou para trás
~40 commits e levou o trabalho do dia junto.

Você pede a comparação para confirmar, e ela confirma:

```
$ gh api repos/<o>/<r>/compare/e35a055...6d4d371 \
    --jq '"\(.status) ahead_by:\(.ahead_by) behind_by:\(.behind_by)"'
behind ahead_by:0 behind_by:19
```

**"behind", "19".** A conclusão se forma sozinha: a `main` está 19 commits
atrás. É aqui que se abre a boca para dizer ao mantenedor que o trabalho dele
sumiu.

**Causa:** os campos são relativos ao **head**, não à base, e o nome
`behind_by` é o oposto do que a leitura apressada sugere.

Em `compare/{base}...{head}`:

- `ahead_by` = quantos commits o **head** tem que a base não tem
- `behind_by` = quantos commits a **base** tem que o head não tem
- `status` descreve o **head** em relação à base

No exemplo acima, `base=e35a055` (a `main`) e `head=6d4d371` (o commit antigo).
`behind_by: 19` quer dizer que **`6d4d371` está 19 commits atrás da `main`** —
ou seja, a `main` está à frente, e tudo está no lugar. O contrário exato do que
foi lido.

A confusão tem um cúmplice: **o título do commit de merge carrega o número do
PR, não a ordem cronológica.** Um PR antigo que ficou aberto o dia todo e só
agora pousou produz um commit NOVO com título velho. `#426` no topo depois de
`#467` não é regressão — é um PR de manhã que pousou à tarde.

**Solução:** pergunte na direção que responde a sua dúvida de verdade, e
prefira a pergunta cuja resposta não depende de decorar o vocabulário:

```bash
# "o meu trabalho continua na main?"  base = o meu merge, head = a main
gh api repos/<o>/<r>/compare/<meu-merge>...<main> \
  --jq '"\(.status) ahead_by:\(.ahead_by) behind_by:\(.behind_by)"'
# ahead / behind_by:0  =>  a main CONTÉM o meu merge. Nada se perdeu.
```

Ou, sem vocabulário nenhum, no clone:

```bash
git merge-base --is-ancestor <meu-merge> origin/main && echo "esta la"
```

E antes de qualquer alarme: **o estado dos PRs é a testemunha mais barata.**
`gh pr view <N> --json state,mergeCommit` continuar dizendo `MERGED` com o sha
do merge existindo no servidor já elimina a hipótese de force-push destrutivo.

**A lição que atravessa:** este erro não estava no comando nem no repositório —
estava na leitura de uma saída de três palavras. O reflexo certo é o mesmo do
`ci/_nucleo.py`: **antes de anunciar um fato alarmante, meça de novo pelo outro
lado.** Um alarme falso entregue ao mantenedor gasta a confiança de que o
alarme verdadeiro vai precisar — e neste projeto o mantenedor é leigo, então
ele não tem como conferir sozinho e vai acreditar.

**Como foi achado:** auditoria interna das Ondas 3 a 6 (29/08/2026), ao criar
um worktree e estranhar o commit do topo. A conclusão errada chegou a ser
escrita antes de a segunda medição desfazê-la.
