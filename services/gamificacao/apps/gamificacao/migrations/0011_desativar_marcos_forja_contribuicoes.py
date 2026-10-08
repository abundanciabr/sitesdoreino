from django.db import migrations
from django.db.models import Q, F

def desativar(apps, schema_editor):
    db = schema_editor.connection.alias
    Conquista = apps.get_model("gamificacao", "ConquistaDefinicao")
    filtro = (Q(classe="marco") | Q(slug__in=["dez-forjas", "primeira-contribuicao", "portfolio-publicado", "primeiro-cliente", "primeiros-dolares"])
              | Q(criterio__tipo__in=["forjas_seladas", "contribuicoes_aceitas"]))
    Conquista.objects.using(db).filter(filtro, ativa=True).update(ativa=False, versao=F("versao")+1)
    apps.get_model("gamificacao", "ItemCosmetico").objects.using(db).filter(slug="titulo-forjador").update(ativa=False)
    apps.get_model("gamificacao", "TarefaComunitaria").objects.using(db).filter(aberta=True).update(aberta=False)

class Migration(migrations.Migration):
    dependencies = [("gamificacao", "0010_gesto_da_equipe_sem_motivo_obrigatorio")]
    operations = [migrations.RunPython(desativar, migrations.RunPython.noop)]
