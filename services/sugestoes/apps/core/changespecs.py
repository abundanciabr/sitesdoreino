"""Registro histórico de um gesto da equipe sobre uma sugestão.

A linha é append-only e aponta para quem a registrou. O documento, o nome de
aprovação e a data podem acompanhar o gesto, mas não são pré-condições da API
de gestão autenticada.
"""

import uuid
from datetime import date

from django.db import IntegrityError, transaction
from django.utils.dateparse import parse_date

from apps.sugestoes.models import ChangeSpecAprovado

class ChangeSpecInvalido(Exception):
    """Dados inválidos para o registro histórico."""


# ---------------------------------------------------------------------------
# O registro
# ---------------------------------------------------------------------------


def _conferir(campos: dict) -> dict:
    """Normaliza metadados opcionais e valida privacidade e largura dos campos."""
    erros = []

    change_id = (campos.get("change_id") or "").strip()
    if not change_id:
        change_id = f"CS-SUGESTOES-{uuid.uuid4().int}"
    if len(change_id) > 60:
        erros.append("O identificador deve ter no máximo 60 caracteres.")

    documento = (campos.get("documento") or "").strip()
    if len(documento) > 300:
        erros.append("O documento deve ter no máximo 300 caracteres.")

    aprovado_por = (campos.get("aprovado_por") or "").strip()
    if len(aprovado_por) > 120:
        erros.append("O nome deve ter no máximo 120 caracteres.")
    if "@" in aprovado_por:
        erros.append(
            "Use um nome nesse campo; o e-mail fica na identidade do responsável."
        )

    data_informada = campos.get("aprovado_em")
    aprovado_em = (
        data_informada
        if isinstance(data_informada, date)
        else parse_date(str(data_informada or "").strip())
    )
    if data_informada and aprovado_em is None:
        erros.append("A data da aprovação vai no formato AAAA-MM-DD.")

    if erros:
        raise ChangeSpecInvalido(erros)

    return {
        "change_id": change_id,
        "documento": documento,
        "aprovado_por": aprovado_por,
        "aprovado_em": aprovado_em,
    }


def registrar(*, sugestao, por, **campos) -> ChangeSpecAprovado:
    """Acrescenta um registro com responsável identificado e ID único por ideia."""
    if por is None or not por.pk or not (por.email or "").strip():
        raise ChangeSpecInvalido(["Informe quem está registrando esta decisão."])
    limpos = _conferir(campos)
    try:
        with transaction.atomic():
            return ChangeSpecAprovado.objects.create(
                sugestao=sugestao, registrado_por=por, **limpos
            )
    except IntegrityError:
        raise ChangeSpecInvalido(
            [f"O identificador {limpos['change_id']} já está registrado nesta ideia."]
        )
