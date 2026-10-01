"""O teto de gasto que o mantenedor autorizou para os robôs.

Na conversa de 01/10/2026 a pergunta foi quanto os robôs podem gastar com o
modelo por mês, e a resposta dele foi "Até US$ 10/mês (Recomendado)". Esta é
a ÚNICA autorização de gasto dos robôs; outra só entra pela palavra dele.
"""

from decimal import Decimal

from django.db import migrations

FONTE = (
    "Conversa de 01/10/2026 com o mantenedor, pergunta sobre o gasto dos "
    "robôs com a OpenAI: 'Até US$ 10/mês (Recomendado)'. Luna na conversa, "
    "Sol no panorama; o robô para ao chegar no teto."
)


def autorizar(apps, schema_editor):
    Autorizacao = apps.get_model("agentes", "AutorizacaoDeGasto")
    if not Autorizacao.objects.exists():
        Autorizacao.objects.create(
            descricao="Robôs pessoais: modelos da OpenAI",
            teto_mensal_usd=Decimal("10.00"),
            fonte=FONTE,
            ativa=True,
        )


class Migration(migrations.Migration):
    dependencies = [("agentes", "0001_inicial")]

    operations = [migrations.RunPython(autorizar, migrations.RunPython.noop)]
