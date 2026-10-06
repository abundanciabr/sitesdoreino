import json
from pathlib import Path
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.cursos.models import Base3D, Atividade3D

class Command(BaseCommand):
    help='Disponibiliza as bases reconstruídas e conserva as versões dos itens já salvos.'
    def handle(self, *args, **options):
        catalog=json.loads((Path(__file__).resolve().parents[4]/'static/praticas-3d/catalogo.json').read_text(encoding='utf8'))
        assert len(catalog)==11 and all(m['versao']==2 for m in catalog)
        latest={m['id']:f"{m['id']}@{m['versao']}" for m in catalog}
        with transaction.atomic():
            for m in catalog:
                Base3D.objects.get_or_create(chave=m['id'],versao=m['versao'],defaults={'dados':m})
            for a in Atividade3D.objects.select_for_update().filter(grupo__in=['desafio-item-original','primeiros-dolares-experiencia']):
                cfg=dict(a.configuracao)
                cfg['modelos']=list(dict.fromkeys([latest.get(k.split('@')[0],k) for k in cfg.get('modelos',[])]+list(latest.values())))
                a.configuracao=cfg;a.save(update_fields=['configuracao'])
        self.stdout.write('11 bases reconstruídas disponíveis. Versões anteriores e personalizações conservadas.')
