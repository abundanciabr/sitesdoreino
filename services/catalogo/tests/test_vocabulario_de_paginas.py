# tests/test_vocabulario_de_paginas.py
# O vocabulario e a fronteira desta entrega: secao fora da lista e slot fora da
# lista da secao sao recusados, e a recusa diz qual e a lista valida.
import pytest
from django.core.exceptions import ValidationError

from apps.paginas.vocabulario import ORDEM_CANONICA, SECOES, normalizar_secoes


def test_secao_fora_do_vocabulario_recusa_dizendo_a_lista_valida():
    with pytest.raises(ValidationError) as erro:
        normalizar_secoes([{"nome": "banner", "slots": {"headline": "oi"}}])

    mensagem = "; ".join(erro.value.messages)
    assert "banner" in mensagem
    for nome in ORDEM_CANONICA:
        assert nome in mensagem


def test_slot_fora_da_secao_recusa_dizendo_os_slots_daquela_secao():
    with pytest.raises(ValidationError) as erro:
        normalizar_secoes([{"nome": "garantia", "slots": {"depoimento": "oi"}}])

    mensagem = "; ".join(erro.value.messages)
    assert "depoimento" in mensagem
    assert "garantia" in mensagem
    for slot in SECOES["garantia"]:
        assert slot in mensagem
    # O slot existe em OUTRA secao, e por isso a mensagem tem de citar os slots
    # desta: sem isso, quem le acha que o nome esta errado em toda a plataforma.
    assert "prova" not in mensagem


def test_secoes_chegam_fora_de_ordem_e_saem_na_ordem_canonica():
    normalizadas = normalizar_secoes(
        [
            {"nome": "faq", "slots": {"headline": "Perguntas"}},
            {"nome": "hero", "slots": {"headline": "Titulo"}},
            {"nome": "oferta", "slots": {"preco_texto": "R$ 9,90"}},
        ]
    )

    assert [secao["nome"] for secao in normalizadas] == ["hero", "oferta", "faq"]
    # `ordem` e o lugar do nome na ordem canonica, nao a posicao na lista: assim
    # ele nao muda quando uma secao entra ou sai.
    assert [secao["ordem"] for secao in normalizadas] == [
        ORDEM_CANONICA.index("hero"),
        ORDEM_CANONICA.index("oferta"),
        ORDEM_CANONICA.index("faq"),
    ]


def test_ordem_que_o_chamador_manda_e_ignorada_em_favor_da_canonica():
    normalizadas = normalizar_secoes(
        [
            {"nome": "faq", "ordem": 0, "slots": {"headline": "Perguntas"}},
            {"nome": "hero", "ordem": 99, "slots": {"headline": "Titulo"}},
        ]
    )

    assert [secao["nome"] for secao in normalizadas] == ["hero", "faq"]
    assert normalizadas[0]["ordem"] == ORDEM_CANONICA.index("hero")


def test_slot_vazio_e_omitido_e_nao_e_erro():
    normalizadas = normalizar_secoes(
        [{"nome": "hero", "slots": {"headline": "Titulo", "subheadline": "   "}}]
    )

    assert normalizadas == [
        {
            "nome": "hero",
            "ordem": ORDEM_CANONICA.index("hero"),
            "slots": {"headline": "Titulo"},
        }
    ]


def test_secao_sem_nenhum_slot_preenchido_nao_aparece():
    normalizadas = normalizar_secoes(
        [
            {"nome": "hero", "slots": {"headline": "Titulo"}},
            {"nome": "prova", "slots": {"depoimento": "", "numeros": ""}},
        ]
    )

    # Pagina que ainda nao tem depoimento e pagina sem a secao de prova.
    assert [secao["nome"] for secao in normalizadas] == ["hero"]


def test_secao_repetida_recusa():
    with pytest.raises(ValidationError) as erro:
        normalizar_secoes(
            [
                {"nome": "hero", "slots": {"headline": "Um"}},
                {"nome": "hero", "slots": {"headline": "Dois"}},
            ]
        )

    assert "hero" in "; ".join(erro.value.messages)


def test_valor_de_slot_precisa_ser_texto():
    with pytest.raises(ValidationError) as erro:
        normalizar_secoes([{"nome": "oferta", "slots": {"preco_texto": 990}}])

    assert "preco_texto" in "; ".join(erro.value.messages)


def test_secoes_precisa_ser_lista_de_objetos_com_nome():
    with pytest.raises(ValidationError):
        normalizar_secoes({"hero": {"headline": "Titulo"}})
    with pytest.raises(ValidationError):
        normalizar_secoes([{"slots": {"headline": "Titulo"}}])


def test_vocabulario_declarado_e_o_combinado_com_o_contrato():
    assert ORDEM_CANONICA == (
        "hero",
        "problema",
        "mecanismo",
        "prova",
        "oferta",
        "garantia",
        "faq",
    )
    assert SECOES["hero"] == (
        "eyebrow",
        "headline",
        "subheadline",
        "cta_texto",
        "cta_destino",
        "imagem",
    )
    assert SECOES["prova"] == ("headline", "depoimento", "numeros", "autoridade")
