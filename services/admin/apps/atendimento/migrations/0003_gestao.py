from django.db import migrations, models
class Migration(migrations.Migration):
    dependencies = [('atendimento','0002_conversa')]
    operations = [
        migrations.AddField(model_name='conversa',name='prioridade',field=models.CharField(max_length=10,choices=[('baixa','Baixa'),('normal','Normal'),('alta','Alta')],default='normal')),
        migrations.AddField(model_name='conversa',name='primeira_resposta_em',field=models.DateTimeField(null=True,blank=True)),
        migrations.AddField(model_name='conversa',name='encerrada_em',field=models.DateTimeField(null=True,blank=True)),
        migrations.AddField(model_name='conversa',name='rodada_iniciada_em',field=models.DateTimeField(null=True,blank=True)),
    ]
