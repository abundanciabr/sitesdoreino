"""Os guardas do contrato de pagamento que não carrega nome de fornecedor.

O que está em jogo: quatro células (checkout, alunos, leads, mensageria) e o
modelo de tentativa de pagamento nascem em cima do que este contrato congelar.
Contrato errado aqui vira retrabalho em cinco lugares, e por isso cada lei que o
v2 introduz tem aqui um teste que reprova quando ela é afrouxada.

Rode assim, da raiz do repositório:

    python -m pytest contracts/test_pagamento_sem_nome_de_fornecedor.py -q
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

import fixtures_de_pagamento as cartas


AQUI = Path(__file__).parent
EVENTOS = AQUI / "eventos"


def evento(nome: str) -> dict:
    return json.loads((EVENTOS / f"{nome}.json").read_text(encoding="utf-8"))


def documento(nome: str) -> dict:
    return yaml.safe_load((AQUI / f"{nome}.openapi.yaml").read_text(encoding="utf-8"))



VALIDAS = {
    "pagamento.aprovado.v2": cartas.APROVADO_V2_VALIDA,
    "pagamento.recusado.v2": cartas.RECUSADO_V2_VALIDA,
    "pagamento.estornado.v2": cartas.ESTORNADO_V2_VALIDA,
}

INVALIDAS = {
    "pagamento.aprovado.v2": cartas.APROVADO_V2_INVALIDA,
    "pagamento.recusado.v2": cartas.RECUSADO_V2_INVALIDA,
    "pagamento.estornado.v2": cartas.ESTORNADO_V2_INVALIDA,
}


# ---------------------------------------------------------------------------
# O v1 continua valendo, inteiro
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("nome", ["pagamento.aprovado.v1", "pagamento.recusado.v1"])
def test_o_v1_continua_de_pe_e_nao_sabe_do_v2(nome: str) -> None:
    """O v1 segue sendo emitido até o último consumidor migrar (RITOS.md §3).

    Nenhum campo do v2 pode vazar para ele: um v1 que ganhasse `provider` viraria
    um terceiro formato, e os consumidores das duas versões passariam a decidir
    por adivinhação qual dos dois estão lendo.
    """
    schema = evento(nome)
    assert schema["properties"]["version"]["const"] == 1
    dados = schema["properties"]["data"]
    assert "site_id" in dados["required"]
    assert "platform_site_id" not in dados["properties"]
    assert "provider" not in dados["properties"]
    assert "provider_reference_id" not in dados["properties"]


def test_o_aprovado_v1_continua_exigindo_o_campo_do_mercado_pago() -> None:
    dados = evento("pagamento.aprovado.v1")["properties"]["data"]
    assert "mp_payment_id" in dados["required"]


# ---------------------------------------------------------------------------
# As cartas do v2
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("nome", sorted(VALIDAS))
def test_a_carta_valida_passa_no_schema(nome: str) -> None:
    Draft202012Validator(evento(nome)).validate(VALIDAS[nome])


@pytest.mark.parametrize("nome", sorted(INVALIDAS))
def test_a_carta_invalida_e_recusada_pelo_schema(nome: str) -> None:
    erros = list(Draft202012Validator(evento(nome)).iter_errors(INVALIDAS[nome]))
    assert erros, f"{nome} aceitou uma carta que precisa recusar"


def test_a_referencia_do_provedor_nao_pode_chegar_vazia() -> None:
    """`required` aceita string vazia, e aqui isso seria pior que a ausência.

    Duas compras com `provider_reference_id` vazio dividiriam a mesma chave de
    deduplicação, e a segunda matrícula sumiria em silêncio. Quem recusa é o
    `minLength`.
    """
    erros = list(
        Draft202012Validator(evento("pagamento.aprovado.v2")).iter_errors(
            cartas.APROVADO_V2_SEM_REFERENCIA
        )
    )
    assert erros, "o aprovado v2 aceitou uma referência de provedor vazia"


# ---------------------------------------------------------------------------
# A lei que dá nome à tarefa: nenhum fornecedor dentro do nome do campo
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("nome", sorted(VALIDAS))
def test_nenhum_campo_do_v2_carrega_o_nome_de_um_fornecedor(nome: str) -> None:
    """`mp_payment_id` era o Mercado Pago escrito na fronteira entre células.

    O texto dos schemas pode citar os provedores (é o enum, e é a explicação de
    como migrar), mas nenhum NOME DE CAMPO pode: o dia em que o pagamento chega
    pela Appmax, um campo chamado `mp_*` passa a mentir em silêncio.
    """
    def nomes(schema: dict) -> list[str]:
        achados: list[str] = []
        for chave, valor in (schema.get("properties") or {}).items():
            achados.append(chave)
            if isinstance(valor, dict):
                achados.extend(nomes(valor))
        return achados

    for campo in nomes(evento(nome)):
        assert not campo.startswith("mp_"), f"{nome} tem o campo {campo}"
        assert "mercadopago" not in campo
        assert "appmax" not in campo


@pytest.mark.parametrize("nome", sorted(VALIDAS))
def test_o_par_neutro_e_obrigatorio_e_o_enum_de_provedor_e_fechado(nome: str) -> None:
    dados = evento(nome)["properties"]["data"]
    assert "provider" in dados["required"]
    assert "provider_reference_id" in dados["required"]
    assert dados["properties"]["provider"]["enum"] == ["mercadopago", "appmax"]
    assert dados["properties"]["provider_reference_id"]["type"] == "string"


@pytest.mark.parametrize("nome", sorted(VALIDAS))
def test_o_site_da_plataforma_tem_nome_proprio_e_e_obrigatorio(nome: str) -> None:
    """`platform_site_id`, e não `site_id`, porque a Appmax também tem um.

    O envelope do webhook da Appmax carrega um `site_id` que é da Appmax, não
    nosso. Deixar o nome curto no v2 seria convidar as quatro células a rotear
    um aluno pelo identificador do fornecedor.
    """
    dados = evento(nome)["properties"]["data"]
    assert "platform_site_id" in dados["required"]
    assert "site_id" not in dados["properties"]


#: A ponte que cada v2 declara para a sua versão anterior. As duas são
#: DIFERENTES, e é exatamente por isso que elas precisam estar escritas em
#: forma de dado: o v1 do aprovado carrega `mp_payment_id`, que vale como
#: (`mercadopago`, aquele valor); o v1 do recusado nunca carregou referência de
#: provedor nenhuma, e nele o que atravessa as versões é o `payment_id`. Quatro
#: células vão ler isto, e uma que leia errado transforma um pagamento em duas
#: matrículas.
PONTES_ENTRE_VERSOES = {
    "pagamento.aprovado.v2": {
        "versao_anterior": "pagamento.aprovado.v1",
        "chave_entre_versoes": ["provider", "provider_reference_id"],
        "no_v1": {
            "provider": "mercadopago",
            "provider_reference_id": "data.mp_payment_id",
        },
    },
    "pagamento.recusado.v2": {
        "versao_anterior": "pagamento.recusado.v1",
        "chave_entre_versoes": ["payment_id"],
        "no_v1": {"payment_id": "data.payment_id"},
    },
}


@pytest.mark.parametrize("nome", sorted(PONTES_ENTRE_VERSOES))
def test_a_ponte_entre_as_duas_versoes_esta_escrita_no_contrato(nome: str) -> None:
    """A regra de deduplicação entre v1 e v2 mora no contrato, e em forma de dado.

    Prosa não serve aqui: cada uma das quatro células consumidoras leria a sua
    e derivaria a sua. Em forma de dado, as quatro derivam a MESMA chave.
    """
    ponte = {
        chave: valor
        for chave, valor in evento(nome)["x-ponte-do-v1"].items()
        if not chave.startswith("_")
    }
    assert ponte == PONTES_ENTRE_VERSOES[nome]


@pytest.mark.parametrize("nome", sorted(PONTES_ENTRE_VERSOES))
def test_a_ponte_aponta_para_campos_que_existem_nas_duas_versoes(nome: str) -> None:
    """A ponte não pode envelhecer em silêncio apontando para campo nenhum."""
    ponte = evento(nome)["x-ponte-do-v1"]
    campos_v2 = evento(nome)["properties"]["data"]["properties"]
    for campo in ponte["chave_entre_versoes"]:
        assert campo in campos_v2, f"{nome}: a ponte cita {campo}, que não existe"

    campos_v1 = evento(ponte["versao_anterior"])["properties"]["data"]["properties"]
    for campo, origem in ponte["no_v1"].items():
        assert campo in ponte["chave_entre_versoes"]
        if origem.startswith("data."):
            assert origem.removeprefix("data.") in campos_v1, (
                f"{nome}: a ponte tira {campo} de {origem}, "
                f"que não existe em {ponte['versao_anterior']}"
            )


def test_o_estorno_nasce_na_versao_2_e_nao_tem_v1() -> None:
    """Não existe `pagamento.estornado.v1`, e não pode passar a existir.

    O fato nasce com a família de cartas sem nome de fornecedor. Inventar um v1
    agora seria declarar uma versão que nenhum publicador jamais emitiu, e os
    consumidores passariam a esperar por ela. Por isso ele também não declara
    ponte: não há para onde.
    """
    assert not (EVENTOS / "pagamento.estornado.v1.json").exists()
    estornado = evento("pagamento.estornado.v2")
    assert estornado["properties"]["version"]["const"] == 2
    assert "x-ponte-do-v1" not in estornado


# ---------------------------------------------------------------------------
# O estorno, que corta o acesso do aluno na hora
# ---------------------------------------------------------------------------


def test_o_estorno_so_aceita_os_dois_motivos_que_cortam_o_acesso() -> None:
    dados = evento("pagamento.estornado.v2")["properties"]["data"]
    assert dados["properties"]["motivo"]["enum"] == ["estorno", "contestacao"]
    assert "motivo" in dados["required"]


def test_o_valor_estornado_e_inteiro_em_centavos() -> None:
    dados = evento("pagamento.estornado.v2")["properties"]["data"]
    assert dados["properties"]["amount_cents"]["type"] == "integer"
    assert dados["properties"]["amount_cents"]["minimum"] == 1
    assert "amount_cents" in dados["required"]


# ---------------------------------------------------------------------------
# A porta do cartão do Mercado Pago, que continua vendendo
# ---------------------------------------------------------------------------


def test_a_porta_do_cartao_do_mercado_pago_continua_de_pe() -> None:
    """Esta porta não sai: é o cartão pelo Mercado Pago, e ele ainda vende.

    A porta neutra saiu do contrato em 20/09/2026 porque foi congelada antes
    de existir código que a atendesse, e o freeze reprovava as duas células
    por isso. Ela volta a ser escrita no Rito de Contrato do lote que a
    construir, provedor primeiro. Esta aqui nunca esteve em jogo, e o guarda
    existe para que a remoção daquela jamais leve esta junto.
    """
    doc = documento("pagamentos")
    assert "/intents/{intent_id}/card" in doc["paths"]
    assert "card_token" in doc["components"]["schemas"]["CardConfirm"]["required"]
