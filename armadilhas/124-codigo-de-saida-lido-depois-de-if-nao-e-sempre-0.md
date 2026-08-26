# `codigo=$?` dentro de um `if ! cmd; then` é SEMPRE 0 — o veredito se perde na negação, e o script imprime "(exit 0)" ao reprovar

**Sintoma:** um portão de shell escrito assim

```bash
if ! saida="$(node $passo 2>&1)"; then
  codigo=$?
  echo "reprovou em: $passo (exit $codigo)"
  if [[ $codigo -eq 2 ]]; then exit 2; fi   # nunca dispara
  falhou=1
fi
```

reprova corretamente, mas **imprime `(exit 0)`** — e o ramo que trata o `exit 2`
(ERROR, "não consegui medir") nunca roda: todo ERROR sai como FAIL.

**Causa:** dentro do `then`, `$?` é o status da **condição do `if` inteira**, e a
condição inclui o `!`. Se o comando falhou com 2, o `!` inverte para 0, o `if`
entra no ramo — e o `$?` que você lê ali é **o 0 da negação**, não o 2 do
comando. O `!` consome o veredito exatamente como o `| tail` da armadilha 123
consome: lá ele se perde no cano, aqui na negação.

Reproduz em uma linha:

```bash
bash -c 'f(){ return 2; }; if ! saida="$(f)"; then echo "capturado=$?"; fi'   # capturado=0
```

**Por que é perigoso e não só feio:** o dialeto da casa
(`RETROSPECTIVA-FASE-D.md` §1) separa **FAIL (1) = medi e achei violação** de
**ERROR (2) = não consegui medir**, e essa diferença é o que impede "instrumento
quebrado" de ser lido como "conteúdo errado". Com o `$?` zerado, os dois viram a
mesma coisa e o número impresso na tela é uma mentira — num script cuja função é
justamente não deixar ninguém mentir. Aqui a falha caiu para o lado seguro (ERROR
virou FAIL, e a CI ficou vermelha do mesmo jeito), mas o inverso é possível em
qualquer script que decida "se for 2, tolere".

**Solução:** capture o código **antes de qualquer teste**, e teste a variável.

```bash
saida="$(node $passo 2>&1)"
codigo=$?
if [[ $codigo -ne 0 ]]; then
  ...
fi
```

Regra de bolso, irmã da 123: **`$?` só vale imediatamente depois do comando que
você quer medir** — qualquer coisa entre os dois (um `!`, um pipe, outro
comando, até um `echo`) troca o número por baixo do pano. Vale também para
`if cmd; then ... else codigo=$?`, pelo mesmo motivo.

**Como um teste pega isto:** exercite o portão num cenário que produza ERROR de
verdade (instrumento sem conseguir medir) e afirme **duas** coisas — o exit code
`2` **e** o texto `(exit 2)` na saída. Afirmar só o exit code não pega o "(exit
0)" impresso; afirmar só o texto não pega o rebaixamento.

**Origem:** auditoria da reforma dos painéis, 26/08/2026 —
`ci/muralha-do-painel.sh` imprimia `(exit 0)` ao reprovar e rebaixava a ERROR do
`gerar_manifesto.js` (pasta de registros vazia) a FAIL. O arquivo de teste
`ci/tests/test_muralha_do_painel.py` dizia no cabeçalho cobrir "os três estados"
e cobria dois: o estado que faltava era exatamente o que o bug apagava. Corrigido
no PR #227, com o caso de ERROR virando teste.
