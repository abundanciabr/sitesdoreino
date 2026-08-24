# tests/test_idioma_do_site.py
# Idioma é DADO do site (PLANO-I18N D3, fase 4): o catálogo guarda e serve.
# Dois eixos aqui: a coerência fail-closed do modelo e a FORMA da resposta —
# incluindo a regressão que prova que o site monolíngue não mudou nada.
import pytest
from django.core.exceptions import ValidationError

from apps.sites.models import Site, normalizar_idiomas

pytestmark = pytest.mark.django_db

TRES_IDIOMAS = [
    {"code": "en"},
    {"code": "pt-br"},
    {"code": "es", "indexable": False},
]


@pytest.fixture
def token_valido(settings):
    settings.TOKENS_ACEITOS = {"token-de-teste"}
    return "token-de-teste"


def _get_site(client, token, host):
    return client.get(
        f"/api/catalogo/sites/by-host/{host}",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )


# --------------------------------------------------------------------------
# Coerência no modelo — o que PODE ser salvo
# --------------------------------------------------------------------------


def test_site_multilingue_valido_salva_e_normaliza():
    site = Site.objects.create(
        host="meshcraft.top",
        name="Meshcraft",
        default_language="EN",  # caixa alta na declaração...
        languages=[
            {"code": "EN"},
            {"code": "PT-BR"},
            {"code": "es", "indexable": False},
        ],
    )
    site.refresh_from_db()

    # ...sai canônica do banco: minúscula e com `indexable` sempre explícito,
    # para o consumidor nunca depender de lembrar o default do contrato.
    assert site.default_language == "en"
    assert site.languages == [
        {"code": "en", "indexable": True},
        {"code": "pt-br", "indexable": True},
        {"code": "es", "indexable": False},
    ]


def test_site_sem_idioma_e_monolingue_por_ausencia():
    site = Site.objects.create(host="monolingue.com.br", name="Monolíngue")
    site.refresh_from_db()

    assert site.default_language == ""
    assert site.languages == []


def test_variante_regional_e_aceita():
    # pt-pt existe como forma válida (D4) — o modelo não pode barrar o formato.
    padrao, idiomas = normalizar_idiomas(
        "pt-br", [{"code": "pt-br"}, {"code": "pt-pt"}]
    )

    assert padrao == "pt-br"
    assert {i["code"] for i in idiomas} == {"pt-br", "pt-pt"}


# --------------------------------------------------------------------------
# Coerência no modelo — o que NUNCA pode ser salvo (fail-closed)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "padrao,idiomas,pedaco_da_mensagem",
    [
        # default fora da lista declarada
        ("de", [{"code": "en"}, {"code": "pt-br"}], "não está entre os idiomas"),
        # languages sem default
        ("", [{"code": "en"}], "precisa de default_language"),
        # default sem languages — o mesmo torto, ao contrário
        ("en", [], "sem 'languages'"),
        # code duplicado
        ("en", [{"code": "en"}, {"code": "EN"}], "duplicado"),
        # formato errado: underscore no lugar do hífen
        ("pt_br", [{"code": "pt_br"}], "inválido"),
        # formato errado: nome do idioma por extenso
        ("english", [{"code": "english"}], "inválido"),
        # formato errado: três níveis
        ("pt-br-x", [{"code": "pt-br-x"}], "inválido"),
        # indexable não é booleano
        ("en", [{"code": "en", "indexable": "sim"}], "true/false"),
        # item sem code
        ("en", [{"indexable": True}], "sem 'code'"),
        # languages não é lista
        ("en", {"code": "en"}, "precisa ser uma lista"),
        # item que não é objeto
        ("en", ["en"], "precisa ser um objeto"),
    ],
)
def test_declaracao_incoerente_nunca_e_salva(padrao, idiomas, pedaco_da_mensagem):
    with pytest.raises(ValidationError) as erro:
        Site.objects.create(
            host="torto.com.br",
            name="Torto",
            default_language=padrao,
            languages=idiomas,
        )

    assert pedaco_da_mensagem in " ".join(erro.value.messages)
    assert not Site.objects.filter(host="torto.com.br").exists()


def test_queryset_update_nao_fura_o_guarda_do_save():
    # [ARMADILHAS §4.4] update() não passa por save(): sem guarda próprio, este
    # seria o caminho de escrita que aceita um site torto pela porta dos fundos.
    site = Site.objects.create(
        host="meshcraft.top",
        name="Meshcraft",
        default_language="en",
        languages=[{"code": "en"}],
    )

    with pytest.raises(ValidationError):
        Site.objects.filter(pk=site.pk).update(
            default_language="de", languages=[{"code": "en"}]
        )

    site.refresh_from_db()
    assert site.default_language == "en"


def test_update_de_um_campo_de_idioma_so_e_recusado():
    # A coerência é do PAR: com um campo só, o guarda não teria o outro para
    # conferir linha a linha — então recusa em vez de adivinhar.
    site = Site.objects.create(
        host="meshcraft.top",
        name="Meshcraft",
        default_language="en",
        languages=[{"code": "en"}],
    )

    with pytest.raises(ValidationError) as erro:
        Site.objects.filter(pk=site.pk).update(languages=[])

    assert "juntos" in " ".join(erro.value.messages)


def test_update_coerente_passa_e_normaliza():
    site = Site.objects.create(host="meshcraft.top", name="Meshcraft")

    Site.objects.filter(pk=site.pk).update(
        default_language="EN", languages=[{"code": "EN"}, {"code": "es"}]
    )

    site.refresh_from_db()
    assert site.default_language == "en"
    assert site.languages == [
        {"code": "en", "indexable": True},
        {"code": "es", "indexable": True},
    ]


# --------------------------------------------------------------------------
# API — a FORMA do contrato
# --------------------------------------------------------------------------


def test_api_serve_idiomas_na_forma_do_contrato(client, token_valido):
    Site.objects.create(
        host="meshcraft.top",
        name="Meshcraft",
        active=True,
        default_offer_slug="curso-teste",
        default_language="en",
        languages=TRES_IDIOMAS,
    )

    corpo = _get_site(client, token_valido, "meshcraft.top").json()

    assert corpo["default_language"] == "en"
    assert corpo["languages"] == [
        {"code": "en", "indexable": True},
        {"code": "pt-br", "indexable": True},
        {"code": "es", "indexable": False},  # D5: o es NASCE noindex
    ]


def test_regressao_site_monolingue_responde_identico_ao_de_hoje(client, token_valido):
    # A prova de que a fase 4 não tocou em ninguém: o site que não declara
    # idioma responde com EXATAMENTE as mesmas chaves de antes — os campos
    # novos ficam AUSENTES, não vazios. Consumidor atual não vê diferença.
    Site.objects.create(
        host="monolingue.com.br",
        name="Monolíngue",
        active=True,
        default_offer_slug="curso-x",
    )

    corpo = _get_site(client, token_valido, "monolingue.com.br").json()

    assert set(corpo) == {
        "id",
        "host",
        "name",
        "active",
        "theme",
        "default_offer_slug",
    }
    assert "default_language" not in corpo
    assert "languages" not in corpo
