# 329 — O dublê do teste não reproduz a configuração que a coisa real faz, e o vermelho vira alarme falso

**Sintoma.** Um teste fica vermelho só numa plataforma (aqui, Windows), verde na
CI. Você investiga, encontra uma explicação técnica boa e coerente, e conclui
que **a coisa real está quebrada**. Só que não está: quem está errado é o dublê
que o teste escreve, e a explicação boa descrevia um defeito que não existe.

Caso real, 04/09/2026. Dois testes de `ci/tests/test_espera.py` reprovando no
Windows. `esperar.py --e-pousar` decide remedir o portão casando uma frase
ACENTUADA da saída dele:

```python
MARCA_DO_GITHUB_RECALCULANDO = "calcula isso de forma assíncrona"
saida = (proc.stdout or "") + (proc.stderr or "")      # lido com encoding="utf-8", errors="replace"
recalculando = proc.returncode == 2 and MARCA_DO_GITHUB_RECALCULANDO in saida
```

No Windows um processo Python escreve na codificação da região. Medido:

```
$ python -c "import sys,locale; print(sys.stdout.encoding, locale.getpreferredencoding())"
cp1252 cp1252
$ python -c "print('assíncrona')" | python -c "import sys; print(sys.stdin.buffer.read())"
b'ass\xedncrona\r\n'
```

Conclusão tentadora, e ERRADA: "a remedição do pouso está morta no Windows, em
silêncio". Foi escrita numa tarefa da fila, num registro do livro e nesta
própria armadilha. **O desmentido veio ao vivo, no PR que carregava a tarefa:**

```
⏳ o portão não conseguiu medir (o GitHub ainda recalcula o PR 1033);
   remeço em 20.0s (1 de 6)
```

**Causa.** A medição foi feita num `python -c` pelado e a conclusão foi tirada
sobre outro programa. O portão de verdade (`ci/mergear.py`) chama
`configurar_saida()` na linha 864, e essa função (`ci/_nucleo.py`) faz
`sys.stdout.reconfigure(encoding="utf-8", errors="replace")`. A casa já tinha
resolvido a classe inteira, anos-luz antes desta sessão.

O portão de MENTIRA que o teste gera em `_rodar` não chama essa função:

```python
portao.write_text(
    "import json, sys, pathlib\n"
    ...
    "print(atual['saida'])\n",
    encoding="utf-8",
)
```

Repare no detalhe cruel: o teste grava o ARQUIVO em utf-8 (correto), o que dá a
impressão de que a codificação foi cuidada. O que falta é a saída em tempo de
execução, e é justamente ela que o programa sob teste vai ler.

**Solução.**

1. **Antes de acusar a coisa real, leia a coisa real.** Não conclua sobre o
   comportamento de um programa medindo outro. Um `grep` por `reconfigure`,
   `configurar_saida` ou `PYTHONIOENCODING` no processo filho custa dez
   segundos e teria evitado três artefatos errados nesta sessão.
2. **Procure o desmentido mais barato que existir.** Aqui ele era gratuito: o
   próprio caminho estava rodando ao vivo. "Isto está quebrado em produção" é
   uma afirmação que quase sempre tem uma observação direta disponível.
3. **Dublê que não reproduz a configuração da coisa real não prova nada sobre
   ela** — nem quando fica verde (falso-verde), nem quando fica vermelho
   (alarme falso). Quando o dublê e a realidade divergem, o conserto é no
   dublê, e ele deve chamar a função da casa em vez de copiar o comportamento à
   mão, senão volta a divergir na próxima mudança.
4. **Vermelho local com CI verde não é ruído, e também não é prova.** É um
   pedido de investigação. As duas conclusões preguiçosas ("é chatice de
   ambiente" e "a produção está quebrada") custam caro; a barata é ir ler.

**O que ficou caro nesta:** uma tarefa da fila, um registro do livro e esta
armadilha nasceram com o diagnóstico invertido e tiveram de ser corrigidos
antes de pousar, com o PR já aberto e na fila da pista (foi preciso tirar o
rótulo `pousar` para não deixar entrar). O erro não foi medir: foi medir uma
coisa e falar de outra.

**Onde vive o caso:** `ci/tests/test_espera.py` (a função `_rodar`),
`ci/_nucleo.py::configurar_saida`, `ci/mergear.py` linha 864, e a tarefa
`TAR-142`, que carrega as duas medições, a errada e a certa.

**Parentes:** `armadilhas/003` (acento virando lixo na saída), `armadilhas/012`
(CRLF que só quebra fora do Windows), `armadilhas/138` (teste que reprova só no
Windows) e `armadilhas/266` (a contraprova do guarda mora dentro do teste, não
na cabeça de quem o escreveu).
