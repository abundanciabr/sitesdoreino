from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone


def iniciar_canais(apps, schema_editor):
    apps.get_model('atendimento', 'Configuracao').objects.filter(canais_entrada_em__isnull=True).update(canais_entrada_em=timezone.now())


class Migration(migrations.Migration):
    dependencies = [('atendimento', '0007_conversa_arquivada_em')]
    operations = [
        migrations.AddField('configuracao', 'canais_entrada_em', models.DateTimeField(null=True, blank=True)),
        migrations.RunPython(iniciar_canais, migrations.RunPython.noop),
        migrations.AddField('conversa', 'canal', models.CharField(max_length=20, default='site')),
        migrations.AddField('conversa', 'origem_conversa', models.CharField(max_length=100, blank=True)),
        migrations.AddField('conversa', 'origem_lead', models.CharField(max_length=100, blank=True)),
        migrations.AddField('conversa', 'proximo_passo', models.TextField(blank=True)),
        migrations.AddField('conversa', 'passo_prazo', models.DateTimeField(null=True, blank=True)),
        migrations.AddField('conversa', 'passo_responsavel', models.CharField(max_length=100, blank=True)),
        migrations.AddField('conversa', 'passo_responsavel_nome', models.CharField(max_length=160, blank=True)),
        migrations.CreateModel(name='HistoricoDoPasso', fields=[
            ('id', models.BigAutoField(primary_key=True, serialize=False, auto_created=True, verbose_name='ID')),
            ('texto', models.TextField(blank=True)),
            ('prazo', models.DateTimeField(null=True, blank=True)),
            ('responsavel', models.CharField(max_length=100, blank=True)),
            ('responsavel_nome', models.CharField(max_length=160, blank=True)),
            ('por', models.CharField(max_length=100)),
            ('criada_em', models.DateTimeField(auto_now_add=True)),
            ('conversa', models.ForeignKey(to='atendimento.conversa', on_delete=django.db.models.deletion.PROTECT, related_name='passos')),
        ], options={'db_table': 'atendimento_acompanhamento'}),
    ]
