"""O contrato que suspende acesso sem afirmar um valor devolvido."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import FormatError


ARQUIVO = Path(__file__).parent / "eventos" / "pagamento.reversao_confirmada.v2.json"


def schema() -> dict:
    return json.loads(ARQUIVO.read_text(encoding="utf-8"))


def carta() -> dict:
    return {
        "event": "pagamento.reversao_confirmada",
        "version": 2,
        "event_id": "2a4e5f2e-5a84-4de6-89c4-2581c2fc3e11",
        "occurred_at": "2026-09-26T18:00:00Z",
        "data": {
            "platform_site_id": "site-meshcraft",
            "provider": "appmax",
            "provider_reference_id": "pedido-23019",
            "motivo": "contestacao",
        },
    }


def erros(envelope: object) -> list:
    validador = Draft202012Validator(schema(), format_checker=FormatChecker())
    return list(validador.iter_errors(envelope))


def test_o_envelope_minimo_e_valido() -> None:
    assert erros(carta()) == []


@pytest.mark.parametrize(
    "alteracao",
    [
        {"data": {"amount_cents": 495}},
        {"data": {"platform_site_id": ""}},
        {"data": {"provider_reference_id": ""}},
        {"data": {"motivo": "chargeback_vencido"}},
        {"version": 1},
    ],
)
def test_o_contrato_recusa_cinco_formas_de_prova_insuficiente(
    alteracao: dict,
) -> None:
    envelope = copy.deepcopy(carta())
    for caminho, valor in alteracao.items():
        if caminho == "data":
            envelope["data"].update(valor)
        else:
            envelope[caminho] = valor

    assert erros(envelope), f"aceitou a alteração proibida: {alteracao}"


def test_o_envelope_recusa_campo_extra() -> None:
    envelope = carta()
    envelope["extra"] = "proibido"

    assert erros(envelope)


@pytest.mark.parametrize(
    ("nivel", "campo"),
    [
        ("envelope", "event"),
        ("envelope", "version"),
        ("envelope", "event_id"),
        ("envelope", "occurred_at"),
        ("envelope", "data"),
        ("data", "platform_site_id"),
        ("data", "provider"),
        ("data", "provider_reference_id"),
        ("data", "motivo"),
    ],
)
def test_o_envelope_recusa_campo_obrigatorio_ausente(
    nivel: str, campo: str
) -> None:
    envelope = carta()
    if nivel == "data":
        del envelope["data"][campo]
    else:
        del envelope[campo]

    assert erros(envelope), f"aceitou {nivel}.{campo} ausente"


def test_o_envelope_recusa_evento_desconhecido() -> None:
    envelope = carta()
    envelope["event"] = "pagamento.reversao_confirmada.v1"

    assert erros(envelope)


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("envelope", []),
        ("data", []),
        ("event_id", 7),
        ("occurred_at", 7),
        ("platform_site_id", 7),
        ("provider_reference_id", 7),
    ],
)
def test_o_envelope_recusa_tipos_invalidos(
    campo: str, valor: object
) -> None:
    envelope = carta()
    if campo == "envelope":
        envelope = valor
    elif campo == "data":
        envelope["data"] = valor
    elif campo in {"platform_site_id", "provider_reference_id"}:
        envelope["data"][campo] = valor
    else:
        envelope[campo] = valor

    assert erros(envelope), f"aceitou tipo inválido em {campo}"


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("provider", "stripe"),
        ("event_id", "nao-e-uuid"),
        ("occurred_at", "nao-e-data"),
    ],
)
def test_o_envelope_recusa_identidade_e_datas_invalidas(
    campo: str, valor: str
) -> None:
    envelope = carta()
    if campo in envelope["data"]:
        envelope["data"][campo] = valor
    else:
        envelope[campo] = valor

    assert erros(envelope), f"aceitou {campo} inválido"


def test_o_runtime_reconhece_date_time() -> None:
    with pytest.raises(FormatError):
        FormatChecker().check("nao-e-data", "date-time")


def test_o_evento_nao_declara_valor_financeiro() -> None:
    dados = schema()["properties"]["data"]
    assert set(dados["properties"]) == {
        "platform_site_id",
        "provider",
        "provider_reference_id",
        "motivo",
    }
    assert "amount_cents" not in dados["required"]
