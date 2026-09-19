"""O modo reunião, `/admin/reuniao/` (degrau 3 do plano do painel de gestão).

O que estes guardas protegem:

1. **A pauta lê o mesmo placar**: os oito passos aparecem, com os números que
   `/admin/placar/` mostra, e os passos sem fonte dizem "sem dados".
2. **A tela salva privado**: o POST preserva o pedido para o robô e nenhuma
   chamada de escrita sai daqui (só as leituras da `alunos`).
3. **O pedido para o robô carrega o vocabulário do livro**: tipo
   `compromisso`, `vence_em_dias`, `responde_a`, a restrição confirmada.
4. **Vazio é dito**: sem nenhum campo preenchido, "nada para pedir".
5. **A porta continua sendo a porta**, e o placar leva até aqui.
"""

from __future__ import annotations

import datetime as dt

import httpx
import pytest
import respx
from django.test import Client
from django.urls import get_script_prefix, reverse, set_script_prefix

from apps.core import placar, reuniao

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"
ALUNOS = "http://alunos:8000/api/alunos"
FILA = f"{ALUNOS}/pre-matriculas"
ALUNOS_LISTA = f"{ALUNOS}/matriculas"
HOJE = dt.date(2026, 9, 21)


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    monkeypatch.setenv("ALUNOS_API_URL", ALUNOS)
    monkeypatch.setenv("ALUNOS_API_TOKEN", "token-do-par-admin-alunos")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"
    monkeypatch.setattr(placar.timezone, "localdate", lambda: HOJE)
    monkeypatch.setattr(reuniao.timezone, "localdate", lambda: HOJE)


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


def _a_escola_responde():
    respx.get(FILA, params={"status": "aguardando"}).mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "status": "aguardando",
                    "criada_em": "2026-09-16T12:00:00-03:00",
                    "esperando_ha_dias": 5,
                }
            ],
        )
    )
    respx.get(FILA, params={"status": "recusada"}).mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get(ALUNOS_LISTA).mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "status": "ativa",
                    "origem": "liberado",
                    "criada_em": "2026-09-10T12:00:00-03:00",
                    "virou_aluno_em": "2026-09-11T12:00:00-03:00",
                }
            ],
        )
    )


# ------------------------------------------------------------------ o pedido


def test_o_pedido_carrega_o_vocabulario_do_livro():
    campos = {
        "compromisso1": "Ligar para as 5 pessoas da fila até quarta",
        "compromisso2": "",
        "confirmar_restricao": "a liberação",
        "decisoes": "A meta do mês de outubro fica em 150.",
        "aprendemos": "",
    }
    texto = reuniao.montar_o_pedido(campos, HOJE)
    assert "21/09/2026" in texto
    assert "tipo `compromisso`, vence_em_dias: 7" in texto
    assert "Ligar para as 5 pessoas da fila" in texto
    assert "RESTRIÇÃO CONFIRMADA" in texto and "a liberação" in texto
    assert "restricao-da-semana.json" in texto
    assert "DECISÃO" in texto and "150" in texto
    assert "APRENDIZADO" not in texto
    assert "responde_a" in texto


def test_sem_campos_nao_ha_pedido():
    assert reuniao.montar_o_pedido({}, HOJE) is None
    assert reuniao.montar_o_pedido({"compromisso1": "   "}, HOJE) is None


def test_no_maximo_dois_compromissos_entram_no_pedido():
    campos = {"compromisso1": "a", "compromisso2": "b", "compromisso3": "c"}
    texto = reuniao.montar_o_pedido(campos, HOJE)
    assert texto.count("COMPROMISSO (") == 2


# -------------------------------------------------------------------- a tela


@respx.mock
def test_a_pauta_mostra_os_oito_passos_lidos_do_placar():
    _a_escola_responde()
    html = _dentro().get(reverse("reuniao")).content.decode()
    for numero in range(1, 9):
        assert f"{numero}. " in html
    assert "estamos ganhando" in html
    assert "1 pessoa virou aluna em 09/2026" in html or "virou aluna em 09/2026" in html
    assert "Suspeita: pediu entrada" in html, "a restrição do placar aparece na pauta"
    assert html.count("sem dados") >= 3, "estrelas e doze dizem que não têm fonte"
    assert (
        reverse("laboratorio") in html
    ), "o passo 6 aponta o Laboratório pela rota, não por texto morto"
    assert "Nenhum compromisso nas últimas 4 semanas" in html or "compromisso" in html


@respx.mock
def test_o_post_salva_privado_sem_escrita_remota():
    _a_escola_responde()
    cliente = _dentro()
    formulario = cliente.get(reverse("reuniao")).context["formulario"]
    resposta = cliente.post(
        reverse("reuniao"),
        {
            "formulario": formulario,
            "compromisso1": "Abrir a fila toda manhã",
            "confirmar_restricao": "a liberação",
        },
    )
    assert resposta.status_code == 302
    html = cliente.get(resposta.url).content.decode()
    assert "Pedido privado salvo" in html
    assert "Abrir a fila toda manhã" in html
    assert "tipo `compromisso`" in html
    assert all(c.request.method == "GET" for c in respx.calls), "a reunião só lê"


@respx.mock
def test_o_post_vazio_diz_que_nao_ha_o_que_pedir():
    _a_escola_responde()
    cliente = _dentro()
    formulario = cliente.get(reverse("reuniao")).context["formulario"]
    html = cliente.post(reverse("reuniao"), {"formulario": formulario}).content.decode()
    assert "Nada para pedir" in html


@respx.mock
def test_o_placar_leva_ate_a_reuniao():
    _a_escola_responde()
    html = _dentro().get(reverse("placar")).content.decode()
    assert reverse("reuniao") in html


@respx.mock
def test_sem_cracha_a_pagina_nao_abre():
    respx.get(SESSAO).mock(
        return_value=httpx.Response(200, json={"autenticado": False})
    )
    assert Client().get(reverse("reuniao")).status_code != 200


# ------------------------------------------------------ a porta na capa


@pytest.fixture
def sob_o_prefixo_publico():
    """O regime de produção: a área inteira mora sob `/admin`.

    Mexe no PREFIXO DE SCRIPT, e não em `settings.FORCE_SCRIPT_NAME`, porque é
    o prefixo de thread que `reverse()` lê (`armadilhas/081`). O `finally`
    restaura o anterior: o prefixo vaza entre testes.
    """
    anterior = get_script_prefix()
    set_script_prefix("/admin/")
    try:
        yield
    finally:
        set_script_prefix(anterior)


@respx.mock
def test_a_visao_geral_oferece_a_porta_da_reuniao(sob_o_prefixo_publico):
    """Um botão que ninguém encontra é uma funcionalidade que não existe.

    E o endereço tem de levar o prefixo público: `href="/reuniao/"` abriria
    no PC de quem desenvolve e daria 404 só na tela dele (`armadilhas/081`).
    """
    _a_escola_responde()
    html = _dentro().get("/").content.decode()

    assert "Abrir a pauta da reunião" in html
    assert 'href="/admin/reuniao/"' in html
