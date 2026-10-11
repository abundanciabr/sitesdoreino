"""Corte temporal dos eventos da progressão após o reinício das faixas."""

from django.utils import timezone
from django.utils.dateparse import parse_datetime


CHAVE = "reinicio-autorizado-20261011"


def evento_anterior_ao_reinicio(site_id, envelope):
    """Um evento atrasado não pode refazer as conquistas anteriores ao corte."""
    from .models import BackupDoReinicioDasFaixas

    corte = (BackupDoReinicioDasFaixas.objects.filter(
        site_id=site_id, chave=CHAVE, aplicado_em__isnull=False,
    ).order_by("-criado_em").values_list("criado_em", flat=True).first())
    if corte is None:
        return False
    data = envelope.get("data") or {}
    if data.get("historico"):
        return True
    bruto = data.get("ocorrido_em") or envelope.get("occurred_at")
    ocorrido = parse_datetime(str(bruto or ""))
    if ocorrido is None:
        # Sem instante verificável, não recriamos progresso após o corte.
        return True
    if timezone.is_naive(ocorrido):
        ocorrido = timezone.make_aware(ocorrido)
    return ocorrido < corte
