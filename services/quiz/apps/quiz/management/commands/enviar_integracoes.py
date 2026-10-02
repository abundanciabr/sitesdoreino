"""Envia conclusões do quiz e saídas para a oferta a GA4, Meta, TikTok, Klaviyo e
ActiveCampaign. Serviço sem variável de ambiente fica "nao_configurado".

    python manage.py enviar_integracoes [--dry-run] [--servico meta] [--dias 7]
"""

import json

from django.core.management.base import BaseCommand, CommandError

from apps.quiz.integracoes import servico


class Command(BaseCommand):
    help = "Envia eventos recentes às integrações configuradas (idempotente)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--servico", choices=sorted(servico.ADAPTADORES))
        parser.add_argument("--dias", type=int, default=7)

    def handle(self, *args, **opcoes):
        so = opcoes["servico"]
        if opcoes["dias"] < 1:
            raise CommandError("--dias precisa ser >= 1")
        if opcoes["dry_run"]:
            total = 0
            for evento in servico.eventos_recentes(opcoes["dias"]):
                for item in servico.payloads_mascarados(evento, so=so):
                    self.stdout.write(json.dumps(item, ensure_ascii=False, default=str))
                    total += 1
            self.stdout.write(f"dry-run: {total} requisicoes, nada enviado")
            return
        contagem = servico.enviar_pendentes(dias=opcoes["dias"], so=so)
        for chave in sorted(contagem):
            self.stdout.write(f"{chave}: {contagem[chave]}")
        self.stdout.write("enviar_integracoes: fim")
