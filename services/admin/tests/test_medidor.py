"""O medidor, e a única coisa que ele nunca pode fazer: atrapalhar a porta.

Este arquivo prova duas famílias de coisa, e a segunda importa mais que a
primeira.

**Que ele mede o que promete.** E, acima de tudo, que "estourou o tempo" e "a
identidade recusou" caem em contadores DIFERENTES. Na tela do dono os dois
chegam idênticos — 503 nos dois casos — e foi essa indistinção que fez o
diagnóstico de 27/08/2026 levar um dia inteiro. Um medidor que juntasse os dois
seria pior que nenhum: daria a sensação de estar medindo.

**Que ele não muda NADA na porta.** Esta é uma área fail-closed: a porta decide
ACESSO. Um defeito no contador não pode virar um 500 numa rota que deveria
devolver 302, nem — muito pior — mudar quem entra. Por isso há um teste que
QUEBRA o medidor de propósito e exige que a porta responda exatamente igual.

A prova de que a porta continua a mesma também mora em outro lugar, e de
propósito: `tests/test_inv_porta_fail_closed.py` **não foi tocado** por este
trabalho. Se as respostas dela tivessem mudado, ele reprovaria.
"""

import httpx
import pytest
import respx
from django.test import Client

from apps.core import medidor

BASE = "http://identidade:8000/interno"
SESSAO = f"{BASE}/sessao/completa"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"


@pytest.fixture(autouse=True)
def cenario(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", BASE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"
    medidor.zerar()


def _com_cookie() -> Client:
    cliente = Client()
    cliente.defaults["HTTP_COOKIE"] = COOKIE
    return cliente


def _sessao_boa():
    return httpx.Response(
        200,
        json={
            "autenticado": True,
            "id": "id-opaco-123",
            "nome_exibido": "Dono",
            "email": DONO,
        },
    )


# ----------------------------------------------------- ele mede o que promete


@respx.mock
def test_a_distincao_que_custou_o_dia_27_08():
    """Timeout e recusa são contadores DIFERENTES.

    Os dois viram 503 na tela. Se virassem um número só aqui também, o medidor
    reproduziria a própria cegueira que motivou sua existência — e mandaria
    investigar capacidade quando o problema é configuração, ou o contrário.
    """
    respx.get(SESSAO).mock(side_effect=httpx.ConnectTimeout("estourou"))
    _com_cookie().get("/")
    depois_do_timeout = medidor.leitura()["desfechos"]

    medidor.zerar()
    respx.get(SESSAO).mock(return_value=httpx.Response(403, json={"erro": "nao"}))
    _com_cookie().get("/")
    depois_da_recusa = medidor.leitura()["desfechos"]

    assert depois_do_timeout["estourou_o_tempo"] == 1
    assert depois_do_timeout["recusou"] == 0
    assert depois_da_recusa["recusou"] == 1
    assert depois_da_recusa["estourou_o_tempo"] == 0


@respx.mock
def test_conta_o_que_a_porta_decidiu():
    """Entrou, mandou para o login, não existe para você, indisponível."""
    respx.get(SESSAO).mock(return_value=_sessao_boa())
    _com_cookie().get("/")
    assert medidor.leitura()["respostas_da_porta"]["entrou"] == 1

    # Sem cookie a porta nem pergunta — manda para o login.
    Client().get("/")
    assert medidor.leitura()["respostas_da_porta"]["mandou_para_o_login"] == 1

    # Sessão válida, e-mail fora da lista: 404, e não 403 (DECISAO-celula-admin).
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "x",
                "nome_exibido": "Outro",
                "email": "outro@exemplo.com",
            },
        )
    )
    _com_cookie().get("/")
    assert medidor.leitura()["respostas_da_porta"]["nao_existe_para_voce"] == 1


@respx.mock
def test_o_503_e_contado_e_e_ele_que_fecha_o_caso_de_agosto():
    """O contador que torna verificável o critério de encerramento.

    Durante um incidente, 503 por minuto deveria bater com quantos registros o
    painel deixou de carregar. Depois do conserto, zero. Se sobrarem 503 com o
    painel pedindo pouco, a identidade está doente por conta própria — e o caso
    muda de dono. Nada disso era mensurável antes deste contador.
    """
    respx.get(SESSAO).mock(side_effect=httpx.ConnectTimeout("estourou"))
    resposta = _com_cookie().get("/")
    assert resposta.status_code == 503
    assert medidor.leitura()["respostas_da_porta"]["indisponivel_503"] == 1


@respx.mock
def test_a_latencia_entra_inclusive_nos_desfechos_ruins():
    """Um timeout é a medição mais informativa que existe aqui.

    Deixá-lo de fora da amostra faria o p95 parecer saudável exatamente quando
    não está — o modo de falha clássico de medição de latência.
    """
    respx.get(SESSAO).mock(side_effect=httpx.ConnectTimeout("estourou"))
    _com_cookie().get("/")
    latencia = medidor.leitura()["latencia_ms"]
    assert latencia["amostras"] == 1
    assert latencia["p50"] is not None
    assert latencia["maior"] is not None


@respx.mock
def test_a_leitura_traz_a_regua_junto_do_numero():
    """Número sem régua não informa um leigo.

    "180 ms" não diz nada sozinho. A leitura carrega o que é saudável (menos de
    50 ms para uma chamada no mesmo host) e o teto da paciência da porta (2s,
    depois do qual a tela vira 503).
    """
    respx.get(SESSAO).mock(return_value=_sessao_boa())
    _com_cookie().get("/")
    leitura = medidor.leitura()
    assert leitura["regua_ms"] == {"saudavel_ate": 50, "teto_da_porta": 2000}
    assert leitura["de_pe_ha_segundos"] >= 0


@respx.mock
def test_a_leitura_nao_carrega_dado_pessoal():
    """Contagens e tempos, nada mais.

    Um medidor que precisasse ser protegido pelo que guarda seria um problema
    novo em vez de um instrumento. Ele já está atrás da porta — mas isso é a
    segunda linha de defesa, não a primeira.
    """
    respx.get(SESSAO).mock(return_value=_sessao_boa())
    _com_cookie().get("/")
    cru = str(medidor.leitura())
    assert DONO not in cru
    assert "id-opaco-123" not in cru
    assert COOKIE not in cru


# ------------------------------------------ e ele NÃO atrapalha o controle de acesso


@respx.mock
def test_medidor_quebrado_nao_muda_a_porta(monkeypatch):
    """A propriedade que justifica o `except` amplo do medidor.

    Observabilidade jamais derruba controle de acesso. Aqui o medidor é
    substituído por um que explode em toda chamada, e a porta tem de responder
    EXATAMENTE o mesmo — sem sessão vira 302, com sessão boa vira 200.

    Sem este teste, o `except Exception` do medidor seria só uma boa intenção
    escrita num comentário.
    """

    def explode(*a, **k):
        raise RuntimeError("o medidor quebrou de proposito")

    monkeypatch.setattr(medidor, "registrar_chamada", explode)
    monkeypatch.setattr(medidor, "registrar_resposta", explode)

    assert Client().get("/").status_code == 302

    respx.get(SESSAO).mock(return_value=_sessao_boa())
    assert _com_cookie().get("/").status_code == 200


@respx.mock
def test_leitura_quebrada_devolve_erro_e_nao_zero(monkeypatch):
    """ "Não consegui medir" é resultado; zero seria mentira.

    Zerado, o painel mostraria "nenhum 503" justamente quando não sabe — a
    mesma doença que `divida.py` evita ao nunca responder "0 pendências" sem
    ter conseguido perguntar.
    """
    monkeypatch.setattr(medidor, "_TRAVA", None)  # quebra a leitura por dentro
    leitura = medidor.leitura()
    assert "erro" in leitura
    assert "perguntas_a_identidade" not in leitura


# ---------------------------------------------------------------- a rota


@respx.mock
def test_diag_json_esta_atras_da_porta():
    """Os números são de dentro da casa. Medido de fora, não lido do código."""
    resposta = Client().get("/painel/diag.json")
    assert resposta.status_code == 302
    assert "/entrar/google" in resposta["Location"]


@respx.mock
def test_diag_json_responde_para_quem_entra():
    respx.get(SESSAO).mock(return_value=_sessao_boa())
    resposta = _com_cookie().get("/painel/diag.json")
    assert resposta.status_code == 200
    assert resposta["Cache-Control"] == "no-store"
    corpo = resposta.json()
    assert "desfechos" in corpo
    assert "respostas_da_porta" in corpo
    # A própria requisição que buscou o diagnóstico já passou pela porta.
    assert corpo["respostas_da_porta"]["entrou"] >= 1
