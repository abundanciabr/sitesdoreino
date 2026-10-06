from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0044_acompanhamento_alunos')]
    operations = [
        migrations.CreateModel(name='VotoDaGaleria', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('pessoa_id', models.CharField(max_length=150)),
            ('imagem', models.SlugField(max_length=40)),
            ('ativo', models.BooleanField(default=True)),
            ('atualizado_em', models.DateTimeField(auto_now=True)),
        ], options={'db_table': 'core_votodagaleria', 'constraints': [models.UniqueConstraint(fields=('pessoa_id', 'imagem'), name='galeria_um_voto_por_aluno_imagem')]}),
        migrations.CreateModel(name='ComentarioDaGaleria', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('pessoa_id', models.CharField(max_length=150)),
            ('nome', models.CharField(max_length=250)),
            ('email', models.EmailField(max_length=254)),
            ('imagem', models.SlugField(max_length=40)),
            ('texto', models.TextField()),
            ('chave', models.UUIDField()),
            ('criado_em', models.DateTimeField(auto_now_add=True)),
        ], options={'db_table': 'core_comentariodagaleria', 'ordering': ['-criado_em', '-pk'], 'constraints': [models.UniqueConstraint(fields=('pessoa_id', 'chave'), name='galeria_comentario_idempotente')]}),
    ]
