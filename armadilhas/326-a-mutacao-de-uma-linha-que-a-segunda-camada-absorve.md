---
schema_version: 2
armadilha: 326
estado: documentada
degrau: 6
confianca: alta
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: "nenhum portão sabe distinguir 'esta segunda camada é redundância morta' de 'esta segunda camada cobre uma corrida que nenhum teste sequencial encena' — a diferença mora fora do arquivo, na pergunta 'existe um segundo processo?'. O que existe é o rito da mutação deliberada (RITOS §2 peça 3), que ACHA o caso; este arquivo diz o que fazer quando ele acha, e por que a receita da 269 é a errada aqui."
sinal:
  - "AINDA VERDE .guarda cego."
  - "mutação de uma linha verde num filtro de consulta repetido dentro da trava"
  - "select_for_update seguido de uma reconferência do mesmo campo"
---

# A mutação de uma linha fica verde porque a SEGUNDA CAMADA absorve, e a receita de apagar a linha é a errada

**Sintoma.** Você provou treze guardas por mutação, e dois teimam em ficar
verdes. A saída do arredor diz, para os dois:

```
J10: a varredura passa a rever o que ja abriu     AINDA VERDE (guarda cego)  7 passed
J10: a varredura passa a rever a oferta ja fechada AINDA VERDE (guarda cego)  7 passed
```

A leitura natural é a pior possível, e ela tem até uma armadilha desta casa a
sustentá-la ([`269`](269-defesa-contra-caminho-que-nao-existe-mascara-a-mutacao.md)):
*"há duas coisas produzindo o mesmo resultado, a segunda é defesa contra um
caminho que não existe, apague-a"*. **Aqui, apagá-la é o erro.**

**Causa.** O código tem defesa em profundidade de propósito, e as duas camadas
dizem a mesma coisa por motivos diferentes:

```python
esperando = list(                                    # (1) o FILTRO da consulta
    Encomenda.objects.filter(site_id=site_id, status__in=ESTADOS_DA_ESPERA)
    .values_list("pk", flat=True)
)
for encomenda_id in esperando:
    with transaction.atomic():
        encomenda = Encomenda.objects.select_for_update().get(pk=encomenda_id)
        if encomenda.status not in ESTADOS_DA_ESPERA:  # (2) a RECONFERÊNCIA
            continue
```

- **(1) é o que o teste mede.** Rodar a passada duas vezes não reabre o que já
  abriu porque a segunda consulta nem devolve a linha.
- **(2) é o que a PRODUÇÃO precisa.** Ela cobre a encomenda que saiu da espera
  **entre a varredura e a trava**: outro processo do mesmo worker, um aceite do
  aluno, um gesto do plantão. Durante um deploy há dois workers de pé por alguns
  segundos, e isso não é hipótese.

Mutar (1) sozinho: (2) absorve, verde. Mutar (2) sozinho: (1) absorve, verde.
**Nenhuma mutação de UMA LINHA consegue ficar vermelha**, e o arredor de
mutação, que mede uma linha por vez, marca os dois como cegos.

A diferença para a `269` cabe numa pergunta: **o caminho de que a segunda camada
defende existe?** Na `269` a resposta era não, e um `grep` provava — a linha era
peso morto e saiu. Aqui a resposta é sim, e ela é a única coisa que separa um
`TransicaoProibida` de minuto em minuto no primeiro deploy com dois workers.

**Solução — mutar a REGRA, não a linha.**

O arredor de uma linha continua sendo o certo para o caso comum. Quando ele
acusar um "AINDA VERDE" num par assim, faça uma segunda rodada em que a mutação
derruba **as duas camadas de uma vez**: é a mudança semântica única que uma
sessão futura faria ao "simplificar", e é dela que o guarda tem de proteger.

```python
MUTACOES = [
    ("a regra 'so abre quem ainda espera' some das DUAS camadas", [
        ("status__in=ESTADOS_DA_ESPERA)", ').exclude(status="cancelada")'),
        ("if encomenda.status not in ESTADOS_DA_ESPERA:", "if False:"),
    ], [GUARDA]),
]
```

Em 04/09/2026, na célula `encomendas` (TAR-122), essa segunda rodada devolveu
**um vermelho e um verde**. O vermelho fechou o assunto. O verde era um buraco
de verdade no guarda: nenhum teste rodava o tique DUAS vezes depois de uma
oferta já ter expirado — todos paravam na primeira passada seguinte ao
vencimento. Sem a regra, a segunda passada tentaria fechar de novo uma oferta já
fechada, `Oferta.responder` recusaria, e o worker de um minuto morreria de
minuto em minuto, para sempre, com a suíte inteira verde. O guarda que faltava
tem seis linhas.

**A regra de bolso, e a ordem importa:**

1. Mutação de uma linha ficou verde? **Não apague nada ainda.**
2. Pergunte se existe uma segunda camada dizendo a mesma coisa. Se não existe, é
   a `267` (cenário pobre) ou a `277` (par verde escapando por outro caminho).
3. Se existe, pergunte **de que caminho ela defende**. Caminho imaginário: é a
   `269`, apague a linha. Caminho real que nenhum teste sequencial encena
   (corrida entre processos, `select_for_update`, retentativa de fila): mantenha
   as duas e **mute a regra inteira**.
4. Escreva no código, ao lado da segunda camada, que ela não fica vermelha num
   teste de um processo só. Sem essa frase, a próxima sessão refaz esta análise
   inteira — ou, pior, aplica a receita da `269` e apaga a linha.

**Onde isto já mordeu:** `services/encomendas/apps/encomendas/tique.py`, nos dois
gestos do tique de um minuto (expirar ofertas vencidas e abrir o que esperou
demais). Os dois têm hoje o comentário do passo 4, e o guarda novo está em
`tests/test_inv_j10_motor_idempotente.py::test_a_passada_seguinte_a_uma_expiracao_e_inerte`.
