# GNU Make devolve exit **2** quando a receita reprova — e quem lê `1 = FAIL` chama reprovação de "não consegui medir"

**Sintoma:** um portão que roda `make -C services/<celula> ci` como subprocesso
imprime, diante de um `black --check` que reprovou de verdade:

```
Motivo: o baseline não conseguiu rodar (exit 2)
...
would reformat .../apps/quiz/lixo.py
Oh no! 💥 💔 💥
make: *** [Makefile:16: lint] Error 1
```

A mensagem manda investigar o **instrumento** (make quebrado? ferramenta
ausente?) quando o que aconteceu foi o **código** reprovar. É o §5.6 ao
contrário: em vez de um verde que não mediu, um "não medi" que na verdade mediu
e reprovou.

**Causa:** o exit code do `make` **não é** o da receita. O `black --check` sai
1, o make imprime `Error 1` e sai com **2** — o código que o GNU Make reserva
para "uma receita falhou". Quem convencionou `1 = violação · 2 = não foi
possível medir` (a semântica do `ci/_nucleo.py`, certa para os portões escritos
em Python) e aplica a mesma tabela ao `make` classifica errado **toda**
reprovação de célula: lint, mypy, pytest, freeze — todas chegam como 2.

**Solução:** ao encapsular `make`, não classifique pelo número 1. Classifique
pelas **sentinelas que o seu próprio executor inventa** quando o comando nem
chegou a rodar — 127 (não encontrado), 126 (erro de SO), 124 (timeout) — e
trate *qualquer outro* não-zero como veredito do programa:

```python
SENTINELAS_DE_INSTRUMENTACAO = frozenset({124, 126, 127})

if saida.exit_code in SENTINELAS_DE_INSTRUMENTACAO:
    ...  # ERROR: nada foi provado
elif saida.exit_code != 0:
    ...  # FAIL: a célula reprovou, e o log diz onde
```

Ver `rodar_baseline` em `ci/sessao.py`, e o teste
`test_baseline_vermelho_e_FAIL_exit_1_e_manda_parar_e_reportar`, que é
parametrizado em `[1, 2]` justamente para que a correção não se perca.

**Onde isto ainda morde (dívida aberta em 25/08/2026):** `rodar_celula` em
`ci/ci.py` tem exatamente a tabela antiga — `returncode == 1` vira FAIL,
qualquer outra coisa vira ERROR. Como o make praticamente nunca devolve 1, o
`python ci/ci.py --celula <x>` (e o `make celula CELULA=<x>`) reporta
**ERROR — make ci não conseguiu rodar** para uma célula que simplesmente
reprovou no lint. O arquivo era somente-leitura no despacho que descobriu isto;
a correção é de uma linha e cabe em qualquer despacho que tenha `ci/ci.py` no
mandato.

**Origem:** despacho `ci/make-sessao` (peça C3 do PLANO-10X), medido ao vivo com
`black --check` reprovando em `services/quiz`, 25/08/2026.
