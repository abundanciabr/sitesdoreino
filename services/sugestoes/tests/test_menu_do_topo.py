"""O menu do topo na Caixa: o MESMO menu do site, lido do mesmo lugar.

Cópia do PADRÃO da `funil` e do `forum` (Lei 7), inclusive nos guardas. Cada um
corresponde a uma forma diferente de isto dar errado:

1. **A Caixa cair porque o catálogo caiu.** Um menu é enfeite de navegação; a
   Caixa tem de abrir igual sem ele, e é este o guarda mais importante do
   arquivo.
2. **O par de tokens ainda não provisionado virar um erro por página.** É o
   estado real enquanto o passo do mantenedor não roda, e ele tem de ser
   silencioso e sem tocar na rede.
3. **A regra "esta página não tem menu" ser ignorada.** Versão vazia numa
   página precisa VENCER a versão padrão do site.
4. **O estilo não chegar ao navegador.** Esta célula serve o CSS por rota
   própria (`armadilhas/083`), então classe nova no HTML sem regra no arquivo é
   um menu sem forma, e nada ficaria vermelho.
"""

import httpx
import pytest
from django.urls import reverse

from apps.core import menu as motor

CATALOGO = "http://catalogo:8000/api/catalogo"

# O prefixo público desta célula, pelo mesmo motivo do fórum: em produção a
# Caixa mora em `/forms/sugestoes/`, e é esse caminho que a regra "o item da
# área atual some" compara.
PREFIXO = {"SCRIPT_NAME": "/forms/sugestoes"}

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
    "pages": [{"page": "sugestoes/sugestoes/nova", "version": ""}],
}

# O mesmo menu, com o item da própria Caixa dentro — é ele que a regra nova
# tem de esconder quando a pessoa já está aqui.
MENU_COM_A_CAIXA = dict(
    MENU,
    versions=[
        dict(
            MENU["versions"][0],
            items=MENU["versions"][0]["items"]
            + [
                {
                    "url": "/forms/sugestoes/",
                    "labels": {"pt-br": "Caixa"},
                    "localized": False,
                    "audience": "everyone",
                    "new_tab": False,
                }
            ],
        ),
        MENU["versions"][1],
    ],
)

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
    faria o guarda do seguinte passar por herança, não por medição."""
    monkeypatch.setenv("CATALOGO_API_URL", CATALOGO)
    monkeypatch.setenv("TOKEN_CATALOGO", "token-do-par-sugestoes-catalogo")
    motor.limpar_cache()
    yield
    motor.limpar_cache()


@pytest.fixture(autouse=True)
def catalogo_de_pe(rede):
    """O catálogo respondendo ANTES de qualquer página abrir.

    Precisa ser `autouse`, e a razão é de ordem: entrar na Caixa (a fixture
    `dentro`) já ABRE uma página, e o processador de contexto do menu roda em
    toda página. Sem isto, a primeira requisição da suíte bateria num catálogo
    não registrado e o `respx` estouraria — vermelho de instrumento, não de
    defeito (INV-CI01).

    Quem quiser outra resposta a troca com `catalogo_diz`, que limpa o cache
    junto.
    """
    catalogo_diz(rede)


def catalogo_diz(rede, site=None, resposta=None):
    """O catálogo servindo o site (com menu), pelo dublê da própria suíte.

    Limpa o cache do menu junto, e isso não é detalhe: trocar a resposta sem
    limpar deixaria a leitura anterior valendo por 60s, e o teste mediria o
    menu do teste passado — verde por herança.
    """
    rota = rede.mock.get(f"{CATALOGO}/sites/by-host/testserver").mock(
        return_value=(
            resposta
            if resposta is not None
            else httpx.Response(200, json=site if site is not None else SITE)
        )
    )
    motor.limpar_cache()
    return rota


def so_o_menu(corpo: str) -> str:
    """Só o pedaço do menu.

    A precisão importa: a moldura da Caixa tem trilho, migalha e barra do fim,
    e várias dessas peças também levam a lugares do site. Procurar no HTML
    inteiro faria estes guardas reprovarem por um link que não é do menu.
    """
    inicio = corpo.index('<nav class="menu-topo">')
    return corpo[inicio : corpo.index("</nav>", inicio)]


# ---------------------------------------------------------------------------
# A Caixa abre, tenha menu ou não
# ---------------------------------------------------------------------------


def test_sem_menu_configurado_a_caixa_abre_como_antes(dentro, rede, quadro):
    catalogo_diz(rede, site=dict(SITE, menu={}))
    resposta = dentro.client.get(reverse("quadro"), **PREFIXO)
    assert resposta.status_code == 200
    assert "menu-topo" not in resposta.content.decode()


def test_catalogo_fora_do_ar_nao_derruba_a_caixa(dentro, rede, quadro):
    """O guarda mais importante do arquivo: um menu é enfeite de navegação, e a
    Caixa é onde o aluno fala com a escola."""
    rede.mock.get(f"{CATALOGO}/sites/by-host/testserver").mock(
        side_effect=httpx.ConnectError("sem rede")
    )
    motor.limpar_cache()
    resposta = dentro.client.get(reverse("quadro"), **PREFIXO)
    assert resposta.status_code == 200
    assert "menu-topo" not in resposta.content.decode()


def test_par_de_tokens_ausente_nao_custa_nem_uma_tentativa_de_rede(
    dentro, rede, quadro, monkeypatch
):
    """O estado real enquanto o passo do mantenedor não roda. Silencioso, e sem
    bater na rede: o `respx` estoura em requisição não registrada, então este
    guarda falharia sozinho se alguém tentasse perguntar."""
    monkeypatch.delenv("TOKEN_CATALOGO", raising=False)
    motor.limpar_cache()
    resposta = dentro.client.get(reverse("quadro"), **PREFIXO)
    assert resposta.status_code == 200
    assert "menu-topo" not in resposta.content.decode()


def test_host_desconhecido_no_catalogo_e_caixa_sem_menu(dentro, rede, quadro):
    catalogo_diz(rede, resposta=httpx.Response(404))
    resposta = dentro.client.get(reverse("quadro"), **PREFIXO)
    assert resposta.status_code == 200
    assert "menu-topo" not in resposta.content.decode()


def test_versao_apontada_que_sumiu_nao_derruba_a_pagina(dentro, rede, quadro):
    catalogo_diz(
        rede,
        site=dict(
            SITE, menu={"default_version": "fantasma", "versions": [], "pages": []}
        ),
    )
    resposta = dentro.client.get(reverse("quadro"), **PREFIXO)
    assert resposta.status_code == 200
    assert "menu-topo" not in resposta.content.decode()


# ---------------------------------------------------------------------------
# Com menu configurado
# ---------------------------------------------------------------------------


def test_o_menu_aparece_no_quadro(dentro, rede, quadro):
    catalogo_diz(rede)
    corpo = dentro.client.get(reverse("quadro"), **PREFIXO).content.decode()
    assert '<nav class="menu-topo">' in corpo
    assert "Início" in so_o_menu(corpo)
    assert 'href="/forum/"' in so_o_menu(corpo)


def test_o_rotulo_sai_no_idioma_padrao_do_site(dentro, rede, quadro):
    """Esta célula é monolíngue: o nome do item é o do idioma padrão, e o
    prefixo de idioma nunca é aplicado."""
    catalogo_diz(rede)
    menu = so_o_menu(dentro.client.get(reverse("quadro"), **PREFIXO).content.decode())
    assert "Início" in menu
    assert "Home" not in menu
    assert "/pt-br/" not in menu


def test_o_item_de_visitante_some_para_quem_esta_na_caixa(dentro, rede, quadro):
    """Quem chega a uma tela com moldura já entrou: `Cadastro` ali seria convite
    para se cadastrar de novo."""
    catalogo_diz(rede)
    menu = so_o_menu(dentro.client.get(reverse("quadro"), **PREFIXO).content.decode())
    assert "Início" in menu
    assert "Cadastro" not in menu


def test_a_pagina_marcada_sem_menu_nao_mostra_menu(dentro, rede, quadro):
    """`version: ""` numa página VENCE a versão padrão do site. Cair no padrão
    aqui traria o menu de volta justamente onde ele mandou tirá-lo."""
    catalogo_diz(rede)
    corpo = dentro.client.get(reverse("nova_sugestao"), **PREFIXO).content.decode()
    assert "menu-topo" not in corpo


def test_o_menu_nao_custa_uma_consulta_por_pagina(dentro, rede, quadro):
    """Uma ida ao catálogo por janela de cache, não por página aberta."""
    rota = catalogo_diz(rede)
    antes = rota.call_count
    dentro.client.get(reverse("quadro"), **PREFIXO)
    dentro.client.get(reverse("quadro"), **PREFIXO)
    dentro.client.get(reverse("quadro"), **PREFIXO)
    # a diferenca, e nao o total: entrar na Caixa (a fixture `dentro`) ja abriu
    # uma pagina antes deste teste comecar, e ela tambem consultou o catalogo
    assert rota.call_count - antes == 1


def test_rotulo_com_marcacao_sai_escapado(dentro, rede, quadro):
    """O rótulo é texto que uma pessoa digita numa tela de administração."""
    menu = {
        "default_version": "v",
        "versions": [
            {
                "slug": "v",
                "name": "V",
                "items": [
                    {
                        # NAO a raiz: dependendo do caminho medido ela pode ser
                        # "a pagina atual", e o item sumiria antes de ser escapado.
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
    catalogo_diz(rede, site=dict(SITE, menu=menu))
    corpo = dentro.client.get(reverse("quadro"), **PREFIXO).content.decode()
    assert "<script>alert(1)</script>" not in corpo
    assert "&lt;script&gt;" in corpo


def test_o_estilo_do_menu_chega_ao_navegador(client):
    """Esta célula serve o CSS por rota própria (`armadilhas/083`): classe nova
    no HTML sem regra no arquivo é um menu sem forma, e nada ficaria vermelho."""
    resposta = client.get(
        reverse("estatico", kwargs={"caminho": "sugestoes/caixa.css"})
    )
    corpo = (
        b"".join(resposta.streaming_content) if resposta.streaming else resposta.content
    ).decode("utf-8")
    assert ".barra-do-site" in corpo
    assert "position: sticky" in corpo


# ---------------------------------------------------------------------------
# O item do lugar onde voce ja esta nao aparece (pedido de 01/09/2026)
# ---------------------------------------------------------------------------


def test_na_caixa_o_item_da_caixa_some(dentro, rede, quadro):
    """ "A mesma coisa em Caixa": estando nela, o item dela é um link para onde
    a pessoa já está."""
    catalogo_diz(rede, site=dict(SITE, menu=MENU_COM_A_CAIXA))
    menu = so_o_menu(dentro.client.get(reverse("quadro"), **PREFIXO).content.decode())
    assert "Início" in menu
    assert 'href="/forms/sugestoes/"' not in menu


def test_o_item_da_caixa_some_tambem_nas_telas_de_dentro(dentro, rede, quadro):
    """A regra é por ÁREA: escrevendo uma ideia, a pessoa continua na Caixa."""
    catalogo_diz(rede, site=dict(SITE, menu=MENU_COM_A_CAIXA))
    corpo = dentro.client.get(reverse("nova_sugestao"), **PREFIXO).content.decode()
    if "menu-topo" in corpo:  # esta tela pode ter regra própria de menu
        assert 'href="/forms/sugestoes/"' not in so_o_menu(corpo)


def test_os_outros_lugares_continuam_no_menu_da_caixa(dentro, rede, quadro):
    """O controle positivo: some SÓ o item de quem é dono da página."""
    catalogo_diz(rede, site=dict(SITE, menu=MENU_COM_A_CAIXA))
    menu = so_o_menu(dentro.client.get(reverse("quadro"), **PREFIXO).content.decode())
    assert 'href="/"' in menu
    assert 'href="/forum/"' in menu


# ---------------------------------------------------------------------------
# A plateia `staff` — o atalho que só quem é da equipe vê (03/09/2026)
# ---------------------------------------------------------------------------
# Quatro guardas, e o quarto é o que ninguém pediria: plateia que esta célula
# NÃO conhece some, em vez de aparecer para todo mundo. É ele que impede um
# valor novo no catálogo de vazar um atalho durante a janela em que uma das
# células ainda não subiu com o código novo.
#
# Toda asserção é sobre o CORPO RENDERIZADO, nunca sobre a tabela de regras
# (`armadilhas/242`): uma tabela certa com um chamador que passa o argumento
# errado passaria num teste que só lê a tabela.
MENU_COM_EQUIPE = {
    "default_version": "v",
    "versions": [
        {
            "slug": "v",
            "name": "V",
            "items": [
                {
                    "url": "/admin/",
                    "labels": {"pt-br": "Admin"},
                    "localized": False,
                    "audience": "staff",
                    "new_tab": False,
                },
                {
                    "url": "/inventada/",
                    "labels": {"pt-br": "Plateia Inventada"},
                    "localized": False,
                    # Valor que ESTA célula não conhece. Em produção ele só pode
                    # chegar aqui de um catálogo mais novo que o container, que
                    # é exatamente a janela de um deploy em andamento.
                    "audience": "plateia-que-nao-existe",
                    "new_tab": False,
                },
                {
                    "url": "/forum/",
                    "labels": {"pt-br": "Fórum"},
                    "localized": False,
                    "audience": "everyone",
                    "new_tab": False,
                },
                {
                    # O segundo item de controle, e ele existe por um motivo
                    # medido: cada célula esconde o item que aponta para a área
                    # onde a pessoa já está. Com um `everyone` só, o menu de
                    # teste ficava VAZIO na célula dona daquele endereço — e um
                    # menu vazio não é desenhado, então o guarda estourava
                    # procurando a tag em vez de medir a plateia.
                    "url": "/",
                    "labels": {"pt-br": "Início"},
                    "localized": False,
                    "audience": "everyone",
                    "new_tab": False,
                },
            ],
        }
    ],
    "pages": [],
}


@pytest.mark.parametrize(
    "papel,aparece",
    [("staff", True), ("aluno", False)],
    ids=["equipe", "aluno"],
)
def test_o_atalho_da_equipe_so_aparece_para_a_equipe(
    entrar_como, rede, quadro, papel, aparece
):
    """A pessoa entra pela porta REAL da Caixa, e o que muda é só o `papel` que
    a identidade responde — que é o campo que decide o atalho."""
    pessoa = entrar_como(papel=papel)
    catalogo_diz(rede, site=dict(SITE, menu=MENU_COM_EQUIPE))
    menu = so_o_menu(pessoa.client.get(reverse("quadro"), **PREFIXO).content.decode())
    assert (">Admin</a>" in menu) is aparece
    assert ">Fórum</a>" in menu, "o menu inteiro sumiu — o guarda não mediu nada"


def test_plateia_desconhecida_nao_aparece_para_ninguem(entrar_como, rede, quadro):
    """Fail-CLOSED. Até 03/09/2026 esta célula mostrava para TODO MUNDO o que
    não entendia."""
    pessoa = entrar_como(papel="staff")
    catalogo_diz(rede, site=dict(SITE, menu=MENU_COM_EQUIPE))
    menu = so_o_menu(pessoa.client.get(reverse("quadro"), **PREFIXO).content.decode())
    assert "Plateia Inventada" not in menu
