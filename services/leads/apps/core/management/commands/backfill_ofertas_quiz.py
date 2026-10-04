"""Abre a oportunidade de venda de cada contato do quiz já guardado, sem remover registros."""

from django.core.management.base import BaseCommand

from apps.core.compras import reconstruir_compras
from apps.core.contatos import contatos_dos_quizzes
from apps.core.models import TimelineEvent
from apps.core.oferta import FONTE, abrir_oferta_do_quiz


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
            abrir_oferta_do_quiz(
                evento.lead, evento.payload or {}, evento.event_id or evento.id, evento
            )
        for contato in contatos.iterator():
            if contato.oportunidades.filter(fonte_tipo=FONTE).exists():
                continue
            origem = contato.source or ""
            slug = origem.split(":", 1)[1] if ":" in origem else ""
            abrir_oferta_do_quiz(
                contato, {"quiz_slug": slug}, f"captura:{contato.pk}", origem="captura"
            )
        # Pedidos e pagamentos movem só a oferta da compra correspondente.
        reconstruir_compras(TimelineEvent.objects.filter(lead__in=contatos))
        depois = sum(c.oportunidades.filter(fonte_tipo=FONTE).count() for c in contatos)
        self.stdout.write(f"Oportunidades de venda criadas: {depois - antes}")
