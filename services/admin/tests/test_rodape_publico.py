"""As duas peças do site nas páginas PÚBLICAS desta célula (`/docs/`).

Esta célula é bastidor com duas janelas para a rua, e por isso a regra aqui é a
INVERTIDA das outras: o padrão é NÃO mostrar as peças, e as rotas públicas são a
exceção declarada. Ver o cabeçalho de `apps/core/rodape.py` para o porquê.

O QUE CADA GUARDA DESTE ARQUIVO PROTEGE
---------------------------------------
1. **A lista `ROTAS_PUBLICAS` envelhecendo.** Ela é escrita à mão, e lista
   escrita à mão apodrece — é a Classe 8 do plano dos robôs sem colisão. O
   guarda a compara com o que `painel/mapa-do-site.json` declara público NESTA
   célula: página pública nova reprova o PR até entrar na lista.
2. **O bastidor ganhando a assinatura do site sem ninguém pedir.** A barra e o
   rodapé do site em cima da área de administração diriam ao mantenedor "você
   está no site" quando ele está na sala de máquinas.
3. **A tabela certa e o molde ignorando a decisão.** Toda asserção é sobre o
   CORPO RENDERIZADO (`armadilhas/087`).
4. **O estilo que não chega.** Aqui o CSS é EMBUTIDO no molde — então a prova é
   que a regra está na página servida, não num arquivo à parte.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from django.urls import get_resolver, reverse

from apps.core import rodape as regras

RAIZ_DO_REPO = Path(__file__).resolve().parents[3]
MAPA = RAIZ_DO_REPO / "painel" / "mapa-do-site.json"


def rotas_publicas_pelo_mapa() -> set:
    """Os NOMES das rotas que o mapa do site declara públicas nesta célula.

    O mapa guarda o PADRÃO da rota (`docs/`, `^docs/(?P<nome>…)$`), que é a
    mesma string do `urls.py`; daí sai o nome. Derivar em vez de reescrever é o
    que faz esta comparação valer alguma coisa — duas listas à mão concordariam
    por copiar uma da outra.
    """
    assert MAPA.is_file(), (
        f"{MAPA} não existe. Este guarda não tem o que medir, e isso não é um "
        "OK — [INV-CI01]."
    )
    dados = json.loads(MAPA.read_text(encoding="utf-8"))
    padroes = {
        entrada["rota"]
        for entrada in dados["enderecos"]
        if entrada.get("celula") == "admin"
        and entrada.get("alcance") == "publico"
        and not entrada.get("gesto")
        and entrada.get("para_quem") in ("visitante", "aluno")
    }
    assert padroes, (
        "o mapa não declara página pública nenhuma nesta célula — isto é falha "
        "de medição, não notícia boa ([INV-CI01])."
    )
    nomes = {
        padrao.name
        for padrao in get_resolver().url_patterns
        if getattr(padrao, "name", None) and str(padrao.pattern) in padroes
    }
    assert len(nomes) == len(padroes), (
        f"o mapa declara {len(padroes)} rota(s) pública(s) nesta célula e eu "
        f"casei {len(nomes)} no urlconf. Se o padrão de uma rota mudou, o mapa "
        f"precisa mudar junto — não relaxe esta asserção."
    )
    return nomes


# ---------------------------------------------------------------------------
# 1. A lista não envelhece
# ---------------------------------------------------------------------------
def test_a_lista_de_rotas_publicas_bate_com_o_mapa_do_site():
    """Página pública nova nesta célula entra em `ROTAS_PUBLICAS` no MESMO PR.

    Nos dois sentidos: faltando, a página nasce sem as peças do site e ninguém
    percebe (foi assim que `/conquistas/` passou um dia e meio sozinha —
    `armadilhas/286`). Sobrando, a lista promete rodapé numa rota que não
    existe mais.
    """
    assert set(regras.ROTAS_PUBLICAS) == rotas_publicas_pelo_mapa()


def test_toda_rota_publica_tem_uma_variante_que_existe():
    for nome in regras.ROTAS_PUBLICAS:
        assert regras.variante_da_rota(nome) in regras.VARIANTES


def test_o_bastidor_nao_ganha_a_assinatura_do_site():
    """O padrão desta célula é NÃO mostrar, e é isso que o mantém honesto.

    Tela nova do bastidor nasce sem a barra e sem o rodapé do site, sem ninguém
    precisar lembrar de tirá-los.
    """
    assert regras.variante_da_rota("visao_geral") is None
    assert regras.variante_da_rota("painel") is None
    assert regras.variante_da_rota("uma-tela-do-bastidor-que-nascer-amanha") is None
    assert regras.variante_da_rota(None) is None


# ---------------------------------------------------------------------------
# 2. O que a página servida realmente mostra
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_a_biblioteca_publica_tem_o_rodape_do_site(client):
    corpo = client.get(reverse("docs_publicos")).content.decode()
    assert '<footer class="rodape rodape-completo">' in corpo
    assert "Meshcraft Academy" in corpo
    assert "Todos os direitos reservados" in corpo
    for rotulo in ("Início do site", "Documentos"):
        assert f">{rotulo}</a>" in corpo


@pytest.mark.django_db
def test_o_pe_antigo_de_uma_linha_nao_voltou(client):
    """A troca foi ESCOLHA do mantenedor em 02/09/2026, não descuido.

    Ele viu as duas opções — trocar pelo rodapé do site, ou manter o pé pequeno
    e pôr o do site embaixo — e escolheu trocar. Se este guarda ficar vermelho,
    alguém trouxe o pé antigo de volta num merge.
    """
    corpo = client.get(reverse("docs_publicos")).content.decode()
    assert "voltar ao site" not in corpo


@pytest.mark.django_db
def test_o_estilo_das_duas_pecas_vem_junto_com_a_pagina(client):
    """Aqui o CSS é EMBUTIDO no molde (célula sob prefixo, `armadilhas/083`),
    então a prova é que a regra está na página servida — classe no HTML sem
    regra no estilo é uma peça sem forma, e nada ficaria vermelho."""
    corpo = client.get(reverse("docs_publicos")).content.decode()
    for regra in (
        ".rodape .marca",
        ".rodape .links",
        ".barra-do-site",
        "position: sticky",
    ):
        assert regra in corpo


@pytest.mark.django_db
def test_sem_menu_configurado_a_biblioteca_abre_igual(client):
    """O estado real enquanto o catálogo não responder: sem barra, sem erro.

    Um menu é enfeite de navegação; derrubar a biblioteca de documentos por
    causa dele seria a troca errada.
    """
    resposta = client.get(reverse("docs_publicos"))
    assert resposta.status_code == 200
    # A MARCAÇÃO, e não o nome da classe: o CSS desta célula é EMBUTIDO no
    # molde, então `menu-topo` aparece na página como REGRA DE ESTILO mesmo sem
    # barra nenhuma. Procurar a string solta é a `armadilhas/247` — o guarda
    # ficaria vermelho por ler o estilo como se fosse conteúdo da tela.
    assert '<nav class="menu-topo">' not in resposta.content.decode()


# ---------------------------------------------------------------------------
# 3. O item do lugar onde você já está não aparece
# ---------------------------------------------------------------------------
MENU_DE_TESTE = {
    "default_version": "v",
    "versions": [
        {
            "slug": "v",
            "name": "V",
            "items": [
                {
                    "url": "/",
                    "labels": {"pt-br": "Início"},
                    "localized": False,
                    "audience": "everyone",
                    "new_tab": False,
                },
                {
                    "url": "/docs/",
                    "labels": {"pt-br": "Documentos"},
                    "localized": False,
                    "audience": "everyone",
                    "new_tab": False,
                },
            ],
        }
    ],
    "pages": [],
}

SITE_DE_TESTE = {
    "id": "site-mesh",
    "host": "testserver",
    "default_language": "pt-br",
    "menu": MENU_DE_TESTE,
}


@pytest.fixture
def catalogo_dublado(monkeypatch):
    from apps.core import barra_do_site

    barra_do_site.limpar_cache()
    monkeypatch.setattr(
        "apps.core.barra_do_site.CatalogoClient",
        lambda: type(
            "Dublê", (), {"site_por_host": lambda self, host: SITE_DE_TESTE}
        )(),
    )
    yield
    barra_do_site.limpar_cache()


@pytest.mark.django_db
def test_o_item_documentos_some_dentro_da_propria_biblioteca(
    client, settings, catalogo_dublado
):
    """Um link para onde você já está gasta espaço e ensina a desconfiar do menu.

    **Esta célula é a exceção da casa, e o conserto foi MEDIDO.** Nas outras, o
    prefixo público faz parte do endereço do item e `request.path` casa. Aqui o
    `FORCE_SCRIPT_NAME` é `/admin` e a biblioteca é servida em `/docs/`: o
    `request.path` sai `/admin/docs/` e não casa com o item `/docs/`.

    Antes do conserto, a barra renderizava, numa requisição a `/docs/` sob
    `SCRIPT_NAME=/admin`:

        <a href="/">Início</a><a href="/docs/">Documentos</a>

    Por isso a comparação é contra `path_info`, e por isso este guarda liga o
    `FORCE_SCRIPT_NAME`: sem ele o teste passaria por acidente, medindo um mundo
    que não é o de produção.
    """
    settings.FORCE_SCRIPT_NAME = "/admin"
    corpo = client.get("/docs/").content.decode()

    inicio = corpo.index('<nav class="menu-topo">')
    menu = corpo[inicio : corpo.index("</nav>", inicio)]
    assert 'href="/docs/"' not in menu
    assert ">Início</a>" in menu, (
        "a raiz sumiu junto — `/` é prefixo de QUALQUER caminho, e tratá-la "
        "como as outras faria 'Início' desaparecer do site inteiro."
    )


# ---------------------------------------------------------------------------
# 4. As peças NÃO vazam para o bastidor
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_a_barra_do_site_nao_aparece_no_bastidor(client, rf):
    """A prova é sobre o PROCESSADOR, e não sobre uma página do bastidor.

    Uma página do bastidor exige a porta fail-closed desta célula, e um teste
    que passasse por ela mediria a porta, não a peça — ficaria verde por
    redirecionamento, que é uma segunda causa suficiente para o "não tem menu"
    (`armadilhas/266`).
    """
    from apps.core import barra_do_site

    class Casamento:
        def __init__(self, nome, rota):
            self.url_name = nome
            self.route = rota

    def requisicao_de(nome, rota):
        pedido = rf.get("/")
        pedido.resolver_match = Casamento(nome, rota)
        return pedido

    assert barra_do_site.menu_do_contexto(requisicao_de("visao_geral", "")) == {}
    assert regras.rodape_do_contexto(requisicao_de("visao_geral", "")) == {}
    assert "rodape" in regras.rodape_do_contexto(
        requisicao_de("docs_publicos", "docs/")
    )
