"""O menu do topo nas Conquistas: o MESMO menu do site, lido do mesmo lugar.

Cópia do PADRÃO da `funil`, do `forum` e da `sugestoes` (Lei 7), inclusive nos
guardas. Cada um corresponde a uma forma diferente de isto dar errado:

1. **As Conquistas caírem porque o catálogo caiu.** Um menu é enfeite de
   navegação; a tela do aluno tem de abrir igual sem ele, e é este o guarda mais
   importante do arquivo.
2. **O par de tokens ainda não provisionado virar um erro por página.** É o
   estado REAL desta célula no dia em que este arquivo nasce — o par
   `gamificacao→catalogo` só existe depois que o mantenedor rodar
   `infra/provisionar-par-do-menu.sh` na VPS — e ele tem de ser silencioso.
3. **A regra "esta página não tem menu" ser ignorada.** Versão vazia numa página
   precisa VENCER a versão padrão do site: é ela a metade "exceto nas páginas
   que já configuramos para não ter" do pedido do mantenedor.
4. **O estilo não chegar ao navegador.** Esta célula serve o CSS por rota
   própria (`armadilhas/083`), então classe nova no HTML sem regra no arquivo é
   um menu sem forma, e nada fica vermelho.
5. **A pergunta "entrou?" custar um segundo salto de rede por página.** Os itens
   "Caixa" e "Conquistas" do menu do site nascem com plateia `logged_in`
   (migração `sites/0005`), então o caminho com pergunta é o NORMAL aqui, não o
   raro.

Os dublês trocam o TRANSPORTE (`respx`), nunca a função — é o idioma desta
célula (ver `test_cliente_do_forum.py`), e é o que faz o guarda medir o cliente
de verdade.
"""

from __future__ import annotations

import httpx
import pytest
import respx
from django.urls import reverse

from apps.core import menu as motor

pytestmark = pytest.mark.django_db

CATALOGO = "http://catalogo:8000/api/catalogo"
POR_HOST = f"{CATALOGO}/sites/by-host/testserver"

# O prefixo público desta célula. Em produção quem o aplica é
# `FORCE_SCRIPT_NAME`, do env; aqui ele entra pelo test client. Sem ele as
# Conquistas seriam servidas em `/`, e a regra "o item da área atual some"
# compararia um caminho que não existe em lugar nenhum.
PREFIXO = {"SCRIPT_NAME": "/conquistas"}

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
                    "url": "/conquistas/",
                    "labels": {"pt-br": "Conquistas", "en": "Achievements"},
                    "localized": False,
                    "audience": "everyone",
                    "new_tab": False,
                },
            ],
        },
        {"slug": "enxuto", "name": "Só o essencial", "items": []},
    ],
    # A metade "exceto nas páginas que já configuramos para não ter".
    "pages": [{"page": "gamificacao/forja", "version": ""}],
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
    faria o guarda do teste seguinte passar por herança, não por medição.
    """
    monkeypatch.setenv("CATALOGO_API_URL", CATALOGO)
    monkeypatch.setenv("TOKEN_CATALOGO", "token-do-par-gamificacao-catalogo")
    monkeypatch.setenv("SITE_ID", "site-mesh")
    motor.limpar_cache()
    yield
    motor.limpar_cache()


@pytest.fixture(autouse=True)
def visitante(monkeypatch):
    """Ninguém entrou — o estado que a maioria dos guardas daqui exercita.

    São DOIS dublês porque são dois caminhos: a view pergunta por conta dela, e
    o processador de contexto do menu pergunta pela dele. Em produção os dois
    chamam a MESMA função, e a resposta é reaproveitada pela memória de
    requisição de `sessao.quem_e`; num teste, cada módulo tem a própria
    referência e precisa do próprio dublê.
    """
    monkeypatch.setattr("apps.core.views.quem_e", lambda request: None)
    monkeypatch.setattr("apps.core.menu.quem_e", lambda request: None)


def _corpo(resposta) -> str:
    """O corpo, venha ele inteiro ou em pedaços.

    A rota do CSS devolve um `FileResponse`, que NÃO tem `.content` — pedir por
    ele levanta `AttributeError` e o teste fica vermelho por instrumento, não
    por defeito (INV-CI01: não medir não é estar certo).
    """
    if resposta.streaming:
        return b"".join(resposta.streaming_content).decode("utf-8")
    return resposta.content.decode("utf-8")


def _menu(corpo: str) -> str:
    """Só o pedaço da barra do site.

    A página tem rodapé e faixa, e os dois também levam a lugares do site — uma
    asserção sobre a página inteira acharia "Conquistas" no rodapé e passaria
    verde sobre um menu vazio.
    """
    inicio = corpo.index('<nav class="menu-topo">')
    return corpo[inicio : corpo.index("</nav>", inicio)]


# ---------------------------------------------------------------------------
# 1. As Conquistas abrem, tenha menu ou não
# ---------------------------------------------------------------------------
def test_sem_menu_configurado_a_pagina_abre_exatamente_como_antes(client):
    with respx.mock:
        respx.get(POR_HOST).mock(
            return_value=httpx.Response(200, json=dict(SITE, menu={}))
        )
        resposta = client.get(reverse("base"))
    assert resposta.status_code == 200
    assert "menu-topo" not in resposta.content.decode()


def test_catalogo_fora_do_ar_nao_derruba_as_conquistas(client):
    """O guarda mais importante do arquivo: um menu é enfeite de navegação, e
    derrubar a tela do aluno por causa dele seria a troca errada."""
    with respx.mock:
        respx.get(POR_HOST).mock(side_effect=httpx.ConnectError("sem rede"))
        resposta = client.get(reverse("base"))
    assert resposta.status_code == 200
    assert "menu-topo" not in resposta.content.decode()


def test_par_de_tokens_ausente_nao_custa_nem_uma_tentativa_de_rede(client, monkeypatch):
    """O estado REAL desta célula enquanto o passo do mantenedor não roda.

    Silencioso, e sem bater na rede: o `respx.mock` sem rota registrada levanta
    em qualquer chamada, então uma tentativa deixaria este teste vermelho.
    """
    monkeypatch.delenv("TOKEN_CATALOGO", raising=False)
    with respx.mock:
        resposta = client.get(reverse("base"))
    assert resposta.status_code == 200
    assert "menu-topo" not in resposta.content.decode()


def test_host_desconhecido_no_catalogo_e_pagina_sem_menu(client):
    with respx.mock:
        respx.get(POR_HOST).mock(return_value=httpx.Response(404))
        resposta = client.get(reverse("base"))
    assert resposta.status_code == 200
    assert "menu-topo" not in resposta.content.decode()


def test_resposta_fora_do_contrato_nao_derruba_a_pagina(client):
    with respx.mock:
        respx.get(POR_HOST).mock(
            return_value=httpx.Response(200, text="isto não é json")
        )
        resposta = client.get(reverse("base"))
    assert resposta.status_code == 200
    assert "menu-topo" not in resposta.content.decode()


# ---------------------------------------------------------------------------
# 2. Com menu configurado
# ---------------------------------------------------------------------------
def test_o_menu_aparece_na_base_das_conquistas(client):
    """Com o PREFIXO, que e o unico jeito de medir isto honestamente: sem ele a
    Base seria servida em `/`, e o item `/` do menu sumiria por ser "a pagina
    atual" -- um falso vermelho sobre uma regra que so existe em producao."""
    with respx.mock:
        respx.get(POR_HOST).mock(return_value=httpx.Response(200, json=SITE))
        corpo = client.get(reverse("base"), **PREFIXO).content.decode()
    assert '<nav class="menu-topo">' in corpo
    assert "Início" in _menu(corpo)
    assert 'href="/forum/"' in _menu(corpo)


def test_o_menu_aparece_tambem_na_trilha_de_marcos(client):
    """ "Em todas as páginas" é processador de contexto e moldura compartilhada,
    nunca uma inclusão que alguém lembra de escrever: tela nova das Conquistas
    nasce com menu (`armadilhas/242` e `/286`)."""
    with respx.mock:
        respx.get(POR_HOST).mock(return_value=httpx.Response(200, json=SITE))
        corpo = client.get(reverse("marcos")).content.decode()
    assert '<nav class="menu-topo">' in corpo


def test_o_rotulo_sai_no_idioma_padrao_do_site(client):
    """Esta célula é monolíngue: o nome do item é o do idioma padrão, e nunca o
    prefixo de idioma — `/pt-br/conquistas` não existe."""
    with respx.mock:
        respx.get(POR_HOST).mock(return_value=httpx.Response(200, json=SITE))
        corpo = client.get(reverse("base"), **PREFIXO).content.decode()
    assert "Início" in _menu(corpo)
    assert "Home" not in _menu(corpo)
    assert "/pt-br/" not in corpo


def test_a_pagina_marcada_sem_menu_nao_mostra_menu(client):
    """A outra metade do pedido do mantenedor: `version: ""` numa página VENCE a
    versão padrão do site. Cair no padrão aqui traria o menu de volta justamente
    onde ele mandou tirá-lo."""
    with respx.mock:
        respx.get(POR_HOST).mock(return_value=httpx.Response(200, json=SITE))
        corpo = client.get(reverse("forja")).content.decode()
    assert "menu-topo" not in corpo


def test_versao_apontada_que_sumiu_nao_derruba_a_pagina(client):
    morto = {"default_version": "fantasma", "versions": [], "pages": []}
    with respx.mock:
        respx.get(POR_HOST).mock(
            return_value=httpx.Response(200, json=dict(SITE, menu=morto))
        )
        resposta = client.get(reverse("base"))
    assert resposta.status_code == 200
    assert "menu-topo" not in resposta.content.decode()


def test_o_menu_nao_custa_uma_consulta_por_pagina(client):
    """Uma ida ao catálogo por janela de cache, não por página aberta."""
    with respx.mock:
        rota = respx.get(POR_HOST).mock(return_value=httpx.Response(200, json=SITE))
        client.get(reverse("base"))
        client.get(reverse("marcos"))
        client.get(reverse("base"))
    assert rota.call_count == 1


def test_rotulo_com_marcacao_sai_escapado(client):
    """O rótulo é texto que uma pessoa digita numa tela de administração."""
    menu = {
        "default_version": "v",
        "versions": [
            {
                "slug": "v",
                "name": "V",
                "items": [
                    {
                        # NÃO a raiz: sem o prefixo público, a Base é `/` no
                        # test client, e um item para `/` sumiria por ser "a
                        # página atual".
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
    with respx.mock:
        respx.get(POR_HOST).mock(
            return_value=httpx.Response(200, json=dict(SITE, menu=menu))
        )
        corpo = client.get(reverse("base")).content.decode()
    assert "<script>alert(1)</script>" not in corpo
    assert "&lt;script&gt;" in corpo


# ---------------------------------------------------------------------------
# 3. Para quem cada item aparece
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


def test_item_de_aluno_nao_aparece_para_visitante(client):
    with respx.mock:
        respx.get(POR_HOST).mock(
            return_value=httpx.Response(200, json=_com_plateia("logged_in", "everyone"))
        )
        corpo = client.get(reverse("base")).content.decode()
    assert "Item everyone" in _menu(corpo)
    assert "Item logged_in" not in _menu(corpo)


def test_item_de_aluno_aparece_para_quem_entrou(client, monkeypatch):
    monkeypatch.setattr("apps.core.menu.quem_e", lambda request: "pes-abc")
    with respx.mock:
        respx.get(POR_HOST).mock(
            return_value=httpx.Response(
                200, json=_com_plateia("logged_in", "logged_out")
            )
        )
        corpo = client.get(reverse("base")).content.decode()
    assert "Item logged_in" in _menu(corpo)
    assert "Item logged_out" not in _menu(corpo)


def test_menu_sem_item_condicional_nao_pergunta_quem_e(client, monkeypatch):
    """Perguntar "entrou?" custa um salto de rede. Menu que não tem item
    condicional não faz a pergunta — e este guarda tem dentes de verdade: o
    dublê EXPLODE se for chamado."""

    def nao_deveria_perguntar(request):
        raise AssertionError(
            "o menu perguntou quem entrou num menu sem item condicional"
        )

    monkeypatch.setattr("apps.core.menu.quem_e", nao_deveria_perguntar)
    with respx.mock:
        respx.get(POR_HOST).mock(
            return_value=httpx.Response(200, json=_com_plateia("everyone"))
        )
        assert client.get(reverse("base")).status_code == 200


# ---------------------------------------------------------------------------
# 4. O item do lugar onde você já está não aparece (pedido de 01/09/2026)
# ---------------------------------------------------------------------------
def test_nas_conquistas_o_item_conquistas_some(client):
    """Um link para onde você já está gasta espaço e ensina o aluno a
    desconfiar do menu."""
    with respx.mock:
        respx.get(POR_HOST).mock(return_value=httpx.Response(200, json=SITE))
        menu = _menu(client.get(reverse("base"), **PREFIXO).content.decode())
    assert "Início" in menu
    assert 'href="/conquistas/"' not in menu


def test_o_item_conquistas_some_tambem_nas_telas_de_dentro(client):
    """A regra é por ÁREA, não por página exata: na trilha de marcos o aluno
    continua nas Conquistas."""
    with respx.mock:
        respx.get(POR_HOST).mock(return_value=httpx.Response(200, json=SITE))
        menu = _menu(client.get(reverse("marcos"), **PREFIXO).content.decode())
    assert 'href="/conquistas/"' not in menu
    assert 'href="/forum/"' in menu


def test_o_item_inicio_continua_aparecendo(client):
    """A raiz do site não é "aqui" quando se está nas Conquistas — e sem este
    guarda um tratamento ingênuo de prefixo faria `/` casar com tudo."""
    with respx.mock:
        respx.get(POR_HOST).mock(return_value=httpx.Response(200, json=SITE))
        menu = _menu(client.get(reverse("base"), **PREFIXO).content.decode())
    assert 'href="/"' in menu


# ---------------------------------------------------------------------------
# 5. O estilo chega mesmo ao navegador
# ---------------------------------------------------------------------------
def test_o_estilo_do_menu_chega_pela_rota_do_css(client):
    """Classe nova no HTML sem regra no arquivo é um menu sem forma, e nada
    ficaria vermelho (`armadilhas/083`)."""
    folha = _corpo(client.get(reverse("estatico", args=["gamificacao.css"])))
    assert ".barra-do-site" in folha
    assert "position: sticky" in folha


# ---------------------------------------------------------------------------
# 6. A memória de requisição — o segundo salto que não acontece
# ---------------------------------------------------------------------------
def test_quem_e_pergunta_uma_vez_so_por_requisicao(rf, monkeypatch):
    """A view e o menu perguntam "quem é?"; a `identidade` responde uma vez.

    Mede a função REAL (`sessao.quem_e`), com a cadeia de baixo dublada: um
    teste que dublasse `quem_e` mediria o dublê, e é justamente a memória DELE
    que este guarda existe para provar.
    """
    from apps.core import sessao

    chamadas = []

    def falsa_sessao(cookie: str) -> dict:
        chamadas.append(cookie)
        return {"autenticado": True, "id": "pes-abc"}

    monkeypatch.setattr(sessao, "_sessao", falsa_sessao)

    requisicao = rf.get("/", HTTP_COOKIE="sessionid=opaco")
    assert sessao.quem_e(requisicao) == "pes-abc"
    assert sessao.quem_e(requisicao) == "pes-abc"
    assert sessao.quem_e(requisicao) == "pes-abc"
    assert len(chamadas) == 1


def test_visitante_tambem_e_lembrado(rf, monkeypatch):
    """`None` é resposta legítima, e precisa ser lembrada como qualquer outra.

    Sem o sentinela, todo visitante perguntaria de novo — e visitante é o caso
    mais comum de uma página pública, não o raro.
    """
    from apps.core import sessao

    chamadas = []

    def falsa_sessao(cookie: str) -> dict:
        chamadas.append(cookie)
        return {"autenticado": False}

    monkeypatch.setattr(sessao, "_sessao", falsa_sessao)

    requisicao = rf.get("/", HTTP_COOKIE="sessionid=opaco")
    assert sessao.quem_e(requisicao) is None
    assert sessao.quem_e(requisicao) is None
    assert len(chamadas) == 1


def test_a_memoria_morre_com_a_requisicao(rf, monkeypatch):
    """Duas pessoas nunca compartilham a mesma resposta.

    Cache de sessão em variável de processo é exatamente como uma tela passa
    verde mostrando o nome de outra pessoa — este guarda prova que a memória é
    da requisição, e não do módulo.
    """
    from apps.core import sessao

    quem = iter(["pes-abc", "pes-xyz"])
    monkeypatch.setattr(
        sessao, "_sessao", lambda cookie: {"autenticado": True, "id": next(quem)}
    )

    assert sessao.quem_e(rf.get("/", HTTP_COOKIE="a=1")) == "pes-abc"
    assert sessao.quem_e(rf.get("/", HTTP_COOKIE="a=2")) == "pes-xyz"


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
    client, monkeypatch, papel, aparece
):
    monkeypatch.setattr("apps.core.menu.quem_e", lambda request: "pes-abc")
    monkeypatch.setattr("apps.core.menu.papel_de_exibicao", lambda request: papel)
    with respx.mock:
        respx.get(POR_HOST).mock(
            return_value=httpx.Response(200, json=dict(SITE, menu=MENU_COM_EQUIPE))
        )
        menu = _menu(client.get(reverse("base"), **PREFIXO).content.decode())
    assert (">Admin</a>" in menu) is aparece
    assert ">Fórum</a>" in menu, "o menu inteiro sumiu — o guarda não mediu nada"


def test_o_atalho_da_equipe_some_para_visitante(client):
    """O dublê `visitante` do arquivo já responde "ninguém entrou"."""
    with respx.mock:
        respx.get(POR_HOST).mock(
            return_value=httpx.Response(200, json=dict(SITE, menu=MENU_COM_EQUIPE))
        )
        menu = _menu(client.get(reverse("base"), **PREFIXO).content.decode())
    assert ">Admin</a>" not in menu
    assert ">Fórum</a>" in menu


def test_plateia_desconhecida_nao_aparece_para_ninguem(client, monkeypatch):
    """Fail-CLOSED. Até 03/09/2026 esta célula mostrava para TODO MUNDO o que
    não entendia — inclusive para visitante."""
    monkeypatch.setattr("apps.core.menu.quem_e", lambda request: "pes-abc")
    monkeypatch.setattr("apps.core.menu.papel_de_exibicao", lambda request: "staff")
    with respx.mock:
        respx.get(POR_HOST).mock(
            return_value=httpx.Response(200, json=dict(SITE, menu=MENU_COM_EQUIPE))
        )
        menu = _menu(client.get(reverse("base"), **PREFIXO).content.decode())
    assert "Plateia Inventada" not in menu
