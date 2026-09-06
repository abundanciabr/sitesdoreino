"""O menu do topo na casa das Páginas: o MESMO menu do site, do mesmo lugar.

Cópia do PADRÃO da `funil`, do `forum`, da `sugestoes` e da `gamificacao`
(Lei 3), inclusive nos guardas. Cada um corresponde a uma forma diferente de
isto dar errado:

1. **A Prancheta cair porque o catálogo caiu.** Um menu é enfeite de navegação;
   a tela do aluno tem de abrir igual sem ele, e é este o guarda mais importante
   do arquivo.
2. **O par de tokens ainda não provisionado virar um erro por página.** É o
   estado REAL desta célula no dia em que este arquivo nasce: o par
   `pages→catalogo` não existe enquanto o mantenedor não rodar a versão de
   `infra/provisionar-par-do-menu.sh` que também escreve `env/pages.env`. Ele
   tem de ser silencioso, e não pode custar nem uma tentativa de rede.
3. **As três telas da porta ficarem sem menu.** Elas são desenhadas pelo
   middleware ANTES de a rota ser resolvida, e são as primeiras páginas que um
   visitante desta casa vê. É a diferença desta célula para todas as vizinhas.
4. **A regra "esta página não tem menu" ser ignorada.** Versão vazia numa página
   precisa VENCER a versão padrão do site: é ela a metade "exceto nas páginas
   que já configuramos para não ter" do pedido do mantenedor.
5. **O prefixo público.** Esta casa é servida em `/pages`, e a marca de "você
   está aqui" compara com `request.path`, que carrega o prefixo. Medir sem ele
   seria medir um endereço que não existe em lugar nenhum.

Os dublês trocam o TRANSPORTE (`respx`, pelo fixture `rede` do `conftest`),
nunca a função: é o que faz o guarda medir o cliente de verdade.
"""

from __future__ import annotations

import httpx
import pytest

from django.test import Client

from apps.core import menu as motor

from tests.conftest import COOKIE

CATALOGO = "http://catalogo:8000/api/catalogo"
POR_HOST = f"{CATALOGO}/sites/by-host/testserver"

# O prefixo público desta célula. Em produção quem o aplica é
# `FORCE_SCRIPT_NAME`, do env; aqui ele entra pelo test client. Sem ele a
# Prancheta seria servida em `/`, e a regra "o item da área atual some"
# compararia um caminho que não existe em lugar nenhum.
PREFIXO = {"SCRIPT_NAME": "/pages"}

# A marca da barra DESENHADA, e nunca a string `menu-topo` solta: esta casa
# serve o estilo embutido na moldura, então `.menu-topo { ... }` está no corpo
# de TODA página. Um guarda escrito com a string solta ficaria vermelho para
# sempre, medindo a folha de estilo em vez do menu.
BARRA = '<nav class="menu-topo">'

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
                    "url": "/pages/",
                    "labels": {"pt-br": "Prancheta", "en": "Board"},
                    "localized": False,
                    "audience": "everyone",
                    "new_tab": False,
                },
            ],
        },
        {"slug": "enxuto", "name": "Só o essencial", "items": []},
    ],
    "pages": [],
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
def par_ligado(monkeypatch):
    """O par provisionado, e o cache limpo dos dois lados do teste.

    O cache do menu não pode vazar entre testes: um menu que um teste ensinou
    faria o guarda do teste seguinte passar por herança, e não por medição.
    """
    monkeypatch.setenv("CATALOGO_API_URL", CATALOGO)
    monkeypatch.setenv("TOKEN_CATALOGO", "token-do-par-pages-catalogo")
    motor.limpar_cache()
    yield
    motor.limpar_cache()


def dublar_catalogo(rede, site=None, **resposta):
    """O catálogo responde este site, ou o que `resposta` mandar."""
    if site is not None:
        resposta = {"json": site}
    return rede.get(POR_HOST).mock(return_value=httpx.Response(200, **resposta))


def abrir(caminho: str = "/", *, cookie: str | None = None, prefixo: bool = False):
    extras = dict(PREFIXO) if prefixo else {}
    if cookie:
        extras["HTTP_COOKIE"] = cookie
    return Client().get(caminho, **extras)


def texto(resposta) -> str:
    return resposta.content.decode("utf-8")


def so_o_menu(corpo: str) -> str:
    """Só o pedaço da barra do site.

    A página tem rodapé e faixa, e os dois também levam a lugares do site: uma
    asserção sobre a página inteira acharia "Início do site" no rodapé e
    passaria verde sobre um menu vazio.
    """
    inicio = corpo.index(BARRA)
    return corpo[inicio : corpo.index("</nav>", inicio)]


# ---------------------------------------------------------------------------
# 1. A Prancheta abre, tenha menu ou não
# ---------------------------------------------------------------------------
def test_par_de_tokens_ausente_nao_custa_nem_uma_tentativa_de_rede(
    aluna, rede, monkeypatch
):
    """O estado REAL desta célula enquanto o passo do mantenedor não roda.

    Silencioso, e sem bater na rede: o `rede` do `conftest` levanta em qualquer
    chamada não registrada, e o catálogo não está registrado neste teste.
    """
    monkeypatch.delenv("TOKEN_CATALOGO", raising=False)
    resposta = abrir(cookie=COOKIE)
    assert resposta.status_code == 200
    assert BARRA not in texto(resposta)


def test_catalogo_fora_do_ar_nao_derruba_a_prancheta(aluna, rede):
    """O guarda mais importante do arquivo: um menu é enfeite de navegação, e
    derrubar a tela do aluno por causa dele seria a troca errada."""
    rede.get(POR_HOST).mock(side_effect=httpx.ConnectError("sem rede"))
    resposta = abrir(cookie=COOKIE)
    assert resposta.status_code == 200
    assert BARRA not in texto(resposta)


def test_host_desconhecido_no_catalogo_e_pagina_sem_menu(aluna, rede):
    rede.get(POR_HOST).mock(return_value=httpx.Response(404))
    resposta = abrir(cookie=COOKIE)
    assert resposta.status_code == 200
    assert BARRA not in texto(resposta)


def test_resposta_fora_do_contrato_nao_derruba_a_pagina(aluna, rede):
    dublar_catalogo(rede, text="isto não é json")
    resposta = abrir(cookie=COOKIE)
    assert resposta.status_code == 200
    assert BARRA not in texto(resposta)


def test_versao_apontada_que_sumiu_nao_derruba_a_pagina(aluna, rede):
    morto = {"default_version": "fantasma", "versions": [], "pages": []}
    dublar_catalogo(rede, dict(SITE, menu=morto))
    resposta = abrir(cookie=COOKIE)
    assert resposta.status_code == 200
    assert BARRA not in texto(resposta)


# ---------------------------------------------------------------------------
# 2. Com menu configurado
# ---------------------------------------------------------------------------
def test_o_menu_aparece_na_prancheta(aluna, rede):
    dublar_catalogo(rede, SITE)
    menu = so_o_menu(texto(abrir(cookie=COOKIE, prefixo=True)))
    assert "Início" in menu
    assert 'href="/forum/"' in menu


def test_o_menu_aparece_tambem_na_tela_da_porta(env_dos_pares, rede):
    """A diferença desta casa para todas as vizinhas.

    A porta desenha ANTES de a rota ser resolvida, então não há `route` de onde
    tirar a chave da página. A primeira página que um visitante desta casa vê
    não pode ser a única do site sem navegação (`armadilhas/286`).
    """
    dublar_catalogo(rede, SITE)
    corpo = texto(abrir(prefixo=True))
    assert "Entre para ver a sua Prancheta" in corpo
    assert 'href="/forum/"' in so_o_menu(corpo)


def test_o_rotulo_sai_no_idioma_padrao_do_site(aluna, rede):
    """Esta célula é monolíngue: o nome do item é o do idioma padrão, e nunca o
    prefixo de idioma, porque `/pt-br/pages` não existe."""
    dublar_catalogo(rede, SITE)
    corpo = texto(abrir(cookie=COOKIE, prefixo=True))
    assert "Início" in so_o_menu(corpo)
    assert "Home" not in so_o_menu(corpo)
    assert "/pt-br/" not in corpo


def test_a_pagina_marcada_sem_menu_nao_mostra_menu(aluna, rede):
    """A outra metade do pedido do mantenedor: `version: ""` numa página VENCE a
    versão padrão do site. Cair no padrão aqui traria o menu de volta justamente
    onde ele mandou tirá-lo."""
    sem = dict(MENU, pages=[{"page": "pages/", "version": ""}])
    dublar_catalogo(rede, dict(SITE, menu=sem))
    assert BARRA not in texto(abrir(cookie=COOKIE, prefixo=True))


def test_o_mesmo_botao_manda_nas_duas_caras_do_endereco(env_dos_pares, rede):
    """UM botão na tela dele, e ele alcança as duas caras de `/pages/`.

    A tela `/admin/menu/` monta as opções a partir de `painel/mapa-do-site.json`,
    e lá `/pages/` é uma página só: a mesma entrada descreve os três desfechos da
    porta e o aluno reconhecido. Por isso a chave das telas da porta é a da raiz,
    e não um nome próprio, que seria um botão que a tela dele nunca mostraria.

    O par com o guarda de cima é o que dá sentido aos dois: lá a regra apaga o
    menu do aluno reconhecido, aqui a MESMA regra o apaga para quem ainda não
    entrou.
    """
    sem = dict(MENU, pages=[{"page": "pages/", "version": ""}])
    dublar_catalogo(rede, dict(SITE, menu=sem))
    corpo = texto(abrir(prefixo=True))
    assert "Entre para ver a sua Prancheta" in corpo
    assert BARRA not in corpo


def test_rotulo_com_marcacao_sai_escapado(aluna, rede):
    """O rótulo é texto que uma pessoa digita numa tela de administração."""
    versao = {
        "slug": "v",
        "name": "V",
        "items": [
            {
                "url": "/cadastro",
                "labels": {"pt-br": "<script>alert(1)</script>"},
                "localized": False,
                "audience": "everyone",
                "new_tab": False,
            }
        ],
    }
    dublar_catalogo(
        rede,
        dict(SITE, menu={"default_version": "v", "versions": [versao], "pages": []}),
    )
    corpo = texto(abrir(cookie=COOKIE, prefixo=True))
    assert "<script>alert(1)</script>" not in corpo
    assert "&lt;script&gt;" in corpo


def test_o_menu_nao_custa_uma_consulta_por_pagina(aluna, rede):
    """Uma ida ao catálogo por janela de cache, não por página aberta."""
    rota = dublar_catalogo(rede, SITE)
    abrir(cookie=COOKIE)
    abrir(cookie=COOKIE)
    abrir(cookie=COOKIE)
    assert rota.call_count == 1


# ---------------------------------------------------------------------------
# 3. O prefixo público, e o item do lugar onde você já está
# ---------------------------------------------------------------------------
def test_na_prancheta_o_item_da_prancheta_some(aluna, rede):
    """Um link para onde você já está gasta espaço e ensina o aluno a
    desconfiar do menu (pedido do mantenedor em 01/09/2026).

    Este é o guarda do SCRIPT_NAME: sem o prefixo, `request.path` seria `/` e o
    item `/pages/` nunca casaria com a página atual.
    """
    dublar_catalogo(rede, SITE)
    menu = so_o_menu(texto(abrir(cookie=COOKIE, prefixo=True)))
    assert 'href="/pages/"' not in menu
    assert 'href="/forum/"' in menu


def test_o_item_inicio_continua_aparecendo(aluna, rede):
    """A raiz do site não é "aqui" quando se está na Prancheta, e sem este
    guarda um tratamento ingênuo de prefixo faria `/` casar com tudo."""
    dublar_catalogo(rede, SITE)
    assert 'href="/"' in so_o_menu(texto(abrir(cookie=COOKIE, prefixo=True)))


# ---------------------------------------------------------------------------
# 4. Para quem cada item aparece
# ---------------------------------------------------------------------------
def _com_plateia(*plateias: str) -> dict:
    itens = [
        {
            "url": f"/so-para-{p}",
            "labels": {"pt-br": f"Item {p}"},
            "localized": False,
            "audience": p,
            "new_tab": False,
        }
        for p in plateias
    ]
    return dict(
        SITE,
        menu={
            "default_version": "v",
            "versions": [{"slug": "v", "name": "V", "items": itens}],
            "pages": [],
        },
    )


def test_item_de_aluno_aparece_para_quem_a_porta_deixou_passar(aluna, rede):
    dublar_catalogo(rede, _com_plateia("logged_in", "logged_out"))
    menu = so_o_menu(texto(abrir(cookie=COOKIE, prefixo=True)))
    assert "Item logged_in" in menu
    assert "Item logged_out" not in menu


def test_item_de_aluno_nao_aparece_na_tela_da_porta(env_dos_pares, rede):
    """Nas telas da porta, "entrou" é falso: esta casa só sabe quem passou.

    O preço está escrito em `menu._quem_esta_aqui` e é este: quem entrou no site
    e não tem matrícula vê o item de plateia `logged_out` (o "Cadastro"). Custa
    um clique inútil; o erro contrário custaria a porta de entrada da escola.
    """
    dublar_catalogo(rede, _com_plateia("logged_in", "logged_out"))
    menu = so_o_menu(texto(abrir(prefixo=True)))
    assert "Item logged_out" in menu
    assert "Item logged_in" not in menu


@pytest.mark.parametrize("plateia", ["staff", "plateia-que-nao-existe"])
def test_o_que_esta_casa_nao_sabe_dizer_nao_aparece_para_ninguem(aluna, rede, plateia):
    """Fail-CLOSED, nas duas pontas, e as duas estão ditas na cara.

    `staff` é papel de exibição, e a PORTA desta casa guarda em `request.aluno`
    só o id e o nome: o atalho da administração não aparece no menu daqui
    enquanto for assim, e aparece nas outras áreas do site. Plateia que esta
    célula não conhece some pelo mesmo motivo: item que some é aborrecimento,
    item que aparece para quem não devia é outra coisa.

    O item de controle prova que o menu inteiro não sumiu: sem ele este guarda
    passaria verde medindo nada.
    """
    dublar_catalogo(rede, _com_plateia(plateia, "everyone"))
    menu = so_o_menu(texto(abrir(cookie=COOKIE, prefixo=True)))
    assert f"Item {plateia}" not in menu
    assert "Item everyone" in menu, "o menu inteiro sumiu: o guarda não mediu nada"


# ---------------------------------------------------------------------------
# 5. O estilo chega mesmo ao navegador
# ---------------------------------------------------------------------------
def test_o_estilo_do_menu_chega_junto_com_a_pagina(aluna, rede):
    """Classe nova no HTML sem regra no estilo é um menu sem forma, e nada
    ficaria vermelho (`armadilhas/083`). Esta casa serve o estilo embutido na
    moldura, então a prova é sobre o corpo servido."""
    dublar_catalogo(rede, SITE)
    corpo = texto(abrir(cookie=COOKIE, prefixo=True))
    assert ".barra-do-site" in corpo
    assert ".menu-topo {" in corpo
