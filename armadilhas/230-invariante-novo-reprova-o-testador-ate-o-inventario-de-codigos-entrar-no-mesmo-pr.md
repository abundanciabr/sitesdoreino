---
schema_version: 2
armadilha: 230
estado: documentada
degrau: 5
confianca: alta
custo_por_queda: baixo
guarda:
  tipo: CI
  motivo: o próprio `ci/tests/test_guarda_dos_guardas.py` reprova por desenho quando um invariante nasce, e o docstring dele já diz que acrescentar o código é manutenção de inventário; o que faltava era a entrada avisar que o conserto cabe no MESMO PR e que ele obriga a tocar `ci/`
---

# Invariante novo em `INVARIANTES.md` reprova o `testador`, e o conserto mora em `ci/`

**Sintoma.** Você declara um invariante novo no `INVARIANTES.md`, o
`python ci/guarda_dos_guardas.py` fica **PASS**, as 13 muralhas ficam **PASS** —
e cinco minutos depois a suíte de `ci/tests` reprova num teste que não fala do
seu assunto:

```
E       AssertionError: assert ['INV-P1', 'I...'INV-P6', ...] == ['INV-P1', 'I...'INV-P6', ...]
E         At index 21 diff: 'INV-GAM1' != 'INV-CI01'
E         Left contains 3 more items, first extra item: 'INV-GAM2'
ci\tests\test_guarda_dos_guardas.py:653: AssertionError
1 failed, 1307 passed in 286.44s (0:04:46)
```

**Causa.** `test_parse_do_documento_real_casa_os_blocos_de_hoje` compara por
**igualdade exata** a lista de códigos que o parser acha no `INVARIANTES.md`
real. Não é um teste frouxo que envelheceu: o docstring dele diz que falhar
quando um invariante nasce **é o comportamento pretendido**, para obrigar quem
escreve o próximo a conferir que o parser ainda enxerga todos. Acrescentar o
código à lista é manutenção de inventário; trocar o `==` por `<=` seria
afrouxar, e mataria o único mecanismo que força a revisão.

**Solução: a linha do inventário viaja no MESMO PR que o invariante** — como a
rota e o `painel/mapa-do-site.json` da `armadilhas/223`, e pela mesma razão: o
inventário sozinho descreveria um código que ainda não existe, e o
`INVARIANTES.md` sozinho reprova. A ordem dentro da lista é a de **aparição no
documento**, não a numérica.

**O que isso custa, e precisa estar no despacho:** o conserto fica em
`ci/tests/test_guarda_dos_guardas.py`, que é caminho **CODEOWNERS** e quase
nunca está no `toca` de uma tarefa de célula. Declarar um invariante **implica**
tocar `ci/` — quem escreve o despacho deve prever isso, e quem executa deve
anunciar o caminho nominalmente. E rode `pytest ci/tests` **antes** de abrir o
PR: o portão que você acabou de deixar verde não é o que vai reprovar.

**O bônus, para quem for provar este portão por sabotagem.** Retirar da
declaração **só o caminho** da linha `Teste-Guarda` não serve como vermelho: o
parser levanta `ErroDeInstrumentacao` ("invariante com `Teste-Guarda:` sem
caminho") e o resultado é **ERROR (exit 2)** — vermelho morto no INSTRUMENTO, o
caso exato da `armadilhas/195`. A sabotagem honesta é **apagar o bloco
`### [INV-XXX]` inteiro**: aí a regra 5 (o INVERSO) acusa em **FAIL (exit 1)**,
nomeando o arquivo que ficou em disco sem invariante declarado. Confira o exit
antes de colar a saída: 1 é a regra falando, 2 é o instrumento cego.

Duas notas que economizam uma rodada: o varredor lê `git ls-files --cached`, então
guarda renomeado ou criado precisa de `git add` antes de o portão local enxergá-lo;
e `ci/guardas-nao-declarados.txt` **não** é o caminho barato aqui — ela só encolhe,
e cada linha nova aparece no diff como dívida crescendo.

**Origem:** 30/08/2026, TAR-042 (as três leis da economia da gamificação viram
invariante declarado, PR #641). O `guarda_dos_guardas` estava verde com
[INV-GAM1..3] declarados; quem reprovou foi o inventário, seis minutos de suíte
depois.
