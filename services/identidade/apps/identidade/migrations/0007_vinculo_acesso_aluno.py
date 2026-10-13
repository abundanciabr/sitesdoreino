from django.db import migrations, models
class Migration(migrations.Migration):
    dependencies = [("identidade", "0006_acesso_previa")]
    operations = [migrations.AddField(model_name="acessoprevia",name="vinculo_hash",field=models.CharField(max_length=64,blank=True,default=""))]
