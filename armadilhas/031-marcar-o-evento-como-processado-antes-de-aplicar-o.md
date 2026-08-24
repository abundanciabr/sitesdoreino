<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §4 — Django e django-ninja
     ID historico: §4.12  ·  referencias antigas "ARMADILHAS §4.12" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 4.12 Marcar o evento como processado ANTES de aplicar o efeito descarta reentrega em silêncio

**Sintoma:** nenhum — e é esse o problema. Um pagamento aprovado não vira matrícula, uma
timeline fica com buraco, um e-mail de boas-vindas nunca sai. Não há erro, log nem
alerta: a célula reporta "evento já processado" para um evento cujo efeito nunca
aconteceu.
**Causa:** a Receita R4 grava a linha de dedup (`EventoProcessado`) numa transação que
**commita**, e só então chama o handler:

```python
try:
    with transaction.atomic():
        EventoProcessado.objects.create(event_id=envelope["event_id"])
except IntegrityError:
    return
handlers[envelope["event"]](envelope["data"])   # ← FORA da transação acima
```

Basta o handler falhar por motivo transitório (deadlock, conexão caída, timeout num
pico) para o evento ficar marcado como visto. Toda reentrega futura — e o transporte é
at-least-once **de propósito** — cai no `except IntegrityError` e é descartada.
**Solução:** duas transações aninhadas, com o handler dentro do `atomic` externo mas
**FORA do `try`**:

```python
with transaction.atomic():          # (1) registro e efeito: vivem ou morrem juntos
    try:
        with transaction.atomic():  # (2) savepoint: SÓ o create
            EventoProcessado.objects.create(event_id=envelope["event_id"])
    except IntegrityError:
        return                      # já processado de verdade
    handlers[envelope["event"]](envelope["data"])
```

**A armadilha da correção óbvia:** mover o handler para dentro do `try` conserta a
atomicidade e planta um bug novo — um `IntegrityError` vindo do handler (qualquer
constraint sem relação com `event_id`) passa a ser lido como "já processado". Não é
hipótese: em `leads` é `uniq_lead_site_email`, disputada por `get_or_create()`; em
`mensageria` é `uniq_envio_por_order_tipo_canal`. É o mesmo bug de antes, só que mais
difícil de enxergar — o savepoint interno existe para que o `except` enxergue apenas o
`create()`.

**É falha da receita, e agora há contagem em vez de suspeita.** Das quatro células que
consomem eventos, **três** tinham o bug: `alunos` (PR #43), `leads` (#46) e `mensageria`
(#47). A quarta, `checkout`, escapou por **não usar a tabela de dedup** — o handler dela
é idempotente por construção (`UPDATE ... WHERE status=aguardando_pagamento`), então não
existe a fenda entre marcar e aplicar. O lado **produtor** está íntegro: o relay de
`pagamentos` publica no Redis **antes** de marcar `published_at`, então falha ali
republica em vez de perder.

**Variante mais afiada, em `mensageria`:** lá o caminho de dedup chamava `r.xack(...)`
antes do `continue`, então a reentrega descartada era **removida do stream** — não
sobrava nem a mensagem na PEL para recuperar depois. Com o fix o `xack` volta a ser
seguro, porque "já processado" passou a significar o que diz.

**Relação com o §4.8:** aquele item cobre **metade** disto — a necessidade do savepoint
para a transação não ficar abortada. Esta é a outra metade: por que existe uma transação
**externa** em volta, e por que o handler fica fora do `try`. Os dois `atomic` parecem
redundantes e não são; remover qualquer um reabre um bug silencioso. Escreva o comentário
no código dizendo isso — o próximo agente vai olhar e achar que é gordura.

**O que este item NÃO resolve:** devolver a *possibilidade* de reentregar não é
reentregar. A mensagem que fez o handler estourar fica na PEL do grupo e ninguém a
reclama — medido pelo despacho infra/consumers e registrado no §9, com a peça que falta
(`XAUTOCLAIM` ou releitura do próprio PEL) nomeada lá. Não abra linha nova para isso.

**O que ainda não foi feito:** a receita R4 em `CAMINHO-DOURADO.md` continua mostrando a
forma errada. Arquivo sob CODEOWNERS ⇒ decisão do mantenedor, com Rito — não de sessão.
Enquanto isso, **qualquer célula nova que copiar R4 nasce com este bug**.
**Origem:** varredura das quatro células consumidoras (21/08/2026), depois de o bug
aparecer em `alunos` e ser reencontrado em `leads` e `mensageria`.
