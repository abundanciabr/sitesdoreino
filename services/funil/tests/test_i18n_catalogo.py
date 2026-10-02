"""Loader YAML estrito (D2.7), instalação do catálogo, runtime
t()/plural/escape (D2) e, desde a FASE 4, os idiomas do SITE lidos do
catálogo (`apps.i18n.idiomas`, contrato `Site`)."""

from pathlib import Path
from types import MappingProxyType

import pytest
import yaml
from django.template import engines
from django.test import RequestFactory

from apps.i18n import catalogo as cat
from apps.i18n import idiomas as idi
from apps.i18n import validador as val

RAIZ_REAL = Path(__file__).resolve().parent.parent

# Variante de mentira para o teste de instalação (D4). A célula real tem
# `cat.VARIANTES` vazio.
VARIANTES_TESTE = {"pt-pt": "pt-br"}


def _plural(texto_um: str, texto_outros: str, idioma: str) -> dict:
    # As categorias vêm do babel PINADO (nunca lista hardcoded).
    return {
        categoria: (texto_um if categoria == "one" else texto_outros)
        for categoria in sorted(cat.categorias_plural(idioma))
    }


def _spec(en, ptbr, es, **extras) -> dict:
    base = {"_fonte": cat.hash_da_fonte(en), "en": en, "pt-br": ptbr, "es": es}
    base.update(extras)
    return base


def _doc_ok() -> dict:
    return {
        "titulo": _spec(
            "Learn Meshcraft now",
            "Aprenda Meshcraft agora",
            "Aprende Meshcraft ahora",
        ),
        "saudacao": _spec("Hello {nome}", "Olá {nome}", "Hola {nome}"),
        "itens": _spec(
            _plural("{quantidade} item", "{quantidade} items", "en"),
            _plural("{quantidade} item", "{quantidade} itens", "pt-br"),
            _plural("{quantidade} ítem", "{quantidade} ítems", "es"),
        ),
        "js": {"erro": _spec("Try again", "Tente de novo", "Intenta de nuevo")},
    }


TEMPLATE_OK = (
    '{% t "cadastro.titulo" %} {% t "cadastro.saudacao" nome=n %} '
    '{% t "cadastro.itens" quantidade=q %}'
)


def _celula(tmp_path, doc=None, template=TEMPLATE_OK):
    """Célula de mentira: traduções + templates. Desde a fase 4 não há mais
    arquivo de registro de idiomas para escrever — a política de tradução vem
    do módulo (`cat.IDIOMAS_BASE`/`VARIANTES`)."""
    (tmp_path / "traducoes").mkdir(exist_ok=True)
    (tmp_path / "templates").mkdir(exist_ok=True)
    if doc is not None:
        texto = doc if isinstance(doc, str) else yaml.safe_dump(doc, allow_unicode=True)
        (tmp_path / "traducoes" / "cadastro.yaml").write_text(texto, encoding="utf-8")
    if template is not None:
        (tmp_path / "templates" / "pagina.html").write_text(template, encoding="utf-8")
    return tmp_path


def test_nenhum_registro_local_de_idioma_sobrou_na_celula():
    # Fase 4: o interim `sites_i18n.yaml` morreu — quem declara idioma é o
    # catálogo. Se alguém recriar o arquivo, este teste conta a história.
    assert not (RAIZ_REAL / "sites_i18n.yaml").exists()
    assert not list(RAIZ_REAL.glob("*i18n*.yaml"))


# ---------------------------------------------------------------------------
# Loader estrito (D2.7).
# ---------------------------------------------------------------------------
def test_loader_rejeita_chave_duplicada():
    with pytest.raises(cat.ErroDeCatalogo, match="duplicada"):
        cat.carregar_yaml_estrito("a: 'x'\na: 'y'\n")


def test_loader_rejeita_ancora_e_alias():
    with pytest.raises(cat.ErroDeCatalogo, match="âncora|alias"):
        cat.carregar_yaml_estrito("a: &m 'x'\nb: *m\n")


def test_loader_rejeita_tag_explicita():
    with pytest.raises(cat.ErroDeCatalogo, match="tag explícita"):
        cat.carregar_yaml_estrito("a: !!str x\n")


def test_loader_rejeita_folha_nao_string():
    with pytest.raises(cat.ErroDeCatalogo, match="não é string"):
        cat.carregar_yaml_estrito("a:\n  b: no\n")  # `no` viraria False
    with pytest.raises(cat.ErroDeCatalogo, match="não é string"):
        cat.carregar_yaml_estrito("a: 12:30\n")  # viraria 750 (sexagesimal)


def test_loader_rejeita_chave_nao_string():
    # No dia do norueguês: `no:` viraria a CHAVE False antes de qualquer
    # validação de folha — cai aqui como tipo inválido de chave (D2.7).
    with pytest.raises(cat.ErroDeCatalogo, match="chave não-string"):
        cat.carregar_yaml_estrito("no: 'norsk'\n")


# ---------------------------------------------------------------------------
# Fase 4 — os idiomas do SITE vêm do catálogo (contrato `Site`), e o que o
# contrato NÃO carrega (tag BCP 47, dir) a célula deriva do código.
# ---------------------------------------------------------------------------
TRES_IDIOMAS = [
    {"code": "en", "indexable": True},
    {"code": "pt-br", "indexable": True},
    {"code": "es", "indexable": False},
]


def _site(**extras) -> dict:
    return {"id": "s1", "host": "x.exemplo.com", "name": "X", "active": True, **extras}


def test_idiomas_do_site_saem_do_contrato_com_tag_e_dir_derivados():
    cfg = idi.idiomas_do_site(_site(default_language="en", languages=TRES_IDIOMAS))
    assert cfg["default"] == "en"
    assert list(cfg["idiomas"]) == ["en", "pt-br", "es"]
    # tag e dir NÃO vêm do contrato: derivam do código, aqui na célula.
    assert cfg["idiomas"]["pt-br"] == {"tag": "pt-BR", "dir": "ltr", "indexavel": True}
    assert cfg["idiomas"]["es"]["indexavel"] is False  # D5: es segue noindex


@pytest.mark.parametrize(
    "site",
    [
        {},  # nem default_language nem languages — o caso da degradação
        {"languages": []},
        {"default_language": "en"},  # default sem lista de idiomas
    ],
)
def test_site_sem_languages_e_monolingue(site):
    assert idi.idiomas_do_site(_site(**site)) is None


def test_languages_sem_default_language_nao_elege_um_por_conta(caplog):
    # O contrato manda `languages` conter `default_language`; se vier sem,
    # escolher "o primeiro da lista" seria o site-padrão silencioso que o
    # [INV-P11] proíbe — e mandaria a raiz redirecionar para um idioma que
    # ninguém escolheu. Monolíngue, com ERROR no log.
    assert idi.idiomas_do_site(_site(languages=TRES_IDIOMAS)) is None
    assert "MONOLÍNGUE" in caplog.text


def test_indexable_ausente_e_true_por_contrato():
    cfg = idi.idiomas_do_site(_site(default_language="en", languages=[{"code": "en"}]))
    assert cfg["idiomas"]["en"]["indexavel"] is True


def test_indexable_nao_booleano_vira_noindex_e_alarma(caplog):
    cfg = idi.idiomas_do_site(
        _site(default_language="en", languages=[{"code": "en", "indexable": "false"}])
    )
    # Fail-closed para o lado barato: indexar por engano é o erro caro.
    assert cfg["idiomas"]["en"]["indexavel"] is False
    assert "indexable" in caplog.text


def test_default_language_fora_dos_idiomas_serve_monolingue(caplog):
    assert (
        idi.idiomas_do_site(_site(default_language="fr", languages=TRES_IDIOMAS))
        is None
    )
    assert "MONOLÍNGUE" in caplog.text  # nunca um default silencioso (INV-P11)


def test_idioma_sem_catalogo_na_celula_e_ignorado(caplog):
    cfg = idi.idiomas_do_site(
        _site(default_language="en", languages=TRES_IDIOMAS + [{"code": "fr"}])
    )
    # Servir /fr/ publicaria a página em inglês sob URL francesa (D5).
    assert "fr" not in cfg["idiomas"]
    assert "fr" in caplog.text


def test_codigo_de_idioma_fora_da_forma_e_ignorado(caplog):
    cfg = idi.idiomas_do_site(
        _site(
            default_language="en",
            languages=TRES_IDIOMAS + [{"code": "PT_BR"}, {"codigo": "es"}],
        )
    )
    assert list(cfg["idiomas"]) == ["en", "pt-br", "es"]
    assert caplog.text.count("inválido") == 2


@pytest.mark.parametrize(
    "codigo,tag",
    [("en", "en"), ("pt-br", "pt-BR"), ("es-419", "es-419"), ("zh-hant", "zh-Hant")],
)
def test_tag_bcp47_deriva_do_codigo_da_url(codigo, tag):
    assert idi.tag_bcp47(codigo) == tag


@pytest.mark.parametrize(
    "codigo,dir_", [("en", "ltr"), ("pt-br", "ltr"), ("ar", "rtl"), ("he-il", "rtl")]
)
def test_dir_deriva_do_idioma_nunca_do_site(codigo, dir_):
    assert idi.direcao(codigo) == dir_


# ---------------------------------------------------------------------------
# BOOT: o catálogo é instalado imutável em memória.
# ---------------------------------------------------------------------------
@pytest.fixture
def estado_protegido(monkeypatch):
    monkeypatch.setattr(cat, "_CATALOGO", cat._CATALOGO)
    monkeypatch.setattr(cat, "_BASES", cat._BASES)
    monkeypatch.setattr(cat, "CONTADOR_DE_FALTAS", {})


def test_boot_instala_catalogo_imutavel(tmp_path, estado_protegido, monkeypatch):
    monkeypatch.setattr(cat, "VARIANTES", VARIANTES_TESTE)
    val.validar_e_instalar(_celula(tmp_path, _doc_ok()))
    assert "cadastro.titulo" in cat.catalogo_instalado()
    assert cat.bases_instaladas() == VARIANTES_TESTE  # a cadeia de fallback (D4)
    with pytest.raises(TypeError):
        cat.catalogo_instalado()["cadastro.titulo"] = {}


# ---------------------------------------------------------------------------
# Runtime t()/t_lazy — escape por padrão, .html com whitelist, plural,
# cadeia variante → base → en, contador de falta.
# ---------------------------------------------------------------------------
@pytest.fixture
def catalogo_de_runtime(monkeypatch):
    chaves = {
        "pagina.perigo": {"_fonte": "000000", "en": "<b>bold</b> & Co"},
        "pagina.aviso.html": {
            "_fonte": "000000",
            "en": "See <strong>{nome}</strong>",
            "pt-br": "Veja <strong>{nome}</strong>",
        },
        "pagina.itens": {
            "_fonte": "000000",
            "en": _plural("{quantidade} item", "{quantidade} items", "en"),
            "pt-br": _plural("{quantidade} item", "{quantidade} itens", "pt-br"),
        },
        "pagina.titulo": {
            "_fonte": "000000",
            "en": "Title",
            "pt-br": "Título",
        },
        "pagina.so_en": {"_fonte": "pendente", "en": "Only english"},
        "pagina.js.erro": {"_fonte": "000000", "en": "Oops", "pt-br": "Opa"},
    }
    monkeypatch.setattr(cat, "_CATALOGO", MappingProxyType(chaves))
    monkeypatch.setattr(cat, "_BASES", MappingProxyType({"pt-pt": "pt-br"}))
    monkeypatch.setattr(cat, "CONTADOR_DE_FALTAS", {})


def _render(texto, contexto=None):
    template = engines["django"].from_string("{% load t %}" + texto)
    request = RequestFactory().get("/pt-br/x", HTTP_HOST="qualquer.exemplo.com")
    request.idioma = "pt-br"
    return template.render(contexto or {}, request=request)


def test_tag_t_escapa_por_padrao(catalogo_de_runtime):
    saida = _render('{% t "pagina.perigo" %}')  # idioma pt-br cai no en (pendente-like)
    assert saida == "&lt;b&gt;bold&lt;/b&gt; &amp; Co"


def test_chave_html_passa_whitelist_e_escapa_os_valores(catalogo_de_runtime):
    saida = _render('{% t "pagina.aviso.html" nome=nome %}', {"nome": "<i>x</i>"})
    assert saida == "Veja <strong>&lt;i&gt;x&lt;/i&gt;</strong>"


def test_t_plural_escolhe_a_categoria_do_idioma(catalogo_de_runtime):
    assert cat.t("pagina.itens", "pt-br", quantidade=1) == "1 item"
    assert cat.t("pagina.itens", "pt-br", quantidade=2) == "2 itens"
    assert cat.t("pagina.itens", "en", quantidade=2) == "2 items"


def test_t_variante_herda_da_base_sem_alarme(catalogo_de_runtime):
    assert cat.t("pagina.titulo", "pt-pt") == "Título"
    assert cat.CONTADOR_DE_FALTAS == {}  # herança de overlay não é falta


def test_t_fallback_ate_o_en_conta_e_loga(catalogo_de_runtime):
    assert cat.t("pagina.so_en", "pt-br") == "Only english"
    assert cat.CONTADOR_DE_FALTAS[("pagina.so_en", "pt-br")] == 1


def test_formatador_seguro_bloqueia_atributo_indice_e_spec(catalogo_de_runtime):
    for malicia in ("{a.b}", "{a[0]}", "{a!r}", "{a:>10}"):
        with pytest.raises(cat.ErroDeCatalogo):
            cat._FORMATADOR.vformat(malicia, (), {"a": object()})


def test_t_lazy_resolve_tarde(catalogo_de_runtime):
    preguicosa = cat.t_lazy("pagina.titulo", "pt-br")
    assert str(preguicosa) == "Título"


def test_js_da_pagina_expoe_subarvore(catalogo_de_runtime):
    assert cat.js_da_pagina("pagina", "pt-br") == {"erro": "Opa"}


def test_pseudo_texto_preserva_placeholder_e_marca():
    pseudo = val._pseudo_texto("Hello {nome}, welcome")
    assert pseudo.startswith(val.MARCA_INICIO) and pseudo.endswith(val.MARCA_FIM)
    assert "{nome}" in pseudo  # placeholder intacto para o format
    sem_campo = pseudo.replace("{nome}", "")
    assert not any("a" <= c.lower() <= "z" for c in sem_campo)  # tudo acentuado
    assert len(pseudo) >= len("Hello {nome}, welcome")  # ~40% maior + marcas
