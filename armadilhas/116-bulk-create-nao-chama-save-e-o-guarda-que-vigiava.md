# `bulk_create` não chama `save()` — e o guarda que vigiava o `save()` vira decoração sem ficar vermelho

**Sintoma:** existe um teste-guarda que prova uma regra interceptando
`Model.save` — por `monkeypatch`, por sinal `pre_save`, ou por sobrescrita do
método. Alguém troca a escrita de um laço de `Model.objects.create()` por um
`Model.objects.bulk_create([...])`, por desempenho, e **o guarda continua
verde**: ele não é chamado nem uma vez, e "nunca disparou" é indistinguível de
"disparou e aprovou".

**Causa:** está na cara, na docstring do próprio Django (medido em 5.1.4,
`QuerySet.bulk_create`):

> *"Insert each of the instances into the database. **Do \*not\* call save() on
> each of the instances, do not send any pre/post_save signals**, and do not set
> the primary key attribute if it is an autoincrement field…"*

Conferido no código: `'.save(' in inspect.getsource(QuerySet.bulk_create)` →
`False`. O `bulk_create` monta o `INSERT` direto pelo compilador de SQL.

Ou seja, **toda** garantia pendurada em `save()` desaparece quando a escrita vira
lote: validação no `save()`, carimbo de auditoria, sinal, contador, e — o caso que
importa aqui — o **teste** que vigiava qualquer uma dessas coisas.

**Por que isto é da família do falso-verde e não um mero "pegadinha de API":** o
guarda não some do relatório. Ele continua lá, verde, com nome de garantia. A
suíte inteira segue passando. A regra que ele protegia é que deixou de ser
verificada — e não há linha vermelha em lugar nenhum apontando o momento em que
isso aconteceu.

**Este projeto teve sorte da primeira vez.** No EVO-42, a troca para `bulk_create`
fez o guarda que interceptava `Aviso.save` reprovar **alto**, porque ele estava
escrito para exigir a chamada. Se estivesse escrito ao contrário — *"nenhuma
escrita fora da transação"*, verificando que o patch **não** foi acionado
indevidamente — teria ficado verde para sempre, sem nunca disparar.

**Solução — duas, e a segunda é a que dá sono tranquilo:**

1. **Ao trocar `create()` por `bulk_create()`, procure quem observa o `save()`**
   daquele model antes de commitar: `grep -rn "save" tests/ | grep <Model>`,
   sinais registrados, e validação dentro do próprio `save()`. Se a regra
   precisava valer, ela agora precisa de outro lugar — a transação, uma
   constraint no banco, ou uma trigger.
2. **Prefira guardas que meçam o EFEITO, não a chamada.** Contar as linhas que
   apareceram na tabela, ou afirmar o estado depois do rollback, sobrevive a
   qualquer troca de mecanismo de escrita. Guarda amarrado ao *método* mede a
   implementação de hoje; guarda amarrado ao *resultado* mede a promessa.

**Regra que generaliza, e vale muito além do Django:** todo guarda que espiona um
ponto de passagem (método, sinal, hook, middleware) carrega a premissa não escrita
de que aquele ponto **continua sendo passado**. Quando a premissa cai, o guarda
não reprova — ele emudece. Ao escrever esse tipo de teste, escreva junto o caso
que prova que ele **é** chamado; sem isso, você não consegue distinguir "aprovou"
de "não rodou".

**Origem:** EVO-42 da Caixa de Sugestões, 25/08/2026, ao trocar um `create()` por
pessoa pelo `bulk_create` do leque de avisos (o número de consultas precisava
parar de crescer com a plateia). Ver também `armadilhas/115`, achada no mesmo
despacho.
