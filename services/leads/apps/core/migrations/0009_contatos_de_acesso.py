from django.db import migrations, models
from django.db.models import Q
import re

def copiar(apps, schema_editor):
    Lead = apps.get_model("core", "Lead")
    Evento = apps.get_model("core", "TimelineEvent")
    Contato = apps.get_model("core", "ContatoDeAcesso")
    db = schema_editor.connection.alias
    origem = r"^quiz($|[:-])"
    ids = Evento.objects.using(db).filter(Q(event__in=("quiz.completado", "quiz.captura_parcial", "aluno.matricula", "cadastro.site")) | Q(event="lead.upsert", payload__source__iregex=origem)).values("lead_id")
    contatos = Lead.objects.using(db).filter(Q(source__iregex=origem) | Q(pk__in=ids)).exclude(email="")
    for c in contatos.iterator():
        if re.search(r"(^|[^a-z0-9])(teste|test|sandbox)([^a-z0-9]|$)", c.name, re.I) or "sandbox" in c.source.lower() or c.email.lower().endswith(("@example.com", "@exemplo.test")):
            continue
        phone = re.sub(r"[^0-9]", "", c.phone)
        if len(phone) in (10,11): phone = "55"+phone
        if not re.fullmatch(r"[1-9][0-9]{9,14}", phone): phone = ""
        Contato.objects.using(db).get_or_create(id=c.pk, defaults={"site_id":c.site_id,"email":c.email.strip().lower(),"telefone":phone})

class Migration(migrations.Migration):
    dependencies = [("core", "0008_captura_contato_corrigido_e_acompanhamento")]
    operations = [migrations.CreateModel(name="ContatoDeAcesso", fields=[
        ("id", models.UUIDField(primary_key=True, editable=False, serialize=False)),
        ("site_id", models.CharField(max_length=100)), ("email", models.EmailField(max_length=254)),
        ("telefone", models.CharField(max_length=15, blank=True, default="")),
    ], options={"indexes":[models.Index(fields=["site_id","email"],name="crm_acesso_email"),models.Index(fields=["site_id","telefone"],name="crm_acesso_telefone")]}),
    migrations.RunPython(copiar, migrations.RunPython.noop)]
