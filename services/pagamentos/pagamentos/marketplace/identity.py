"""Validação dos dados obrigatórios do pagador, sem registrar CPF em texto."""
from __future__ import annotations

import hashlib
import hmac
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email


class InvalidPayer(ValueError):
    pass


def _cpf_valid(cpf: str) -> bool:
    if len(cpf) != 11 or len(set(cpf)) == 1:
        return False
    for length in (9, 10):
        remainder = sum(int(cpf[index]) * (length + 1 - index) for index in range(length)) % 11
        digit = 0 if remainder < 2 else 11 - remainder
        if digit != int(cpf[length]):
            return False
    return True


def digest(value: str) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), value.encode(), hashlib.sha256).hexdigest()


def payer(*, name: str, cpf: str, email: str) -> tuple[str, str, str]:
    clean_name = " ".join(name.strip().split())
    parts = clean_name.split(" ")
    if (len(parts) < 2 or len(clean_name) > 160
            or any(not re.fullmatch(r"[^\W\d_][^\W\d_'-]*", part, re.UNICODE) for part in parts)):
        raise InvalidPayer("nome completo inválido")
    digits = "".join(char for char in cpf if char.isdigit())
    if any(not (char.isdigit() or char in " .-/") for char in cpf) or not _cpf_valid(digits):
        raise InvalidPayer("CPF inválido")
    clean_email = email.strip().lower()
    try:
        validate_email(clean_email)
    except ValidationError as exc:
        raise InvalidPayer("email inválido") from exc
    if clean_email.rsplit("@", 1)[-1].endswith((".test", ".invalid", ".localhost")):
        raise InvalidPayer("email de teste não aceito pelo provedor")
    return clean_name, digits, clean_email
