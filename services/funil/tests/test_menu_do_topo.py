"""O menu do topo desenhado nas páginas públicas.

O menu é DADO DO SITE: ele chega no mesmo `getSiteByHost` que o CONV-SITE já
buscava, e é o mantenedor quem o escreve pela tela do Admin. Estes testes
provam o que a célula faz com esse dado, e o que ela faz quando ele está
ausente, incompleto ou torto.

A regra que atravessa todos: **falhar para o lado de "sem menu"**. Um menu é
enfeite de navegação; derrubar a vitrine porque um item está errado seria a
troca errada.
"""

import httpx
import pytest

from tests.conftest import (
    CATALOGO,
    HOST_A,
    HOST_MESH,
    SITE_A,
    SITE_MESH,
    caminho_mesh,
)

# O mesmo crachá opaco que a célula repassa sem interpretar (ela não conhece o
# nome do cookie da identidade, e não deve conhecer).
COOKIE = "meshcraft_sessao=valor-opaco-que-o-funil-nao-interpreta"


@pytest.fixture
def logado(rede):
    """Alguém entrou. A resposta é EXATAMENTE a do contrato, nada além."""
    rede["get_session"].mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "idt-de-teste",
                "nome_exibido": "Quem Entrou",
                "papel": "aluno",
            },
        )
    )
    return rede


MENU = {
    "default_version": "completo",
    "versions": [
        {
            "slug": "completo",
            "name": "Menu completo",
            "items": [
                {
                    "url": "/",
                    "labels": {"pt-br": "Início", "en": "Home", "es": "Inicio"},
                    "localized": True,
                    "audience": "everyone",
                    "new_tab": False,
                },
                {
                    "url": "/forum",
                    "labels": {"pt-br": "Fórum", "en": "Forum", "es": "Foro"},
                    "localized": False,
                    "audience": "everyone",
                    "new_tab": False,
                },
                {
                    "url": "/cadastro",
                    "labels": {"pt-br": "Cadastro", "en": "Sign up", "es": "Registro"},
                    "localized": True,
                    "audience": "logged_out",
                    "new_tab": False,
                },
            ],
        },
        {
            "slug": "enxuto",
            "name": "Só o essencial",
            "items": [
                {
                    "url": "/",
                    "labels": {"pt-br": "Início", "en": "Home", "es": "Inicio"},
                    "localized": True,
                    "audience": "everyone",
                    "new_tab": False,
                }
            ],
        },
    ],
    "pages": [
        {"page": "funil/cadastro", "version": "enxuto"},
        {"page": "funil/login", "version": ""},
    ],
}


def com_menu(rede, site: dict, host: str, menu: dict = None):
    """Reensina o catálogo a servir este site COM menu.

    A configuração viaja dentro do Site, então o mock é o mesmo de sempre com
    uma chave a mais — é literalmente o que o provedor faz.
    """
    resposta = dict(site, menu=MENU if menu is None else menu)
    rede.get(f"{CATALOGO}/sites/by-host/{host}").mock(
        return_value=httpx.Response(200, json=resposta)
    )
    return resposta


# ---------------------------------------------------------------------------
# Sem configuração, nada muda
# ---------------------------------------------------------------------------


def test_site_sem_menu_nao_desenha_nada(client, rede):
    """O caso de hoje, e o mais importante: a ausência de menu não pode virar
    uma tag vazia nem um estilo a mais. É a mesma garantia que a regressão
    byte-a-byte de `test_i18n_http.py` protege pelo outro lado."""
    corpo = client.get("/", HTTP_HOST=HOST_A).content.decode()
    assert "menu-topo" not in corpo


def test_menu_configurado_mas_sem_versao_padrao_nao_desenha(client, rede):
    """Menu escrito e nenhuma versão apontada é uma configuração legítima: o
    mantenedor pode ter tirado o menu do site inteiro sem apagar o que
    escreveu."""
    com_menu(rede, SITE_A, HOST_A, menu=dict(MENU, default_version="", pages=[]))
    corpo = client.get("/", HTTP_HOST=HOST_A).content.decode()
    assert "menu-topo" not in corpo


def test_versao_apontada_que_sumiu_nao_derruba_a_pagina(client, rede):
    """Falha para o lado de 'sem menu': a página abre 200 e sem menu, em vez de
    500 por causa de um apelido órfão."""
    com_menu(
        rede,
        SITE_A,
        HOST_A,
        menu={"default_version": "fantasma", "versions": [], "pages": []},
    )
    resp = client.get("/", HTTP_HOST=HOST_A)
    assert resp.status_code == 200
    assert "menu-topo" not in resp.content.decode()


# ---------------------------------------------------------------------------
# Com configuração: a página, o idioma e quem lê
# ---------------------------------------------------------------------------


def test_o_menu_aparece_na_pagina_inicial(client, rede):
    com_menu(rede, SITE_A, HOST_A)
    corpo = client.get("/", HTTP_HOST=HOST_A).content.decode()
    assert '<nav class="menu-topo">' in corpo
    assert "Cadastro" in corpo


def test_a_pagina_marcada_sem_menu_nao_mostra_menu(client, rede):
    """A metade do pedido do mantenedor que é fácil de perder: `version: ""`
    numa página tem de VENCER a versão padrão do site, não cair nela."""
    com_menu(rede, SITE_MESH, HOST_MESH)
    corpo = client.get("/login", HTTP_HOST=HOST_MESH).content.decode()
    assert "menu-topo" not in corpo


def test_cada_pagina_pode_ter_uma_versao_diferente(client, rede):
    """A outra metade: a mesma configuração desenha menus diferentes em páginas
    diferentes."""
    com_menu(rede, SITE_MESH, HOST_MESH)
    inicial = client.get("/", HTTP_HOST=HOST_MESH).content.decode()
    cadastro = client.get("/cadastro", HTTP_HOST=HOST_MESH).content.decode()
    assert "Forum" in so_o_menu(inicial)  # versão completa (o site nasce em inglês)
    assert "menu-topo" in cadastro
    assert "Forum" not in so_o_menu(cadastro)  # versão enxuta: só a página inicial


@pytest.mark.parametrize(
    "idioma,inicio,cadastro",
    [
        ("en", "Home", "Sign up"),
        ("pt-br", "Início", "Cadastro"),
        ("es", "Inicio", "Registro"),
    ],
)
def test_o_rotulo_sai_no_idioma_de_quem_le(client, rede, idioma, inicio, cadastro):
    com_menu(rede, SITE_MESH, HOST_MESH)
    corpo = client.get(caminho_mesh(idioma), HTTP_HOST=HOST_MESH).content.decode()
    assert inicio in corpo
    assert cadastro in corpo


def test_link_traduzido_ganha_o_prefixo_e_o_de_outra_celula_nao(client, rede):
    """A armadilha do R12, e a razão de `localized` ser um dado e não um
    palpite: `/pt-br/cadastro` existe, `/pt-br/forum` é 404 — e o erro só
    apareceria fora do idioma padrão, que não é o que se abre para conferir."""
    com_menu(rede, SITE_MESH, HOST_MESH)
    corpo = client.get(caminho_mesh("pt-br"), HTTP_HOST=HOST_MESH).content.decode()
    assert 'href="/pt-br/cadastro"' in corpo
    assert 'href="/forum"' in corpo
    assert "/pt-br/forum" not in corpo


def test_no_idioma_padrao_o_link_nasce_sem_prefixo(client, rede):
    """D1 revisto: `/en/cadastro` não existe no meshcraft, é 404."""
    com_menu(rede, SITE_MESH, HOST_MESH)
    corpo = client.get("/", HTTP_HOST=HOST_MESH).content.decode()
    assert 'href="/cadastro"' in corpo
    assert "/en/cadastro" not in corpo


def test_rotulo_faltando_no_idioma_cai_no_padrao_do_site(client, rede):
    """Idioma novo num site com itens já escritos: melhor o item aparecer no
    idioma padrão do que sumir do menu sem ninguém entender por quê."""
    menu = {
        "default_version": "v",
        "versions": [
            {
                "slug": "v",
                "name": "V",
                "items": [
                    {
                        "url": "/",
                        "labels": {"en": "Home"},  # sem pt-br
                        "localized": True,
                        "audience": "everyone",
                        "new_tab": False,
                    }
                ],
            }
        ],
        "pages": [],
    }
    com_menu(rede, SITE_MESH, HOST_MESH, menu=menu)
    # Medido FORA da raiz de propósito: desde 01/09/2026 o item da página atual
    # não aparece, e este item aponta para a raiz.
    corpo = client.get(
        caminho_mesh("pt-br", "/cadastro"), HTTP_HOST=HOST_MESH
    ).content.decode()
    assert "Home" in corpo


def so_o_menu(corpo: str) -> str:
    """Só o pedaço do menu, e a precisão importa: a página tem rodapé, e o
    rodapé também leva ao cadastro. Procurar no HTML inteiro faria este guarda
    reprovar por causa de um link que não é do menu."""
    inicio = corpo.index('<nav class="menu-topo">')
    return corpo[inicio : corpo.index("</nav>", inicio)]


def test_item_de_visitante_some_para_quem_entrou(client, rede, logado):
    """`Cadastro` para quem já tem conta é convite para se cadastrar de novo."""
    com_menu(rede, SITE_MESH, HOST_MESH)
    corpo = client.get("/", HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE).content.decode()
    # "Home" some por outro motivo (e a pagina atual), entao a sonda do que
    # SOBRA e o forum; o que este guarda mede e o sumico do item de visitante.
    assert "Forum" in so_o_menu(corpo)
    assert "Sign up" not in so_o_menu(corpo)


def test_a_pagina_atual_nao_e_marcada_porque_nem_aparece(client, rede):
    """A marca de "você está aqui" deixou de existir, e não por descuido.

    Desde 01/09/2026 o item da área atual NÃO APARECE (pedido do mantenedor),
    então nenhum item pode ser a página atual. Manter o atributo seria código
    morto que a próxima pessoa leria como intenção.
    """
    com_menu(rede, SITE_A, HOST_A)
    corpo = client.get("/", HTTP_HOST=HOST_A).content.decode()
    assert "aria-current" not in corpo


def test_aba_nova_leva_o_rel_noopener(client, rede):
    """`target=_blank` sem `rel=noopener` entrega à página aberta o controle da
    aba de origem. O par não se separa."""
    menu = {
        "default_version": "v",
        "versions": [
            {
                "slug": "v",
                "name": "V",
                "items": [
                    {
                        "url": "https://www.roblox.com",
                        "labels": {"pt-br": "Roblox"},
                        "localized": False,
                        "audience": "everyone",
                        "new_tab": True,
                    }
                ],
            }
        ],
        "pages": [],
    }
    com_menu(rede, SITE_A, HOST_A, menu=menu)
    corpo = client.get("/", HTTP_HOST=HOST_A).content.decode()
    assert 'target="_blank" rel="noopener"' in corpo


def test_rotulo_com_marcacao_sai_escapado(client, rede):
    """O rótulo é texto que uma pessoa digita numa tela de administração. O
    autoescape do Django cobre isso, e o teste existe para que ninguém o
    desligue com um `|safe` bem-intencionado num refactor futuro."""
    menu = {
        "default_version": "v",
        "versions": [
            {
                "slug": "v",
                "name": "V",
                "items": [
                    {
                        # NÃO a raiz: na raiz este item some (é a página atual),
                        # e o guarda mediria uma página sem menu nenhum.
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
    com_menu(rede, SITE_A, HOST_A, menu=menu)
    corpo = client.get("/", HTTP_HOST=HOST_A).content.decode()
    assert "<script>alert(1)</script>" not in corpo
    assert "&lt;script&gt;" in corpo


def test_o_menu_nao_custa_nenhuma_ida_a_rede(client, rede):
    """O ponto do desenho inteiro: o menu viaja dentro do site, então desenhá-lo
    não acrescenta nem uma chamada. Se um dia alguém o mover para um endpoint
    próprio, este teste é que vai contar."""
    com_menu(rede, SITE_A, HOST_A)
    client.get("/", HTTP_HOST=HOST_A)
    chamadas_ao_catalogo = [c for c in rede.calls if CATALOGO in str(c.request.url)]
    # uma pelo site, uma pela oferta da landing — e nenhuma pelo menu
    assert len(chamadas_ao_catalogo) == 2


# ---------------------------------------------------------------------------
# O item do lugar onde voce ja esta nao aparece (pedido de 01/09/2026)
# ---------------------------------------------------------------------------


def test_na_pagina_inicial_o_item_inicio_some(client, rede):
    """ "No início em / ele mostra Fórum, Caixa" — sem "Início", porque é aqui."""
    com_menu(rede, SITE_A, HOST_A)
    menu = so_o_menu(client.get("/", HTTP_HOST=HOST_A).content.decode())
    assert "Fórum" in menu
    assert "Início" not in menu


def test_fora_da_raiz_o_item_inicio_volta(client, rede):
    """A raiz é o caso especial: `/` é prefixo de TUDO, e tratá-la como as
    outras faria "Início" sumir do site inteiro."""
    # SITE_MESH e nao SITE_A: `/cadastro` so existe no site multilingue
    com_menu(rede, SITE_MESH, HOST_MESH)
    menu = so_o_menu(client.get("/cadastro", HTTP_HOST=HOST_MESH).content.decode())
    assert "Home" in menu
    assert ">Cadastro<" not in menu  # este agora é o "aqui"


@pytest.mark.parametrize("idioma", ["en", "pt-br", "es"])
def test_o_item_inicio_so_some_na_raiz_daquele_idioma(client, rede, idioma):
    """O guarda que pega o erro mais traiçoeiro desta regra.

    Se a comparação usasse o endereço JÁ prefixado, `/es/` seria prefixo de
    `/es/cadastro` e "Início" sumiria de toda página em espanhol. A comparação
    usa o destino CRU contra o caminho que o resolver já decapou.
    """
    com_menu(rede, SITE_MESH, HOST_MESH)
    na_raiz = so_o_menu(
        client.get(caminho_mesh(idioma), HTTP_HOST=HOST_MESH).content.decode()
    )
    no_cadastro = so_o_menu(
        client.get(
            caminho_mesh(idioma, "/cadastro"), HTTP_HOST=HOST_MESH
        ).content.decode()
    )
    assert "/forum" in na_raiz  # a raiz mostra os outros
    assert 'href="/"' not in na_raiz and f'href="/{idioma}/"' not in na_raiz
    assert ">Cadastro<" not in no_cadastro and ">Sign up<" not in no_cadastro
    assert ">Registro<" not in no_cadastro  # o cadastro esconde a si mesmo
    assert 'href="/"' in no_cadastro or f'href="/{idioma}/"' in no_cadastro


def test_endereco_de_fora_nunca_e_aqui(client, rede):
    """Um site de fora leva para outro lugar: ele nunca é a página atual."""
    menu = {
        "default_version": "v",
        "versions": [
            {
                "slug": "v",
                "name": "V",
                "items": [
                    {
                        "url": "https://www.roblox.com",
                        "labels": {"pt-br": "Roblox"},
                        "localized": False,
                        "audience": "everyone",
                        "new_tab": True,
                    }
                ],
            }
        ],
        "pages": [],
    }
    com_menu(rede, SITE_A, HOST_A, menu=menu)
    assert "Roblox" in so_o_menu(client.get("/", HTTP_HOST=HOST_A).content.decode())
