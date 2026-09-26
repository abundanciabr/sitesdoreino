"""O sorteio do experimento: quem cai em qual versão da página.

A fórmula é a do desenho comum do sistema de experimentos (26/09/2026) e não
pode mudar com o experimento no ar: um visitante que trocasse de braço no meio
da medição contaminaria as duas amostras sem que nenhuma tela percebesse. Por
isso os vetores abaixo são números fixos, calculados uma vez, e não recalculados
pelo teste: qualquer processo, em qualquer máquina, tem de chegar neles.
"""

import logging
import math
import random
import uuid

import pytest

from apps.core.sorteio import balde, sortear

EXPERIMENTO = "0b7e9f3a-5c21-4d8e-9a64-2f1c3b5d7e90"
OUTRO_EXPERIMENTO = "6d1e2c4b-8a7f-4e3d-b2c1-9f0a8e7d6c5b"
AMOSTRA = 100_000


def experimento(pesos, id_=EXPERIMENTO):
    return {
        "id": id_,
        "secao": "hero",
        "slot": "titulo",
        "variantes": [
            {"variante_id": vid, "peso": peso, "valor": f"texto {vid}"}
            for vid, peso in pesos
        ],
    }


def visitantes(quantos, semente=20260926):
    gerador = random.Random(semente)
    return [
        str(uuid.UUID(int=gerador.getrandbits(128), version=4)) for _ in range(quantos)
    ]


def contagem(exp, ids):
    contados = {}
    for visitor_id in ids:
        vid = sortear(exp, visitor_id)["variante_id"]
        contados[vid] = contados.get(vid, 0) + 1
    return contados


def tolerancia_de_3_desvios(n, p):
    return 3 * math.sqrt(n * p * (1 - p))


def p_do_qui_quadrado_com_1_grau(observados, esperados):
    qui = sum((o - e) ** 2 / e for o, e in zip(observados, esperados))
    return math.erfc(math.sqrt(qui / 2))


# (visitor_id, balde, braço em 50/50, braço em 90/10), para EXPERIMENTO.
VETORES = [
    ("e8926983-d3a9-433c-8fa0-75410a604540", 1, "a", "a"),
    ("d7ecfbb5-816f-4677-99b4-4b433aa2133a", 4816, "a", "a"),
    ("f61313f3-10c1-412e-a6ba-676b6737db90", 4999, "a", "a"),
    ("a786effc-3eb6-4c1c-9ba4-688147fd7d46", 5000, "b", "a"),
    ("e91481a3-748c-4606-84bf-593fa55a5fb4", 5307, "b", "a"),
    ("1595f16e-a617-4d4d-a856-0e02fa681a14", 8999, "b", "a"),
    ("459e69e3-9dbe-4b87-b060-4ec48d4193e6", 9000, "b", "b"),
    ("5a1b73b5-0842-492c-9aa7-93b823d5549a", 9940, "b", "b"),
]


@pytest.mark.parametrize("visitor_id,esperado,_meio,_noventa", VETORES)
def test_balde_bate_com_os_vetores_fixos(visitor_id, esperado, _meio, _noventa):
    assert balde(EXPERIMENTO, visitor_id) == esperado


@pytest.mark.parametrize("visitor_id,_balde,meio,noventa", VETORES)
def test_braco_bate_com_os_vetores_fixos(visitor_id, _balde, meio, noventa):
    assert (
        sortear(experimento([("a", 5000), ("b", 5000)]), visitor_id)["variante_id"]
        == meio
    )
    assert (
        sortear(experimento([("a", 9000), ("b", 1000)]), visitor_id)["variante_id"]
        == noventa
    )


def test_devolve_a_variante_inteira_para_a_pagina_mostrar_o_valor():
    variante = sortear(experimento([("a", 5000), ("b", 5000)]), VETORES[4][0])
    assert variante == {"variante_id": "b", "peso": 5000, "valor": "texto b"}


def test_mesmo_visitante_cai_sempre_no_mesmo_braco():
    exp = experimento([("a", 5000), ("b", 5000)])
    for visitor_id in visitantes(1000):
        primeira = sortear(exp, visitor_id)
        assert all(sortear(exp, visitor_id) == primeira for _ in range(3))


def test_ordem_das_variantes_na_entrada_nao_muda_o_braco():
    em_ordem = experimento([("a", 9000), ("b", 1000)])
    invertido = experimento([("b", 1000), ("a", 9000)])
    for visitor_id in visitantes(5000):
        assert sortear(em_ordem, visitor_id) == sortear(invertido, visitor_id)


def test_distribuicao_50_50_fica_dentro_de_3_desvios():
    contados = contagem(experimento([("a", 5000), ("b", 5000)]), visitantes(AMOSTRA))
    limite = tolerancia_de_3_desvios(AMOSTRA, 0.5)
    assert abs(contados["a"] - AMOSTRA * 0.5) <= limite, contados
    assert contados["a"] + contados["b"] == AMOSTRA


def test_distribuicao_90_10_da_os_90_ao_primeiro_variante_id_em_ordem():
    contados = contagem(experimento([("b", 1000), ("a", 9000)]), visitantes(AMOSTRA))
    limite = tolerancia_de_3_desvios(AMOSTRA, 0.1)
    assert abs(contados["b"] - AMOSTRA * 0.1) <= limite, contados
    assert contados["a"] + contados["b"] == AMOSTRA


def test_dois_experimentos_sorteiam_de_forma_independente():
    ids = visitantes(AMOSTRA)
    x = [balde(EXPERIMENTO, v) for v in ids]
    y = [balde(OUTRO_EXPERIMENTO, v) for v in ids]
    mx, my = sum(x) / AMOSTRA, sum(y) / AMOSTRA
    cov = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sx = math.sqrt(sum((a - mx) ** 2 for a in x))
    sy = math.sqrt(sum((b - my) ** 2 for b in y))
    correlacao = cov / (sx * sy)
    assert abs(correlacao) <= 3 / math.sqrt(AMOSTRA), correlacao


def test_quem_caiu_em_a_num_experimento_se_divide_ao_meio_no_outro():
    primeiro = experimento([("a", 5000), ("b", 5000)])
    segundo = experimento([("a", 5000), ("b", 5000)], id_=OUTRO_EXPERIMENTO)
    em_a = [
        v for v in visitantes(AMOSTRA) if sortear(primeiro, v)["variante_id"] == "a"
    ]
    em_a_no_segundo = sum(1 for v in em_a if sortear(segundo, v)["variante_id"] == "a")
    assert abs(em_a_no_segundo - len(em_a) * 0.5) <= tolerancia_de_3_desvios(
        len(em_a), 0.5
    )


def test_a_a_simulado_nao_dispara_o_alarme_de_srm():
    contados = contagem(
        experimento([("a", 5000), ("b", 5000)], id_=OUTRO_EXPERIMENTO),
        visitantes(AMOSTRA, semente=7),
    )
    p = p_do_qui_quadrado_com_1_grau(
        [contados["a"], contados["b"]], [AMOSTRA * 0.5, AMOSTRA * 0.5]
    )
    assert p >= 0.001, (contados, p)


def test_o_alarme_de_srm_do_teste_dispara_num_sorteio_torto():
    p = p_do_qui_quadrado_com_1_grau([51_000, 49_000], [50_000, 50_000])
    assert p < 0.001


def test_sem_experimento_ativo_devolve_none_em_silencio(caplog):
    with caplog.at_level(logging.ERROR, logger="funil.sorteio"):
        assert sortear(None, VETORES[0][0]) is None
    assert caplog.records == []


@pytest.mark.parametrize("visitor_id", ["", None])
def test_sem_visitante_devolve_none_e_diz_por_que(caplog, visitor_id):
    with caplog.at_level(logging.ERROR, logger="funil.sorteio"):
        assert sortear(experimento([("a", 5000), ("b", 5000)]), visitor_id) is None
    assert "sem visitor_id" in caplog.text
    assert EXPERIMENTO in caplog.text


INVALIDOS = [
    ("pesos somam 9999", experimento([("a", 5000), ("b", 4999)]), "somam 9999"),
    ("pesos somam 10001", experimento([("a", 5001), ("b", 5000)]), "somam 10001"),
    ("lista vazia", experimento([]), "sem variantes"),
    ("variantes ausentes", {"id": EXPERIMENTO}, "sem variantes"),
    ("maiúscula", experimento([("A", 5000), ("b", 5000)]), "'A'"),
    ("começa com dígito", experimento([("1a", 5000), ("b", 5000)]), "'1a'"),
    ("vazio", experimento([("", 5000), ("b", 5000)]), "''"),
    ("longo demais", experimento([("a" * 33, 5000), ("b", 5000)]), "a" * 33),
    ("repetida", experimento([("a", 5000), ("a", 5000)]), "repetida"),
    ("peso negativo", experimento([("a", 10001), ("b", -1)]), "peso"),
    ("peso fracionário", experimento([("a", 5000.0), ("b", 5000)]), "peso"),
    ("peso booleano", experimento([("a", True), ("b", 9999)]), "peso"),
    ("sem id", {"variantes": experimento([("a", 10000)])["variantes"]}, "sem id"),
    ("variante não é objeto", {"id": EXPERIMENTO, "variantes": ["a"]}, "variante"),
    ("experimento não é objeto", ["a", "b"], "não é um objeto"),
]


@pytest.mark.parametrize(
    "exp,trecho", [(e, t) for _, e, t in INVALIDOS], ids=[n for n, _, _ in INVALIDOS]
)
def test_experimento_invalido_devolve_none_e_diz_o_que_houve(caplog, exp, trecho):
    with caplog.at_level(logging.ERROR, logger="funil.sorteio"):
        assert sortear(exp, VETORES[0][0]) is None
    assert trecho in caplog.text
    assert "versão publicada" in caplog.text
