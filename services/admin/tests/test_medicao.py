"""A linha da memória no placar (degrau 7.6): o painel lendo a célula de medição.

O que estes guardas protegem, e por que cada um existe:

1. **"Não perguntei" nunca vira "não há nada".** São cinco desfechos com cinco
   frases, e o valor inteiro desta linha está em não os confundir: um zero
   inventado num painel de gestão é pior que número nenhum, porque parece
   medido. É a lei da célula que responde (`AGENTS.metricas.md`) e a régua 8 do
   plano.
2. **A memória fora do ar NÃO derruba o placar.** Ela é uma linha de confiança
   no cabeçalho; trocar um aviso por um apagão seria o remédio pior que a
   doença. Fail-open aqui, ao contrário da identidade, que decide acesso.
3. **A linha não é um bloco.** A capa tem teto de nove e se recusa a crescer
   (plano §3); `tests/test_capa.py` conta, e este arquivo existe para que
   ninguém "resolva" o teto transformando isto num bloco.
4. **Assunto que parou de chegar aparece.** É o único lugar da casa onde
   "os avisos pararam de sair de alguma célula" fica visível antes de os
   números históricos envelhecerem calados.
5. **A segunda pergunta não derruba a primeira.** A fila de eventos mortos é
   outra chamada; se ela falhar sozinha, a linha continua dizendo o que a
   cobertura contou, e simplesmente não fala dos quebrados.
"""

from __future__ import annotations

import datetime as dt

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.core import medicao
from apps.core.clients import MedicaoClient

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
CATALOGO = "http://catalogo:8000/api/catalogo"
ALUNOS = "http://alunos:8000/api/alunos"
METRICAS = "http://metricas:8000/api/metricas"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"
SITE_ID = "site-mesh"

AGORA = dt.datetime(2026, 9, 4, 15, 0, tzinfo=dt.timezone.utc)


class ClienteFalso:
    """Um dublê com a MESMA forma do cliente de verdade.

    Duplê, e não `respx`, nos testes de regra: o que eles medem é a decisão
    sobre a resposta, não o transporte. O transporte tem os testes de tela,
    abaixo, e é lá que o contrato importa.
    """

    def __init__(self, cobertura=(MedicaoClient.OK, None), quebrados=None):
        self._cobertura = cobertura
        self._quebrados = quebrados or (MedicaoClient.OK, 0)

    def cobertura(self, site_id):
        return self._cobertura

    def quebrados(self):
        return self._quebrados


def _tipo(nome, quantidade=1, dias=0, recebido="2026-09-04T14:58:00+00:00"):
    return {
        "tipo": nome,
        "celula": nome.split(".")[0],
        "quantidade": quantidade,
        "ultimo_ocorrido_em": recebido,
        "ultimo_recebido_em": recebido,
        "dias_desde_o_ultimo": dias,
    }


# ---------------------------------------------------------------------------
# 1. Os cinco desfechos, e a distância entre eles
# ---------------------------------------------------------------------------


def test_sem_site_nao_pergunta_nada():
    """Sem saber o site, a pergunta seria sobre a escola errada (Lei 9)."""
    assert medicao.a_memoria(None, AGORA, ClienteFalso())["veredito"] == "sem-site"


def test_par_nao_provisionado_diz_que_falta_a_senha():
    cliente = ClienteFalso(cobertura=(MedicaoClient.SEM_CONFIGURACAO, None))

    assert medicao.a_memoria(SITE_ID, AGORA, cliente)["veredito"] == "sem-configuracao"


def test_medicao_fora_do_ar_nao_vira_zero():
    """O guarda que dá sentido a todos os outros."""
    cliente = ClienteFalso(cobertura=(MedicaoClient.NAO_RESPONDEU, None))

    memoria = medicao.a_memoria(SITE_ID, AGORA, cliente)

    assert memoria["veredito"] == "nao-respondeu"
    assert "fatos" not in memoria, "inventou um número para uma pergunta sem resposta"


def test_memoria_vazia_e_diferente_de_memoria_muda():
    """Respondeu e não há nada é uma afirmação sobre o mundo; a outra não é."""
    cliente = ClienteFalso(cobertura=(MedicaoClient.OK, []))

    assert medicao.a_memoria(SITE_ID, AGORA, cliente)["veredito"] == "vazia"


def test_medindo_soma_os_fatos_e_conta_os_assuntos():
    cliente = ClienteFalso(
        cobertura=(
            MedicaoClient.OK,
            [_tipo("identidade.pessoa-cadastrada", 12), _tipo("quiz.completado", 5)],
        ),
        quebrados=(MedicaoClient.OK, 3),
    )

    memoria = medicao.a_memoria(SITE_ID, AGORA, cliente)

    assert memoria["veredito"] == "medindo"
    assert memoria["fatos"] == 17
    assert memoria["assuntos"] == 2
    assert memoria["quebrados"] == 3
    assert memoria["ultimo"] == "há 2 minutos"


# ---------------------------------------------------------------------------
# 2. O que parou de chegar
# ---------------------------------------------------------------------------


def test_assunto_parado_ha_mais_de_uma_semana_e_nomeado_em_portugues():
    cliente = ClienteFalso(
        cobertura=(
            MedicaoClient.OK,
            [
                _tipo("identidade.pessoa-cadastrada", 12, dias=0),
                _tipo("forum.topico-criado", 4, dias=9),
            ],
        )
    )

    memoria = medicao.a_memoria(SITE_ID, AGORA, cliente)

    assert memoria["parados"] == ["pergunta no fórum"]


def test_assunto_desconhecido_aparece_com_o_nome_cru_em_vez_de_sumir():
    """Tradução que falta não pode virar fato que some."""
    cliente = ClienteFalso(
        cobertura=(MedicaoClient.OK, [_tipo("celula-nova.coisa-nova", 1, dias=30)])
    )

    memoria = medicao.a_memoria(SITE_ID, AGORA, cliente)

    assert memoria["parados"] == ["celula-nova.coisa-nova"]


def test_a_fila_de_mortos_fora_do_ar_nao_derruba_a_contagem():
    cliente = ClienteFalso(
        cobertura=(MedicaoClient.OK, [_tipo("quiz.completado", 7)]),
        quebrados=(MedicaoClient.NAO_RESPONDEU, None),
    )

    memoria = medicao.a_memoria(SITE_ID, AGORA, cliente)

    assert memoria["veredito"] == "medindo"
    assert memoria["fatos"] == 7
    assert memoria["quebrados"] is None


# ---------------------------------------------------------------------------
# 3. O relógio em português
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "segundos,esperado",
    [
        (10, "agora mesmo"),
        (60 * 5, "há 5 minutos"),
        (60 * 60, "há 1 hora"),
        (60 * 60 * 5, "há 5 horas"),
        (60 * 60 * 24, "há 1 dia"),
        (60 * 60 * 24 * 3, "há 3 dias"),
    ],
)
def test_ha_quanto_tempo_fala_portugues(segundos, esperado):
    antes = AGORA - dt.timedelta(seconds=segundos)

    assert medicao.ha_quanto_tempo(antes, AGORA) == esperado


# ---------------------------------------------------------------------------
# 4. A tela, de ponta a ponta
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    monkeypatch.setenv("ALUNOS_API_URL", ALUNOS)
    monkeypatch.setenv("ALUNOS_API_TOKEN", "token-do-par-admin-alunos")
    monkeypatch.setenv("CATALOGO_API_URL", CATALOGO)
    monkeypatch.setenv("TOKEN_CATALOGO", "token-do-par-admin-catalogo")
    monkeypatch.setenv("METRICAS_API_URL", METRICAS)
    monkeypatch.setenv("METRICAS_API_TOKEN", "token-do-par-admin-metricas")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


def _dentro() -> Client:
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "id-opaco-123",
                "nome_exibido": "Fulano",
                "papel": None,
                "email": DONO,
            },
        )
    )
    respx.get(f"{CATALOGO}/sites/by-host/testserver").mock(
        return_value=httpx.Response(200, json={"id": SITE_ID, "host": "testserver"})
    )
    respx.get(f"{ALUNOS}/pre-matriculas").mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get(f"{ALUNOS}/matriculas").mock(return_value=httpx.Response(200, json=[]))
    c = Client()
    c.defaults["HTTP_COOKIE"] = COOKIE
    return c


@respx.mock
def test_a_tela_mostra_o_que_a_medicao_respondeu():
    cliente = _dentro()
    respx.get(f"{METRICAS}/cobertura").mock(
        return_value=httpx.Response(
            200,
            json={
                "site_id": SITE_ID,
                "medido_em": "2026-09-04T15:00:00+00:00",
                "tipos": [_tipo("identidade.pessoa-cadastrada", 12)],
            },
        )
    )
    respx.get(f"{METRICAS}/eventos-mortos").mock(
        return_value=httpx.Response(
            200, json={"total": 0, "itens": [], "proximo_cursor": None}
        )
    )

    corpo = cliente.get(reverse("placar")).content.decode()

    assert "A memória da escola está guardando." in corpo
    assert "12 fatos" in corpo


@respx.mock
def test_a_medicao_fora_do_ar_nao_derruba_o_placar():
    """Fail-OPEN: a tela abre e DIZ que não conseguiu perguntar."""
    cliente = _dentro()
    respx.get(f"{METRICAS}/cobertura").mock(side_effect=httpx.ConnectError("recusou"))

    resposta = cliente.get(reverse("placar"))

    assert resposta.status_code == 200
    assert "Não consegui perguntar à memória agora." in resposta.content.decode()


@respx.mock
def test_a_memoria_vazia_e_dita_na_tela():
    """O teto de nove blocos não pode ser furado por esta linha."""
    cliente = _dentro()
    respx.get(f"{METRICAS}/cobertura").mock(
        return_value=httpx.Response(
            200, json={"site_id": SITE_ID, "medido_em": "x", "tipos": []}
        )
    )

    corpo = cliente.get(reverse("placar")).content.decode()

    assert "A memória da escola está ligada e ainda não guardou nada." in corpo
