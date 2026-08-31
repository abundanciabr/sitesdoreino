"""Ligar o aviso na tela do celular — o lado do site (Fase 7, 31/08/2026).

A regra de produto, e é ela que quase todo teste aqui mede de um ângulo:
**o navegador só pergunta UMA VEZ.** Permissão negada não tem segunda chance,
então o cartaz só existe para quem já entrou, num site que tem chave
configurada, e a caixa do sistema só abre depois de um toque. Um cartaz
mostrado cedo demais gasta a única pergunta que a plataforma tem.

O que dá para medir daqui é o que o SERVIDOR entrega: quem ganha o cartaz, o
que a rota faz com a inscrição que chega, e os textos do aviso injetados no
`/sw.js` no idioma certo. A outra metade (o aparelho decidindo mostrar) mora em
`static/funil/avisos.js` e não tem como ser medida sem um celular — por isso o
que se mede aqui é que, sem JavaScript, ninguém vê convite nenhum.
"""

import json
import re
from pathlib import Path

import httpx
import pytest
import respx

from tests.conftest import (
    HOST_A,
    HOST_MESH,
    NOTIFICACOES,
    SITE_MESH,
    caminho_mesh,
)
from test_sessao_no_site import COOKIE, logado

CHAVE_PUBLICA = "BPbd0bvtswwjNON4Lv18RDgfuVUx1YAllP6QjuZy12TD9B5V6w1cGMQjPrNGQ90WjcQ4vDJihYZAWPDZ69XsMew"
INSCRICAO = {
    "endpoint": "https://push.exemplo.com/aparelho/abc123",
    "p256dh": "BLc4xRz" + "P" * 80,
    "auth": "tBHItJI5svbpez7KI4CCQ",
}


@pytest.fixture
def com_chave(monkeypatch):
    """A chave PÚBLICA do push no ambiente desta célula. Sem ela o cartaz não
    existe: é o estado de hoje, enquanto o segredo não foi instalado."""
    monkeypatch.setenv("VAPID_PUBLIC_KEY", CHAVE_PUBLICA)


@pytest.fixture
def notificacoes_configurada(monkeypatch):
    monkeypatch.setenv("NOTIFICACOES_API_URL", NOTIFICACOES)
    monkeypatch.setenv("NOTIFICACOES_API_TOKEN", "token-do-par-funil-notificacoes")


# ---------------------------------------------------------------------------
# Quem ganha o cartaz
# ---------------------------------------------------------------------------
def test_quem_entrou_ve_o_cartaz_escondido_esperando_o_aparelho(
    client, rede, com_chave, logado
):
    corpo = client.get(
        caminho_mesh("pt-br"), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE
    ).content.decode()

    assert '<aside id="avisos-no-celular"' in corpo
    assert "hidden" in corpo
    assert f'data-chave="{CHAVE_PUBLICA}"' in corpo
    assert 'data-ligar="/pt-br/avisos/ligar"' in corpo
    assert '<script src="/static/funil/avisos.js" defer></script>' in corpo


def test_visitante_anonimo_nao_ve_o_cartaz(client, rede, com_chave):
    """Um aviso é de alguém. Perguntar a quem não entrou gastaria a única
    pergunta que o navegador permite, e não haveria a quem endereçar."""
    corpo = client.get(caminho_mesh("pt-br"), HTTP_HOST=HOST_MESH).content.decode()

    assert "avisos-no-celular" not in corpo


def test_sem_chave_configurada_o_cartaz_nao_existe(client, rede, logado):
    """Fail-CLOSED, ao contrário do sino: sem a chave o navegador não teria
    como se inscrever, e um botão que não funciona é pior que nenhum botão."""
    corpo = client.get(
        caminho_mesh("pt-br"), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE
    ).content.decode()

    assert "avisos-no-celular" not in corpo


def test_o_site_monolingue_nao_ganhou_cartaz_nenhum(client, rede, com_chave):
    corpo = client.get("/", HTTP_HOST=HOST_A).content.decode()

    assert "avisos-no-celular" not in corpo
    assert "avisos.js" not in corpo


def test_o_cartaz_fala_o_idioma_da_pagina(client, rede, com_chave, logado):
    pt = client.get(
        caminho_mesh("pt-br"), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE
    ).content.decode()
    es = client.get(
        caminho_mesh("es"), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE
    ).content.decode()

    assert "Ligar os avisos" in pt and 'data-ligar="/pt-br/avisos/ligar"' in pt
    assert "Activar los avisos" in es and 'data-ligar="/es/avisos/ligar"' in es


# ---------------------------------------------------------------------------
# A rota que liga
# ---------------------------------------------------------------------------
def _ligar(client, corpo=None, caminho=None):
    return client.post(
        caminho or caminho_mesh("pt-br", "/avisos/ligar"),
        json.dumps(INSCRICAO if corpo is None else corpo),
        "application/json",
        HTTP_HOST=HOST_MESH,
        HTTP_COOKIE=COOKIE,
    )


def test_ligar_repassa_a_inscricao_com_o_id_da_plataforma(
    client, rede, logado, notificacoes_configurada
):
    """O navegador nunca fala com a `notificacoes` direto: o token do par é
    segredo de servidor. E quem endereça é o id da PLATAFORMA, nunca o
    e-mail — ele não atravessa esta fronteira."""
    rota = rede.post(f"{NOTIFICACOES}/inscricoes-push").mock(
        return_value=httpx.Response(200, json={"ja_estava_inscrito": False})
    )

    resposta = _ligar(client)

    assert resposta.status_code == 200
    assert resposta.json() == {"ligado": True}
    enviado = json.loads(rota.calls[0].request.content)
    assert enviado["destinatario_id"] == "idt-de-teste"
    assert enviado["site_id"] == SITE_MESH["id"]
    assert enviado["endpoint"] == INSCRICAO["endpoint"]
    assert "@" not in json.dumps(enviado)  # nenhum e-mail atravessa


def test_ligar_sem_ter_entrado_e_401(client, rede, notificacoes_configurada):
    resposta = client.post(
        caminho_mesh("pt-br", "/avisos/ligar"),
        json.dumps(INSCRICAO),
        "application/json",
        HTTP_HOST=HOST_MESH,
    )

    assert resposta.status_code == 401


@pytest.mark.parametrize("faltando", ["endpoint", "p256dh", "auth"])
def test_inscricao_incompleta_e_422_e_nem_chega_na_rede(
    client, rede, logado, notificacoes_configurada, faltando
):
    corpo = dict(INSCRICAO)
    del corpo[faltando]

    resposta = _ligar(client, corpo)

    assert resposta.status_code == 422
    assert [c for c in rede.calls if "inscricoes-push" in str(c.request.url)] == []


def test_quando_a_caixa_nao_confirma_a_tela_fica_sabendo(
    client, rede, logado, notificacoes_configurada
):
    """ "2xx não é sucesso" (RETROSPECTIVA-FASE-D §1), do lado de cá: se a
    `notificacoes` não confirmou, esta rota NÃO pode responder 200 — a tela
    prometeria avisos que nunca chegariam."""
    rede.post(f"{NOTIFICACOES}/inscricoes-push").mock(
        return_value=httpx.Response(500, text="tudo errado")
    )

    resposta = _ligar(client)

    assert resposta.status_code == 502
    assert resposta.json() == {"ligado": False}


def test_notificacoes_fora_do_ar_nao_derruba_a_pagina_nem_mente(
    client, rede, logado, notificacoes_configurada
):
    rede.post(f"{NOTIFICACOES}/inscricoes-push").mock(
        side_effect=httpx.ConnectError("sem rota para o host")
    )

    assert _ligar(client).status_code == 502


def test_desligar_nao_exige_sessao(client, rede, notificacoes_configurada):
    """Desligar acontece justamente quando a pessoa está saindo. Um aparelho
    que não consegue se desinscrever continuaria recebendo aviso de uma conta
    que já não é usada ali."""
    rota = rede.delete(f"{NOTIFICACOES}/inscricoes-push").mock(
        return_value=httpx.Response(200, json={"existia": True})
    )

    resposta = client.post(
        caminho_mesh("pt-br", "/avisos/desligar"),
        json.dumps({"endpoint": INSCRICAO["endpoint"]}),
        "application/json",
        HTTP_HOST=HOST_MESH,
    )

    assert resposta.status_code == 200
    assert resposta.json() == {"desligado": True}
    assert json.loads(rota.calls[0].request.content)["site_id"] == SITE_MESH["id"]


def test_as_rotas_de_aviso_nao_existem_em_site_monolingue(client, rede):
    for caminho in ("/avisos/ligar", "/avisos/desligar"):
        resposta = client.post(
            caminho, json.dumps({}), "application/json", HTTP_HOST=HOST_A
        )
        assert resposta.status_code == 404


# ---------------------------------------------------------------------------
# O texto do aviso, injetado no service worker
# ---------------------------------------------------------------------------
def test_o_sw_leva_os_textos_no_idioma_de_quem_instalou(client, rede):
    """A frase nasce na LEITURA, e a leitura acontece no aparelho: por isso os
    textos viajam para dentro do `/sw.js` (DECISAO-notificacoes §5.1)."""
    corpo = client.get("/sw.js?idioma=pt-br", HTTP_HOST=HOST_MESH).content.decode()

    configuracao = json.loads(
        re.search(r"self\.AVISOS_DO_SITE = (\{.*?\});", corpo, re.S).group(1)
    )
    assert (
        configuracao["textos"]["sugestao.status-alterado"]["corpo"]
        == "Sua sugestão teve uma novidade."
    )
    assert configuracao["generico"]["corpo"] == "Você tem um aviso novo."
    # E o arquivo continua inteiro depois da injeção.
    assert 'self.addEventListener("push"' in corpo


def test_idioma_desconhecido_no_sw_cai_no_idioma_fonte(client, rede):
    corpo = client.get("/sw.js?idioma=zz", HTTP_HOST=HOST_MESH).content.decode()

    assert "You have a new notice." in corpo
    assert "zz" not in corpo.split("self.AVISOS_DO_SITE = ")[1].split(";")[0]


def test_o_toque_no_aviso_leva_a_pagina_de_avisos(client, rede):
    """O endereço público é conhecimento DESTA célula
    (`apps/core/enderecos.py`), nunca da `notificacoes`: é por isso que ele
    viaja daqui, e não junto do envio."""
    corpo = client.get("/sw.js", HTTP_HOST=HOST_MESH).content.decode()

    configuracao = json.loads(
        re.search(r"self\.AVISOS_DO_SITE = (\{.*?\});", corpo, re.S).group(1)
    )
    assert configuracao["caminho"].startswith("/")
    assert configuracao["caminho"] != "/"


def test_nenhum_pedido_de_permissao_abre_sem_um_toque():
    """A regra que o incidente de 31/08/2026 tornou inegociável: o pedido de
    permissão automático ("abre sozinho onde o navegador deixa", registro
    20260831-075) fez o Malwarebytes Browser Guard bloquear o meshcraft.top
    INTEIRO como site malicioso, por "excesso de solicitação de notificações",
    no dia da inauguração (armadilhas/257). Pedir sem gesto, página após
    página, é a assinatura que as ferramentas de segurança caçam.

    Medido no arquivo servido, que é a única prova possível sem um celular:
    só existe UM `requestPermission`, e o único lugar que o alcança é o
    clique no botão do cartaz. Não recrie o caminho automático."""
    js = (
        Path(__file__).resolve().parent.parent / "static" / "funil" / "avisos.js"
    ).read_text(encoding="utf-8")

    assert "abreSozinho" not in js
    assert js.count("Notification.requestPermission") == 1

    corpo = js.replace("function pedirPermissao(registro)", "", 1)
    assert corpo.count("pedirPermissao(registro)") == 1
    clique = corpo.index('botao.addEventListener("click"')
    assert corpo.index("pedirPermissao(registro)") > clique


def test_o_cartaz_com_botao_e_o_unico_caminho_em_todo_navegador():
    """O convite é um cartaz NOSSO, dentro da página: elemento comum, que
    nenhuma ferramenta de segurança confunde com a caixa do sistema. A caixa
    do navegador só nasce do toque no botão, e isso vale para Chrome, Android,
    iPhone e Firefox por igual."""
    js = (
        Path(__file__).resolve().parent.parent / "static" / "funil" / "avisos.js"
    ).read_text(encoding="utf-8")

    assert 'mostrarSo("convite")' in js
    assert '[data-acao="ligar-avisos"]' in js
    # E a recusa educada continua existindo: o "depois" silencia por 30 dias.
    assert '[data-acao="avisos-depois"]' in js


def test_o_service_worker_promete_um_aviso_visivel_por_push():
    """`userVisibleOnly` do lado do site, `showNotification` do lado do worker:
    a promessa que o navegador cobra. Um push que não vira aviso visível faz o
    navegador mostrar a mensagem genérica dele e, repetido, tira a permissão do
    site."""
    sw = (
        Path(__file__).resolve().parent.parent / "static" / "funil" / "sw.js"
    ).read_text(encoding="utf-8")
    js = (
        Path(__file__).resolve().parent.parent / "static" / "funil" / "avisos.js"
    ).read_text(encoding="utf-8")

    assert "showNotification" in sw
    assert "userVisibleOnly: true" in js
