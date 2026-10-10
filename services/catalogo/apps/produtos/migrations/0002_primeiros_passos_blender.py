"""Nome e investimento solicitados pelo mantenedor para o mesmo produto."""
from django.db import migrations

def atualizar_produto(apps, schema_editor):
    Product=apps.get_model('produtos','Product')
    Offer=apps.get_model('ofertas','Offer')
    alias=schema_editor.connection.alias
    offer=Offer.objects.using(alias).filter(site__host='meshcraft.top',slug='desafio-como-ganhar-em-dolar-com-roblox').first()
    if offer is None:
        return
    Product.objects.using(alias).filter(pk=offer.product_id).update(name='Curso Primeiros Passos com 3d no Blender',price_cents=2700)
    if offer.price_cents != 2700:
        offer.price_cents=2700
        offer.version+=1
        offer.save(using=alias,update_fields=['price_cents','version'])

class Migration(migrations.Migration):
    dependencies=[('produtos','0001_initial'),('ofertas','0001_initial')]
    operations=[migrations.RunPython(atualizar_produto,migrations.RunPython.noop)]
