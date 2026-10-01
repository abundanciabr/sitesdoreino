from preparar import _preservar_tabelas_migracoes, _preservar_tabelas_modelos, _reescrever


def test_migration_keeps_registry_api_and_old_table():
    source = """
from django.db import migrations, models

def seed(apps, schema_editor):
    Pessoa = apps.get_model('forum', 'Pessoa')
    return Pessoa.objects.count()

class Migration(migrations.Migration):
    dependencies = [('forum', '0001_initial')]
    operations = [migrations.CreateModel(
        name='Pessoa',
        fields=[('id', models.AutoField(primary_key=True))],
    )]
"""
    rewritten = _reescrever(source, "forum", {"forum", "core"}, {"settings"})
    rewritten = _preservar_tabelas_migracoes(rewritten, "forum")
    assert "apps.get_model('forum_forum', 'Pessoa')" in rewritten
    assert "modules.forum.apps.get_model" not in rewritten
    assert "('forum_forum', '0001_initial')" in rewritten
    assert "'db_table': 'forum_pessoa'" in rewritten
    compile(rewritten, "migration.py", "exec")


def test_model_keeps_existing_table_name():
    source = """
from django.db import models
class Pessoa(models.Model):
    nome = models.TextField()
"""
    rewritten = _preservar_tabelas_modelos(source, "forum")
    assert "db_table = 'forum_pessoa'" in rewritten
    compile(rewritten, "models.py", "exec")


def test_concrete_model_inheriting_abstract_base_keeps_old_table():
    source = """
from django.db import models
class Registro(models.Model):
    class Meta:
        abstract = True
class Historico(Registro):
    conteudo = models.TextField()
"""
    rewritten = _preservar_tabelas_modelos(source, "sugestoes")
    assert "db_table = 'sugestoes_historico'" in rewritten
    compile(rewritten, "models.py", "exec")
