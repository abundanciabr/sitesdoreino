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

**Onde isto mordia — ✅ FECHADO em 25/08/2026, no mesmo lote:** `rodar_celula`
em `ci/ci.py` tinha exatamente a tabela antiga (`returncode == 1` vira FAIL,
qualquer outra coisa vira ERROR), e como o make praticamente nunca devolve 1, o
`python ci/ci.py --celula <x>` — e o `make celula CELULA=<x>` — reportava
**ERROR — make ci não conseguiu rodar** para uma célula que simplesmente
reprovou no lint. Reproduzido antes de consertar, com um arquivo mal formatado
em `services/quiz`.

**A correção NÃO foi de uma linha,** e a diferença importa: trocar `1` por
`!= 0` teria consertado a reprovação e quebrado o outro lado, porque o GNU Make
devolve **2 também para alvo inexistente** — que é ERROR de verdade. As duas
metades do 2 não se separam pelo número, e ler a mensagem
(`No rule to make target`) não serve: as mensagens do make são traduzíveis por
locale, e portão que depende do idioma do runner é portão com data para quebrar.
O que entrou:

* um **ensaio** `make -n ci` antes da execução — se o alvo não é sequer
  planejável, é ERROR ali, com o comando de reprodução; provado que é, um 2
  depois só pode ser reprovação;
* `classificar_exit_do_make()`, com as mesmas sentinelas de `ci/sessao.py`
  (124/126/127 = não medi; qualquer outro não-zero = veredito do programa);
* `subprocess.TimeoutExpired` capturado e traduzido para a sentinela 124 — antes
  ele subia como traceback e derrubava o runner inteiro, que é o oposto de
  fail-closed legível;
* Makefile ausente na célula ⇒ ERROR explícito ("portão ausente não é portão
  satisfeito").

**E um guarda contra a deriva das duas cópias:**
`ci/tests/test_exit_do_make.py::test_as_duas_copias_da_sentinela_nao_derivaram`
lê `ci/ci.py` e `ci/sessao.py` e reprova se os conjuntos de sentinela
divergirem. Os dois encapsulam o MESMO `make ci`; sem o guarda, o dia em que um
aprendesse um código novo e o outro não seria descoberto só no incidente
(§5.11 — duplicação consciente é aceitável, duplicação sem guarda é armadilha
com data marcada).

**Origem:** despacho `ci/make-sessao` (peça C3 do PLANO-10X), medido ao vivo com
`black --check` reprovando em `services/quiz`, 25/08/2026.
