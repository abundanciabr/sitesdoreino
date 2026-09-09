"""A régua que protege a cota e a reputação do provedor de e-mail."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.utils import timezone

from .models import JanelaDeCapacidade

MAX_FALHAS_ATE_DISJUNTOR = 3
TEMPO_DO_DISJUNTOR = timedelta(minutes=5)
BACKOFF_BASE = 30
BACKOFF_MAXIMO = 15 * 60


class CapacidadeDoProvedor(RuntimeError):
    """O envio precisa esperar porque a capacidade está indisponível."""

    def __init__(self, motivo: str, atraso: float):
        super().__init__(motivo)
        self.atraso = max(1, int(atraso))


class CapacidadeNaoConfigurada(ImproperlyConfigured):
    """A conta do provedor ainda não informou seus limites contratados."""


@dataclass(frozen=True)
class ReservaDeEnvio:
    instante: datetime


def _jitter() -> float:
    return random.uniform(0, 5)


def atraso_com_backoff(tentativas: int) -> int:
    """Calcula backoff exponencial limitado, sempre com jitter."""

    base = min(BACKOFF_MAXIMO, BACKOFF_BASE * (2 ** max(0, tentativas - 1)))
    return int(base + _jitter())


def _segundos_ate(instante: datetime, agora: datetime) -> float:
    return max(1, (instante - agora).total_seconds())


def _limites_configurados() -> tuple[int, int]:
    minuto = settings.EMAIL_MAX_EMAILS_POR_MINUTO
    hora = settings.EMAIL_MAX_EMAILS_POR_HORA
    if minuto is None or hora is None:
        raise CapacidadeNaoConfigurada(
            "EMAIL_MAX_EMAILS_POR_MINUTO e EMAIL_MAX_EMAILS_POR_HORA ausentes; "
            "informe os limites contratados do provedor antes de enviar"
        )
    return minuto, hora


def reservar_envio(agora: datetime | None = None) -> ReservaDeEnvio:
    """Reserva uma vaga de e-mail sem permitir corrida entre trabalhadores."""

    limite_por_minuto, limite_por_hora = _limites_configurados()
    agora = agora or timezone.now()
    minuto = agora.replace(second=0, microsecond=0)
    hora = agora.replace(minute=0, second=0, microsecond=0)
    with transaction.atomic():
        estado, _ = JanelaDeCapacidade.objects.select_for_update().get_or_create(
            chave="email",
            defaults={
                "minuto_em": minuto,
                "hora_em": hora,
            },
        )
        if estado.minuto_em != minuto:
            estado.minuto_em = minuto
            estado.envios_no_minuto = 0
        if estado.hora_em != hora:
            estado.hora_em = hora
            estado.envios_na_hora = 0

        if estado.disjuntor_ate and estado.disjuntor_ate > agora:
            raise CapacidadeDoProvedor(
                "disjuntor do provedor aberto após falhas consecutivas",
                _segundos_ate(estado.disjuntor_ate, agora) + _jitter(),
            )
        if estado.envios_no_minuto >= limite_por_minuto:
            proximo = minuto + timedelta(minutes=1)
            raise CapacidadeDoProvedor(
                "teto de e-mails por minuto atingido",
                _segundos_ate(proximo, agora) + _jitter(),
            )
        if estado.envios_na_hora >= limite_por_hora:
            proximo = hora + timedelta(hours=1)
            raise CapacidadeDoProvedor(
                "teto de e-mails por hora atingido",
                _segundos_ate(proximo, agora) + _jitter(),
            )

        estado.envios_no_minuto += 1
        estado.envios_na_hora += 1
        estado.save()
    return ReservaDeEnvio(instante=agora)


def registrar_sucesso() -> None:
    """Fecha a sequência de falhas após uma entrega aceita."""

    JanelaDeCapacidade.objects.filter(chave="email").update(
        falhas_consecutivas=0,
        disjuntor_ate=None,
    )


def registrar_falha(agora: datetime | None = None) -> None:
    """Abre o disjuntor quando o provedor falha repetidamente."""

    agora = agora or timezone.now()
    with transaction.atomic():
        estado, _ = JanelaDeCapacidade.objects.select_for_update().get_or_create(
            chave="email",
            defaults={
                "minuto_em": agora.replace(second=0, microsecond=0),
                "hora_em": agora.replace(minute=0, second=0, microsecond=0),
            },
        )
        estado.falhas_consecutivas += 1
        if estado.falhas_consecutivas >= MAX_FALHAS_ATE_DISJUNTOR:
            estado.disjuntor_ate = agora + TEMPO_DO_DISJUNTOR
        estado.save()
