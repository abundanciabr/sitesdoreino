---
schema_version: 2
armadilha: 416
estado: guardada
degrau: 3
confianca: alta
custo_por_queda: alto
gatilho:
  - .github/workflows/pouso.yml
  - ci/tempos_esperados.json
guarda:
  tipo: CI
  dono: ci/tests/test_pista_a_fila_anda.py
  detector: 'test_checks_acima_do_teto_antigo_ainda_pousam_com_teto_da_regua: um conjunto de checks de 460s pousa; com teto fixo de 420s o teste reprova'
sinal: 'a pista atualiza um PR, espera checks lentos e o devolve quando o teto fixo vence'
licao: 'O teto da espera da pista deve ser calculado do p90 versionado dos checks, com folga explícita e arredondamento, nunca repetido como número fixo no workflow.'
---

# 416: Teto fixo da pista envelhece fora da régua

## Sintoma

Um PR atrasado é atualizado pela pista, os checks terminam verdes depois de
sete minutos e o PR volta à fila porque o workflow encerra a espera em 420
segundos.

## Causa

O job dos checks mudou de duração, mas `TETO_DA_ESPERA` continuou sendo uma
constante escrita no workflow. A régua versionada já mede o p90 dos checks e
não era usada para dimensionar a espera.

## Lição

Leia o p90 de `ci/tempos_esperados.json`, aplique a folga definida no workflow
e arredonde para minutos inteiros. Se a régua estiver ausente ou inválida, a
espera deve parar com erro, nunca inventar um número.

## Evidência

`python -m pytest ci/tests/test_pista_a_fila_anda.py -q` passou com 8 testes.
Na contraprova, trocar o cálculo pela constante `TETO_DA_ESPERA=420` fez o
novo teste reprovar: o cenário de 460 segundos foi devolvido à fila.
