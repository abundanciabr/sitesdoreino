# [INV-P11] `site_id` entra na IDENTIDADE do fato, não só na leitura da
# timeline. Sem isso, um aviso com o site errado (bug do publicador, ou
# mensagem injetada no stream) grava a identidade do fato verdadeiro sem
# produzir o efeito no site certo, e o aviso legítimo que chegasse depois é
# descartado como duplicado: a timeline do site certo nunca recebe nada.
#
# Migration ADITIVA de propósito (não edita 0003): a tabela ainda não tem
# linha nenhuma em produção (PR ainda não integrado), então o default de
# `site_id` abaixo nunca precisa cobrir dado real — existe só para a operação
# de esquema em si.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_fatodepagamentoprocessado_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="fatodepagamentoprocessado",
            name="site_id",
            field=models.CharField(default="", max_length=100),
            preserve_default=False,
        ),
        migrations.RemoveConstraint(
            model_name="fatodepagamentoprocessado",
            name="uniq_fato_pagamento_por_evento",
        ),
        migrations.AddConstraint(
            model_name="fatodepagamentoprocessado",
            constraint=models.UniqueConstraint(
                fields=("evento", "site_id", "chave"),
                name="uniq_fato_pagamento_por_site",
            ),
        ),
    ]
