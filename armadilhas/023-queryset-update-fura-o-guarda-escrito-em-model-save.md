<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §4 — Django e django-ninja
     ID historico: §4.4  ·  referencias antigas "ARMADILHAS §4.4" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 4.4 `QuerySet.update()` fura o guarda escrito em `Model.save()`

**Sintoma:** o teste de imutabilidade passa por `save()` mas o campo muda via
`Model.objects.filter(...).update(campo=...)`.
**Causa:** `QuerySet.update()` **não passa** por `Model.save()`.
**Solução:** guarda de imutabilidade precisa existir nos **dois** caminhos — override
de `save()` **e** de `update()` num `QuerySet` customizado. (O `save()` interno do
Django usa `_update()`, com underscore, então não entra em laço com o seu override.)
**Origem:** Prompt 4 (checkout, INV-P1).
