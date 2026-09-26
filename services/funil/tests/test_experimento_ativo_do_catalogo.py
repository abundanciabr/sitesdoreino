"""`CatalogoClient.obter_pagina` e o `experimento_ativo` que o `getPage` passa a
trazer (frente F5 do sistema de experimentos).

A regra que estes testes seguram é o fail-open: o experimento nunca derruba a
oferta. Experimento ausente, nulo ou fora de forma vira "sem experimento", e a
página publicada segue inteira para quem visita. A diferença entre os três é o
log: ausente e nulo são o estado normal de uma página sem teste rodando, e fora
de forma é defeito do catálogo, que precisa ficar escrito com o motivo.

O catálogo aqui é o contrato mockado (respx), como no resto da célula.
"""

import logging

import httpx
import pytest

from apps.core.clients import SEM_RESPOSTA, CatalogoClient

from tests.conftest import CATALOGO, SITE_A

ROTA = f"{CATALOGO}/sites/{SITE_A['id']}/paginas/oferta"

EXPERIMENTO = {
    "id": "0b6f1c3e-8a52-4d7e-9f10-2c4b6d8e0a13",
    "secao": "cubo",
    "slot": "headline",
    "variantes": [
        {"variante_id": "a", "peso": 5000, "valor": "O texto publicado hoje"},
        {"variante_id": "b", "peso": 5000, "valor": "A headline B do cubo"},
    ],
}


def pagina(**extra):
    return {
        "id": "pag-da-oferta",
        "site_id": SITE_A["id"],
        "slug": "oferta",
        "version": 3,
        "offer_slug": "curso-esqueleto",
        "published_at": "2026-09-19T12:00:00-03:00",
        "secoes": [{"nome": "cubo", "ordem": 0, "slots": {"headline": "Oi"}}],
        **extra,
    }


def com_variantes(*variantes):
    return {**EXPERIMENTO, "variantes": list(variantes)}


def variante(variante_id="a", peso=5000, valor="texto"):
    return {"variante_id": variante_id, "peso": peso, "valor": valor}


def ler(rede, corpo):
    rede.get(ROTA).mock(return_value=httpx.Response(200, json=corpo))
    return CatalogoClient().obter_pagina(SITE_A["id"], "oferta")


def erros(caplog):
    return [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]


def test_experimento_ativo_em_forma_chega_inteiro_a_quem_renderiza(rede, caplog):
    lida = ler(rede, pagina(experimento_ativo=EXPERIMENTO))

    assert lida["experimento_ativo"] == EXPERIMENTO
    assert lida["version"] == 3
    assert erros(caplog) == []


@pytest.mark.parametrize(
    "corpo",
    [
        pytest.param(pagina(), id="ausente"),
        pytest.param(pagina(experimento_ativo=None), id="nulo"),
    ],
)
def test_pagina_sem_experimento_e_o_estado_normal_e_nao_escreve_erro(
    rede, caplog, corpo
):
    lida = ler(rede, corpo)

    assert lida["experimento_ativo"] is None
    assert lida["secoes"] == pagina()["secoes"]
    assert erros(caplog) == []


@pytest.mark.parametrize(
    "experimento, motivo",
    [
        pytest.param(["a", "b"], "não é um objeto", id="nao-e-objeto"),
        pytest.param({**EXPERIMENTO, "id": None}, "UUID", id="sem-id"),
        pytest.param({**EXPERIMENTO, "id": "exp-1"}, "UUID", id="id-nao-e-uuid"),
        pytest.param(
            {**EXPERIMENTO, "id": EXPERIMENTO["id"].upper()}, "UUID", id="id-fora-do-canonico"
        ),
        pytest.param({**EXPERIMENTO, "secao": ""}, "secao ausente", id="secao-vazia"),
        pytest.param(
            {k: v for k, v in EXPERIMENTO.items() if k != "slot"}, "slot ausente", id="sem-slot"
        ),
        pytest.param({**EXPERIMENTO, "variantes": {}}, "variantes ausente", id="variantes-nao-e-lista"),
        pytest.param(com_variantes(), "variantes ausente", id="sem-variantes"),
        pytest.param(com_variantes("a", variante("b", 10000)), "uma variante não é", id="variante-nao-e-objeto"),
        pytest.param(
            com_variantes(variante("A"), variante("b")), "fora do padrão", id="variante-id-maiusculo"
        ),
        pytest.param(
            com_variantes(variante("a\n"), variante("b")), "fora do padrão", id="variante-id-com-quebra"
        ),
        pytest.param(
            com_variantes(variante("a"), variante("a")), "repetido", id="variante-id-repetido"
        ),
        pytest.param(
            com_variantes(variante("a", True), variante("b", 9999)), "peso", id="peso-booleano"
        ),
        pytest.param(
            com_variantes(variante("a", 15000), variante("b", -5000)), "peso", id="peso-negativo"
        ),
        pytest.param(
            com_variantes(variante("a", "5000"), variante("b")), "peso", id="peso-em-texto"
        ),
        pytest.param(
            com_variantes(variante("a", 5000), variante("b", 4000)), "9000", id="pesos-nao-somam-10000"
        ),
        pytest.param(
            com_variantes(variante("a"), variante("b", valor=None)), "valor", id="valor-nao-e-texto"
        ),
    ],
)
def test_experimento_fora_de_forma_vira_sem_experimento_e_a_pagina_publicada_segue(
    rede, caplog, experimento, motivo
):
    lida = ler(rede, pagina(experimento_ativo=experimento))

    assert lida is not SEM_RESPOSTA
    assert lida["experimento_ativo"] is None
    assert lida["version"] == 3
    assert lida["secoes"] == pagina()["secoes"]
    (mensagem,) = erros(caplog)
    assert "experimento_ativo" in mensagem
    assert motivo in mensagem
    assert "versão publicada" in mensagem


def test_catalogo_fora_do_ar_continua_sendo_sem_resposta_e_nao_sem_experimento(rede):
    rede.get(ROTA).mock(side_effect=httpx.ConnectError("catalogo fora do ar"))

    assert CatalogoClient().obter_pagina(SITE_A["id"], "oferta") is SEM_RESPOSTA


def test_experimento_em_forma_nao_salva_pagina_fora_do_contrato(rede):
    corpo = pagina(experimento_ativo=EXPERIMENTO)
    del corpo["version"]

    assert ler(rede, corpo) is SEM_RESPOSTA
