"""Solicita estorno da cobrança que aprovou uma intent."""

from __future__ import annotations

from uuid import UUID

from django.core.management.base import BaseCommand, CommandError, CommandParser

from pagamentos.core.estorno import estornar
from pagamentos.core.models import Intent, PaymentAttempt


class Command(BaseCommand):
    help = "Solicita uma vez o estorno da tentativa aprovada; confirmação vem da consulta."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("intent_id", type=UUID)

    def handle(self, *args: object, **options: object) -> None:
        intent_id = options["intent_id"]
        intent = Intent.objects.filter(pk=intent_id).first()
        if intent is None or intent.status != "approved":
            raise CommandError("Intent não encontrada ou sem pagamento aprovado.")
        tentativa = PaymentAttempt.objects.filter(intent=intent, state="approved").first()
        if tentativa is None:
            raise CommandError("Intent sem tentativa aprovada para devolver.")
        try:
            resultado = estornar(tentativa, "devolucao_da_intent")
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            f"Estorno da intent {intent.pk}: {resultado.estorno_estado}. "
            "A confirmação será feita por consulta ao provedor."
        )
