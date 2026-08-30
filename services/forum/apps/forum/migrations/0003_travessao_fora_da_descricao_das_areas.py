"""O TRAVESSÃO SAI DA DESCRIÇÃO QUE JÁ ESTÁ NO BANCO.

Decisão do mantenedor em 30/08/2026 (`CLAUDE.md`, "Nenhum texto publicado sai
com travessão"). A lei entrou, o portão entrou, e o texto-fonte de
`semear_areas.py` foi corrigido no PR #607 — **e nada mudou no site**.

O motivo é a mesma lição que a `0002` já pagou, e que a célula guardou no
`LICOES.md`: `semear_areas` é `get_or_create` pelo slug e **de propósito não
altera o que já existe**, para nunca pisar numa edição do mantenedor. As quatro
áreas nasceram em 28/08; desde então o comando não alcança nenhuma delas.
Corrigir a receita não muda o bolo que já foi assado.

Quem viu primeiro foi o mantenedor, olhando o fórum no ar. O teste não veria:
em banco de teste recém-criado este `UPDATE` não encontra linha nenhuma.

POR QUE ELE CASA O TEXTO INTEIRO ANTES DE TROCAR
------------------------------------------------
`filter(descricao=ANTES)` em vez de `filter(slug=...)`. Se alguém já tiver
reescrito a descrição — o mantenedor pela mão, ou um trabalho futuro —, a
migração não encontra nada e **não faz nada**. O pior desfecho possível aqui
seria uma migração de correção de texto sobrescrevendo texto melhor; casar o
valor exato é o que torna isso impossível, e não apenas improvável.
"""

from django.db import migrations

SLUG = "mostre-seu-trabalho"

ANTES = (
    "O que você está construindo. Modelo pela metade também conta — é vendo "
    "o meio do caminho que se aprende o caminho."
)
DEPOIS = (
    "O que você está construindo. Modelo pela metade também conta: é vendo "
    "o meio do caminho que se aprende o caminho."
)


def tirar_o_travessao(apps, schema_editor):
    Area = apps.get_model("forum", "Area")
    Area.objects.filter(slug=SLUG, descricao=ANTES).update(descricao=DEPOIS)


def nao_devolve(apps, schema_editor):
    """Descer esta migração NÃO recoloca o travessão no site.

    Um reverso que reintroduzisse o travessão faria um `migrate` para trás —
    coisa que se faz às pressas, num rollback, sem ninguém lendo o código —
    desobedecer a uma lei do projeto em silêncio. O reverso honesto é não
    fazer nada: o texto correto fica.
    """


class Migration(migrations.Migration):
    dependencies = [("forum", "0002_pagina_publica_so_a_escola_fala")]

    operations = [migrations.RunPython(tirar_o_travessao, nao_devolve)]
