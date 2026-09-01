---
schema_version: 2
armadilha: 264
estado: guardada
degrau: 3
confianca: alta
custo_por_queda: alto
guarda:
  tipo: CI
  dono: services/sugestoes/tests/test_cartas_da_gamificacao.py
sinal:
  - `ValueError: day is out of range for month`
  - `parse_date`
  - `datetime.date.fromisoformat`
---

# `parse_date()` do Django **levanta** em data com formato certo e dia impossível, e uma linha de dado torto derruba a página inteira de uma pessoa

**Sintoma.** Uma tela que lê dado de fora (uma carta da caixa central de avisos,
a resposta de outra célula, uma coluna de texto) converte uma data com
`django.utils.dateparse.parse_date`. Toda a suíte está verde. Em produção, um
único registro com `"2026-02-31"` devolve **500 na página inteira**, e não um
campo vazio naquela linha:

```
ValueError: day is out of range for month
```

O que confunde é que a mesma função devolve `None`, sem reclamar, para
`"ontem"`, `""`, `"2026-08-25T10:00:00Z"` e qualquer outro lixo. O programador
testa exatamente esses casos, vê `None` nos quatro, conclui que a função é
fail-open e segue sem `try`.

**Causa.** `parse_date` faz duas coisas, e só a primeira falha suave:

1. Casa a string contra uma expressão regular de formato. **Não casou, devolve
   `None`.** É daqui que vem a impressão de que ela nunca levanta.
2. Casou? Entrega os grupos a `datetime.date(...)`, que **valida o calendário**
   e **levanta `ValueError`** quando o dia não existe naquele mês.

`"2026-02-31"` está no meio: passa pela régua do formato e morre na do
calendário. É a única faixa de entrada em que a função é fail-closed, e é
justamente a que ninguém escreve teste para.

Vale igual para `datetime.date.fromisoformat`, que também levanta em vez de
devolver `None`.

**Por que o custo é a página inteira, e não a linha.** Numa lista, a conversão
acontece dentro do laço que monta os itens. Uma exceção ali não estraga um
cartão: ela sobe pela view e a pessoa perde **todos** os avisos dela, inclusive
os que estavam perfeitos. É a mesma família do `NoReverseMatch` que fez esta
mesma tela ganhar o ramo do `desconhecido` (`armadilhas/156` e o cartão de
matrícula de 29/08/2026): uma carta ruim não pode calar as boas.

**Solução: `try/except ValueError` em volta, e a falha vira ausência.**

```python
try:
    semana = parse_date(parametros.get("semana") or "")
except ValueError:
    # Formato certo e dia impossível ("2026-02-31"): parse_date LEVANTA em vez
    # de devolver None, e uma carta não pode derrubar a página de ninguém por
    # causa de um caractere.
    semana = None
```

A regra que fica, e ela é mais larga que a data: **num consumidor de dado
externo, o parse de UM campo nunca pode decidir o destino da REQUISIÇÃO
inteira.** Ausência é uma resposta apresentável, e uma frase mais curta que
continua verdadeira é melhor que um 500. O contrário só vale na ESCRITA, onde
fail-closed é a lei (a origem recusa o dado torto e ninguém o grava).

**E o teste tem de citar a data impossível pelo nome**, porque nenhuma outra
entrada exercita esse ramo:

```python
@pytest.mark.parametrize("torta", ["", "ontem", "2026-02-31", "2026-08-25T10:00:00Z"])
def test_data_ausente_ou_torta_some_em_vez_de_estourar(...):
```

Sem o `"2026-02-31"` na lista, os outros três passam com e sem o `try`, e o
teste declara verde sobre um caminho que nunca rodou. Falso-verde clássico
(`RETROSPECTIVA-FASE-D` §1).

**Origem:** despacho das quatro cartas da gamificação no sininho
(`sugestoes`, PR #827, 01/09/2026), degrau 21a da escada da gamificação. O
parâmetro `semana` de `gamificacao.destaque-da-semana` é uma data de calendário
(a segunda-feira da semana), e o contrato a manda como DATA e não como data-hora
justamente para ninguém converter fuso e exibir a semana errada
(`armadilhas/099`). Foi ao escrever o teste dessa conversão que o ramo apareceu.
