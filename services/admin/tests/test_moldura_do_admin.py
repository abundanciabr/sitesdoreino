"""A MOLDURA das telas de administração: o menu do topo e o rodapé de `/admin`.

Pedido do mantenedor em 02/09/2026: *"crie uma forma de todas as páginas da
parte do admin terem o menu e o rodapé de admin, não é o mesmo menu do site, é
um menu e um rodapé exclusivo da parte de /admin"*.

O QUE CADA GUARDA DESTE ARQUIVO PROTEGE
---------------------------------------
1. **A moldura vazando para quem a porta recusa.** É o guarda mais importante
   daqui, e o único que protege uma decisão de SEGURANÇA em vez de desenho.
   `admin/404.html` estende o mesmo molde, e é ele que a porta devolve a quem
   não está na lista de administradores: um menu com as nove seções desenhado
   ali entregaria o mapa do bastidor a um estranho, e desfaria em uma linha de
   template a escolha da porta de responder "não existe" em vez de "você não
   pode".
2. **`SECOES` envelhecendo.** Ela é escrita à mão, e lista escrita à mão
   apodrece (Classe 8 do plano dos robôs sem colisão). O guarda a compara com
   as seções que `painel/mapa-do-site.json` declara, o mesmo mapa que tem
   varredor no CI provando que ele não mente sobre o roteamento. Seção nova
   reprova o PR até ganhar nome curto.
3. **A faixa copiada à mão voltando.** Ela morreu em 21 templates para nascer
   uma vez no molde. Se voltar num merge, a página passa a ter duas.
4. **"Onde você está" mentindo sob o prefixo de produção.** Esta área mora sob
   `SCRIPT_NAME=/admin`, e a `armadilhas/081` é sobre exatamente isto: o
   prefixo que `reverse()` usa é um valor de THREAD, não a variável de
   ambiente. Um guarda que só rodasse sem prefixo ficaria verde medindo o
   regime que a produção não usa.
5. **O menu levando a um link quebrado.** Toda seção tem de resolver de
   verdade, nos dois regimes.

Toda asserção é sobre o CORPO RENDERIZADO, nunca sobre o arquivo de template
(`armadilhas/087`): o que importa é o que chega ao navegador do mantenedor.

A rede é dublada com `respx`, como nos irmãos desta pasta: além de isolar, é
isso que prova que a moldura não sai para a rede por conta própria, porque
`respx.mock` sem rota registrada estoura em qualquer chamada inesperada.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx
from django.test import Client
from django.urls import get_script_prefix, reverse, set_script_prefix

from apps.core import moldura

RAIZ_DO_REPO = Path(__file__).resolve().parents[3]
MAPA = RAIZ_DO_REPO / "painel" / "mapa-do-site.json"

BASE = "http://identidade:8000/interno"
SESSAO = f"{BASE}/sessao/completa"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"
DE_FORA = "estranho@exemplo.com"


@pytest.fixture(autouse=True)
def env_da_porta(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", BASE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


def _pessoa(email: str) -> dict:
    return {
        "autenticado": True,
        "id": "id-opaco-123",
        "nome_exibido": "Fulano",
        "papel": None,
        "email": email,
    }


def _cliente(email: str = DONO) -> Client:
    respx.get(SESSAO).mock(return_value=httpx.Response(200, json=_pessoa(email)))
    c = Client()
    c.defaults["HTTP_COOKIE"] = COOKIE
    return c


def _texto(resposta) -> str:
    return resposta.content.decode()


@pytest.fixture
def sob_o_prefixo_publico():
    """O regime de produção: a área inteira mora sob `/admin`.

    Mexe no PREFIXO DE SCRIPT, e não em `settings.FORCE_SCRIPT_NAME`, porque é
    o prefixo de thread que `reverse()` lê (`armadilhas/081`); ajustar só a
    variável deixaria o teste verde sem medir o regime de produção. O `finally`
    restaura o anterior: o prefixo vaza para os testes seguintes, e o vermelho
    apareceria num arquivo sem relação nenhuma.
    """
    anterior = get_script_prefix()
    set_script_prefix("/admin/")
    try:
        yield
    finally:
        set_script_prefix(anterior)


# ---------------------------------------------------------------------------
# 1. A moldura não existe para quem a porta recusa
# ---------------------------------------------------------------------------
def test_sem_cracha_a_moldura_nao_existe():
    """Fail-closed na fonte: sem `request.admin`, o processador devolve vazio."""

    class Pedido:
        path_info = "/"

    assert moldura.moldura_do_contexto(Pedido()) == {}


@respx.mock
def test_quem_a_porta_recusa_nao_ve_o_menu_do_bastidor():
    """O 404 da porta usa o MESMO molde, e não pode entregar o mapa da área.

    Este é o guarda de segurança do arquivo. Se alguém tirar o `{% if admin %}`
    de `admin/base.html` achando que é decoração, é aqui que fica vermelho.
    """
    resposta = _cliente(DE_FORA).get(reverse("escola"))
    assert resposta.status_code == 404
    html = _texto(resposta)
    assert 'class="menu-do-admin"' not in html
    assert 'class="rodape-do-admin"' not in html
    for _, rotulo in moldura.SECOES:
        assert f">{rotulo}</a>" not in html


@respx.mock
def test_quem_nem_entrou_nao_ve_o_menu_do_bastidor():
    resposta = Client().get(reverse("escola"))
    assert resposta.status_code == 302
    assert "menu-do-admin" not in _texto(resposta)


# ---------------------------------------------------------------------------
# 2. A lista de seções não envelhece
# ---------------------------------------------------------------------------
def secoes_pelo_mapa() -> set:
    """Os NOMES das rotas que o mapa declara como SEÇÃO desta área.

    Seção é uma página de `/admin` que não pende de outra: `rota` sem barra no
    meio. `escola/` é seção; `escola/alunos/` mora dentro dela. Derivar em vez
    de reescrever é o que faz esta comparação valer alguma coisa: duas listas à
    mão concordariam por terem sido copiadas uma da outra.
    """
    assert MAPA.is_file(), (
        f"{MAPA} não existe. Este guarda não tem o que medir, e isso não é um "
        "OK — [INV-CI01]."
    )
    dados = json.loads(MAPA.read_text(encoding="utf-8"))
    padroes = set()
    for entrada in dados["enderecos"]:
        if entrada.get("celula") != "admin":
            continue
        if entrada.get("para_quem") != "equipe" or entrada.get("gesto"):
            continue
        rota = entrada["rota"]
        if "<" in rota or "(?P" in rota:
            continue  # molde: vale para muitos endereços, não é um lugar
        if rota.rstrip("/").count("/"):
            continue  # pende de uma seção, não é uma
        padroes.add(rota)
    assert padroes, (
        "o mapa não declara seção nenhuma nesta célula — isto é falha de "
        "medição, não notícia boa ([INV-CI01])."
    )
    prefixo = get_script_prefix()
    nomes = {
        nome for nome, _ in moldura.SECOES if reverse(nome)[len(prefixo) :] in padroes
    }
    assert len(nomes) == len(padroes), (
        f"o mapa declara {len(padroes)} seção(ões) nesta área e eu casei "
        f"{len(nomes)} pelo urlconf. Seção nova precisa de nome curto em "
        f"`apps/core/moldura.py::SECOES`; seção que morreu precisa sair de lá. "
        f"Não relaxe esta asserção: é ela que impede o menu de envelhecer."
    )
    return nomes


def test_as_secoes_do_menu_batem_com_o_mapa_do_site():
    """Seção nova entra no menu no MESMO PR, nos dois sentidos.

    Faltando, a tela nova nasce inalcançável pelo menu e só quem souber o
    endereço de cor chega nela. Sobrando, o menu promete uma porta que não
    existe mais.
    """
    assert {nome for nome, _ in moldura.SECOES} == secoes_pelo_mapa()


def test_cada_secao_tem_um_rotulo_curto_e_unico():
    rotulos = [rotulo for _, rotulo in moldura.SECOES]
    assert len(rotulos) == len(set(rotulos)), "dois itens do menu com o mesmo nome"
    for rotulo in rotulos:
        assert rotulo.strip() and len(rotulo) <= 20, (
            f"{rotulo!r} não é nome curto de menu. Rótulo longo quebra a faixa "
            "em várias linhas no celular do mantenedor."
        )


# ---------------------------------------------------------------------------
# 3. O que a página servida realmente mostra
# ---------------------------------------------------------------------------
@respx.mock
def test_toda_tela_da_area_traz_o_menu_e_o_rodape():
    """A prova de que "todas as páginas" não depende de ninguém lembrar.

    As telas escolhidas cobrem os quatro cantos da área: a capa, uma seção,
    uma página FILHA de seção (que nunca teve navegação própria) e uma tela que
    lê o mapa do site.
    """
    cliente = _cliente()
    for rota in ("visao_geral", "escola", "escola_jornada", "perpetuo"):
        html = _texto(cliente.get(reverse(rota)))
        assert 'class="menu-do-admin"' in html, f"{rota} abriu sem o menu"
        assert 'class="rodape-do-admin"' in html, f"{rota} abriu sem o rodapé"
        assert "Ver o site como um visitante" in html
        for _, rotulo in moldura.SECOES:
            assert f">{rotulo}</a>" in html, f"{rota} não oferece {rotulo!r}"


@respx.mock
def test_a_faixa_copiada_a_mao_nao_voltou():
    """Ela nasce UMA vez no molde. Duas seria a marca de um merge desatento."""
    html = _texto(_cliente().get(reverse("escola")))
    assert html.count('class="barra"') == 1
    assert html.count("Meshcraft &middot; Administração") == 1


@respx.mock
def test_o_menu_acende_onde_voce_esta():
    cliente = _cliente()
    html = _texto(cliente.get(reverse("escola")))
    assert f'href="{reverse("escola")}" class="aqui" aria-current="page"' in html
    assert html.count('class="aqui"') == 1, "duas seções acesas ao mesmo tempo"


@respx.mock
def test_a_capa_so_acende_na_capa():
    """A CASA é prefixo de todo mundo: por prefixo, ela acenderia sempre."""
    cliente = _cliente()
    na_capa = _texto(cliente.get(reverse("visao_geral")))
    assert f'href="{reverse("visao_geral")}" class="aqui"' in na_capa

    # O `href="` da frente é a âncora, e não é preciosismo: sem prefixo o
    # endereço da capa é `/`, que casa DENTRO de `/escola/`. Sem ele este
    # guarda ficaria vermelho com o código certo.
    na_escola = _texto(cliente.get(reverse("escola")))
    assert f'href="{reverse("visao_geral")}" class="aqui"' not in na_escola


@respx.mock
def test_a_pagina_filha_acende_a_secao_dela():
    """`/escola/alunos/` é da Escola, e o menu diz isso.

    Sem esta regra, toda página funda da área abriria com o menu apagado e o
    mantenedor perderia a única pista de onde está.
    """
    html = _texto(_cliente().get(reverse("escola_alunos")))
    assert f'href="{reverse("escola")}" class="aqui"' in html
    assert html.count('class="aqui"') == 1


# ---------------------------------------------------------------------------
# 4. O regime de produção, sob o prefixo `/admin`
# ---------------------------------------------------------------------------
def test_o_menu_aponta_para_dentro_do_prefixo(sob_o_prefixo_publico):
    """Os endereços saem de `reverse()`, então o prefixo entra sozinho.

    Somar `/admin` a uma rota à mão é a `armadilhas/197`: o endereço público
    de uma célula sob prefixo não é "prefixo + rota", e já dobrou uma vez.
    """
    itens = moldura.secoes_do_menu("/escola/")
    assert itens, "o menu ficou vazio sob o prefixo de produção"
    for item in itens:
        assert item["href"].startswith("/admin/"), item
        assert "/admin/admin/" not in item["href"], item


def test_onde_voce_esta_continua_certo_sob_o_prefixo(sob_o_prefixo_publico):
    """O guarda que a primeira versão deste código teria reprovado.

    Ela comparava `request.path` com `reverse()`, e em produção os dois lados
    concordam por acaso; na suíte, não. Descontar o prefixo dos dois é o que
    faz a mesma conta valer nos dois regimes.
    """
    acesas = [
        i["rotulo"] for i in moldura.secoes_do_menu("/escola/alunos/") if i["aqui"]
    ]
    assert acesas == ["Escola"], acesas

    acesas = [i["rotulo"] for i in moldura.secoes_do_menu("/") if i["aqui"]]
    assert acesas == ["Visão geral"], acesas


def test_toda_secao_resolve_nos_dois_regimes(sob_o_prefixo_publico):
    """Item de menu que não resolve some da tela, e sumir em silêncio é o pior.

    O código PULA a seção que não resolve, porque um link para 404 faz o
    mantenedor concluir que o site caiu. Este guarda é o que impede esse pulo
    de acontecer sem ninguém ver.
    """
    assert len(moldura.secoes_do_menu("/")) == len(moldura.SECOES)


# ---------------------------------------------------------------------------
# 5. O rodapé desta área não é o do site
# ---------------------------------------------------------------------------
@respx.mock
def test_o_rodape_do_bastidor_nao_e_a_assinatura_do_site():
    """São duas peças diferentes, e misturá-las diria ao mantenedor que ele
    está no site quando está na sala de máquinas."""
    html = _texto(_cliente().get(reverse("escola")))
    assert "Todos os direitos reservados" not in html
    assert 'class="rodape rodape-' not in html
    assert "sala de máquinas" in html


def test_o_rodape_declara_o_endereco_que_e_de_outra_celula():
    """Os guardas de prefixo (`armadilhas/029` e `/081`) leem esta declaração.

    Endereço de outra célula escrito à mão precisa sair de quem o declara, e
    não de uma cópia dentro do teste.
    """
    assert moldura.URL_DO_SITE in moldura.enderecos_de_outras_celulas()
