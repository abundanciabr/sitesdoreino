from django.db import migrations, models
class Migration(migrations.Migration):
    dependencies = [('atendimento','0003_gestao')]
    operations = [
        migrations.AddField(model_name='conversa',name='interesse',field=models.JSONField(default=dict,blank=True)),
        migrations.CreateModel(name='AgendaDoProduto',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('site_id',models.CharField(max_length=100)),
            ('produto_id',models.CharField(max_length=100)),
            ('produto_nome',models.CharField(max_length=255)),
            ('inicio',models.DateTimeField(null=True,blank=True)),
            ('detalhes',models.TextField(blank=True)),
            ('atualizado_por',models.CharField(max_length=160,blank=True)),
            ('atualizado_em',models.DateTimeField(auto_now=True)),
        ],options={'db_table':'atendimento_agenda_produto'}),
        migrations.AddConstraint(model_name='agendadoproduto',constraint=models.UniqueConstraint(fields=['site_id','produto_id'],name='suporte_agenda_produto_unica')),
    ]
