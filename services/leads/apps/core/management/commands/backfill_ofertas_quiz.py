"""Abre a oportunidade de venda de cada contato do quiz já guardado, sem remover registros."""

from django.core.management.base import BaseCommand

from apps.core.contatos import contatos_dos_quizzes
from apps.core.models import TimelineEvent
from apps.core.oferta import FONTE, abrir_oferta_do_quiz, avancar_ofertas_com_pedido


class Command(BaseCommand):
    help = "Cria uma oportunidade de venda para cada contato vindo dos quizzes"

    def add_arguments(self, parser):
        parser.add_argument("--site-id", default="")

    def handle(self, *args, **options):
        contatos = contatos_dos_quizzes()
        if options["site_id"]:
            contatos = contatos.filter(site_id=options["site_id"])
        antes = sum(c.oportunidades.filter(fonte_tipo=FONTE).count() for c in contatos)
        quizzes = TimelineEvent.objects.select_related("lead").filter(
            event="quiz.completado", lead__in=contatos
        ).order_by("occurred_at", "id")
        for evento in quizzes.iterator():
            oportunidade = abrir_oferta_do_quiz(
                evento.lead, evento.payload or {}, evento.event_id or evento.id, evento
            )
            if oportunidade.encerrada:
                continue
            pedido = TimelineEvent.objects.filter(
                lead=evento.lead, event="pedido.criado", occurred_at__gte=evento.occurred_at
            ).order_by("occurred_at", "id").first()
            if pedido is not None:
                avancar_ofertas_com_pedido(
                    evento.lead, pedido.payload or {}, pedido.event_id or pedido.id
                )
        for contato in contatos.iterator():
            if contato.oportunidades.filter(fonte_tipo=FONTE).exists():
                continue
            origem = contato.source or ""
            slug = origem.split(":", 1)[1] if ":" in origem else ""
            abrir_oferta_do_quiz(contato, {"quiz_slug": slug}, f"captura:{contato.pk}")
        depois = sum(c.oportunidades.filter(fonte_tipo=FONTE).count() for c in contatos)
        self.stdout.write(f"Oportunidades de venda criadas: {depois - antes}")
