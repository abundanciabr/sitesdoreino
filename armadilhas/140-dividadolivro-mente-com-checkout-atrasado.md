# `mergear.py --conferir` acusa dívida do livro já paga — quando o checkout está atrasado

**Sintoma:** `python ci/mergear.py <N> --conferir` reprova em "dívida do livro",
listando um PR que você tem certeza de já ter sido contado — inclusive com uma
URL `.../pull/<N>` visível dentro de um registro que você acabou de ler no
GitHub segundos antes.

**Causa:** `ci/divida_do_livro.py::numeros_citados()` lê `painel/registros/*.js`
**do disco local**, não do `origin/main`. Rodando o comando a partir de um
checkout desatualizado — o clone principal espelho, por exemplo, que a
`armadilhas/135` já proíbe EDITAR mas não impede de ler — os registros mais
novos (que citam o PR em questão) simplesmente ainda não existem naquela
pasta. O guarda está certo sobre o que vê; o que ele vê é que está errado.

É a `armadilhas/101` (clone desatualizado engana um revisor) na variante
mecânica: lá era um humano/agente lendo código velho para confirmar um bug já
corrigido; aqui é um PORTÃO AUTOMÁTICO caindo na mesma armadilha, porque
também lê arquivo do disco em vez de perguntar ao GitHub. A regex de citação
(`_CITACAO`) e a folga de `GRACA_EM_MINUTOS` estavam certas o tempo todo — não
há nada para consertar no `divida_do_livro.py`; o defeito é de onde o comando
foi executado, não de como ele mede.

**Solução:** rode `mergear.py` (qualquer flag, inclusive `--conferir`) de
dentro de um worktree recém-criado a partir de `origin/main`
(`git fetch origin && git worktree add ... origin/main`) — nunca do clone
principal sem antes conferir que ele está em dia (`git status` mostrando
"behind" já é o sinal). Se uma dívida apontada parecer errada, a primeira
pergunta não é "quem esqueceu de registrar" — é comparar
`git log -1 --format=%H` de onde o comando rodou contra
`git rev-parse origin/main`.

**Origem:** lote do sininho (Fase 3 das notificações, segunda metade),
27/08/2026 — a maestro quase reabriu uma investigação de "dívida" que já
estava paga havia 12 horas, porque conferiu a partir do clone principal (8+
commits atrás de `origin/main` no momento).
