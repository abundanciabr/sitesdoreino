---
schema_version: 2
armadilha: 189
estado: guardada
degrau: 4
confianca: alta
custo_por_queda: medio
guarda:
  tipo: sino
  dono: ci/sino_das_armadilhas.py
sinal:
  - `assert (datetime\.datetime\([^)]*\)) [<>]=? \1`
---

# `assert datetime.datetime(...) > datetime.datetime(...)` com os DOIS lados IDÊNTICOS — no Windows, dois `timezone.now()` seguidos caem no mesmo tique do relógio

**Sintoma:** um teste que compara instantes falha **às vezes**, só na máquina de
quem desenvolve (Windows), e sempre verde no Linux da CI. A mensagem mostra os
dois lados **iguais até o microssegundo**:

```
>       assert novo.ultima_atividade_em > marca, "o tópico nasceu depois da marca"
E       AssertionError: o tópico nasceu depois da marca
E       assert datetime.datetime(2026, 8, 30, 1, 43, 24, 235317, tzinfo=datetime.timezone.utc)
E            > datetime.datetime(2026, 8, 30, 1, 43, 24, 235317, tzinfo=datetime.timezone.utc)
```

Medido em 29/08/2026 em `services/forum`, com PostgreSQL real:
**10 falhas em 30 execuções** do mesmo teste, sem mudar uma linha entre elas.

**Causa — o relógio do Windows anda aos saltos de 15,625 ms.** Não é o banco,
não é fuso, não é `USE_TZ`:

```bash
python -c "import time; print(time.get_clock_info('time').resolution)"
# Windows 11: 0.015625   |   Linux da CI: ~1e-09
```

`time.time()` no Windows vem de `GetSystemTimeAsFileTime`, cuja granularidade é
o tique do agendador — ~15,6 ms. Dentro de um mesmo tique, **todo
`timezone.now()` devolve exatamente o mesmo valor**.

O teste fazia duas leituras desse relógio:

1. `marca = timezone.now()` — a marca-d'água;
2. `Topico.objects.create(...)`, cujo campo `ultima_atividade_em` é
   `auto_now_add=True` — e `auto_now_add` **não** é `NOW()` do Postgres: é
   `DateTimeField.pre_save()` chamando `timezone.now()` **em Python**, no mesmo
   processo e no mesmo relógio grosso (o mesmo mecanismo da `armadilhas/139`).

Entre as duas há apenas um `INSERT` de ida e volta — 1 a 3 ms, **menos que um
tique**. Então na maior parte das vezes as duas leituras caem no mesmo salto e
`a > b` vira `a == b`. No Linux, com resolução de nanossegundos, a chance é
desprezível: **por isso a CI fica verde e a máquina do desenvolvedor não** — é
falso-verde por plataforma, e "passa na CI" não é prova de que o teste é
determinístico.

**Solução — tire o relógio da equação, não a asserção:**

```python
from datetime import timedelta

# ERRADO: as duas leituras podem cair no mesmo tique
marca = timezone.now()

# CERTO: a referência nasce explicitamente no passado — 64 tiques de folga
marca = timezone.now() - timedelta(seconds=1)
```

Depois disso: **0 falhas em 30 execuções** do teste isolado, e 10 rodadas
seguidas da suíte inteira da célula (69 testes) verdes.

**O que NÃO fazer, e o motivo:**

- **Não afrouxe para `>=`.** É a correção que primeiro ocorre e a única que
  destrói o teste: a propriedade que ele existe para provar é justamente que o
  registro nasceu **DEPOIS** da marca. Com `>=`, um tópico criado *antes* da
  marca também passaria — o teste continuaria verde para sempre, inclusive
  quando o código estivesse errado.
- **Não resolva com `time.sleep(0.02)`.** Funciona, e cobra 20 ms de cada
  execução para sempre; determinismo por espera é a versão lenta de
  determinismo por valor explícito.
- **Não conclua "é o banco".** Se o campo fosse `db_default=Now()`, o instante
  viria do relógio do Postgres (microssegundos de verdade) e o diagnóstico seria
  outro. Confira de que lado o timestamp nasce **antes** de investigar: `auto_now`
  e `auto_now_add` nascem em Python, sempre.

**Onde mais essa classe se esconde:** qualquer teste que leia `timezone.now()` e
compare com um campo `auto_now_add`/`auto_now` gravado logo em seguida — marcas
de leitura, janelas de expiração, "criado depois de", ordenação por recência,
dedup por janela de tempo. A regra de bolso: **o instante de referência de um
teste é um valor que você escolhe, nunca um valor que você lê do mesmo relógio
que está medindo.**

**Guarda:** o sino (`armadilhas/SINAIS.json`) reconhece a assinatura pela
retro-referência `\1` — ele só toca quando os dois lados da comparação são
textualmente **idênticos**, que é a colisão de tique. Uma falha de ordenação
legítima (datas de fato diferentes) não o toca, e nenhuma saída do dia a dia
casa.

**Nota de rodape que custou duas rodadas, e nao e sobre relogio:** esta entrada
nasceu `187`, virou `188` e so entao `189` — colidiu DUAS vezes com entradas que
outras sessoes mergearam enquanto este PR existia. O motivo e um buraco de
documentacao, nao de sorte: **o almoxarife ja sabe dar numero de armadilha**
(`python ci/reservar.py numero armadilha`, uma reserva no servidor do GitHub,
comparar-e-trocar — a mesma trava dos registros do livro), mas o `ARMADILHAS.md`
e o `CLAUDE.md` mandavam "NNN = proximo numero livre", que e escolher a mao e nao
tem trava nenhuma. Duas sessoes leem a pasta, veem o mesmo livre, e o `git merge`
junta os dois arquivos sem ter o que reclamar — nomes diferentes, hunks
diferentes. **Peca o numero; nao o escolha.** O `ARMADILHAS.md` foi corrigido no
mesmo PR desta entrada — e no PR seguinte a regra deixou de depender de leitura:
`ci/muralha-das-reservas.sh` reprova, em todo PR, numero de armadilha novo sem
reserva no servidor, e a recusa ja traz o conserto.

**Origem:** 29/08/2026, `services/forum/tests/test_modelo_de_dados.py::test_a_excecao_existe_para_o_que_foi_lido_depois_da_marca`.
Ver também `armadilhas/139` (o mesmo mecanismo — `pre_save()` de campo — visto
pelo outro lado: ele **sobrescreve** o valor histórico que você atribuiu).
