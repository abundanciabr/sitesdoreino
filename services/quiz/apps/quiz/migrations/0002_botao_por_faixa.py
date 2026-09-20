# O botão da tela de resultado, por faixa (gerada pelo Django 5.1.4).
#
# Expand-and-Contract: os dois campos nascem opcionais, com default vazio, e a
# restrição aceita "os dois vazios". Faixa já plantada continua válida e a tela
# apenas não mostra botão — o código anterior segue de pé contra o schema novo,
# que é o que a migração no boot (Dockerfile) exige.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("quiz", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="resultband",
            name="botao_destino",
            field=models.CharField(blank=True, default="", max_length=500),
        ),
        migrations.AddField(
            model_name="resultband",
            name="botao_rotulo",
            field=models.CharField(blank=True, default="", max_length=80),
        ),
        migrations.AddConstraint(
            model_name="resultband",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("botao_destino", ""), ("botao_rotulo", "")),
                    models.Q(
                        models.Q(("botao_destino", ""), _negated=True),
                        models.Q(("botao_rotulo", ""), _negated=True),
                    ),
                    _connector="OR",
                ),
                name="band_botao_destino_e_rotulo_juntos",
            ),
        ),
    ]
