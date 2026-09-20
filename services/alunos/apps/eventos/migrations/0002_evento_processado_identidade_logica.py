# A identidade do FATO entra na tabela de dedup (20/09/2026).
#
# As linhas que já existem foram gravadas quando só havia uma versão do
# contrato, e delas a célula guardou apenas o `event_id` — a identidade lógica
# daqueles fatos não está em lugar nenhum e não dá para inventá-la. Elas são
# preenchidas com o próprio `event_id`, que é único e nunca colide com uma
# identidade de verdade (estas têm a forma `evento|campo|campo`, com barras).
#
# A consequência é conhecida e aceita: um pagamento processado como v1 ANTES
# desta migração, chegando como v2 DEPOIS, passa pelo dedup. Quem segura esse
# caso é a idempotência de `matricular()` por `order_id`, que é a segunda
# tranca da célula — o efeito é lido, não recriado.
from django.db import migrations, models
from django.db.models.functions import Cast


def preencher_com_o_event_id(apps, schema_editor):
    # Um UPDATE só, e não um laço de `save()`: esta tabela cresce a cada evento
    # consumido desde agosto, e uma migração que percorre linha a linha segura
    # o deploy pelo tempo que a tabela tiver.
    EventoProcessado = apps.get_model("eventos", "EventoProcessado")
    EventoProcessado.objects.filter(identidade_logica="").update(
        identidade_logica=Cast("event_id", models.CharField(max_length=255))
    )


class Migration(migrations.Migration):

    dependencies = [("eventos", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="eventoprocessado",
            name="identidade_logica",
            field=models.CharField(default="", max_length=255),
            preserve_default=False,
        ),
        migrations.RunPython(preencher_com_o_event_id, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="eventoprocessado",
            name="identidade_logica",
            field=models.CharField(max_length=255, unique=True),
        ),
    ]
