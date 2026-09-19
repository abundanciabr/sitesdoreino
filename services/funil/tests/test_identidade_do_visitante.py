"""O número opaco que diz "este navegador já esteve aqui".

Primeiro degrau da telemetria do funil (19/09/2026): antes de `pedido.criado` a
plataforma é cega, e sem identidade estável do visitante anônimo nenhuma
medição de funil fecha e nenhuma atribuição de venda funciona.

Cinco coisas são guardadas aqui, e cada uma corresponde a uma forma diferente
de esta entrega dar errado:

1. **Quem volta é o mesmo.** Reescrever o cookie a cada visita apagaria
   exatamente o que ele existe para medir, e o site continuaria bonito:
   todo visitante recorrente viraria um visitante novo, em silêncio.
2. **O script da página não lê o número.** Cookie de identidade legível por
   JavaScript é cookie roubável por JavaScript.
3. **Rota de máquina não ganha cookie.** `Set-Cookie` numa resposta de
   `/static/` é cache envenenado esperando acontecer.
4. **Cookie adulterado não derruba nada e não vale como identidade.** O valor
   vem do navegador, e o navegador é do outro lado.
5. **Sessão e prévia da equipe seguem intactas.** Esta célula não assina
   `meshcraft_sessao` (quem assina é `identidade`) e o disfarce continua
   gravando o cookie dele, do jeito que gravava.
"""

import uuid

import pytest
from django.http import HttpResponse
from django.test import RequestFactory

from test_categorias_na_home import com_email  # noqa: F401  (fixture do da_equipe)
from test_sessao_no_site import COOKIE as COOKIE_DE_SESSAO  # o da outra célula
from test_sessao_no_site import logado  # noqa: F401  (fixture)
from test_ver_como import TELA, da_equipe  # noqa: F401  (fixture)
from tests.conftest import HOST_A, HOST_DESCONHECIDO, HOST_MESH

from apps.core import visitante

HOME = "/pt-br/"


def _numero(resposta) -> str:
    return resposta.cookies[visitante.COOKIE].value


# ---------------------------------------------------------------------------
# 1. Primeira visita ganha número; quem volta continua o mesmo
# ---------------------------------------------------------------------------
def test_a_primeira_visita_ganha_um_numero_novo_e_opaco(client, rede):
    resposta = client.get(HOME, HTTP_HOST=HOST_MESH)

    assert resposta.status_code == 200
    numero = _numero(resposta)
    assert visitante.id_valido(numero) == numero, (
        f"o cookie saiu com {numero!r}, que não é um UUID4 canônico: o número "
        "é sorteado justamente para não descrever ninguém"
    )


def test_a_view_ja_enxerga_o_numero_antes_de_montar_a_pagina():
    """Espião no lugar da view, e não `resposta.wsgi_request`.

    O segundo olha o objeto DEPOIS de tudo pronto, e ficaria verde mesmo se o
    número fosse escrito no request só na volta. Quem precisa dele é o CORPO
    do HTML: o cookie é `HttpOnly`, então é o servidor que entrega o número à
    telemetria do navegador, e o corpo do HTML nasce dentro da view.
    """
    visto = {}

    def espiao(request):
        visto["numero"] = getattr(request, "id_do_visitante", None)
        return HttpResponse("ok")

    pedido = RequestFactory().get("/", HTTP_HOST=HOST_MESH)
    resposta = visitante.IdentidadeDoVisitante(espiao)(pedido)

    assert visitante.id_valido(visto["numero"] or "")
    assert visto["numero"] == resposta.cookies[visitante.COOKIE].value


def test_quem_volta_com_o_cookie_e_o_mesmo_visitante(client, rede):
    """A guarda central. O `client` do Django guarda os cookies da resposta e
    os reenvia sozinho, que é exatamente o que o navegador faz."""
    primeira = client.get(HOME, HTTP_HOST=HOST_MESH)
    numero = _numero(primeira)

    segunda = client.get("/pt-br/cadastro", HTTP_HOST=HOST_MESH)

    assert visitante.COOKIE not in segunda.cookies, (
        "a segunda visita reescreveu o cookie — reescrever apaga justamente o "
        "que ele serve para medir, e todo visitante recorrente viraria novo"
    )
    assert segunda.wsgi_request.id_do_visitante == numero


def test_quem_entrou_tambem_tem_numero_de_visitante(client, logado):  # noqa: F811
    """O visitante anônimo é ortogonal à pessoa logada: as duas perguntas são
    diferentes, e a resposta de uma não substitui a da outra."""
    resposta = client.get(HOME, HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE_DE_SESSAO)

    assert visitante.id_valido(_numero(resposta))


# ---------------------------------------------------------------------------
# 2. O script da página não lê o número
# ---------------------------------------------------------------------------
def test_o_cookie_e_httponly_lax_e_de_validade_longa(client, rede):
    """O `Secure` não é medido aqui: ele depende do `X-Forwarded-Proto` que o
    Traefik encaminha, e quem exercita isso é
    `tests/test_inv_secure_nos_cookies.py`. Medi-lo nesta requisição sem
    cabeçalho seria medir uma constante."""
    morsel = client.get(HOME, HTTP_HOST=HOST_MESH).cookies[visitante.COOKIE]

    assert morsel["httponly"], (
        "o cookie saiu legível por JavaScript — cookie de identidade legível "
        "por script é cookie roubável por script"
    )
    assert morsel["samesite"] == "Lax"
    assert int(morsel["max-age"]) == visitante.VALIDADE_EM_SEGUNDOS


# ---------------------------------------------------------------------------
# 3. Rota de máquina não ganha cookie
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("caminho", "host"),
    [
        ("/healthz", HOST_A),
        ("/static/funil/api.js", HOST_A),
        ("/sw.js", HOST_MESH),
        ("/sitemap.xml", HOST_MESH),
        ("/manifest.webmanifest", HOST_MESH),
    ],
)
def test_rota_de_maquina_nao_ganha_cookie(client, rede, caminho, host):
    """Sonda, estático e arquivo de robô não são gente. `Set-Cookie` numa
    resposta de `/static/` é cache envenenado esperando acontecer, e num
    `/sitemap.xml` é um número de visitante gasto com um rastreador."""
    resposta = client.get(caminho, HTTP_HOST=host)

    assert resposta.status_code == 200
    assert visitante.COOKIE not in resposta.cookies


def test_o_numero_viaja_no_redirecionamento_da_barra_no_final(client, rede):
    """Quem chegou por `/pt-br/cadastro/` (barra a mais, coisa que o navegador
    e o histórico fazem sozinhos) já sai do 302 com o número.

    É o que a posição deste middleware ANTES do `BarraNoFinal` compra, e está
    escrita na lista do `settings.py`. Sem a prova, a frase de lá é palpite.
    """
    resposta = client.get("/pt-br/cadastro/", HTTP_HOST=HOST_MESH)

    assert resposta.status_code == 302
    assert resposta["Location"] == "/pt-br/cadastro"
    assert visitante.id_valido(_numero(resposta))


def test_host_nao_cadastrado_nao_ganha_numero(client, rede):
    """[INV-P11]: host desconhecido é 404, nunca um site padrão. Um número de
    visitante entregue ali seria identidade gasta com domínio que não é nosso."""
    resposta = client.get("/", HTTP_HOST=HOST_DESCONHECIDO)

    assert resposta.status_code == 404
    assert visitante.COOKIE not in resposta.cookies


# ---------------------------------------------------------------------------
# 4. Cookie adulterado
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "forjado",
    [
        "nao-sou-um-uuid",
        "",
        "<script>alert(1)</script>",
        "00000000-0000-1000-8000-000000000000",  # UUID1: não é o que emitimos
        "6F9619FF-8B86-4D011-B42D-00CF4FC964FF",  # nem UUID nenhum
        str(uuid.uuid4()).upper(),  # forma não canônica do que emitimos
        "urn:uuid:" + str(uuid.uuid4()),
        str(uuid.uuid4()).replace("-", ""),
    ],
)
def test_cookie_forjado_nao_derruba_a_pagina_nem_vira_identidade(client, rede, forjado):
    client.cookies[visitante.COOKIE] = forjado

    resposta = client.get(HOME, HTTP_HOST=HOST_MESH)

    assert resposta.status_code == 200, "um cookie de lixo derrubou a vitrine"
    assert (
        resposta.wsgi_request.id_do_visitante != forjado
    ), f"{forjado!r} veio do navegador e foi aceito como identidade"
    assert visitante.id_valido(_numero(resposta)), (
        "o lixo não foi substituído por um número nosso, e este visitante "
        "nunca seria contado"
    )


# ---------------------------------------------------------------------------
# 5. Sessão e prévia da equipe seguem intactas
# ---------------------------------------------------------------------------
def test_o_funil_continua_sem_assinar_o_cookie_de_sessao(client, rede):
    """Quem assina `meshcraft_sessao` é a `identidade`, e continua sendo ela.
    O número do visitante mora num cookie próprio, com outro nome."""
    resposta = client.get(HOME, HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE_DE_SESSAO)

    assert "meshcraft_sessao" not in resposta.cookies
    assert visitante.COOKIE != "meshcraft_sessao"


def test_a_previa_da_equipe_continua_gravando_o_disfarce(
    client, da_equipe
):  # noqa: F811
    """O fluxo do `ver_como` não mudou: o POST grava o cookie dele, com os
    atributos dele. O número do visitante entra ao lado, nunca no lugar."""
    from apps.core import ver_como

    resposta = client.post(
        TELA,
        {"como": "aluno"},
        HTTP_HOST=HOST_MESH,
        HTTP_COOKIE=COOKIE_DE_SESSAO,
    )

    assert resposta.status_code == 302
    disfarce = resposta.cookies[ver_como.COOKIE]
    assert disfarce.value == "aluno"
    assert disfarce["httponly"]
    assert disfarce["samesite"] == "Lax"
    # Sem `max-age`: o disfarce morre quando o navegador fecha, e a validade
    # longa do visitante não pode ter contaminado isso.
    assert disfarce["max-age"] == ""
