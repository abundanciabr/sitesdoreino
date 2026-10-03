from django.db import migrations, models
import django.db.models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(name="ConfiguracaoWhatsApp", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("site_id", models.CharField(max_length=100, unique=True)),
            ("instancia", models.CharField(max_length=100, unique=True)),
            ("transporte", models.CharField(default="WHATSAPP-BAILEYS", max_length=30)),
            ("ativo", models.BooleanField(default=False)),
            ("atualizado_em", models.DateTimeField(auto_now=True)),
        ]),
        migrations.CreateModel(name="MensagemWhatsApp", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("site_id", models.CharField(max_length=100)),
            ("instancia", models.CharField(blank=True, max_length=100)),
            ("origem", models.CharField(max_length=40)),
            ("referencia", models.CharField(max_length=160)),
            ("destinatario", models.CharField(max_length=20)),
            ("corpo", models.TextField()),
            ("status", models.CharField(choices=[(x,x) for x in ("desconhecido", "aceito", "enviado", "entregue", "lido", "falhou")], default="desconhecido", max_length=20)),
            ("provider_id", models.CharField(blank=True, max_length=160)),
            ("erro", models.CharField(blank=True, max_length=300)),
            ("tentativas", models.PositiveIntegerField(default=0)),
            ("criado_em", models.DateTimeField(auto_now_add=True)),
            ("atualizado_em", models.DateTimeField(auto_now=True)),
        ]),
        migrations.AddConstraint(model_name="mensagemwhatsapp", constraint=models.UniqueConstraint(fields=("site_id", "origem", "referencia"), name="uniq_wa_origem_site_ref")),
        migrations.AddConstraint(model_name="mensagemwhatsapp", constraint=models.UniqueConstraint(condition=~django.db.models.Q(provider_id=""), fields=("instancia", "provider_id"), name="uniq_wa_instancia_provider")),
        migrations.CreateModel(name="EstadoDeProvedor", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("instancia", models.CharField(max_length=100)),
            ("provider_id", models.CharField(max_length=160)),
            ("status", models.CharField(max_length=20)),
            ("atualizado_em", models.DateTimeField(auto_now=True)),
        ]),
        migrations.AddConstraint(model_name="estadodeprovedor", constraint=models.UniqueConstraint(fields=("instancia", "provider_id"), name="uniq_wa_retorno_instancia_id")),
    ]
