# `bulk_create` também dispara `pre_save()` — e sobrescreve `auto_now_add` em silêncio, mesmo atribuído no construtor

**Sintoma:** você monta uma lista de objetos com um campo `auto_now_add=True`
deliberadamente atribuído a um valor do PASSADO (o caso comum: um backfill que
precisa preservar um timestamp histórico), chama
`Model.objects.bulk_create(objetos)` — e cada linha gravada no banco tem a
hora ATUAL, não o valor atribuído. Ler o objeto Python logo depois do
`bulk_create` também mostra "agora": não sobrou, em memória, nenhum jeito de
recuperar o valor original a partir do mesmo objeto.

Isso surpreende mesmo sabendo da `armadilhas/116` ("`bulk_create` não chama
`save()`") — porque a lição de lá não é "nada do mecanismo de `save()` roda",
e este é um mecanismo diferente do que ela cobre.

**Causa:** `armadilhas/116` fala de `Model.save()` e dos sinais
`pre_save`/`post_save` — `bulk_create` pula os dois. O que ela não cobre é um
TERCEIRO mecanismo: o compilador SQL do INSERT
(`django.db.models.sql.compiler.SQLInsertCompiler.pre_save_val`) chama
`field.pre_save(obj, add=True)` para CADA campo de CADA objeto, na hora de
montar os valores da instrução — é POR ISSO que `auto_now_add`/`auto_now`
continuam funcionando em `bulk_create` sem `Model.save()` (o caminho comum:
criar uma linha nova com timestamp automático). `DateTimeField.pre_save()`
faz `setattr(model_instance, self.attname, timezone.now())` — que
**sobrescreve em memória** o valor atribuído no construtor, antes mesmo de o
INSERT ser executado. Depois do `bulk_create`, tanto o banco quanto o objeto
Python em mãos mostram "agora": o valor original não está em lugar nenhum.

Em uma frase: `Model.save()`, os SINAIS e o `pre_save()` de cada campo são
TRÊS mecanismos distintos que um atalho de escrita pode ou não atravessar.
`bulk_create` pula os dois primeiros mas **executa** o terceiro — e é
exatamente esse terceiro que atropela um valor histórico explícito.

**Solução — duas passadas, nunca uma:**

1. `bulk_create(objetos)` — aceitando que todo campo `auto_now_add` vai
   nascer com "agora" (inevitável neste caminho). Guarde os valores REAIS que
   você queria numa lista PARALELA, nunca no próprio objeto (ele vai ser
   sobrescrito pelo passo acima).
2. Reatribua os valores guardados aos objetos (já com `pk` preenchido pelo
   `bulk_create`) e chame `Model.objects.bulk_update(objetos,
   ["campo_auto_now_add"])`. `bulk_update()` monta um `UPDATE ... CASE WHEN`
   via `QuerySet.update()` por baixo — e `QuerySet.update()` **nunca** chama
   `field.pre_save()`, só usa o valor Python que o objeto carrega no momento
   da chamada. É a versão em LOTE do truque que `Voto.criado_em` já tinha
   ensinado nesta plataforma para uma linha só
   (`Model.objects.filter(pk=x).update(campo=valor)`,
   `services/sugestoes/LICOES.md`, "`agora` virou PARÂMETRO") — e a razão de
   funcionar é a mesma: `.update()`/`bulk_update()` são o único caminho de
   escrita comum do Django que pula os TRÊS mecanismos (save, sinais e
   `pre_save()` por campo), e por isso é o único que aceita valor arbitrário
   num campo `auto_now`/`auto_now_add`.

```python
objetos = [Modelo(..., quando_auto_now_add=valor_historico) for valor_historico in valores]
objetos_paralelos = list(zip(objetos, valores))  # sobrevive à sobrescrita

Modelo.objects.bulk_create(objetos)  # aqui `quando_auto_now_add` já virou "agora"

for objeto, valor_historico in objetos_paralelos:
    objeto.quando_auto_now_add = valor_historico
Modelo.objects.bulk_update(objetos, ["quando_auto_now_add"])  # grava o valor de verdade
```

**Como confirmar sem depender de memória:** escreva o teste ANTES — crie um
registro com o campo empurrado bem para o passado (via `.update()`, pela
mesma técnica), rode o backfill, e afirme que o valor sobrevive. Sem o passo
2 acima, o teste falha mostrando "agora" em vez do valor histórico — é a
evidência vermelho→verde que prova que a pegadinha é real e que a correção
morde.

**Origem:** despacho `agent/sugestoes/avisos-para-notificacoes`, 27/08/2026 —
migration de backfill (`0008_backfill_cartas_dos_avisos_existentes.py`) que
precisava preservar `Aviso.criado_em` em `OutboxEvent.occurred_at` (também
`auto_now_add=True`) para cartas retroativas de `notificacao.devida.v1`. Ver
também `armadilhas/116` (o mecanismo irmão: sinais e `save()`).
