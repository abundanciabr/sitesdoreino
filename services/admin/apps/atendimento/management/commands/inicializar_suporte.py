from django.core.management.base import BaseCommand
from apps.atendimento.service import config,reaproveitar_responsaveis


class Command(BaseCommand):
    def add_arguments(self,parser):
        parser.add_argument('--site',required=True)

    def handle(self,*args,**options):
        sid=options['site'];config(sid)
        total=reaproveitar_responsaveis(sid)
        self.stdout.write(f'Suporte configurado em modo assistido; {total} responsáveis encontrados nos cadastros existentes.')
