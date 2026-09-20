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


def confirmacao_de_cartao(nome: str) -> dict:
    return documento(nome)["components"]["schemas"]["ConfirmacaoDeCartao"]


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


#: Qual campo do v1 atravessa para o v2, por evento que TEM um v1. As duas
#: pontes são diferentes, e é por isso que elas estão escritas: o v1 do
#: aprovado carrega `mp_payment_id`, que vale como (`mercadopago`, aquele
#: valor); o v1 do recusado NUNCA carregou referência de provedor nenhuma, e
#: nele o que atravessa as versões é o `payment_id`.
PONTES_ENTRE_VERSOES = {
    "pagamento.aprovado.v2": "mp_payment_id",
    "pagamento.recusado.v2": "payment_id",
}


@pytest.mark.parametrize("nome,chave", sorted(PONTES_ENTRE_VERSOES.items()))
def test_a_ponte_entre_as_duas_versoes_esta_escrita_no_contrato(
    nome: str, chave: str
) -> None:
    """A regra de deduplicação entre v1 e v2 mora aqui, e em nenhum outro lugar.

    As quatro células consumidoras precisam derivar a MESMA chave lógica do
    mesmo fato chegando nas duas versões. Se essa frase sair do contrato, cada
    uma inventa a sua, e o mesmo pagamento vira duas matrículas.
    """
    descricao = evento(nome)["description"]
    assert "v1" in descricao
    assert chave in descricao


def test_o_estorno_nasce_na_versao_2_e_nao_tem_v1() -> None:
    """Não existe `pagamento.estornado.v1`, e não pode passar a existir.

    O fato nasce com a família de cartas sem nome de fornecedor. Inventar um v1
    agora seria declarar uma versão que nenhum publicador jamais emitiu, e os
    consumidores passariam a esperar por ela.
    """
    assert not (EVENTOS / "pagamento.estornado.v1.json").exists()
    assert evento("pagamento.estornado.v2")["properties"]["version"]["const"] == 2


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
# A confirmação de cartão: a pública e a interna
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("celula", ["checkout", "pagamentos"])
def test_a_confirmacao_de_cartao_aceita_a_carta_do_navegador(celula: str) -> None:
    Draft202012Validator(confirmacao_de_cartao(celula)).validate(cartas.CARTAO_VALIDA)


@pytest.mark.parametrize("celula", ["checkout", "pagamentos"])
def test_a_confirmacao_de_cartao_recusa_dinheiro_vindo_do_navegador(celula: str) -> None:
    """INV-P2 na fronteira: o navegador manda intenção, nunca valor.

    `additionalProperties: false` é o que transforma a lei em recusa: total e
    produto vêm do snapshot congelado no servidor, e uma página que os enviasse
    seria a porta para escolher o próprio preço.
    """
    erros = list(
        Draft202012Validator(confirmacao_de_cartao(celula)).iter_errors(
            cartas.CARTAO_INVALIDA
        )
    )
    assert erros, f"{celula} aceitou valor e produto vindos do navegador"


@pytest.mark.parametrize("celula", ["checkout", "pagamentos"])
def test_o_ip_do_comprador_e_obrigatorio_na_confirmacao(celula: str) -> None:
    """Sem `ip` a criação do cliente na Appmax falha, e a venda não acontece.

    A Appmax exige o IP do comprador e ele só é obtido pelo Appmax JS rodando no
    navegador: não existe alternativa por API. Por isso ele é campo do contrato,
    e obrigatório, em vez de algo que o servidor deduz.
    """
    schema = confirmacao_de_cartao(celula)
    assert "ip" in schema["required"]
    sem_ip = {k: v for k, v in cartas.CARTAO_VALIDA.items() if k != "ip"}
    erros = list(Draft202012Validator(schema).iter_errors(sem_ip))
    assert erros, f"{celula} aceitou uma confirmação de cartão sem o IP"


@pytest.mark.parametrize("celula", ["checkout", "pagamentos"])
def test_as_parcelas_vao_de_uma_a_doze(celula: str) -> None:
    parcelas = confirmacao_de_cartao(celula)["properties"]["installments"]
    assert parcelas["type"] == "integer"
    assert parcelas["minimum"] == 1
    assert parcelas["maximum"] == 12


def test_a_operacao_interna_espelha_a_publica() -> None:
    """A mesma carta atravessa as duas portas, campo por campo.

    O navegador entrega ao checkout e o checkout repassa à pagamentos. Duas
    formas diferentes para a mesma carta obrigariam o checkout a traduzir, e
    tradução entre fronteiras é onde o `ip` se perde.
    """
    assert confirmacao_de_cartao("checkout") == confirmacao_de_cartao("pagamentos")


def test_a_confirmacao_publica_de_cartao_existe_no_checkout() -> None:
    operacao = documento("checkout")["paths"]["/pedidos/{order_id}/cartao"]["post"]
    corpo = operacao["requestBody"]["content"]["application/json"]["schema"]
    assert corpo == {"$ref": "#/components/schemas/ConfirmacaoDeCartao"}
    assert operacao["security"] == []


def test_a_confirmacao_interna_de_cartao_existe_na_pagamentos() -> None:
    operacao = documento("pagamentos")["paths"]["/intents/{intent_id}/cartao"]["post"]
    corpo = operacao["requestBody"]["content"]["application/json"]["schema"]
    assert corpo == {"$ref": "#/components/schemas/ConfirmacaoDeCartao"}


def test_a_porta_do_cartao_do_mercado_pago_continua_de_pe() -> None:
    """A rota antiga não sai: ela é o cartão pelo Mercado Pago, que ainda vende.

    A porta neutra nasce ao lado, como o evento v2 nasce ao lado do v1.
    """
    doc = documento("pagamentos")
    assert "/intents/{intent_id}/card" in doc["paths"]
    assert "card_token" in doc["components"]["schemas"]["CardConfirm"]["required"]
