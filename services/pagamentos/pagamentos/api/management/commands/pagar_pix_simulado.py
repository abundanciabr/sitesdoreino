"""Aprova exclusivamente um Pix simulado da Appmax no sandbox."""

from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser

from pagamentos.core.models import Intent, PaymentAttempt
from pagamentos.methods.pix.appmax import _registrar_fato
from pagamentos.core.tentativas import ResultadoDoProvedor, fechar_reconciliacao


class Command(BaseCommand):
    help = "Aprova o Pix simulado de um pedido somente no sandbox Appmax."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--pedido", required=True)

    def handle(self, *args: object, **options: object) -> None:
        if "sandboxappmax.com.br" not in settings.APPMAX_API_URL.lower():
            raise CommandError("Pix simulado só pode ser pago no sandbox.")
        pedido = str(options["pedido"])
        intent = (
            Intent.objects.filter(order_id=pedido, method="pix")
            .order_by("-created_at")
            .first()
        )
        if intent is None:
            raise CommandError("Pedido Pix não encontrado.")
        tentativa = (
            PaymentAttempt.objects.filter(intent=intent, provider="appmax")
            .order_by("-created_at")
            .first()
        )
        if tentativa is None or not tentativa.provider_reference_id.startswith("sim-"):
            raise CommandError("Pedido sem Pix simulado da Appmax.")
        if tentativa.state == "approved":
            self.stdout.write("Pix simulado já aprovado.")
            return
        if tentativa.state != "pending":
            raise CommandError("Pix simulado não está pendente.")
        resultado = ResultadoDoProvedor(
            aprovada=True,
            provider_reference_id=tentativa.provider_reference_id,
            external_order_id=tentativa.external_order_id,
            motivo="aprovado",
        )
        fechar_reconciliacao(
            tentativa, resultado=resultado, registrar_resultado=_registrar_fato
        )
        self.stdout.write("Pix simulado aprovado.")
