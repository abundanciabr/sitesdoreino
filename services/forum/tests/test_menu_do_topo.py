"""O menu do topo no fórum: o MESMO menu do site, lido do mesmo lugar.

Cópia do PADRÃO da `funil` (Lei 7), inclusive nos guardas. Cada um corresponde
a uma forma diferente de isto dar errado:

1. **O fórum cair porque o catálogo caiu.** Um menu é enfeite de navegação; o
   fórum tem de abrir igual sem ele, e é este o guarda mais importante do
   arquivo.
2. **O par de tokens ainda não provisionado virar um erro por página.** É o
   estado real enquanto o passo do mantenedor não roda, e ele tem de ser
   silencioso.
3. **A regra "esta página não tem menu" ser ignorada.** Versão vazia numa
   página precisa VENCER a versão padrão do site.
4. **O estilo não chegar ao navegador.** O fórum serve o CSS por rota própria
   (`armadilhas/083`), então classe nova no HTML sem regra no arquivo é um menu
   sem forma, e nada fica vermelho.
"""

import httpx
import pytest
from django.urls import reverse

from apps.core import menu as motor
from apps.forum.models import Area

pytestmark = pytest.mark.django_db

CATALOGO = "http://catalogo:8000/api/catalogo"

# O prefixo público desta célula. Em produção quem o aplica é
# `FORCE_SCRIPT_NAME`, do env; aqui ele entra pelo test client. Sem ele o fórum
# seria servido em `/`, e a regra "o item da área atual some" compararia um
# caminho que não existe em lugar nenhum.
PREFIXO = {"SCRIPT_NAME": "/forum"}

MENU = {
    "default_version": "completo",
    "versions": [
        {
            "slug": "completo",
            "name": "Menu completo",
            "items": [
                {
                    "url": "/",
                    "labels": {"pt-br": "Início", "en": "Home"},
                    "localized": True,
                    "audience": "everyone",
                    "new_tab": False,
                },
                {
                    "url": "/forum/",
                    "labels": {"pt-br": "Fórum", "en": "Forum"},
                    "localized": False,
                    "audience": "everyone",
                    "new_tab": False,
                },
                {
                    "url": "/cadastro",
                    "labels": {"pt-br": "Cadastro", "en": "Sign up"},
                    "localized": True,
                    "audience": "logged_out",
                    "new_tab": False,
                },
            ],
        },
        {"slug": "enxuto", "name": "Só o essencial", "items": []},
    ],
    "pages": [{"page": "forum/buscar", "version": ""}],
}

SITE = {
    "id": "site-mesh",
    "host": "testserver",
    "name": "Meshcraft",
    "active": True,
    "default_language": "pt-br",
    "languages": [{"code": "pt-br"}, {"code": "en"}],
    "menu": MENU,
}


@pytest.fixture(autouse=True)
def cache_limpo(monkeypatch):
    """O cache do menu não pode vazar entre testes: um menu que um teste ensinou
    faria o guarda do teste seguinte passar por herança, não por medição."""
    monkeypatch.setenv("CATALOGO_API_URL", CATALOGO)
    monkeypatch.setenv("TOKEN_CATALOGO", "token-do-par-forum-catalogo")
    motor.limpar_cache()
    yield
    motor.limpar_cache()


@pytest.fixture
def area_publica():
    return Area.objects.create(
        slug="duvidas",
        nome="Dúvidas gerais",
        descricao="Pergunte sem medo.",
        visibilidade=Area.Visibilidade.PUBLICA,
    )


def _menu(corpo: str) -> str:
    """Só o pedaço da barra do site — a página tem rodapé e faixa, e os dois
    também levam a lugares do site."""
    inicio = corpo.index('<nav class="menu-topo">')
    return corpo[inicio : corpo.index("</nav>", inicio)]


def _corpo(resposta) -> str:
    """O corpo, venha ele inteiro ou em pedaços.

    A rota do CSS devolve um `FileResponse`, que NÃO tem `.content` — pedir por
    ele levanta `AttributeError` e o teste fica vermelho por instrumento, não
    por defeito (INV-CI01: não medir não é estar certo). Mesma peça de
    `test_rodape.py`, pelo mesmo motivo.
    """
    if resposta.streaming:
        return b"".join(resposta.streaming_content).decode("utf-8")
    return resposta.content.decode("utf-8")


class Contador:
    """Quantas vezes o catálogo foi consultado. É o que prova o cache."""

    def __init__(self):
        self.chamadas = 0


def dublar_catalogo(monkeypatch, *, site=None, resposta=None, erro=None) -> Contador:
    """O catálogo, dublado por URL — o mesmo padrão de `test_moderacao.py`.

    Dublê por `httpx.Client.get`, e não por respx: o `sem_rede` do conftest já
    troca esse mesmo método para TODO teste, e um respx por baixo dele nunca
    seria alcançado. Duas formas de dublar rede na mesma suíte é uma a mais.
    """
    contador = Contador()

    def falso_get(self, url, **kwargs):
        endereco = str(url)
        if "catalogo" not in endereco:
            raise AssertionError(f"chamada inesperada nesta suíte: {endereco}")
        contador.chamadas += 1
        if erro is not None:
            raise erro
        if resposta is not None:
            return resposta
        return httpx.Response(200, json=site if site is not None else SITE)

    monkeypatch.setattr(httpx.Client, "get", falso_get)
    return contador


# ---------------------------------------------------------------------------
# O fórum abre, tenha menu ou não
# ---------------------------------------------------------------------------


def test_sem_menu_configurado_o_forum_abre_exatamente_como_antes(client, monkeypatch):
    dublar_catalogo(monkeypatch, site=dict(SITE, menu={}))
    resp = client.get(reverse("home"))
    assert resp.status_code == 200
    assert "menu-topo" not in resp.content.decode()


def test_catalogo_fora_do_ar_nao_derruba_o_forum(client, monkeypatch):
    """O guarda mais importante do arquivo: um menu é enfeite de navegação."""
    dublar_catalogo(monkeypatch, erro=httpx.ConnectError("sem rede"))
    resp = client.get(reverse("home"))
    assert resp.status_code == 200
    assert "menu-topo" not in resp.content.decode()


def test_par_de_tokens_ausente_nao_custa_nem_uma_tentativa_de_rede(client, monkeypatch):
    """O estado real enquanto o passo do mantenedor não roda. Silencioso, e sem
    bater na rede: o `sem_rede` do conftest levantaria se alguém tentasse."""
    monkeypatch.delenv("TOKEN_CATALOGO", raising=False)
    resp = client.get(reverse("home"))
    assert resp.status_code == 200
    assert "menu-topo" not in resp.content.decode()


def test_host_desconhecido_no_catalogo_e_forum_sem_menu(client, monkeypatch):
    dublar_catalogo(monkeypatch, resposta=httpx.Response(404))
    resp = client.get(reverse("home"))
    assert resp.status_code == 200
    assert "menu-topo" not in resp.content.decode()


# ---------------------------------------------------------------------------
# Com menu configurado
# ---------------------------------------------------------------------------


def test_o_menu_aparece_na_capa_do_forum(client, monkeypatch):
    dublar_catalogo(monkeypatch)
    corpo = client.get(reverse("home")).content.decode()
    assert '<nav class="menu-topo">' in corpo
    assert "Início" in corpo
    assert 'href="/cadastro"' in corpo


def test_o_rotulo_sai_no_idioma_padrao_do_site(client, monkeypatch):
    """O fórum é monolíngue: o nome do item é o do idioma padrão, e nunca o
    prefixo de idioma — `/pt-br/forum` não existe."""
    dublar_catalogo(monkeypatch)
    corpo = client.get(reverse("home")).content.decode()
    assert "Início" in corpo
    assert "Home" not in corpo
    assert "/pt-br/" not in corpo


def test_o_menu_aparece_tambem_dentro_de_uma_area(client, monkeypatch, area_publica):
    """ "Em todas as páginas" é processador de contexto, não `include` que
    alguém lembra de escrever: tela nova do fórum nasce com menu."""
    dublar_catalogo(monkeypatch)
    corpo = client.get(reverse("area", args=[area_publica.slug])).content.decode()
    assert '<nav class="menu-topo">' in corpo


def test_a_pagina_marcada_sem_menu_nao_mostra_menu(client, monkeypatch):
    """`version: ""` numa página VENCE a versão padrão do site. Cair no padrão
    aqui traria o menu de volta justamente onde ele mandou tirá-lo."""
    dublar_catalogo(monkeypatch)
    corpo = client.get(reverse("buscar")).content.decode()
    assert "menu-topo" not in corpo


def test_versao_apontada_que_sumiu_nao_derruba_a_pagina(client, monkeypatch):
    dublar_catalogo(
        monkeypatch,
        site=dict(
            SITE, menu={"default_version": "fantasma", "versions": [], "pages": []}
        ),
    )
    resp = client.get(reverse("home"))
    assert resp.status_code == 200
    assert "menu-topo" not in resp.content.decode()


def test_o_menu_nao_custa_uma_consulta_por_pagina(client, monkeypatch):
    """Uma ida ao catálogo por janela de cache, não por página aberta."""
    contador = dublar_catalogo(monkeypatch)
    client.get(reverse("home"))
    client.get(reverse("home"))
    client.get(reverse("home"))
    assert contador.chamadas == 1


def test_rotulo_com_marcacao_sai_escapado(client, monkeypatch):
    """O rótulo é texto que uma pessoa digita numa tela de administração."""
    menu = {
        "default_version": "v",
        "versions": [
            {
                "slug": "v",
                "name": "V",
                "items": [
                    {
                        # NÃO a raiz: sem o prefixo público, a home do fórum é
                        # `/` no test client, e um item para `/` sumiria por ser
                        # "a página atual".
                        "url": "/cadastro",
                        "labels": {"pt-br": "<script>alert(1)</script>"},
                        "localized": False,
                        "audience": "everyone",
                        "new_tab": False,
                    }
                ],
            }
        ],
        "pages": [],
    }
    dublar_catalogo(monkeypatch, site=dict(SITE, menu=menu))
    corpo = client.get(reverse("home")).content.decode()
    assert "<script>alert(1)</script>" not in corpo
    assert "&lt;script&gt;" in corpo


def test_o_estilo_do_menu_chega_ao_navegador(client):
    """O fórum serve o CSS por rota própria (`armadilhas/083`): classe nova no
    HTML sem regra no arquivo é um menu sem forma, e nada ficaria vermelho."""
    folha = _corpo(client.get(reverse("estatico", args=["forum.css"])))
    assert ".barra-do-site" in folha
    assert "position: sticky" in folha


# ---------------------------------------------------------------------------
# O item do lugar onde voce ja esta nao aparece (pedido de 01/09/2026)
# ---------------------------------------------------------------------------


def test_no_forum_o_item_forum_some(client, monkeypatch):
    """ "No Fórum ele, obviamente, não mostra o menu Fórum." Um link para onde
    você já está gasta espaço e ensina o aluno a desconfiar do menu."""
    dublar_catalogo(monkeypatch)
    menu = _menu(client.get(reverse("home"), **PREFIXO).content.decode())
    assert "Início" in menu
    assert 'href="/forum/"' not in menu


def test_o_item_forum_some_tambem_DENTRO_do_forum(client, monkeypatch, area_publica):
    """A regra é por ÁREA, não por página exata: numa conversa lá dentro o
    aluno continua no fórum, e o item continua sendo um link para onde ele já
    está."""
    dublar_catalogo(monkeypatch)
    corpo = client.get(
        reverse("area", args=[area_publica.slug]), **PREFIXO
    ).content.decode()
    assert 'href="/forum/"' not in _menu(corpo)
    assert "Início" in _menu(corpo)


def test_o_item_inicio_continua_aparecendo_no_forum(client, monkeypatch):
    """A raiz do site não é "aqui" quando se está no fórum — e sem este guarda
    um tratamento ingênuo de prefixo faria `/` casar com tudo."""
    dublar_catalogo(monkeypatch)
    assert 'href="/"' in _menu(client.get(reverse("home"), **PREFIXO).content.decode())
