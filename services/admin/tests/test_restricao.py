"""A restrição desta semana (degrau 1 do plano do painel de gestão).

O que estes guardas protegem:

1. **Etapa sem dados nunca vira restrição**, e a tela nomeia as que faltam.
2. **"Não medi" se declara**: uma lista que não chegou ⇒ `nao-consigo-medir`,
   nunca "sem restrição" (que se leria como "está tudo bem").
3. **A regra da suspeita é a escrita, e não outra**: fila parada há 2 dias ou
   mediana acima de 2 dias ⇒ liberação; ninguém pediu em 28 dias ⇒ entrada;
   senão, sem restrição medível.
4. **A medição é pela data certa e no fuso certo**, e reembolsada não conta
   como liberada.
5. **A tela mostra a suspeita, o gesto e a confiança**, e diz "aguardando a
   sua confirmação" enquanto o cartão não tem `confirmada`.
"""

from __future__ import annotations

import datetime as dt

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.core import placar, restricao

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"
ALUNOS = "http://alunos:8000/api/alunos"
FILA = f"{ALUNOS}/pre-matriculas"
ALUNOS_LISTA = f"{ALUNOS}/matriculas"

HOJE = dt.date(2026, 9, 20)


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    monkeypatch.setenv("ALUNOS_API_URL", ALUNOS)
    monkeypatch.setenv("ALUNOS_API_TOKEN", "token-do-par-admin-alunos")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"
    monkeypatch.setattr(placar.timezone, "localdate", lambda: HOJE)


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
    c = Client()
    c.defaults["HTTP_COOKIE"] = COOKIE
    return c


def _em(dia: str, hora: str = "12:00") -> str:
    return f"{dia}T{hora}:00-03:00"


def _pedido(dia: str, esperando: int) -> dict:
    return {
        "status": "aguardando",
        "criada_em": _em(dia),
        "esperando_ha_dias": esperando,
    }


def _liberada(pediu: str, liberou: str, status: str = "ativa") -> dict:
    return {
        "status": status,
        "origem": "liberado",
        "criada_em": _em(pediu),
        "virou_aluno_em": _em(liberou),
    }


# ------------------------------------------------------------------ a medida


def test_mede_pedidos_liberacoes_e_a_mediana_na_janela():
    aguardando = [_pedido("2026-09-19", 1), _pedido("2026-09-15", 5)]
    recusados = [{"status": "recusada", "criada_em": _em("2026-09-10")}]
    alunos = [
        _liberada("2026-09-10", "2026-09-11"),
        _liberada("2026-09-12", "2026-09-15"),
        _liberada("2026-08-01", "2026-08-02"),  # fora da janela de 28 dias
        _liberada("2026-09-13", "2026-09-14", status="reembolsada"),  # não conta
        {
            "status": "ativa",
            "origem": "comprou",
            "criada_em": _em("2026-09-18"),
            "virou_aluno_em": _em("2026-09-18"),
        },
    ]
    m = restricao.medir_liberacao(aguardando, recusados, alunos, HOJE)
    assert m["pedidos_28"] == 5  # 2 esperando + 1 recusado + 2 liberados na janela
    assert m["pedidos_7"] == 2  # 19/09 e 15/09
    assert m["liberados_28"] == 2 and m["liberados_7"] == 1
    assert m["esperando"] == 2 and m["esperando_ha_muito"] == 1
    assert m["mediana_dias"] == 2  # esperas de 1 e 3 dias
    assert m["taxa_28"] == 0.4


def test_lista_que_nao_chegou_nao_vira_medida():
    assert restricao.medir_liberacao(None, [], [], HOJE) is None
    assert restricao.medir_liberacao([], None, [], HOJE) is None
    assert restricao.medir_liberacao([], [], None, HOJE) is None


def test_o_dia_e_o_de_sao_paulo():
    """02:00Z de 20/09 ainda é 19/09 em São Paulo: um pedido de ontem, não de hoje."""
    aguardando = [
        {
            "status": "aguardando",
            "criada_em": "2026-09-20T02:00:00Z",
            "esperando_ha_dias": 1,
        }
    ]
    m = restricao.medir_liberacao(aguardando, [], [], HOJE)
    assert m["pedidos_7"] == 1


# ---------------------------------------------------------------- a suspeita


CARTAO = {"confirmada": None}


def test_fila_parada_ha_dois_dias_e_a_liberacao():
    m = {
        "pedidos_28": 3,
        "pedidos_7": 1,
        "liberados_28": 1,
        "liberados_7": 0,
        "esperando": 2,
        "esperando_ha_muito": 1,
        "mediana_dias": 1,
        "taxa_28": 0.33,
    }
    r = restricao.escolher_restricao(m, CARTAO)
    assert r["veredito"] == "liberacao" and r["etapa"] == "liberacao"
    assert r["confianca"] == "alta" and r["impacto"] == 2
    assert "fila" in r["gesto"]


def test_mediana_acima_de_dois_dias_e_a_liberacao_mesmo_sem_fila_parada():
    m = {
        "pedidos_28": 4,
        "pedidos_7": 2,
        "liberados_28": 4,
        "liberados_7": 2,
        "esperando": 0,
        "esperando_ha_muito": 0,
        "mediana_dias": 3,
        "taxa_28": 1.0,
    }
    assert restricao.escolher_restricao(m, CARTAO)["veredito"] == "liberacao"


def test_ninguem_pediu_em_28_dias_e_a_entrada():
    m = {
        "pedidos_28": 0,
        "pedidos_7": 0,
        "liberados_28": 0,
        "liberados_7": 0,
        "esperando": 0,
        "esperando_ha_muito": 0,
        "mediana_dias": None,
        "taxa_28": None,
    }
    r = restricao.escolher_restricao(m, CARTAO)
    assert r["veredito"] == "entrada" and r["confianca"] == "media"


def test_liberacao_em_dia_e_sem_restricao_medivel_e_nao_tudo_bem():
    m = {
        "pedidos_28": 5,
        "pedidos_7": 2,
        "liberados_28": 5,
        "liberados_7": 2,
        "esperando": 1,
        "esperando_ha_muito": 0,
        "mediana_dias": 1,
        "taxa_28": 1.0,
    }
    r = restricao.escolher_restricao(m, CARTAO)
    assert r["veredito"] == "sem-restricao-medivel"
    assert r["etapa"] is None
    sem_fonte = [e for e in r["etapas"] if e["fonte"] is None]
    assert len(sem_fonte) == 3, "as três etapas sem dados continuam nomeadas"


def test_sem_medida_e_nao_consigo_medir_e_nunca_sem_restricao():
    r = restricao.escolher_restricao(None, CARTAO)
    assert r["veredito"] == "nao-consigo-medir"


def test_a_confirmacao_vem_do_cartao():
    conf = {"etapa": "liberacao", "em": "2026-09-07", "registro": "20260907-001-x"}
    r = restricao.escolher_restricao(None, {"confirmada": conf})
    assert r["confirmada"] == conf


def test_o_cartao_do_repositorio_e_valido_e_e_de_direcao():
    cartao, problemas = placar.ler_cartao("restricao-da-semana")
    assert cartao is not None, problemas
    assert cartao["tipo"] == "direcao" and cartao["andar"] == 0
    assert cartao["par"] == placar.CARTAO_DA_META


# -------------------------------------------------------------------- a tela


def _a_escola_responde(aguardando, recusados, alunos):
    respx.get(FILA, params={"status": "aguardando"}).mock(
        return_value=httpx.Response(200, json=aguardando)
    )
    respx.get(FILA, params={"status": "recusada"}).mock(
        return_value=httpx.Response(200, json=recusados)
    )
    respx.get(ALUNOS_LISTA).mock(return_value=httpx.Response(200, json=alunos))


@respx.mock
def test_a_tela_mostra_a_restricao_o_gesto_e_pede_confirmacao():
    _a_escola_responde(
        [_pedido("2026-09-15", 5), _pedido("2026-09-19", 1)],
        [],
        [_liberada("2026-09-10", "2026-09-11")],
    )
    html = _dentro().get(reverse("placar")).content.decode()
    assert "A restrição desta semana" in html
    assert "pediu entrada → foi liberada" in html
    assert "Abra a fila" in html
    assert "aguardando a sua confirmação" in html
    assert "cadastrou → pediu entrada" in html, "as etapas sem dados são nomeadas"
    assert "2 pessoas esperando na fila" in html
    assert "1 há 2 dias ou mais" in html
    assert "+2" in html, "o impacto é a fila inteira: cada pessoa parada é +1 na meta"


@respx.mock
def test_a_fila_fora_do_ar_diz_que_nao_mediu():
    respx.get(FILA).mock(side_effect=httpx.ConnectError("recusou"))
    respx.get(ALUNOS_LISTA).mock(return_value=httpx.Response(200, json=[]))
    html = _dentro().get(reverse("placar")).content.decode()
    assert "não consegui medir a restrição" in html
    assert "sem restrição" not in html.lower()
