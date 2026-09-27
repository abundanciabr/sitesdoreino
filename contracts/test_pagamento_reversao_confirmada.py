"""O contrato que suspende acesso sem afirmar um valor devolvido."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker


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


def erros(envelope: dict) -> list:
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


def test_o_evento_nao_declara_valor_financeiro() -> None:
    dados = schema()["properties"]["data"]
    assert set(dados["properties"]) == {
        "platform_site_id",
        "provider",
        "provider_reference_id",
        "motivo",
    }
    assert "amount_cents" not in dados["required"]

