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
        assert f'>{moldura.SAIDA_PARA_O_SITE["rotulo"]}</a>' in html
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

    # O primeiro item é a SAÍDA, e ela é a única que não mora sob o prefixo:
    # `/` é endereço de outra célula. Se um dia ela ganhar `/admin` na frente,
    # o botão de "ver o site" passará a apontar para dentro do bastidor.
    assert itens[0]["href"] == moldura.URL_DO_SITE, itens[0]

    for item in itens[1:]:
        assert item["href"].startswith("/admin/"), item
        assert "/admin/admin/" not in item["href"], item

    # A saída aparece UMA vez, e este é o único regime em que dá para perguntar
    # isso: sem o prefixo, `reverse("visao_geral")` também é `/`, e o site e a
    # capa viram a mesma string. Sob o prefixo elas são `/` e `/admin/`.
    assert [i["href"] for i in itens].count(moldura.URL_DO_SITE) == 1


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
    assert len(moldura.secoes_do_menu("/")) == len(moldura.SECOES) + 1


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


# ---------------------------------------------------------------------------
# 6. O caminho de volta não é dito duas vezes (02/09/2026)
# ---------------------------------------------------------------------------
# Assim que o menu nasceu, o link `← Visão geral` no alto de cada tela virou a
# segunda cópia de um botão que agora existe em TODA página. Escolha do
# mantenedor no mesmo dia: tirar onde repete, manter onde é um passo de verdade
# (a ficha de um aluno volta para a lista de alunos, não para a capa).
TELAS = Path(__file__).resolve().parents[1] / "apps" / "core" / "templates" / "admin"


def test_nenhuma_tela_repete_a_volta_para_a_visao_geral():
    """A capa mora no menu, e o menu está em toda tela desta área.

    Este guarda é de FONTE, e não de página renderizada, de propósito: ele
    precisa alcançar as telas que a suíte não consegue abrir sem montar dado
    (a ficha de uma pessoa, uma ideia da Caixa). O que ele mede é uma marcação
    exata, não uma aparência, e para isso a fonte basta.
    """
    reincidentes = [
        arquivo.name
        for arquivo in sorted(TELAS.glob("*.html"))
        for linha in arquivo.read_text(encoding="utf-8").splitlines()
        if 'class="volta"' in linha and "visao_geral" in linha
    ]
    assert not reincidentes, (
        f"estas telas voltaram a escrever o caminho para a capa à mão: "
        f"{reincidentes}. Ele já está no menu do topo, em toda página da área "
        f"(`apps/core/moldura.py`). Escrever de novo dá ao mantenedor dois "
        f"botões para a mesma porta na mesma tela."
    )


@respx.mock
def test_a_capa_continua_a_um_clique_de_toda_tela():
    """O par do guarda acima: o caminho não sumiu, MUDOU de lugar.

    Sem este, "tirar o link repetido" e "tirar o único link" ficariam
    indistinguíveis para a suíte.
    """
    html = _texto(_cliente().get(reverse("escola")))
    assert f'href="{reverse("visao_geral")}"' in html
    assert ">Visão geral</a>" in html


def test_as_telas_da_caixa_mantiveram_o_passo_para_a_mesa():
    """As quatro abas são telas de DENTRO da Caixa, e o menu só leva à Caixa.

    Elas não perderam nada ao ficar sem o `← Visão geral`, porque a faixa de
    abas (`admin/_caixa_abas.html`) já leva de volta à mesa. Este guarda é o
    que prova isso, em vez de eu ter conferido com o olho e escrito "confiro
    que está tudo bem" no relatório.

    A regra vale para toda tela `caixa_*.html`, inclusive uma que nasça amanhã:
    ou ela traz a faixa de abas, ou ela escreve o próprio caminho para a mesa.
    """
    sem_saida = []
    for arquivo in sorted(TELAS.glob("caixa_*.html")):
        fonte = arquivo.read_text(encoding="utf-8")
        if "_caixa_abas.html" in fonte:
            continue
        if 'class="volta"' in fonte and "'caixa'" in fonte:
            continue
        sem_saida.append(arquivo.name)
    assert not sem_saida, (
        f"estas telas da Caixa não oferecem caminho de volta à mesa: "
        f"{sem_saida}. O menu do topo leva à Caixa, mas quem está numa aba "
        f"precisa das abas ou de um link próprio."
    )


# ---------------------------------------------------------------------------
# 7. A saída para o site é o PRIMEIRO item do menu (02/09/2026)
# ---------------------------------------------------------------------------
# Escolha do mantenedor no dia seguinte ao menu nascer: *"coloque o primeiro
# link do Menu do Admin para ser o link para a / home, acho que antes de Visão
# Geral"*. Ela mexe em três coisas que podem quebrar em silêncio, e cada uma
# tem um guarda abaixo.
def test_o_site_e_o_primeiro_item_do_menu():
    itens = moldura.secoes_do_menu("/")
    assert itens[0]["href"] == moldura.URL_DO_SITE
    assert itens[0]["rotulo"] == moldura.SAIDA_PARA_O_SITE["rotulo"]
    assert itens[1]["rotulo"] == "Visão geral", "a capa tem de vir logo depois"


def test_a_saida_para_o_site_nunca_acende():
    """Você não está NO site enquanto está aqui dentro.

    Se ela acendesse, seria a única luz de "onde você está" que mentiria — e
    nas telas de dentro haveria duas acesas ao mesmo tempo.
    """
    for caminho in ("/", "/escola/", "/escola/alunos/", "/caixa/travessia/"):
        assert moldura.secoes_do_menu(caminho)[0]["aqui"] is False, caminho


def test_a_saida_nao_entra_na_conta_das_secoes():
    """Ela não é uma seção desta área, e o guarda do mapa mede seções.

    Se algum dia alguém a empurrar para dentro de `SECOES` para "simplificar",
    duas coisas quebram de uma vez: `reverse()` estoura num endereço de outra
    célula, e a comparação com `painel/mapa-do-site.json` deixa de fechar. É
    mais barato reprovar aqui, dizendo o porquê.
    """
    assert moldura.URL_DO_SITE not in [nome for nome, _ in moldura.SECOES]
    assert moldura.SAIDA_PARA_O_SITE["rotulo"] not in [r for _, r in moldura.SECOES]


def test_a_capa_esta_amarrada_ao_nome_e_nao_a_posicao():
    """O defeito que esta mudança quase criou, travado antes de existir.

    `CASA` era `SECOES[0][0]` — "o primeiro da lista". Enquanto a capa fosse de
    fato a primeira, as duas leituras davam o mesmo resultado; o defeito ficaria
    DORMINDO até alguém reordenar o menu, e aí a capa pararia de acender em
    silêncio.

    **Este guarda lê a FONTE, e a razão é honesta: nenhum teste de execução
    conseguiria separar as duas.** `CASA` é resolvida uma vez, na importação do
    módulo; reordenar `SECOES` de dentro de um teste não a recalcula, e as duas
    formas passariam igual. Escrever um teste de execução aqui daria a sensação
    de proteção sem a proteção — que é pior que não ter guarda nenhum. Medir a
    linha é o que sobra, e ela é medível.
    """
    fonte = Path(moldura.__file__).read_text(encoding="utf-8")
    assert (
        'CASA = "visao_geral"' in fonte
    ), "a capa precisa ser nomeada, não deduzida da posição na lista"
    assert "CASA = SECOES[" not in fonte, (
        "`CASA` voltou a ser 'o primeiro da lista'. Hoje o primeiro item é a "
        "saída para o site, então isso faria a capa parar de acender sozinha."
    )

    # E a metade que a execução mede de verdade: a capa acende na capa.
    acesas = [i["rotulo"] for i in moldura.secoes_do_menu("/") if i["aqui"]]
    assert acesas == ["Visão geral"], acesas


@respx.mock
def test_o_site_aparece_uma_vez_so_na_tela():
    """O rodapé largou o link quando o menu o assumiu.

    Duas portas para o mesmo lugar na mesma tela é exatamente a repetição que
    o mantenedor mandou tirar no PR #891, poucas horas antes desta mudança.
    """
    html = _texto(_cliente().get(reverse("escola")))

    # Medido no RODAPÉ, e não no documento inteiro, pela razão da
    # `armadilhas/292` — e aqui há um motivo a mais, específico: SEM o prefixo
    # de produção, `reverse("visao_geral")` também é `/`, então o site e a capa
    # viram a mesma string e uma contagem no documento acusaria repetição onde
    # não há. O rodapé é o pedaço de que esta pergunta trata.
    rodape = html[html.index('<footer class="rodape-do-admin">') :]
    assert "Ver o site como um visitante" not in rodape
    assert f'href="{moldura.URL_DO_SITE}"' not in rodape
    assert "Ver a biblioteca pública" in rodape, "a outra saída do rodapé continua"
