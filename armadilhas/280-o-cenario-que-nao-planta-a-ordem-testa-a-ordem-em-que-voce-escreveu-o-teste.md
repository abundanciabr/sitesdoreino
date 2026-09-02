---
schema_version: 2
armadilha: 280
estado: guardada
degrau: 6
confianca: alta
custo_por_queda: medio
guarda:
  tipo: teste
  detector: services/mensageria/tests/test_jornadas_motor.py
  motivo: "test_o_passo_3_sai_em_D5_mesmo_com_o_passo_2_atrasado_pela_regua planta `criada_em` das duas inscrições concorrentes e afirma qual delas levou a vaga do dia; sem o plantio a ordem sai do relógio real e o cenário deixa de ser um cenário. O teste irmão test_a_ordem_da_varredura_e_a_da_regua_e_nao_uma_copia prende a ordem a uma fonte só."
sinal:
  - "assert 'enviada' == 'barrada_pela_regua'"
  - teste de desempate que não escreve o campo do desempate
  - "auto_now_add" num campo usado por `order_by`
---

# O cenário que não planta a ordem está testando a ordem em que você escreveu o teste

**Sintoma.** Você escreveu um cenário de disputa (duas linhas competindo por um
recurso que só uma leva), a regra de desempate está implementada e correta, e o
teste falha dizendo o contrário do que você esperava:

```
assert barrada.resultado == "barrada_pela_regua"
E  AssertionError: assert 'enviada' == 'barrada_pela_regua'
```

A leitura natural é "o desempate está quebrado". Ele não está: **quem perdeu foi
a linha que você chamou de vencedora.**

**Causa.** O critério de desempate era `criada_em`, e `criada_em` é
`auto_now_add` — o relógio REAL do momento em que o teste criou o objeto. As duas
linhas nasceram com milissegundos de diferença, na ordem em que aparecem no
código do teste. Ou seja: o cenário não declarou quem era mais antiga; ele
herdou essa informação da ordem das suas próprias instruções.

Isso é pior do que um teste frágil, e por dois motivos:

1. **Ele passa ou falha por acaso.** Inverta duas linhas do arranjo, ou deixe uma
   criação a mais entrar no meio, e o veredito muda sem que o código sob teste
   tenha mudado.
2. **Quando falha, ele acusa o código.** O vermelho aponta para a implementação
   do desempate, que está certa, e o tempo vai embora procurando defeito onde não
   há. Foi exatamente o que aconteceu aqui.

**Solução — plante o campo do desempate, sempre, e no mesmo lugar onde você
declara quem deve ganhar.**

```python
outra = motor.inscrever(...)          # a que deve levar a vaga
minha = motor.inscrever(...)
# `criada_em` é auto_now_add: o único jeito de plantar a idade é `update()`,
# e sem isto a ordem sairia do relógio real de criação dos objetos no teste.
Inscricao.objects.filter(pk=outra.pk).update(criada_em=quando(15, 9))
Inscricao.objects.filter(pk=minha.pk).update(criada_em=quando(15, 10))
```

E **afirme quem ganhou**, não só quem perdeu: `assert
Entrega.objects.get(inscricao=outra).resultado == "enviada"` ao lado do
`barrada_pela_regua` do outro. Sem as duas asserções, o cenário fica verde também
num mundo em que ninguém recebeu nada.

**A regra curta:** se o código sob teste tem uma ordem DETERMINÍSTICA, o cenário
tem de escrever as chaves dessa ordem. Um desempate que o teste não planta é um
desempate que o teste não mede — e o pior é que ele parece medir.

**Onde isto vale além do `criada_em`:** qualquer `order_by` sobre campo
automático (`auto_now_add`, `auto_now`, `id` sequencial), qualquer fila por
antiguidade, qualquer "o primeiro que chegar leva". A fila de pouso deste próprio
projeto atende por antiguidade, e a mesma armadilha esperaria um teste dela.

**Parente de `armadilhas/267`:** lá o cenário não tinha o caso que o filtro
exclui; aqui o cenário não tem a ORDEM que a regra usa. Nos dois, o teste
descreve a regra certa e não a exercita.

**Origem:** TAR-073, o motor das jornadas
(`services/mensageria/apps/jornadas/motor.py`).
