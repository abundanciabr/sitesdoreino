"""O Crivo explicado do zero sai da pasta aberta e fica só para administradores.

Pedido do mantenedor em 21/09/2026, com estas palavras: "Só para admins".
O documento tinha nascido PÚBLICO no deploy do PR #1858 naquela mesma tarde,
e a decisão dele mudou depois de o ver no ar. Antes disso ele já tinha
lembrado a regra da casa: todo documento nasce privado.

**Por que é uma migração, e não uma edição no arquivo.** Desde 31/08/2026 o
texto dos documentos mora no BANCO, e a pasta `documentos/` é só a semente
(`DECISAO-o-editor-de-documentos.md`). Trocar `publico: true` por `false` no
`.md` corrige a semente para uma instalação nova e não encosta na linha que já
existe em produção: o deploy ficaria verde e a página continuaria aberta
(`armadilhas/253`). Quem muda o banco que existe é esta migração.

**O que ela faz, e só isto:** fecha o documento (`publico=False`). O texto
permanece como está: o pedido foi fechar, não reescrever.

**Sem o documento no banco, não faz nada.** É o banco de uma instalação nova
antes da `0021`, ou um banco em que ele apagou o documento de vez; falhar por
isso derrubaria a célula no `migrate` por um passo de conteúdo (H18).
"""

from django.db import migrations

NOME = "o-crivo-explicado-do-zero"


def fechar_o_crivo(apps, schema_editor):
    Documento = apps.get_model("core", "Documento")
    documento = Documento.objects.filter(nome=NOME).first()
    if documento is None:
        return
    if documento.publico:
        documento.publico = False
        documento.save(update_fields=["publico"])


def nao_reabre(apps, schema_editor):
    """Descer NÃO devolve o documento ao público.

    Um `migrate` para trás se faz às pressas, num rollback, sem ninguém lendo o
    código; reabrir aqui publicaria de novo um texto que o mantenedor mandou
    fechar. O reverso honesto é não fazer nada (a mesma escolha da `0008`).
    """


class Migration(migrations.Migration):
    dependencies = [("core", "0021_semear_o_crivo_explicado")]
    operations = [migrations.RunPython(fechar_o_crivo, nao_reabre)]
