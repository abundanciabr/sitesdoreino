---
schema_version: 2
armadilha: 248
estado: guardada
degrau: 4
confianca: alta
custo_por_queda: alto
guarda:
  tipo: CI
  dono: ci/mergear.py
sinal:
  - `nenhum registro viaja neste PR`
  - `registro a bordo +FAIL`
  - `pagamento\(s\) já EM VOO`
---

# A fila trava para todos, e os robôs pagam a mesma dívida em paralelo

**Sintoma.** A pista de pouso recusa TODO PR por "dívida do livro" de merges
que não são seus. Cada robô travado, sem ver os outros, escreve o próprio PR
de pagamento — e a pista passa a tarde aterrissando escrituração em vez de
trabalho.

Medido em 31/08/2026, entre 16h e 17h40 UTC: **12 das 25 aterrissagens foram
PRs de "livro:"**, e **4 PRs diferentes pagavam as MESMAS duas dívidas** (dos
merges #701 e #703 — os PRs #742, #743, #744 e #745, de robôs distintos). O
título de um deles resume: "registrando o merge #703, o quinto sem aviso na
mesma tarde".

**Causa — a dívida nascia do caminho NORMAL, não do descuido.** Duas leis da
casa se contradiziam:

1. `CLAUDE.md` mandava: registre DEPOIS de confirmar o merge.
2. `RITOS.md` §2 peça 5 manda: peça pouso e **vá embora** — a pista mergeia
   minutos ou horas depois, sozinha.

Junte as duas: quando o merge acontece, não há mais ninguém ali para
registrar. Depois dos 90 minutos de folga, vira dívida. E como a dívida é
COMPARTILHADA (trava a fila de todos, de propósito, para não ser ignorável),
o resultado era punição coletiva + corrida de cobradores: N robôs travados
pagando a mesma conta em N PRs, sem olhar o que já estava em voo.

**Solução — o recibo embarca no próprio PR (a cura, desde 31/08/2026).** O
mesmo desenho que curou a doença do painel (`armadilhas/156`): juntar o fato e
o recibo no mesmo átomo.

1. Abra o PR, leia o número, escreva o registro citando-o e commite **no mesmo
   ramo** (a ordem que a `armadilhas/185` já prescrevia). O registro só entra
   no livro SE o merge acontecer — o recibo não existe sem o fato, então não é
   falso-verde.
2. O portão confere o embarque NA PORTA (`checar_registro_embarcado` em
   `ci/mergear.py`): PR de entrega sem o próprio registro a bordo não pede
   pouso. PR que só escritura (`painel/` e/ou `fila/`) é isento.
3. A cobrança pós-merge (`divida`) vira rede de segurança para merge por fora
   da pista — e, quando reprova, **lista os pagamentos já em voo** (PRs de
   escrituração abertos), para dois robôs não pagarem a mesma conta.

**Se você caiu aqui como PAGADOR:** antes de escrever qualquer registro de
dívida alheia, leia a lista "EM VOO" da própria recusa. Se um PR aberto já
paga aquela conta, espere o pouso dele — não crie outro.

**Contexto.** 31/08/2026. A pergunta do mantenedor que disparou a cura:
"como resolver isso definitivamente, evitando que se percam horas de trabalho
como aconteceu hoje?". As leis mudaram junto com o mecanismo, no mesmo PR:
`CLAUDE.md` (o registro embarca; merge de fora continua gatilho),
`RITOS.md` §2 peça 4, `painel/LEIA-ME.md` passo 0. Testes-guarda em
`ci/tests/test_divida_do_livro.py`.
