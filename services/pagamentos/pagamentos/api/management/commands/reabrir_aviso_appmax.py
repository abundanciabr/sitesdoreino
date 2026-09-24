"""Reabre um aviso da fila morta após correção da causa."""

from typing import cast

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction

from pagamentos.core.models import AppmaxWebhookInbox


class Command(BaseCommand):
    help = "Reabre um aviso Appmax da fila morta para nova consulta ao provedor."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("aviso_id", type=int)

    def handle(self, *args: object, **options: object) -> None:
        aviso_id = cast(int, options["aviso_id"])
        with transaction.atomic():
            aviso = (
                AppmaxWebhookInbox.objects.select_for_update()
                .filter(pk=aviso_id)
                .first()
            )
            if aviso is None or aviso.dead_lettered_at is None:
                raise CommandError(
                    "Aviso não encontrado na fila morta. Confira o ID e consulte as métricas."
                )
            aviso.dead_lettered_at = None
            aviso.failed_attempts = 0
            aviso.next_retry_at = None
            aviso.last_error = ""
            aviso.operational_action = ""
            aviso.save(
                update_fields=[
                    "dead_lettered_at",
                    "failed_attempts",
                    "next_retry_at",
                    "last_error",
                    "operational_action",
                ]
            )
        self.stdout.write(f"Aviso {aviso_id} reaberto para consulta Appmax.")
