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


# ---------------------------------------------------------------------------
# As quatro cartas da gamificação no aviso do celular (degrau 21b, 01/09/2026)
# ---------------------------------------------------------------------------
# Até aqui as quatro caíam no genérico "Você tem um aviso novo": honesto, e sem
# notícia nenhuma. Estes testes medem o que o SERVIDOR entrega, que é a única
# metade mensurável sem um celular na mão — o texto certo, no idioma certo,
# dentro do `/sw.js`.
ASSUNTOS_DA_GAMIFICACAO = (
    "gamificacao.nivel-alcancado",
    "gamificacao.conquista-concedida",
    "gamificacao.marco-validado",
    "gamificacao.destaque-da-semana",
)

#: O que cada assunto diz, nos três idiomas, palavra por palavra. Escrito à mão
#: de propósito: um teste que lesse o mesmo YAML da view passaria com o catálogo
#: inteiro em branco.
FRASES_ESPERADAS = {
    "gamificacao.nivel-alcancado": {
        "en": ("You moved up a level", "Tap to see the step you reached."),
        "pt-br": ("Você subiu de nível", "Toque para ver o degrau que você alcançou."),
        "es": ("Subiste de nivel", "Toca para ver el escalón que alcanzaste."),
    },
    "gamificacao.conquista-concedida": {
        "en": ("You earned a medal", "It is already saved in your profile."),
        "pt-br": ("Você ganhou uma medalha", "Ela já está guardada no seu perfil."),
        "es": ("Ganaste una medalla", "Ya está guardada en tu perfil."),
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
    """Título e corpo próprios, em cada idioma. A escola serve três, e o aviso
    do aparelho sai no idioma de quem INSTALOU (o `?idioma=` que o
    `instalar.js` passa no registro)."""
    textos = _configuracao_do_sw(client, idioma)["textos"]
    titulo, corpo = FRASES_ESPERADAS[assunto][idioma]

    assert textos[assunto] == {"titulo": titulo, "corpo": corpo}


@pytest.mark.parametrize("idioma", ["en", "pt-br", "es"])
def test_nenhuma_carta_da_gamificacao_ficou_com_o_texto_generico(client, rede, idioma):
    """A prova de que o degrau foi de fato subido: se alguém apagar uma linha do
    mapa, o assunto some dos `textos` e o aparelho volta ao genérico. Para estes
    quatro isso é falha, e não é o fail-open do assunto que ninguém conhece."""
    configuracao = _configuracao_do_sw(client, idioma)

    for assunto in ASSUNTOS_DA_GAMIFICACAO:
        assert assunto in configuracao["textos"]
        assert configuracao["textos"][assunto] != configuracao["generico"]


def test_a_frase_do_celular_nunca_pede_um_parametro(client, rede):
    """A decisão de desenho, medida em vez de prometida: o `sw.js` usa `titulo`
    e `corpo` como strings PRONTAS, sem interpolação. Uma frase com `{nivel}`
    dentro chegaria ao celular com a chave crua na tela, porque não há ninguém
    do outro lado para trocá-la — e quase todo parâmetro do contrato é
    opcional, então nem sempre haveria com o que trocar."""
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
    """O fail-ABERTO que não pode ser desfeito: um assunto que esta versão do
    site não conhece tem de continuar sem entrada nos `textos`, para o `sw.js`
    escolher `AVISOS.generico` e a pessoa receber um aviso honesto e vago em vez
    de nenhum.

    E a armadilha específica deste degrau: a forma tentadora de cobrir os quatro
    de uma vez é `assunto.startswith("gamificacao.")`, que passaria a desenhar
    com o cartão do nível um quinto assunto que o contrato ganhe amanhã. Um
    assunto, uma linha, sempre."""
    configuracao = _configuracao_do_sw(client, "pt-br")

    for inventado in (
        "gamificacao.ainda-nao-existe",
        "gamificacao.",
        "matricula.situacao-alterada",
        "jornada.passo",
    ):
        assert inventado not in configuracao["textos"]
    # E o genérico continua lá, preenchido: sem ele o fallback não existiria.
    assert configuracao["generico"]["titulo"] == "Meshcraft"
    assert configuracao["generico"]["corpo"] == "Você tem um aviso novo."


def test_o_service_worker_ainda_sabe_cair_no_generico():
    """A outra metade do fail-aberto mora no arquivo servido, e é uma linha só.
    Sem ela, um assunto desconhecido viraria `undefined.titulo` e o aviso não
    apareceria, que é exatamente o desfecho que o genérico existe para
    impedir."""
    sw = (
        Path(__file__).resolve().parent.parent / "static" / "funil" / "sw.js"
    ).read_text(encoding="utf-8")

    assert "AVISOS.textos[carta.assunto] || AVISOS.generico" in sw


def test_o_aviso_da_sugestao_nao_mudou_uma_virgula(client, rede):
    """O assunto que já existia antes deste degrau. Acrescentar quatro não pode
    reescrever o primeiro: quem instalou o app por causa da Caixa de Sugestões
    continua lendo a mesma frase."""
    configuracao = _configuracao_do_sw(client, "pt-br")

    assert configuracao["textos"]["sugestao.status-alterado"] == {
        "titulo": "Meshcraft",
        "corpo": "Sua sugestão teve uma novidade.",
    }


def test_todo_assunto_que_o_site_conhece_existe_no_contrato(client, rede):
    """A direção segura da cerca: o site nunca inventa um assunto que a
    plataforma não publica. A direção contrária NÃO se testa, de propósito:
    assunto do contrato que ainda não tem frase aqui é justamente o caso do
    genérico, e um teste que o proibisse tornaria impossível acrescentar um
    assunto ao contrato sem tocar nesta célula no mesmo PR."""
    contrato = json.loads(
        (
            Path(__file__).resolve().parents[3]
            / "contracts"
            / "eventos"
            / "notificacao.devida.v1.json"
        ).read_text(encoding="utf-8")
    )
    do_contrato = set(contrato["properties"]["data"]["properties"]["assunto"]["enum"])
    conhecidos = set(_configuracao_do_sw(client, "pt-br")["textos"])

    assert conhecidos, "o site não conhece assunto nenhum"
    assert conhecidos <= do_contrato


def test_o_sw_continua_sem_prefixo_de_idioma_e_com_os_cabecalhos(client, rede):
    """`/sw.js` é rota de MÁQUINA: o escopo de um service worker é a pasta de
    onde ele foi baixado, e `/pt-br/sw.js` mandaria só em `/pt-br/`. O idioma
    vem da query, nunca do caminho. Os dois cabeçalhos são o que faz uma
    correção aqui alcançar quem já instalou."""
    resposta = client.get("/sw.js?idioma=pt-br", HTTP_HOST=HOST_MESH)

    assert resposta.status_code == 200
    assert resposta["Service-Worker-Allowed"] == "/"
    assert resposta["Cache-Control"] == "no-cache"
    assert resposta["Content-Type"] == "text/javascript"
    for prefixo in ("pt-br", "es", "en"):
        assert client.get(f"/{prefixo}/sw.js", HTTP_HOST=HOST_MESH).status_code == 404


# ---------------------------------------------------------------------------
# Quando quem recusou foi o NAVEGADOR (02/09/2026, armadilhas/297)
# ---------------------------------------------------------------------------
# Até aqui o cartaz tinha uma frase só para toda falha: "não deu certo agora,
# tente de novo mais tarde". Ela é honesta quando o NOSSO servidor não
# confirmou, e é promessa falsa quando o navegador é que não conseguiu
# registrar o aparelho — nesse caso tentar amanhã dá exatamente no mesmo,
# porque nada muda sozinho. O mantenedor bateu nisso no próprio site, num
# navegador que bloqueia mensagens push de fábrica, e só descobriu o motivo
# lendo o erro no console.

#: A frase nova, palavra por palavra, nos dois idiomas que o site publica hoje.
#: Escrita à mão de propósito: um teste que lesse o mesmo YAML da view passaria
#: de olhos fechados com o catálogo errado.
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
    """O ponto todo da mudança, medido no HTML entregue: as duas frases são
    DIFERENTES, e só a do nosso lado manda esperar. Se alguém um dia colapsar
    as duas de volta numa chave só, este teste cai."""
    corpo = client.get(
        caminho_mesh("pt-br"), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE
    ).content.decode()

    do_navegador = _frase_da_parte(corpo, "sem-servico")
    do_servidor = _frase_da_parte(corpo, "nao-deu")

    assert do_navegador != do_servidor
    assert "mais tarde" not in do_navegador
    # E a do nosso lado continua sendo a que manda esperar: esperar ali é
    # conselho honesto, porque o que falhou foi o servidor.
    assert "mais tarde" in do_servidor


def test_a_recusa_do_navegador_e_a_do_servidor_tem_caminhos_separados():
    """Medido no arquivo servido, que é a única prova possível sem um aparelho.

    A separação é estrutural, não textual: a recusa do `subscribe` é tratada
    pelo SEGUNDO argumento do `.then`, que só alcança ela. Um `.catch`
    pendurado no fim pegaria junto a falha do `fetch` e desfaria a distinção
    inteira sem mudar uma linha visível — por isso ele é proibido aqui, e por
    isso este teste mede a forma e não a mensagem do erro (que varia entre
    navegador e versão, e nunca deve virar régua)."""
    js = (
        Path(__file__).resolve().parent.parent / "static" / "funil" / "avisos.js"
    ).read_text(encoding="utf-8")

    inscrever = js.split("function inscrever(registro)")[1].split(
        "function aparelhoNaoPode"
    )[0]

    assert "}, aparelhoNaoPode);" in inscrever
    assert ".catch(" not in inscrever
    # Dentro do `inscrever` só existe o desfecho do NOSSO lado; o do navegador
    # mora no tratador próprio, logo abaixo.
    assert 'return "nao-deu";' in inscrever
    assert "sem-servico" not in inscrever
    assert 'return "sem-servico";' in js.split("function aparelhoNaoPode")[1]
    # E o cartaz sabe mostrar a parte nova.
    assert '"sem-servico"' in js.split("function mostrarSo")[1].split("}")[0]
