from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('paginas', '0004_experimento_e_variante')]
    operations = [migrations.CreateModel(name='BancaRegistro', fields=[
        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        ('rodada', models.CharField(max_length=100, unique=True)),
        ('assinatura', models.CharField(max_length=64, blank=True)),
        ('completa', models.BooleanField(default=False)),
        ('exigida', models.BooleanField(default=True)),
        ('rastreio', models.JSONField(default=dict)),
        ('criada_em', models.DateTimeField(auto_now_add=True)),
        ('site', models.ForeignKey(to='sites.site', on_delete=django.db.models.deletion.PROTECT)),
        ('page', models.ForeignKey(to='paginas.page', null=True, on_delete=django.db.models.deletion.PROTECT)),
    ])]
