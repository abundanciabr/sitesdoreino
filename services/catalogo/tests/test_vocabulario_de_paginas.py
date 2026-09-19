# tests/test_vocabulario_de_paginas.py
# O vocabulario e a fronteira desta entrega: secao fora da lista e slot fora da
# lista da secao sao recusados, e a recusa diz qual e a lista valida.
# As onze secoes sao as da ferramenta 73 do mantenedor
# (documentos/ferramentas-do-projeto-meshcraft.md), e a AUSENCIA dos slots que
# a ferramenta 74 proibe e medida aqui, nao so comentada.
import pytest
from django.core.exceptions import ValidationError

from apps.paginas.vocabulario import (
    ORDEM_CANONICA,
    SECOES,
    SLOTS_PROIBIDOS,
    normalizar_secoes,
)


def test_as_onze_secoes_na_ordem_que_o_mantenedor_escreveu():
    # Ferramenta 73: "Onze secoes na ordem: o cubo, os tres viloes, o metodo,
    # os instrumentos, o percurso, quanto tempo leva, para quem nao serve,
    # o que acontece se eu parar, o que recebe e o preco, a carta, perguntas."
    assert ORDEM_CANONICA == (
        "cubo",
        "viloes",
        "metodo",
        "instrumentos",
        "percurso",
        "tempo",
        "para_quem_nao_serve",
        "se_eu_parar",
        "oferta",
        "carta",
        "perguntas",
    )
    assert len(ORDEM_CANONICA) == 11


def test_os_slots_de_cada_secao_sao_os_combinados():
    assert SECOES["cubo"] == (
        "headline",
        "subheadline",
        "cta_texto",
        "cta_destino",
        "imagem",
    )
    # Tres viloes, porque a especificacao diz tres.
    assert SECOES["viloes"] == ("headline", "vilao_1", "vilao_2", "vilao_3", "prova")
    # Seis recusas, porque a especificacao diz seis.
    assert SECOES["para_quem_nao_serve"] == (
        "headline",
        "recusa_1",
        "recusa_2",
        "recusa_3",
        "recusa_4",
        "recusa_5",
        "recusa_6",
    )
    assert SECOES["oferta"] == (
        "headline",
        "o_que_recebe",
        "preco_texto",
        "parcelamento",
        "cta_texto",
    )
    assert SECOES["instrumentos"] == (
        "headline",
        "texto",
        "indice_de_estudios",
        "prova",
    )
    assert SECOES["carta"] == ("headline", "texto", "assinatura")


def test_nenhuma_secao_oferece_slot_que_a_ferramenta_74_proibe():
    # A ferramenta 74 proibe contagem regressiva, "ultimas vagas", valor
    # riscado, promessa de renda ou prazo e superlativo; a 73 manda o preco
    # "uma vez, sem ancoragem". Um slot e um convite a preencher, entao o
    # convite nao pode existir. Vale para TODA secao, inclusive uma nova.
    for nome, slots in SECOES.items():
        for proibido in SLOTS_PROIBIDOS:
            assert proibido not in slots, f"{nome} oferece o slot proibido {proibido}"


def test_a_secao_de_garantia_nao_existe():
    # Ela nao esta entre as onze, e o prazo dela convidaria a promessa de prazo
    # que a ferramenta 74 proibe. Reembolso, se houver, e uma pergunta.
    assert "garantia" not in SECOES
    with pytest.raises(ValidationError):
        normalizar_secoes([{"nome": "garantia", "slots": {"headline": "30 dias"}}])


def test_ancora_de_preco_e_recusada_na_secao_de_oferta():
    with pytest.raises(ValidationError) as erro:
        normalizar_secoes(
            [{"nome": "oferta", "slots": {"ancora_de_preco": "R$ 3.000,00"}}]
        )

    mensagem = "; ".join(erro.value.messages)
    assert "ancora_de_preco" in mensagem
    assert "preco_texto" in mensagem


def test_secao_fora_do_vocabulario_recusa_dizendo_a_lista_valida():
    with pytest.raises(ValidationError) as erro:
        normalizar_secoes([{"nome": "banner", "slots": {"headline": "oi"}}])

    mensagem = "; ".join(erro.value.messages)
    assert "banner" in mensagem
    for nome in ORDEM_CANONICA:
        assert nome in mensagem


def test_slot_fora_da_secao_recusa_dizendo_os_slots_daquela_secao():
    with pytest.raises(ValidationError) as erro:
        normalizar_secoes([{"nome": "se_eu_parar", "slots": {"assinatura": "oi"}}])

    mensagem = "; ".join(erro.value.messages)
    assert "assinatura" in mensagem
    assert "se_eu_parar" in mensagem
    for slot in SECOES["se_eu_parar"]:
        assert slot in mensagem
    # O slot existe em OUTRA secao (carta), e por isso a mensagem tem de citar
    # os slots DESTA: sem isso, quem le acha que o nome esta errado em todo
    # lugar.
    assert "carta" not in mensagem


def test_secoes_chegam_fora_de_ordem_e_saem_na_ordem_canonica():
    normalizadas = normalizar_secoes(
        [
            {"nome": "perguntas", "slots": {"headline": "Perguntas"}},
            {"nome": "cubo", "slots": {"headline": "Titulo"}},
            {"nome": "oferta", "slots": {"preco_texto": "R$ 9,90"}},
            {"nome": "viloes", "slots": {"vilao_1": "O primeiro"}},
        ]
    )

    assert [secao["nome"] for secao in normalizadas] == [
        "cubo",
        "viloes",
        "oferta",
        "perguntas",
    ]
    # `ordem` e o lugar do nome na ordem canonica, nao a posicao na lista:
    # assim ele nao muda quando uma secao entra ou sai.
    assert [secao["ordem"] for secao in normalizadas] == [
        ORDEM_CANONICA.index("cubo"),
        ORDEM_CANONICA.index("viloes"),
        ORDEM_CANONICA.index("oferta"),
        ORDEM_CANONICA.index("perguntas"),
    ]


def test_para_quem_nao_serve_fica_no_meio_da_pagina():
    # Ferramenta 73: "para quem nao serve (no meio, seis recusas)". Se ela
    # escorregar para o fim, a pagina deixa de recusar antes de vender.
    posicao = ORDEM_CANONICA.index("para_quem_nao_serve")
    assert 0 < posicao < ORDEM_CANONICA.index("oferta")


def test_ordem_que_o_chamador_manda_e_ignorada_em_favor_da_canonica():
    normalizadas = normalizar_secoes(
        [
            {"nome": "perguntas", "ordem": 0, "slots": {"headline": "Perguntas"}},
            {"nome": "cubo", "ordem": 99, "slots": {"headline": "Titulo"}},
        ]
    )

    assert [secao["nome"] for secao in normalizadas] == ["cubo", "perguntas"]
    assert normalizadas[0]["ordem"] == ORDEM_CANONICA.index("cubo")


def test_slot_vazio_e_omitido_e_nao_e_erro():
    normalizadas = normalizar_secoes(
        [{"nome": "cubo", "slots": {"headline": "Titulo", "subheadline": "   "}}]
    )

    assert normalizadas == [
        {
            "nome": "cubo",
            "ordem": ORDEM_CANONICA.index("cubo"),
            "slots": {"headline": "Titulo"},
        }
    ]


def test_secao_sem_nenhum_slot_preenchido_nao_aparece():
    normalizadas = normalizar_secoes(
        [
            {"nome": "cubo", "slots": {"headline": "Titulo"}},
            {"nome": "instrumentos", "slots": {"prova": "", "indice_de_estudios": ""}},
        ]
    )

    # Pagina que ainda nao tem o indice de estudios e pagina sem a secao de
    # instrumentos, e isso e honesto.
    assert [secao["nome"] for secao in normalizadas] == ["cubo"]


def test_secao_repetida_recusa():
    with pytest.raises(ValidationError) as erro:
        normalizar_secoes(
            [
                {"nome": "cubo", "slots": {"headline": "Um"}},
                {"nome": "cubo", "slots": {"headline": "Dois"}},
            ]
        )

    assert "cubo" in "; ".join(erro.value.messages)


def test_valor_de_slot_precisa_ser_texto():
    with pytest.raises(ValidationError) as erro:
        normalizar_secoes([{"nome": "oferta", "slots": {"preco_texto": 990}}])

    assert "preco_texto" in "; ".join(erro.value.messages)


def test_secoes_precisa_ser_lista_de_objetos_com_nome():
    with pytest.raises(ValidationError):
        normalizar_secoes({"cubo": {"headline": "Titulo"}})
    with pytest.raises(ValidationError):
        normalizar_secoes([{"slots": {"headline": "Titulo"}}])
