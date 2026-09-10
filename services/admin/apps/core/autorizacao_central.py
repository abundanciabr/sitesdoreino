"""A autorização funcional da central, conferida antes de cada ação."""

import json

from django.conf import settings
from django.core.exceptions import PermissionDenied


RESPONSABILIDADES = frozenset({"estrategia", "operacoes", "ensino", "comercial"})
NOMES_DAS_RESPONSABILIDADES = {
    "estrategia": "Estratégia",
    "operacoes": "Operações",
    "ensino": "Ensino",
    "comercial": "Comercial",
}


def _texto(valor: object, nome: str) -> str:
    if not isinstance(valor, str) or not (resultado := valor.strip()):
        raise ValueError(f"{nome} é obrigatório.")
    return resultado


def _responsaveis() -> dict[str, str]:
    """Lê o único mapa privado aceito, sem transformar falha em permissão."""
    cru = getattr(settings, "CENTRAL_RESPONSAVEIS", "")
    try:
        dados = json.loads(cru)
    except (TypeError, json.JSONDecodeError):
        return {}

    if not isinstance(dados, dict) or set(dados) != RESPONSABILIDADES:
        return {}

    resultado = {}
    for responsabilidade, email in dados.items():
        if not isinstance(email, str) or not (normalizado := email.strip().lower()):
            return {}
        resultado[responsabilidade] = normalizado

    if len(set(resultado.values())) != len(RESPONSABILIDADES):
        return {}
    return resultado


def responsabilidade_da_conta(admin: dict) -> str | None:
    """A função vem do mapa do servidor; identidade apenas reconhece a conta."""
    email = admin.get("email") if isinstance(admin, dict) else None
    if not isinstance(email, str):
        return None
    normalizado = email.strip().lower()
    for responsabilidade, responsavel in _responsaveis().items():
        if normalizado == responsavel:
            return responsabilidade
    return None


def exigir(admin: dict, *, responsabilidade: str, acao: str, recurso: str) -> None:
    """Recusa no servidor quem não é o titular da ação sobre este recurso."""
    acao = _texto(acao, "A ação")
    recurso = _texto(recurso, "O recurso")
    if responsabilidade not in RESPONSABILIDADES:
        raise ValueError("A responsabilidade informada não existe na central.")
    if responsabilidade_da_conta(admin) == responsabilidade:
        return

    nome = NOMES_DAS_RESPONSABILIDADES[responsabilidade]
    raise PermissionDenied(
        f"Você não pode {acao} em {recurso}. Esta ação é da responsabilidade de "
        f"{nome}; se a pessoa estiver ausente, escale ao mantenedor."
    )
