import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('quiz', '0012_captura_publicacao'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConsentimentoDoContato',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_id', models.UUIDField()),
                ('site_id', models.CharField(max_length=64)),
                ('telefone', models.CharField(blank=True, default='', max_length=32)),
                ('aceita_whatsapp', models.BooleanField(default=False)),
                ('texto_whatsapp', models.TextField(blank=True, default='')),
                ('versao_texto', models.CharField(blank=True, default='', max_length=32)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('quiz', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='consentimentos', to='quiz.quiz')),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('quiz', 'session_id'), name='consentimento_quiz_sessao_unico')],
            },
        ),
    ]
