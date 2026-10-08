from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("quiz", "0016_nps_revisao")]
    operations = [migrations.AddField(
        model_name="npstentativa", name="arquivada_em",
        field=models.DateTimeField(null=True, blank=True, db_index=True),
    )]
