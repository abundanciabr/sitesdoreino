import json
from pathlib import Path
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.cursos.models import Base3D, Atividade3D

class Command(BaseCommand):
    help='Acrescenta os modelos do sandbox às práticas existentes, preservando projetos e configurações.'
    def handle(self, *args, **options):
        catalog=json.loads((Path(__file__).resolve().parents[4]/'static/praticas-3d/catalogo.json').read_text(encoding='utf8'))
        keys=[f"{m['id']}@{m['versao']}" for m in catalog]
        with transaction.atomic():
            for m in catalog:
                Base3D.objects.get_or_create(chave=m['id'],versao=m['versao'],defaults={'dados':m})
            for a in Atividade3D.objects.select_for_update().filter(grupo__in=['desafio-item-original','primeiros-dolares-experiencia']):
                cfg=dict(a.configuracao)
                cfg['modelos']=list(dict.fromkeys(cfg.get('modelos',[])+keys))
                a.configuracao=cfg;a.save(update_fields=['configuracao'])
        self.stdout.write(f'{len(catalog)} bases disponíveis; projetos anteriores preservados.')
