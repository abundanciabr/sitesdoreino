"""A semeadura do atalho da equipe (migração `sites/0006`).

As migrações de semeadura desta célula (0004, 0005) nunca tiveram guarda, e a
regra que elas seguem é fácil de quebrar sem ninguém ver: **acrescentar só se
ninguém já apontar para aquele endereço, e não tocar em mais nada.**

Uma migração que sobrescrevesse apagaria escolha do mantenedor — os rótulos que
ele reescreveu, a ordem em que ele pôs os itens, as regras por página. E o
sintoma seria mudo: o menu volta a um estado antigo depois de um deploy, sem
erro em lugar nenhum.

O guarda chama a função da migração direto, com o model de verdade. Não é a
mesma coisa que rodar a migração (o histórico não é este model), mas é a mesma
LÓGICA, que é o que pode estar errado aqui — o encanamento do `RunPython` é do
Django e já tem dono.
"""

from __future__ import annotations

import pytest
from django.apps import apps as apps_reais

pytestmark = pytest.mark.django_db


def _migracao():
    """O módulo da migração, importado por nome.

    Nome de módulo começando com dígito não entra num `import` normal, e é por
    isso que ele vem por `importlib` em vez de no topo do arquivo.
    """
    import importlib

    return importlib.import_module(
        "apps.sites.migrations.0006_menu_ganha_o_atalho_da_equipe"
    )


def _site(menu: dict):
    Site = apps_reais.get_model("sites", "Site")
    return Site.objects.create(
        host="exemplo.test",
        name="Exemplo",
        active=True,
        default_language="pt-br",
        # `languages` junto: o model recusa idioma padrao declarado sem a lista
        # ("site sem idiomas e monolingue e nao tem idioma padrao"). O guarda
        # nao e sobre isso, mas um dado que o model recusa nao mede nada.
        languages=[{"code": "pt-br"}],
        menu=menu,
    )


def _menu_com(itens: list) -> dict:
    return {
        "default_version": "v",
        "versions": [{"slug": "v", "name": "V", "items": itens}],
        "pages": [],
    }


def _rodar():
    _migracao().acrescentar(apps_reais, None)


def _itens(site):
    site.refresh_from_db()
    return site.menu["versions"][0]["items"]


# ---------------------------------------------------------------------------
# O que ela faz
# ---------------------------------------------------------------------------
def test_o_atalho_nasce_com_a_plateia_de_equipe():
    site = _site(
        _menu_com(
            [
                {
                    "url": "/",
                    "labels": {"pt-br": "Início"},
                    "localized": True,
                    "audience": "everyone",
                    "new_tab": False,
                }
            ]
        )
    )
    _rodar()

    novos = [i for i in _itens(site) if i["url"] == "/admin/"]
    assert len(novos) == 1
    assert novos[0]["audience"] == "staff", (
        "o atalho nasceu com outra plateia — com `everyone` ele apareceria para "
        "todo visitante do site, que é exatamente o oposto do pedido."
    )
    assert novos[0]["labels"]["pt-br"] == "Admin"
    assert novos[0]["localized"] is False


# ---------------------------------------------------------------------------
# O que ela NÃO faz — a metade que protege a escolha do mantenedor
# ---------------------------------------------------------------------------
def test_nao_acrescenta_de_novo_quando_o_endereco_ja_esta_la():
    """Rodar duas vezes não cria dois atalhos.

    Vale para o caso real: o mantenedor já acrescentou o item pela tela, com o
    rótulo dele, antes de esta migração rodar.
    """
    site = _site(
        _menu_com(
            [
                {
                    "url": "/admin/",
                    "labels": {"pt-br": "Minha sala de máquinas"},
                    "localized": False,
                    "audience": "staff",
                    "new_tab": False,
                }
            ]
        )
    )
    _rodar()
    _rodar()

    do_admin = [i for i in _itens(site) if i["url"] == "/admin/"]
    assert len(do_admin) == 1
    assert do_admin[0]["labels"]["pt-br"] == "Minha sala de máquinas", (
        "a migração sobrescreveu o rótulo que o mantenedor escreveu. Ela "
        "ACRESCENTA; nunca reescreve."
    )


def test_nao_mexe_na_ordem_nem_nos_outros_itens():
    antes = [
        {
            "url": "/forum/",
            "labels": {"pt-br": "Fórum"},
            "localized": False,
            "audience": "everyone",
            "new_tab": False,
        },
        {
            "url": "/",
            "labels": {"pt-br": "Começo"},
            "localized": True,
            "audience": "everyone",
            "new_tab": False,
        },
    ]
    site = _site(_menu_com([dict(i) for i in antes]))
    _rodar()

    depois = _itens(site)
    assert depois[: len(antes)] == antes, (
        "a migração mexeu nos itens que já existiam, ou na ordem deles. O "
        "mantenedor arrasta os itens na tela; a ordem é escolha dele."
    )
    assert depois[-1]["url"] == "/admin/"


def test_site_sem_menu_continua_sem_menu():
    """Site que nunca teve menu não ganha um só por causa deste item."""
    site = _site({})
    _rodar()
    site.refresh_from_db()
    assert site.menu == {}


def test_desfazer_nao_remove_nada():
    """Voltar a migração não pode levar junto o que o mantenedor escreveu."""
    site = _site(
        _menu_com(
            [
                {
                    "url": "/admin/",
                    "labels": {"pt-br": "Admin"},
                    "localized": False,
                    "audience": "staff",
                    "new_tab": False,
                }
            ]
        )
    )
    _migracao().desfazer(apps_reais, None)
    assert len(_itens(site)) == 1
