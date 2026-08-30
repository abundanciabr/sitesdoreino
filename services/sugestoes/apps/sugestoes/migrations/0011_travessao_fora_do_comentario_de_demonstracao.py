"""O TRAVESSÃO SAI DO COMENTÁRIO DE DEMONSTRAÇÃO QUE JÁ ESTÁ NO BANCO.

Mesma causa da `forum/0003`, e mesma decisão do mantenedor em 30/08/2026
(`CLAUDE.md`, "Nenhum texto publicado sai com travessão").

O `semear_demo` rodou em produção em 29/08/2026 às 23:50 (workflow
`semear-demo-caixa`, run verde). O texto-fonte foi corrigido no PR #607 — mas o
comentário já estava gravado, e é ele que o aluno lê no quadro da Caixa.
Corrigir a receita não muda o bolo que já foi assado.

Por que não `semear_demo --remover` e semear de novo: remover apaga também os
VOTOS e as reações que pessoas de verdade tenham deixado nas ideias de vitrine
desde ontem. Trocar uma frase não vale perder participação real. Um `UPDATE`
casando o texto exato é a operação mínima que resolve.

Por que casa o texto inteiro: se alguém já reescreveu este comentário, a
migração não encontra nada e não faz nada. É a mesma trava da `forum/0003`.
"""

from django.db import migrations

ANTES = (
    "Se der pra separar preço de UGC e preço de encomenda, melhor "
    "ainda — são mercados bem diferentes."
)
DEPOIS = (
    "Se der pra separar preço de UGC e preço de encomenda, melhor "
    "ainda: são mercados bem diferentes."
)


def tirar_o_travessao(apps, schema_editor):
    Comentario = apps.get_model("sugestoes", "Comentario")
    Comentario.objects.filter(texto=ANTES).update(texto=DEPOIS)


def nao_devolve(apps, schema_editor):
    """Descer esta migração NÃO recoloca o travessão. Ver `forum/0003`."""


class Migration(migrations.Migration):
    dependencies = [("sugestoes", "0010_apagamento")]

    operations = [migrations.RunPython(tirar_o_travessao, nao_devolve)]
