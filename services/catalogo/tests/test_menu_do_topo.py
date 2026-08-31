"""O menu do topo como dado do site: a regra de coerência e as duas portas.

O que estes testes protegem, em uma frase cada:

- o menu **sai junto com o site**, e some da resposta quando não existe (é isso
  que mantém intocado o site que ainda não tem menu);
- a configuração **incoerente não entra no banco** por caminho nenhum, nem pelo
  `save()`, nem pelo `update()` do queryset;
- a escrita é **do documento inteiro**, e uma escrita recusada não deixa
  metade gravada.
"""

import pytest
from django.core.exceptions import ValidationError

from apps.sites.menu import normalizar_menu
from apps.sites.models import Site

MENU_DE_EXEMPLO = {
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
                },
                {
                    "url": "/forum",
                    "labels": {"pt-br": "Fórum", "en": "Forum", "es": "Foro"},
                    "localized": False,
                },
                {
                    "url": "/cadastro",
                    "labels": {"pt-br": "Cadastro", "en": "Sign up", "es": "Registro"},
                    "localized": True,
                    "audience": "logged_out",
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
                }
            ],
        },
    ],
    "pages": [
        {"page": "funil/cadastro", "version": "enxuto"},
        {"page": "funil/login", "version": ""},
    ],
}


@pytest.fixture
def token_valido(settings):
    settings.TOKENS_ACEITOS = {"token-de-teste"}
    return "token-de-teste"


@pytest.fixture
def site(db):
    return Site.objects.create(host="escola.exemplo", name="Escola de exemplo")


# ---------------------------------------------------------------------------
# A regra de coerência (apps/sites/menu.py)
# ---------------------------------------------------------------------------


def test_menu_vazio_continua_vazio():
    """Site sem menu é `{}`, e passa intocado. É a forma que faz a resposta da
    API ficar byte a byte igual à de antes desta fase."""
    assert normalizar_menu({}) == {}
    assert normalizar_menu(None) == {}


def test_a_forma_canonica_preenche_todo_padrao():
    """Canônico quer dizer: nenhuma chave depende de alguém lembrar do default
    do contrato. É o que faz a comparação de 'mudou?' ser um != honesto."""
    saida = normalizar_menu(
        {
            "versions": [
                {
                    "slug": "unica",
                    "name": "Única",
                    "items": [{"url": "/", "labels": {"pt-br": "Início"}}],
                }
            ]
        }
    )
    item = saida["versions"][0]["items"][0]
    assert item == {
        "url": "/",
        "labels": {"pt-br": "Início"},
        "localized": True,  # caminho interno nasce traduzido
        "audience": "everyone",
        "new_tab": False,
    }
    assert saida["default_version"] == ""
    assert saida["pages"] == []


def test_endereco_de_fora_nunca_e_traduzido():
    """Nem que alguém peça: `/es/https://…` não existe, e guardar a combinação
    impossível é guardar um bug esperando a hora."""
    saida = normalizar_menu(
        {
            "versions": [
                {
                    "slug": "v",
                    "name": "V",
                    "items": [
                        {
                            "url": "https://roblox.com",
                            "labels": {"pt-br": "Roblox"},
                            "localized": True,
                        }
                    ],
                }
            ]
        }
    )
    assert saida["versions"][0]["items"][0]["localized"] is False


@pytest.mark.parametrize(
    "endereco",
    [
        "javascript:alert(1)",
        "//golpista.example",
        "data:text/html,<script>alert(1)</script>",
        "roblox.com",
    ],
)
def test_endereco_que_nao_e_pagina_nem_site_de_fora_e_recusado(endereco):
    """Fail-closed na borda: a cerca mora na ESCRITA, não na tela. A tela é uma
    porta; o dado é o que sobrevive a ela."""
    with pytest.raises(ValidationError):
        normalizar_menu(
            {
                "versions": [
                    {
                        "slug": "v",
                        "name": "V",
                        "items": [{"url": endereco, "labels": {"pt-br": "x"}}],
                    }
                ]
            }
        )


def test_pagina_apontando_para_versao_que_nao_existe_e_recusada():
    with pytest.raises(ValidationError) as erro:
        normalizar_menu(
            {
                "versions": [
                    {
                        "slug": "completo",
                        "name": "Completo",
                        "items": [{"url": "/", "labels": {"pt-br": "Início"}}],
                    }
                ],
                "pages": [{"page": "funil/login", "version": "fantasma"}],
            }
        )
    assert "fantasma" in str(erro.value)
    assert "completo" in str(erro.value)


def test_versao_padrao_que_nao_existe_e_recusada():
    with pytest.raises(ValidationError):
        normalizar_menu({"versions": [], "default_version": "fantasma"})


def test_duas_versoes_com_o_mesmo_apelido_sao_recusadas():
    versao = {
        "slug": "igual",
        "name": "Igual",
        "items": [{"url": "/", "labels": {"pt-br": "Início"}}],
    }
    with pytest.raises(ValidationError) as erro:
        normalizar_menu({"versions": [versao, dict(versao, name="Outra")]})
    assert "igual" in str(erro.value)


def test_a_mesma_pagina_duas_vezes_e_recusada():
    """Duas regras para a mesma página podem discordar, e a que vence seria
    decidida por ordem de lista. Ordem de lista não é lei."""
    with pytest.raises(ValidationError):
        normalizar_menu(
            {
                "pages": [
                    {"page": "funil/login", "version": ""},
                    {"page": "funil/login", "version": ""},
                ]
            }
        )


def test_chave_de_pagina_fora_da_forma_celula_barra_rota_e_recusada():
    with pytest.raises(ValidationError) as erro:
        normalizar_menu({"pages": [{"page": "login", "version": ""}]})
    assert "celula/rota" in str(erro.value)


def test_pagina_sem_menu_e_versao_vazia_e_isso_e_legitimo():
    """A metade do pedido que é fácil de perder: 'nenhum menu' precisa ser um
    valor que se GRAVA, não a ausência de regra — senão a página cairia no
    padrão do site e o menu voltaria."""
    saida = normalizar_menu({"pages": [{"page": "funil/login", "version": ""}]})
    assert saida["pages"] == [{"page": "funil/login", "version": ""}]


def test_rotulo_em_idioma_que_nao_e_codigo_de_idioma_e_recusado():
    with pytest.raises(ValidationError):
        normalizar_menu(
            {
                "versions": [
                    {
                        "slug": "v",
                        "name": "V",
                        "items": [{"url": "/", "labels": {"portugues": "Início"}}],
                    }
                ]
            }
        )


def test_plateia_desconhecida_e_recusada():
    with pytest.raises(ValidationError):
        normalizar_menu(
            {
                "versions": [
                    {
                        "slug": "v",
                        "name": "V",
                        "items": [
                            {
                                "url": "/",
                                "labels": {"pt-br": "Início"},
                                "audience": "so_os_bons",
                            }
                        ],
                    }
                ]
            }
        )


# ---------------------------------------------------------------------------
# Os dois caminhos de escrita no banco
# ---------------------------------------------------------------------------


def test_save_normaliza_e_grava(site):
    site.menu = {
        "versions": [
            {
                "slug": "v",
                "name": "V",
                "items": [{"url": "/", "labels": {"PT-BR": "  Início  "}}],
            }
        ]
    }
    site.save()
    site.refresh_from_db()
    item = site.menu["versions"][0]["items"][0]
    assert item["labels"] == {"pt-br": "Início"}


def test_save_recusa_menu_torto(site):
    site.menu = {"versions": [{"slug": "v", "name": "V", "items": "não é lista"}]}
    with pytest.raises(ValidationError):
        site.save()


def test_update_do_queryset_tambem_valida(site):
    """[ARMADILHAS §4.4] `QuerySet.update()` NÃO passa pelo `save()`. Sem o
    guarda no queryset, o banco aceitaria um menu torto pela porta dos fundos."""
    with pytest.raises(ValidationError):
        Site.objects.filter(pk=site.pk).update(menu={"versions": "nada disso"})


def test_update_do_queryset_normaliza_o_que_aceita(site):
    Site.objects.filter(pk=site.pk).update(
        menu={
            "versions": [
                {
                    "slug": "V",
                    "name": "V",
                    "items": [{"url": "/", "labels": {"en": "Home"}}],
                }
            ]
        }
    )
    site.refresh_from_db()
    assert site.menu["versions"][0]["slug"] == "v"


# ---------------------------------------------------------------------------
# As três portas: o site, a leitura e a escrita
# ---------------------------------------------------------------------------


def test_site_sem_menu_nao_carrega_a_chave_menu(client, token_valido, site):
    """A ausência é o sinal de 'este site não tem menu'. Mandar `{}` faria
    quem consome ter de distinguir dois vazios."""
    resp = client.get(
        f"/api/catalogo/sites/by-host/{site.host}",
        HTTP_AUTHORIZATION=f"Bearer {token_valido}",
    )
    assert resp.status_code == 200
    assert "menu" not in resp.json()


def test_site_com_menu_serve_o_menu_junto(client, token_valido, site):
    """O ponto do desenho inteiro: quem desenha a página recebe o menu na MESMA
    resposta que já buscava, sem um salto de rede a mais."""
    site.menu = MENU_DE_EXEMPLO
    site.save()
    resp = client.get(
        f"/api/catalogo/sites/by-host/{site.host}",
        HTTP_AUTHORIZATION=f"Bearer {token_valido}",
    )
    corpo = resp.json()
    assert corpo["menu"]["default_version"] == "completo"
    assert [v["slug"] for v in corpo["menu"]["versions"]] == ["completo", "enxuto"]
    assert {"page": "funil/login", "version": ""} in corpo["menu"]["pages"]


def test_leitura_do_menu_de_site_sem_menu_e_200_com_vazio(client, token_valido, site):
    """Para quem vai CONFIGURAR, 'ainda não tem menu' é estado normal, não erro:
    404 aqui mandaria a tela do Admin desenhar um erro onde há um formulário
    em branco."""
    resp = client.get(
        f"/api/catalogo/sites/{site.id}/menu",
        HTTP_AUTHORIZATION=f"Bearer {token_valido}",
    )
    assert resp.status_code == 200
    assert resp.json() == {"menu": {}}


def test_escrita_grava_o_documento_inteiro_e_devolve_o_canonico(
    client, token_valido, site
):
    resp = client.put(
        f"/api/catalogo/sites/{site.id}/menu",
        data={"menu": MENU_DE_EXEMPLO},
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token_valido}",
    )
    assert resp.status_code == 200
    site.refresh_from_db()
    assert site.menu["versions"][0]["slug"] == "completo"
    # o canônico volta na resposta: a tela não precisa adivinhar o que gravou
    assert resp.json()["menu"] == site.menu


def test_escrita_incoerente_e_422_e_nada_e_gravado(client, token_valido, site):
    site.menu = MENU_DE_EXEMPLO
    site.save()
    antes = site.menu

    resp = client.put(
        f"/api/catalogo/sites/{site.id}/menu",
        data={"menu": {"pages": [{"page": "funil/", "version": "fantasma"}]}},
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token_valido}",
    )
    assert resp.status_code == 422
    # a mensagem atravessa a fronteira: é ela que a tela do Admin mostra
    assert "fantasma" in resp.json()["detail"]

    site.refresh_from_db()
    assert site.menu == antes


def test_escrita_esvazia_quando_o_documento_vem_vazio(client, token_valido, site):
    """Tirar o menu do site inteiro é uma escrita legítima, não um caso de erro."""
    site.menu = MENU_DE_EXEMPLO
    site.save()
    resp = client.put(
        f"/api/catalogo/sites/{site.id}/menu",
        data={"menu": {}},
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token_valido}",
    )
    assert resp.status_code == 200
    site.refresh_from_db()
    assert site.menu == {}


def test_site_inexistente_e_404_nas_duas_portas(client, token_valido):
    """Id sem forma de UUID também: sem o tratamento, ele viraria 500."""
    for caminho in ("/api/catalogo/sites/nao-e-uuid/menu",):
        assert (
            client.get(caminho, HTTP_AUTHORIZATION=f"Bearer {token_valido}").status_code
            == 404
        )
        assert (
            client.put(
                caminho,
                data={"menu": {}},
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {token_valido}",
            ).status_code
            == 404
        )


def test_as_duas_portas_novas_exigem_cracha(client, site):
    """API interna: sem Bearer, 401 — inclusive na de escrita, que é a que
    muda o site."""
    assert client.get(f"/api/catalogo/sites/{site.id}/menu").status_code == 401
    assert (
        client.put(
            f"/api/catalogo/sites/{site.id}/menu",
            data={"menu": {}},
            content_type="application/json",
        ).status_code
        == 401
    )


def test_o_menu_padrao_da_migracao_e_coerente():
    """O que a migração 0004 escreve em PRODUÇÃO passa pelo mesmo validador
    que a tela do Admin enfrenta — e sai dele sem mudar nada.

    Sem este teste, um erro de digitação no menu padrão só apareceria depois do
    deploy, gravado no banco de verdade, onde a migração já não roda de novo.
    """
    import importlib

    # O nome do módulo começa com dígito, então ele não se escreve num import
    # normal; `import_module` aceita a string e é o caminho honesto.
    modulo = importlib.import_module("apps.sites.migrations.0004_menu_padrao")
    padrao = modulo.MENU_PADRAO
    assert normalizar_menu(padrao) == padrao
    # a página de entrar nasce sem menu: é o pedido do mantenedor, escrito no dado
    assert {"page": "funil/login", "version": ""} in padrao["pages"]
