"""Ligar o aviso na tela do celular, do lado do site: quem ganha o cartaz, a
rota que liga e desliga, e os textos do aviso injetados no `/sw.js`."""

import json
from pathlib import Path
import re

import httpx
import pytest

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
    """A chave pública do push no ambiente; sem ela o cartaz não existe."""
    monkeypatch.setenv("VAPID_PUBLIC_KEY", CHAVE_PUBLICA)


@pytest.fixture
def notificacoes_configurada(monkeypatch):
    monkeypatch.setenv("NOTIFICACOES_API_URL", NOTIFICACOES)
    monkeypatch.setenv("NOTIFICACOES_API_TOKEN", "token-do-par-funil-notificacoes")


# Quem ganha o cartaz
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
    """Quem não entrou não ganha cartaz: o aviso é de alguém."""
    corpo = client.get(caminho_mesh("pt-br"), HTTP_HOST=HOST_MESH).content.decode()

    assert "avisos-no-celular" not in corpo


def test_sem_chave_configurada_o_cartaz_nao_existe(client, rede, logado):
    """Sem a chave o navegador não consegue se inscrever, então não há cartaz."""
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


# A rota que liga
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
    """A inscrição segue para a `notificacoes` com o id da plataforma, sem e-mail."""
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
    """Se a `notificacoes` não confirma, a rota não responde 200 (responde 502)."""
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
    """Desligar não exige sessão: acontece quando a pessoa está saindo."""
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


# O texto do aviso, injetado no service worker
def test_o_sw_leva_os_textos_no_idioma_de_quem_instalou(client, rede):
    """Os textos viajam para dentro do `/sw.js`, no idioma de quem instalou."""
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
    """O endereço público dos avisos vem desta célula e viaja dentro do `/sw.js`."""
    corpo = client.get("/sw.js", HTTP_HOST=HOST_MESH).content.decode()

    configuracao = json.loads(
        re.search(r"self\.AVISOS_DO_SITE = (\{.*?\});", corpo, re.S).group(1)
    )
    assert configuracao["caminho"].startswith("/")
    assert configuracao["caminho"] != "/"


# As quatro cartas da gamificação no aviso do celular: o servidor entrega o
# texto certo, no idioma certo, dentro do `/sw.js`.
ASSUNTOS_DA_GAMIFICACAO = (
    "gamificacao.nivel-alcancado",
    "gamificacao.conquista-concedida",
    "gamificacao.marco-validado",
    "gamificacao.destaque-da-semana",
)

#: O que cada assunto diz, nos três idiomas, escrito à mão (ler o mesmo YAML
#: da view passaria com o catálogo em branco).
FRASES_ESPERADAS = {
    "gamificacao.nivel-alcancado": {
        "en": ("You moved up a level", "Tap to see the step you reached."),
        "pt-br": ("Você subiu de nível", "Toque para ver o degrau que você alcançou."),
        "es": ("Subiste de nivel", "Toca para ver el escalón que alcanzaste."),
    },
    "gamificacao.conquista-concedida": {
        "en": ("You earned an achievement", "It is already saved in your profile."),
        "pt-br": ("Você ganhou uma conquista", "Ela já está guardada no seu perfil."),
        "es": ("Ganaste un logro", "Ya está guardada en tu perfil."),
    },
    "gamificacao.marco-validado": {
        "en": (
            "Your milestone was accepted",
            "Someone reviewed what you sent, and the milestone is yours.",
        ),
        "pt-br": (
            "Seu marco foi aceito",
            "Alguém conferiu o que você enviou, e o marco agora é seu.",
        ),
        "es": (
            "Tu hito fue aceptado",
            "Alguien revisó lo que enviaste, y el hito ahora es tuyo.",
        ),
    },
    "gamificacao.destaque-da-semana": {
        "en": (
            "Your work was featured",
            "A teacher picked your work for the gallery of the week.",
        ),
        "pt-br": (
            "Sua obra foi destaque",
            "Um professor escolheu o seu trabalho para a galeria da semana.",
        ),
        "es": (
            "Tu obra fue destacada",
            "Un profesor eligió tu trabajo para la galería de la semana.",
        ),
    },
}


def _configuracao_do_sw(client, idioma=None):
    endereco = "/sw.js" if idioma is None else f"/sw.js?idioma={idioma}"
    corpo = client.get(endereco, HTTP_HOST=HOST_MESH).content.decode()
    return json.loads(
        re.search(r"self\.AVISOS_DO_SITE = (\{.*?\});", corpo, re.S).group(1)
    )


@pytest.mark.parametrize("idioma", ["en", "pt-br", "es"])
@pytest.mark.parametrize("assunto", ASSUNTOS_DA_GAMIFICACAO)
def test_as_quatro_cartas_da_gamificacao_falam_os_tres_idiomas(
    client, rede, assunto, idioma
):
    """Título e corpo próprios em cada idioma, o de quem instalou o app."""
    textos = _configuracao_do_sw(client, idioma)["textos"]
    titulo, corpo = FRASES_ESPERADAS[assunto][idioma]

    assert textos[assunto] == {"titulo": titulo, "corpo": corpo}


@pytest.mark.parametrize("idioma", ["en", "pt-br", "es"])
def test_nenhuma_carta_da_gamificacao_ficou_com_o_texto_generico(client, rede, idioma):
    """Nenhuma das quatro cartas cai no texto genérico."""
    configuracao = _configuracao_do_sw(client, idioma)

    for assunto in ASSUNTOS_DA_GAMIFICACAO:
        assert assunto in configuracao["textos"]
        assert configuracao["textos"][assunto] != configuracao["generico"]


def test_a_frase_do_celular_nunca_pede_um_parametro(client, rede):
    """O `sw.js` usa título e corpo como texto pronto, sem interpolação: nenhuma
    frase do celular pede parâmetro."""
    configuracao = _configuracao_do_sw(client, "pt-br")

    frases = [
        valor
        for texto in list(configuracao["textos"].values()) + [configuracao["generico"]]
        for valor in texto.values()
    ]
    assert frases  # senão o teste passaria com o catálogo vazio
    for frase in frases:
        assert "{" not in frase and "}" not in frase
        assert "%s" not in frase and "%(" not in frase


def test_assunto_desconhecido_continua_caindo_no_generico(client, rede):
    """Assunto que o site não conhece fica fora dos `textos`, e o `sw.js` usa
    `AVISOS.generico`; cada assunto tem a sua linha."""
    configuracao = _configuracao_do_sw(client, "pt-br")

    for inventado in (
        "gamificacao.ainda-nao-existe",
        "gamificacao.",
    ):
        assert inventado not in configuracao["textos"]
    # E o genérico continua lá, preenchido: sem ele o fallback não existiria.
    assert configuracao["generico"]["titulo"] == "Meshcraft"
    assert configuracao["generico"]["corpo"] == "Você tem um aviso novo."


def test_o_service_worker_ainda_sabe_cair_no_generico():
    """O `sw.js` ainda cai em `AVISOS.generico` quando o assunto é desconhecido."""
    sw = (
        Path(__file__).resolve().parent.parent / "static" / "funil" / "sw.js"
    ).read_text(encoding="utf-8")

    assert "AVISOS.textos[carta.assunto] || AVISOS.generico" in sw


def test_o_toque_no_aviso_da_sugestao_leva_a_pagina_da_ideia(client, rede):
    configuracao = _configuracao_do_sw(client, "pt-br")

    assert configuracao["links"]["sugestao.status-alterado"] == (
        "/forms/sugestoes/sugestoes/{suggestion_id}"
    )
    assert configuracao["links"]["gamificacao.nivel-alcancado"] == "/conquistas/"
    assert "jornada.passo" not in configuracao["links"]
    sw = (
        Path(__file__).resolve().parent.parent / "static" / "funil" / "sw.js"
    ).read_text(encoding="utf-8")
    assert 'caminho.replace("{suggestion_id}", idDaIdeia)' in sw
    assert "data: { caminho: caminho }" in sw


def test_a_pagina_e_o_celular_usam_a_mesma_tabela_de_assuntos(client, rede):
    from apps.core.notificacoes import TIPOS_POR_ASSUNTO

    assert set(_configuracao_do_sw(client, "pt-br")["textos"]) == set(TIPOS_POR_ASSUNTO)


def test_o_aviso_da_sugestao_nao_mudou_uma_virgula(client, rede):
    """O aviso de sugestão, que já existia, mantém a mesma frase."""
    configuracao = _configuracao_do_sw(client, "pt-br")

    assert configuracao["textos"]["sugestao.status-alterado"] == {
        "titulo": "Meshcraft",
        "corpo": "Sua sugestão teve uma novidade.",
    }


FRASES_DO_PORTFOLIO = {
    "en": {
        "titulo": "Your portfolio was checked",
        "corpo": "The school checked your portfolio. Open your notices to see when.",
    },
    "pt-br": {
        "titulo": "Seu portfólio foi conferido",
        "corpo": "A escola conferiu seu portfólio. Abra os avisos para ver quando.",
    },
    "es": {
        "titulo": "Tu portafolio fue revisado",
        "corpo": "La escuela revisó tu portafolio. Abre tus avisos para ver cuándo.",
    },
}


@pytest.mark.parametrize("idioma", ["en", "pt-br", "es"])
def test_o_aviso_de_portfolio_diz_o_que_aconteceu_e_onde_ver_a_data(
    client, rede, idioma
):
    configuracao = _configuracao_do_sw(client, idioma)

    assert (
        configuracao["textos"]["pages.portfolio-conferido"]
        == FRASES_DO_PORTFOLIO[idioma]
    )


def test_o_sw_continua_sem_prefixo_de_idioma_e_com_os_cabecalhos(client, rede):
    """`/sw.js` não tem prefixo de idioma (o idioma vem da query) e leva os
    cabeçalhos de escopo e de cache."""
    resposta = client.get("/sw.js?idioma=pt-br", HTTP_HOST=HOST_MESH)

    assert resposta.status_code == 200
    assert resposta["Service-Worker-Allowed"] == "/"
    assert resposta["Cache-Control"] == "no-cache"
    assert resposta["Content-Type"] == "text/javascript"
    for prefixo in ("pt-br", "es", "en"):
        assert client.get(f"/{prefixo}/sw.js", HTTP_HOST=HOST_MESH).status_code == 404


# Quando quem recusou foi o navegador: frase própria no cartaz

#: Frase da recusa do navegador, escrita à mão, nos idiomas publicados.
SEM_SERVICO = {
    "pt-br": (
        "Este navegador não conseguiu ligar os avisos. Alguns bloqueiam "
        "mensagens push de fábrica. Veja os ajustes de privacidade dele e "
        "tente de novo."
    ),
    "es": (
        "Este navegador no pudo activar los avisos. Algunos bloquean los "
        "mensajes push de fábrica. Revisa sus ajustes de privacidad y prueba "
        "de nuevo."
    ),
}


def _frase_da_parte(corpo: str, parte: str) -> str:
    achado = re.search(r'data-parte="%s"[^>]*>(.*?)</p>' % parte, corpo, re.S)
    assert achado, f"o cartaz não tem a parte {parte}"
    return achado.group(1).strip()


def test_o_cartaz_tem_um_desfecho_so_para_o_navegador_que_nao_pode(
    client, rede, com_chave, logado
):
    """A frase vem do catálogo, no idioma da página, como as outras três."""
    for idioma, frase in SEM_SERVICO.items():
        corpo = client.get(
            caminho_mesh(idioma), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE
        ).content.decode()

        assert _frase_da_parte(corpo, "sem-servico") == frase


def test_o_desfecho_do_navegador_nao_promete_que_vai_dar_certo_depois(
    client, rede, com_chave, logado
):
    """A frase do navegador difere da do servidor e não manda tentar mais tarde."""
    corpo = client.get(
        caminho_mesh("pt-br"), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE
    ).content.decode()

    do_navegador = _frase_da_parte(corpo, "sem-servico")
    do_servidor = _frase_da_parte(corpo, "nao-deu")

    assert do_navegador != do_servidor
    assert "mais tarde" not in do_navegador
    # Só a frase do servidor manda esperar.
    assert "mais tarde" in do_servidor


# Aviso de teste (botão "Mandar um aviso de teste para mim" em /admin/avisos/):
# texto reconhecível nos três idiomas, sem depender do genérico.

FRASE_DO_TESTE = {
    "en": ("Meshcraft", "It worked. This is the test you asked for."),
    "pt-br": ("Meshcraft", "Deu certo. Este é o teste que você pediu."),
    "es": ("Meshcraft", "Funcionó. Esta es la prueba que pediste."),
}


@pytest.mark.parametrize("idioma", ["en", "pt-br", "es"])
def test_o_aviso_de_teste_fala_os_tres_idiomas(client, rede, idioma):
    textos = _configuracao_do_sw(client, idioma)["textos"]
    titulo, corpo = FRASE_DO_TESTE[idioma]

    assert textos["sistema.teste-de-aviso"] == {"titulo": titulo, "corpo": corpo}


def test_o_aviso_de_teste_nao_ficou_com_o_texto_generico(client, rede):
    """Se a linha do mapa sumir, o aviso de teste volta ao genérico (falha)."""
    configuracao = _configuracao_do_sw(client, "pt-br")

    assert configuracao["textos"]["sistema.teste-de-aviso"] != configuracao["generico"]
