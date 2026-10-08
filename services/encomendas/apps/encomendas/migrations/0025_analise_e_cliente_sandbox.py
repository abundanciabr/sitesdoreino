import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('encomendas', '0024_liberar_reservas_para_pix_manual')]
    operations = [
        migrations.AlterField(model_name='mensagemsandbox', name='papel', field=models.CharField(
            choices=[('aluno', 'Aluno'), ('equipe', 'Equipe'), ('ia', 'IA'), ('cliente', 'Cliente simulado (IA)')], max_length=8)),
        migrations.CreateModel(name='AnaliseArquivoSandbox', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('sha256', models.CharField(max_length=64)), ('chave_cache', models.CharField(max_length=64)),
            ('estado', models.CharField(default='na_fila', max_length=20)),
            ('resultado', models.JSONField(default=dict)), ('falha', models.TextField(blank=True)),
            ('atualizada_em', models.DateTimeField(auto_now=True)),
            ('arquivo', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='analise', to='encomendas.arquivosandbox')),
        ], options={'db_table': 'encomendas_analisearquivosandbox'}),
        migrations.CreateModel(name='AnaliseEntregaSandbox', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('estado', models.CharField(default='na_fila', max_length=20)), ('resultado', models.JSONField(default=dict)),
            ('falha', models.TextField(blank=True)), ('tentativas', models.PositiveIntegerField(default=0)),
            ('tentar_em', models.DateTimeField(null=True)), ('atualizada_em', models.DateTimeField(auto_now=True)),
            ('entrega', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='analise', to='encomendas.entregasandbox')),
        ], options={'db_table': 'encomendas_analiseentregasandbox'}),
        migrations.CreateModel(name='RespostaSandbox', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('origem', models.CharField(max_length=100)), ('papel', models.CharField(max_length=8)),
            ('estado', models.CharField(default='na_fila', max_length=20)), ('tentativas', models.PositiveIntegerField(default=0)),
            ('tentar_em', models.DateTimeField(null=True)), ('atualizada_em', models.DateTimeField(auto_now=True)),
            ('mensagem', models.OneToOneField(null=True, on_delete=django.db.models.deletion.PROTECT, to='encomendas.mensagemsandbox')),
            ('participacao', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='encomendas.participacaosandbox')),
        ], options={'db_table': 'encomendas_respostasandbox', 'constraints': [models.UniqueConstraint(
            fields=('participacao', 'origem', 'papel'), name='sb_resposta_origem_unica')]}),
    ]
