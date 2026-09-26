"""Os contratos que ligam visita, variante sorteada e compra sem dado pessoal."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker


PASTA = Path(__file__).parent / "eventos"
EXPERIMENTO = "7d3f0c2a-9b1e-4c5d-8a6f-2e4b1c9d0f13"


def erros(nome: str, envelope: object) -> list:
    schema = json.loads((PASTA / f"{nome}.json").read_text(encoding="utf-8"))
    validador = Draft202012Validator(schema, format_checker=FormatChecker())
    return list(validador.iter_errors(envelope))


def envelope(evento: str, dados: dict) -> dict:
    return {
        "event": evento,
        "version": 1,
        "event_id": "2a4e5f2e-5a84-4de6-89c4-2581c2fc3e11",
        "occurred_at": "2026-09-26T18:00:00Z",
        "data": dados,
    }


COMUM_DO_FUNIL = {
    "site_id": "site-meshcraft",
    "visitor_id": "v-9f2c",
    "pagina_slug": "oferta",
    "pagina_version": 3,
}

FUNIL = {
    "funil.pagina-vista": {**COMUM_DO_FUNIL, "offer_slug": "mentoria"},
    "funil.secao-vista": {**COMUM_DO_FUNIL, "secao": "cubo"},
    "funil.cta-clicado": {
        **COMUM_DO_FUNIL,
        "secao": "oferta",
        "slot": "cta_texto",
        "destino": "/checkout/mentoria",
    },
    "funil.lead-capturado": {**COMUM_DO_FUNIL, "lead_id": "lead-41"},
}

CHECKOUT = {
    "checkout.pedido-atribuido": {
        "site_id": "site-meshcraft",
        "order_id": "8b1d2c3e-4f5a-4b6c-9d7e-0f1a2b3c4d5e",
        "checkout_session_id": "sessao-77",
        "visitor_id": "v-9f2c",
        "produto": "mentoria",
        "valor_centavos": 49700,
        "moeda": "BRL",
        "criado_em": "2026-09-26T18:00:00-03:00",
    },
    "checkout.pedido-pago": {
        "site_id": "site-meshcraft",
        "order_id": "8b1d2c3e-4f5a-4b6c-9d7e-0f1a2b3c4d5e",
        "visitor_id": "v-9f2c",
        "valor_centavos": 49700,
        "moeda": "BRL",
        "pago_em": "2026-09-26T18:05:00-03:00",
    },
}


@pytest.mark.parametrize("evento", sorted(FUNIL))
def test_o_evento_antigo_sem_experimento_continua_valido(evento: str) -> None:
    assert erros(f"{evento}.v1", envelope(evento, dict(FUNIL[evento]))) == []


@pytest.mark.parametrize("evento", sorted(FUNIL))
def test_o_evento_com_experimento_e_variante_e_valido(evento: str) -> None:
    dados = {**FUNIL[evento], "experimento_id": EXPERIMENTO, "variante_id": "b"}

    assert erros(f"{evento}.v1", envelope(evento, dados)) == []


@pytest.mark.parametrize("evento", sorted(FUNIL))
@pytest.mark.parametrize(
    "metade", [{"experimento_id": EXPERIMENTO}, {"variante_id": "a"}]
)
def test_so_um_dos_dois_campos_do_experimento_e_invalido(
    evento: str, metade: dict
) -> None:
    dados = {**FUNIL[evento], **metade}

    assert erros(f"{evento}.v1", envelope(evento, dados)), (
        f"{evento} aceitou {sorted(metade)} sem o par"
    )


@pytest.mark.parametrize("evento", sorted(FUNIL))
@pytest.mark.parametrize(
    ("experimento_id", "variante_id"),
    [
        ("nao-e-uuid", "a"),
        (EXPERIMENTO, "A"),
        (EXPERIMENTO, "1a"),
        (EXPERIMENTO, ""),
        (EXPERIMENTO, "a" * 33),
        (EXPERIMENTO, "controle_b"),
        (EXPERIMENTO, 7),
    ],
)
def test_identificador_de_experimento_fora_do_formato_e_invalido(
    evento: str, experimento_id: object, variante_id: object
) -> None:
    dados = {
        **FUNIL[evento],
        "experimento_id": experimento_id,
        "variante_id": variante_id,
    }

    assert erros(f"{evento}.v1", envelope(evento, dados)), (
        f"{evento} aceitou experimento={experimento_id!r} variante={variante_id!r}"
    )


@pytest.mark.parametrize("evento", sorted(FUNIL))
def test_o_funil_continua_recusando_campo_nao_declarado(evento: str) -> None:
    dados = {**FUNIL[evento], "headline": "texto da variante"}

    assert erros(f"{evento}.v1", envelope(evento, dados))


@pytest.mark.parametrize("evento", sorted(CHECKOUT))
def test_o_pedido_minimo_e_valido(evento: str) -> None:
    assert erros(f"{evento}.v1", envelope(evento, dict(CHECKOUT[evento]))) == []


@pytest.mark.parametrize("evento", sorted(CHECKOUT))
@pytest.mark.parametrize(
    "pessoal",
    [
        {"customer": {"email": "ana@exemplo.com", "name": "Ana"}},
        {"email": "ana@exemplo.com"},
        {"nome": "Ana"},
        {"telefone": "+5511999990000"},
        {"documento": "12345678909"},
    ],
)
def test_o_pedido_recusa_campo_pessoal(evento: str, pessoal: dict) -> None:
    dados = {**CHECKOUT[evento], **pessoal}

    assert erros(f"{evento}.v1", envelope(evento, dados)), (
        f"{evento} aceitou dado pessoal {sorted(pessoal)}"
    )


@pytest.mark.parametrize(
    ("evento", "campo"),
    [(evento, campo) for evento in sorted(CHECKOUT) for campo in CHECKOUT[evento]],
)
def test_o_pedido_recusa_campo_obrigatorio_ausente(evento: str, campo: str) -> None:
    dados = copy.deepcopy(CHECKOUT[evento])
    del dados[campo]

    assert erros(f"{evento}.v1", envelope(evento, dados)), (
        f"{evento} aceitou {campo} ausente"
    )


@pytest.mark.parametrize("evento", sorted(CHECKOUT))
@pytest.mark.parametrize(
    "alteracao",
    [
        {"visitor_id": ""},
        {"site_id": ""},
        {"order_id": ""},
        {"valor_centavos": 0},
        {"valor_centavos": 497.5},
        {"valor_centavos": "49700"},
        {"moeda": "brl"},
        {"moeda": "REAL"},
    ],
)
def test_o_pedido_recusa_valor_fora_do_formato(evento: str, alteracao: dict) -> None:
    dados = {**CHECKOUT[evento], **alteracao}

    assert erros(f"{evento}.v1", envelope(evento, dados)), (
        f"{evento} aceitou {alteracao}"
    )


@pytest.mark.parametrize(
    ("evento", "campo"),
    [("checkout.pedido-atribuido", "criado_em"), ("checkout.pedido-pago", "pago_em")],
)
def test_o_pedido_recusa_instante_que_nao_e_data(evento: str, campo: str) -> None:
    dados = {**CHECKOUT[evento], campo: "ontem"}

    assert erros(f"{evento}.v1", envelope(evento, dados))


@pytest.mark.parametrize("evento", sorted(CHECKOUT))
def test_o_pedido_recusa_outro_nome_ou_versao(evento: str) -> None:
    trocado = envelope("pedido.criado", dict(CHECKOUT[evento]))
    versao_2 = {**envelope(evento, dict(CHECKOUT[evento])), "version": 2}

    assert erros(f"{evento}.v1", trocado)
    assert erros(f"{evento}.v1", versao_2)


@pytest.mark.parametrize("evento", sorted(CHECKOUT))
def test_o_pedido_declara_somente_campos_sem_dado_pessoal(evento: str) -> None:
    schema = json.loads((PASTA / f"{evento}.v1.json").read_text(encoding="utf-8"))
    dados = schema["properties"]["data"]

    assert dados["additionalProperties"] is False
    assert set(dados["properties"]) == set(CHECKOUT[evento])
    assert set(dados["required"]) == set(CHECKOUT[evento])
