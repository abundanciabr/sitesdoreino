"""A tela `/admin/menu/` — onde o mantenedor monta o menu do topo do site.

O que estes guardas protegem:

1. **Esta tela não guarda nada.** Ela lê e grava no `catalogo`, que é onde dado
   de site mora. Uma cópia aqui seria o mesmo fato em dois lugares, e no dia em
   que as duas discordassem o site mostraria uma coisa e a tela outra.
2. **A lista de páginas sai de `painel/mapa-do-site.json`**, o mesmo arquivo de
   `/admin/mapa/`. Uma lista própria envelheceria em silêncio (a Classe 8).
3. **Cada gesto grava o documento inteiro**, porque a coerência é do conjunto:
   apagar uma versão sem apagar as regras que apontavam para ela produziria uma
   configuração que o catálogo (com razão) recusa.
4. **Recusa do catálogo vira frase na tela**, não 500, e o que a tela mostra
   depois é o que está GRAVADO, nunca o rascunho recusado.
5. **Par de tokens ausente abre a tela mesmo assim**, dizendo o que falta.
   Fail-OPEN: uma tela de operação que não abre é inútil justamente quando você
   precisa dela.
6. **A porta continua sendo a porta**: sem crachá, nada disto responde.
"""

import json

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.auditoria.models import Registro

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
CATALOGO = "http://catalogo:8000/api/catalogo"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"
SITE_ID = "site-mesh"

MENU = {
    "default_version": "completo",
    "versions": [
        {
            "slug": "completo",
            "name": "Menu completo",
            "items": [
                {
                    "url": "/",
                    "labels": {"en": "Home", "pt-br": "Início"},
                    "localized": True,
                    "audience": "everyone",
                    "new_tab": False,
                },
                {
                    "url": "/forum",
                    "labels": {"en": "Forum", "pt-br": "Fórum"},
                    "localized": False,
                    "audience": "everyone",
                    "new_tab": False,
                },
            ],
        },
        {"slug": "enxuto", "name": "Só o essencial", "items": []},
    ],
    "pages": [{"page": "funil/login", "version": ""}],
}

SITE = {
    "id": SITE_ID,
    "host": "testserver",
    "name": "Meshcraft",
    "active": True,
    "default_language": "en",
    "languages": [{"code": "en"}, {"code": "pt-br"}, {"code": "es"}],
    "menu": MENU,
}


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    monkeypatch.setenv("CATALOGO_API_URL", CATALOGO)
    monkeypatch.setenv("TOKEN_CATALOGO", "token-do-par-admin-catalogo")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


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


def _catalogo(site=None):
    """O catálogo respondendo o site (com menu) e aceitando a gravação."""
    respx.get(f"{CATALOGO}/sites/by-host/testserver").mock(
        return_value=httpx.Response(200, json=site if site is not None else SITE)
    )
    return respx.put(f"{CATALOGO}/sites/{SITE_ID}/menu").mock(
        return_value=httpx.Response(200, json={"menu": MENU})
    )


def _gravado(rota) -> dict:
    """O menu que a tela mandou gravar, lido da chamada de verdade."""
    return json.loads(rota.calls.last.request.content)["menu"]


# ---------------------------------------------------------------------------
# A porta
# ---------------------------------------------------------------------------


@respx.mock
def test_sem_cracha_a_tela_do_menu_nao_abre():
    resp = Client().get(reverse("menu_do_topo"))
    assert resp.status_code in (302, 404)


@respx.mock
def test_sem_cracha_nenhum_gesto_escreve():
    """A porta vem antes de tudo, inclusive dos POSTs — e um gesto que passasse
    aqui mudaria o site inteiro para todo visitante."""
    gravar = _catalogo()
    resp = Client().post(reverse("menu_criar_versao"), {"nome": "Invasor"})
    assert resp.status_code in (302, 404)
    assert not gravar.called


# ---------------------------------------------------------------------------
# A tela
# ---------------------------------------------------------------------------


@respx.mock
def test_a_tela_mostra_os_menus_e_as_opcoes():
    _catalogo()
    corpo = _dentro().get(reverse("menu_do_topo")).content.decode()
    assert "Menu completo" in corpo
    assert "Só o essencial" in corpo
    assert "Home" in corpo  # o rótulo no idioma padrão do site
    assert "/forum" in corpo


@respx.mock
def test_a_lista_de_paginas_vem_do_mapa_do_site():
    """Do arquivo, nunca de uma lista escrita nesta célula."""
    _catalogo()
    corpo = _dentro().get(reverse("menu_do_topo")).content.decode()
    # duas páginas públicas que existem no mapa e podem ter menu
    assert "A porta de entrada do site" in corpo
    assert "A tela de entrar" in corpo
    # e nada que seja rota de máquina ou tela de administração
    assert "O sinal de vida do site" not in corpo


@respx.mock
def test_a_tela_oferece_um_campo_de_nome_por_idioma_do_site():
    """Três idiomas no site, três campos. A lista sai do próprio site: idioma
    novo no catálogo faz esta tela crescer sozinha."""
    _catalogo()
    corpo = _dentro().get(reverse("menu_do_topo")).content.decode()
    for idioma in ("en", "pt-br", "es"):
        assert f'name="rotulo_{idioma}"' in corpo


@respx.mock
def test_a_pagina_sem_menu_aparece_marcada_como_tal():
    """`funil/login` está no menu com versão vazia: a tela tem de mostrar isso
    escolhido, senão o mantenedor salvaria por cima sem perceber."""
    _catalogo()
    corpo = _dentro().get(reverse("menu_do_topo")).content.decode()
    assert 'value="__nenhum__" selected' in corpo


# ---------------------------------------------------------------------------
# Os gestos
# ---------------------------------------------------------------------------


@respx.mock
def test_criar_versao_grava_o_documento_inteiro():
    gravar = _catalogo()
    resp = _dentro().post(reverse("menu_criar_versao"), {"nome": "Menu de Natal"})
    assert resp.status_code == 302
    enviado = _gravado(gravar)
    assert [v["slug"] for v in enviado["versions"]] == [
        "completo",
        "enxuto",
        "menu-de-natal",
    ]
    # o que já existia viaja junto e intacto: é o documento inteiro
    assert enviado["pages"] == MENU["pages"]


@respx.mock
def test_o_nome_que_gente_escreve_vira_apelido_sozinho():
    """O mantenedor digita 'Menu de Natal'; a regra de página precisa de
    'menu-de-natal'. Pedir os dois seria pedir que ele entendesse a diferença."""
    gravar = _catalogo()
    _dentro().post(reverse("menu_criar_versao"), {"nome": "MENU do Ção!"})
    assert _gravado(gravar)["versions"][-1]["slug"] == "menu-do-cao"


@respx.mock
def test_a_primeira_versao_vira_a_padrao_sozinha():
    """Versão criada e nenhuma página usando-a seria uma tela que 'não fez
    nada' aos olhos de quem acabou de criá-la."""
    gravar = _catalogo(site=dict(SITE, menu={}))
    _dentro().post(reverse("menu_criar_versao"), {"nome": "Primeiro"})
    assert _gravado(gravar)["default_version"] == "primeiro"


@respx.mock
def test_apagar_versao_leva_junto_as_regras_que_apontavam_para_ela():
    """As duas coisas na MESMA escrita: separá-las deixaria a configuração num
    estado que o catálogo recusa (página apontando para versão inexistente)."""
    menu = dict(MENU, pages=[{"page": "funil/cadastro", "version": "enxuto"}])
    gravar = _catalogo(site=dict(SITE, menu=menu))
    _dentro().post(reverse("menu_apagar_versao"), {"versao": "enxuto"})
    enviado = _gravado(gravar)
    assert [v["slug"] for v in enviado["versions"]] == ["completo"]
    assert enviado["pages"] == []


@respx.mock
def test_apagar_a_versao_padrao_deixa_o_site_sem_menu_em_vez_de_apontar_para_o_vazio():
    gravar = _catalogo()
    _dentro().post(reverse("menu_apagar_versao"), {"versao": "completo"})
    assert _gravado(gravar)["default_version"] == ""


@respx.mock
def test_acrescentar_item_guarda_o_idioma_sozinho_para_pagina_do_funil():
    """O mantenedor não escolhe 'traduzido': quem sabe é o mapa, porque a
    resposta depende de qual célula serve a página (R12)."""
    gravar = _catalogo()
    _dentro().post(
        reverse("menu_adicionar_item"),
        {
            "versao": "completo",
            "pagina": "/cadastro",
            "rotulo_en": "Sign up",
            "rotulo_pt-br": "Cadastro",
            "plateia": "logged_out",
        },
    )
    novo = _gravado(gravar)["versions"][0]["items"][-1]
    assert novo["url"] == "/cadastro"
    assert novo["localized"] is True
    assert novo["labels"] == {"en": "Sign up", "pt-br": "Cadastro"}
    assert novo["audience"] == "logged_out"
    assert novo["new_tab"] is False


@respx.mock
def test_endereco_de_fora_nunca_nasce_traduzido():
    gravar = _catalogo()
    _dentro().post(
        reverse("menu_adicionar_item"),
        {
            "versao": "completo",
            "pagina": "__externo__",
            "endereco": "https://www.roblox.com",
            "rotulo_en": "Roblox",
            "aba_nova": "sim",
        },
    )
    novo = _gravado(gravar)["versions"][0]["items"][-1]
    assert novo["url"] == "https://www.roblox.com"
    assert novo["localized"] is False
    assert novo["new_tab"] is True


@respx.mock
def test_item_sem_nome_nenhum_e_recusado_antes_da_rede():
    """A recusa mora no catálogo; isto só evita mandar a ele algo que já se
    sabe que ele vai recusar, e devolve a frase certa mais rápido."""
    gravar = _catalogo()
    resp = _dentro().post(
        reverse("menu_adicionar_item"), {"versao": "completo", "pagina": "/cadastro"}
    )
    assert resp.status_code == 422
    assert not gravar.called
    assert "nome" in resp.content.decode()


@respx.mock
def test_remover_item_tira_exatamente_um():
    gravar = _catalogo()
    _dentro().post(reverse("menu_remover_item"), {"versao": "completo", "indice": "0"})
    itens = _gravado(gravar)["versions"][0]["items"]
    assert [i["url"] for i in itens] == ["/forum"]


@respx.mock
def test_mover_item_troca_a_ordem():
    """A ordem da lista é a ordem na tela do site."""
    gravar = _catalogo()
    _dentro().post(
        reverse("menu_mover_item"),
        {"versao": "completo", "indice": "1", "para": "cima"},
    )
    itens = _gravado(gravar)["versions"][0]["items"]
    assert [i["url"] for i in itens] == ["/forum", "/"]


@respx.mock
def test_subir_o_primeiro_nao_escreve_nada():
    """Fim da fila não é erro: volta para a tela sem gastar uma gravação."""
    gravar = _catalogo()
    resp = _dentro().post(
        reverse("menu_mover_item"),
        {"versao": "completo", "indice": "0", "para": "cima"},
    )
    assert resp.status_code == 302
    assert not gravar.called


@respx.mock
def test_as_regras_das_paginas_salvam_de_uma_vez():
    gravar = _catalogo()
    _dentro().post(
        reverse("menu_regras_das_paginas"),
        {
            "pagina_funil/": "enxuto",
            "pagina_funil/login": "__nenhum__",
            "pagina_funil/cadastro": "__padrao__",
        },
    )
    enviado = _gravado(gravar)
    assert {"page": "funil/", "version": "enxuto"} in enviado["pages"]
    assert {"page": "funil/login", "version": ""} in enviado["pages"]
    # "usar o padrão" é a AUSÊNCIA de regra, não uma regra com valor
    assert all(r["page"] != "funil/cadastro" for r in enviado["pages"])


# ---------------------------------------------------------------------------
# Quando o outro lado diz não
# ---------------------------------------------------------------------------


@respx.mock
def test_recusa_do_catalogo_vira_frase_na_tela_e_o_menu_mostrado_e_o_gravado():
    respx.get(f"{CATALOGO}/sites/by-host/testserver").mock(
        return_value=httpx.Response(200, json=SITE)
    )
    respx.put(f"{CATALOGO}/sites/{SITE_ID}/menu").mock(
        return_value=httpx.Response(
            422, json={"detail": "endereço 'javascript:x' não é aceito"}
        )
    )
    resp = _dentro().post(
        reverse("menu_adicionar_item"),
        {
            "versao": "completo",
            "pagina": "__externo__",
            "endereco": "javascript:x",
            "rotulo_en": "Mal",
        },
    )
    assert resp.status_code == 422
    corpo = resp.content.decode()
    assert "não é aceito" in corpo
    # o que a tela mostra continua sendo o que está GRAVADO
    assert "Menu completo" in corpo


@respx.mock
def test_toda_tentativa_deixa_linha_de_auditoria_inclusive_a_recusada():
    """A Caixa e a `alunos` já guardam o que MUDOU. O que só esta tabela tem é
    a tentativa recusada: sem ela, o gesto não deixaria rastro em lugar nenhum."""
    respx.get(f"{CATALOGO}/sites/by-host/testserver").mock(
        return_value=httpx.Response(200, json=SITE)
    )
    respx.put(f"{CATALOGO}/sites/{SITE_ID}/menu").mock(
        return_value=httpx.Response(422, json={"detail": "não pode"})
    )
    _dentro().post(reverse("menu_criar_versao"), {"nome": "Qualquer"})
    registro = Registro.objects.latest("quando")
    assert registro.acao == Registro.EDITAR_MENU
    assert registro.desfecho == Registro.RECUSADO_PELA_CELULA
    assert registro.alvo == SITE_ID
    assert registro.quem_email == DONO


@respx.mock
def test_catalogo_mudo_nao_derruba_a_tela():
    """Fail-OPEN: a tela abre dizendo o que falta. Uma tela de operação que não
    abre é inútil justamente quando você precisa dela."""
    respx.get(f"{CATALOGO}/sites/by-host/testserver").mock(
        side_effect=httpx.ConnectError("sem rede")
    )
    resp = _dentro().get(reverse("menu_do_topo"))
    assert resp.status_code == 200
    assert "não consigo falar com o registro de sites" in resp.content.decode()


@respx.mock
def test_par_de_tokens_ausente_tambem_abre_a_tela(monkeypatch):
    """O par `admin→catalogo` é passo do mantenedor na VPS. Enquanto ele não
    existir, a tela explica; nada do que está no ar muda."""
    monkeypatch.delenv("TOKEN_CATALOGO", raising=False)
    resp = _dentro().get(reverse("menu_do_topo"))
    assert resp.status_code == 200
    assert "não consigo falar com o registro de sites" in resp.content.decode()


@respx.mock
def test_nenhum_gesto_escreve_quando_o_catalogo_esta_mudo():
    respx.get(f"{CATALOGO}/sites/by-host/testserver").mock(
        side_effect=httpx.ConnectError("sem rede")
    )
    gravar = respx.put(f"{CATALOGO}/sites/{SITE_ID}/menu").mock(
        return_value=httpx.Response(200, json={"menu": {}})
    )
    resp = _dentro().post(reverse("menu_criar_versao"), {"nome": "Qualquer"})
    assert resp.status_code == 503
    assert not gravar.called


# ---------------------------------------------------------------------------
# Molde nao e lugar
# ---------------------------------------------------------------------------


@respx.mock
def test_molde_nao_e_oferecido_como_destino_de_item():
    """`/forum/t/<int:topico_id>` nao e um lugar: e a forma de todos os
    assuntos do forum. Oferece-lo como destino seria um link para 404 no topo
    de toda pagina."""
    _catalogo()
    corpo = _dentro().get(reverse("menu_do_topo")).content.decode()
    # o controle positivo: pagina concreta CONTINUA sendo oferecida, senao
    # este guarda passaria com a lista inteira vazia
    assert '<option value="/forum/">' in corpo
    # e o molde nao aparece — nem cru nem escapado, que e como ele sairia
    assert 'value="/forum/t/<int:topico_id>"' not in corpo
    assert 'value="/forum/t/&lt;int:topico_id&gt;"' not in corpo
    # e o molde CONTINUA na tabela de regras: todas as conversas mostram o
    # mesmo topo, e isso e configuravel
    assert 'name="pagina_forum/t/&lt;int:topico_id&gt;"' in corpo


@respx.mock
def test_item_apontando_para_molde_e_recusado_mesmo_por_post_montado_a_mao():
    """Cinto e suspensorio: a tela nao oferece, e a escrita tambem recusa."""
    gravar = _catalogo()
    resp = _dentro().post(
        reverse("menu_adicionar_item"),
        {
            "versao": "completo",
            "pagina": "__externo__",
            "endereco": "/forum/t/<int:topico_id>",
            "rotulo_en": "Topic",
        },
    )
    assert resp.status_code == 422
    assert not gravar.called
    assert (
        "varias paginas" in resp.content.decode()
        or "várias páginas" in resp.content.decode()
    )
