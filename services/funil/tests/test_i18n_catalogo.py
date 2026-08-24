"""Validador fail-closed nos TRÊS estados (PASS, FAIL, ERROR — semântica
INV-CI01), loader YAML estrito (D2.7), runtime t()/plural/escape (D2), overlay
de variante (D4), glossário e anti-burla do _fonte (D8) — e, desde a FASE 4,
os idiomas do SITE lidos do catálogo (`apps.i18n.idiomas`, contrato `Site`).

O teste `test_validador_da_celula_real_passa` É a entrada (a) do portão: roda
o validador contra a célula de verdade dentro do `make ci`."""

import subprocess
from pathlib import Path
from types import MappingProxyType

import pytest
import yaml
from django.core.exceptions import ImproperlyConfigured
from django.template import engines
from django.test import RequestFactory

from apps.i18n import catalogo as cat
from apps.i18n import idiomas as idi
from apps.i18n import validador as val

RAIZ_REAL = Path(__file__).resolve().parent.parent

# Variante de mentira para os testes de overlay (D4). A célula real tem
# `cat.VARIANTES` vazio; o validador aceita a tabela por parâmetro justamente
# para o teste não precisar mexer no estado global do módulo.
VARIANTES_TESTE = {"pt-pt": "pt-br"}


def _plural(texto_um: str, texto_outros: str, idioma: str) -> dict:
    # As categorias vêm do babel PINADO (nunca lista hardcoded) — o teste
    # constrói o plural exatamente como o validador vai exigir.
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
    do módulo (`cat.IDIOMAS_BASE`/`VARIANTES`/`GLOSSARIO`)."""
    (tmp_path / "traducoes").mkdir(exist_ok=True)
    (tmp_path / "templates").mkdir(exist_ok=True)
    if doc is not None:
        texto = doc if isinstance(doc, str) else yaml.safe_dump(doc, allow_unicode=True)
        (tmp_path / "traducoes" / "cadastro.yaml").write_text(texto, encoding="utf-8")
    if template is not None:
        (tmp_path / "templates" / "pagina.html").write_text(template, encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# A entrada (a) do portão: a célula REAL passa.
# ---------------------------------------------------------------------------
def test_validador_da_celula_real_passa():
    resultado = val.validar_celula(RAIZ_REAL)
    assert resultado.estado == "PASS", resultado.problemas


def test_nenhum_registro_local_de_idioma_sobrou_na_celula():
    # Fase 4: o interim `sites_i18n.yaml` morreu — quem declara idioma é o
    # catálogo. Se alguém recriar o arquivo, este teste conta a história.
    assert not (RAIZ_REAL / "sites_i18n.yaml").exists()
    assert not list(RAIZ_REAL.glob("*i18n*.yaml"))


# ---------------------------------------------------------------------------
# PASS / FAIL do validador — formato, paridade, _fonte, plural, placeholders.
# ---------------------------------------------------------------------------
def test_catalogo_completo_passa(tmp_path):
    resultado = val.validar_celula(_celula(tmp_path, _doc_ok()), com_diff=False)
    assert resultado.estado == "PASS", resultado.problemas
    assert "cadastro.titulo" in resultado.chaves


def test_falta_de_idioma_base_reprova_nas_duas_direcoes(tmp_path):
    doc = _doc_ok()
    del doc["titulo"]["es"]  # falta
    resultado = val.validar_celula(_celula(tmp_path, doc), com_diff=False)
    assert resultado.estado == "FAIL"
    assert any("falta o idioma-base `es`" in p for p in resultado.problemas)

    doc = _doc_ok()
    doc["titulo"]["fr"] = "Apprendre"  # sobra: idioma não declarado
    resultado = val.validar_celula(_celula(tmp_path, doc), com_diff=False)
    assert resultado.estado == "FAIL"
    assert any("não é idioma declarado" in p for p in resultado.problemas)


def test_fonte_desatualizado_reprova_e_pendente_declara(tmp_path):
    doc = _doc_ok()
    doc["titulo"]["en"] = "Learn Meshcraft today"  # en mudou, hash não
    resultado = val.validar_celula(_celula(tmp_path, doc), com_diff=False)
    assert resultado.estado == "FAIL"
    assert any("obsoleta" in p for p in resultado.problemas)

    doc = _doc_ok()
    doc["titulo"] = {"_fonte": "pendente", "en": "Learn Meshcraft today"}
    resultado = val.validar_celula(_celula(tmp_path, doc), com_diff=False)
    assert resultado.estado == "PASS", resultado.problemas  # degradação declarada


def test_plural_incompleto_para_o_idioma_reprova(tmp_path):
    doc = _doc_ok()
    categoria = sorted(set(doc["itens"]["pt-br"]) - {"other", "one"})[0]
    del doc["itens"]["pt-br"][categoria]
    resultado = val.validar_celula(_celula(tmp_path, doc), com_diff=False)
    assert resultado.estado == "FAIL"
    assert any("categorias CLDR" in p for p in resultado.problemas)


def test_placeholder_divergente_reprova(tmp_path):
    doc = _doc_ok()
    doc["saudacao"]["pt-br"] = "Olá {name}"
    resultado = val.validar_celula(_celula(tmp_path, doc), com_diff=False)
    assert resultado.estado == "FAIL"
    assert any("placeholders" in p for p in resultado.problemas)


def test_placeholder_com_atributo_ou_indice_reprova(tmp_path):
    doc = _doc_ok()
    doc["saudacao"]["en"] = "Hi {user.senha}"
    resultado = val.validar_celula(_celula(tmp_path, doc), com_diff=False)
    assert resultado.estado == "FAIL"
    assert any("placeholder proibido" in p for p in resultado.problemas)


def test_html_fora_da_whitelist_reprova(tmp_path):
    doc = _doc_ok()
    doc["aviso"] = {"html": _spec("<script>x()</script>", "a", "b")}
    doc["aviso"]["html"]["_fonte"] = cat.hash_da_fonte("<script>x()</script>")
    resultado = val.validar_celula(
        _celula(
            tmp_path,
            doc,
            template=TEMPLATE_OK + ' {% t "cadastro.aviso.html" %}',
        ),
        com_diff=False,
    )
    assert resultado.estado == "FAIL"
    assert any("whitelist" in p for p in resultado.problemas)


def test_overlay_de_variante_igual_a_base_reprova(tmp_path):
    doc = _doc_ok()
    doc["titulo"]["pt-pt"] = doc["titulo"]["pt-br"]  # idêntico ⇒ remova
    resultado = val.validar_celula(
        _celula(tmp_path, doc), com_diff=False, variantes=VARIANTES_TESTE
    )
    assert resultado.estado == "FAIL"
    assert any("idêntico à base" in p for p in resultado.problemas)

    doc = _doc_ok()
    doc["so_variante"] = {
        "_fonte": "pendente",
        "en": "Only variant",
        "pt-pt": "Só variante",
    }
    resultado = val.validar_celula(
        _celula(
            tmp_path, doc, template=TEMPLATE_OK + ' {% t "cadastro.so_variante" %}'
        ),
        com_diff=False,
        variantes=VARIANTES_TESTE,
    )
    assert resultado.estado == "FAIL"
    assert any("sem a base" in p for p in resultado.problemas)


def test_variante_com_base_que_nao_e_idioma_base_reprova(tmp_path):
    # D4, fallback de fallback: a base de uma variante tem de ser idioma-BASE
    # da célula. Com a tabela em código (fase 4), é aqui que a regra vive.
    resultado = val.validar_celula(
        _celula(tmp_path, _doc_ok()),
        com_diff=False,
        variantes={"pt-pt": "pt-br", "pt-ao": "pt-pt"},
    )
    assert resultado.estado == "FAIL"
    assert any("fallback de fallback" in p for p in resultado.problemas)


def test_glossario_termo_traduzido_reprova(tmp_path):
    # O glossário vem da CÉLULA (cat.GLOSSARIO) desde a fase 4 — antes vinha
    # do registro por site, que morreu com o interim.
    assert "Meshcraft" in cat.GLOSSARIO
    doc = _doc_ok()
    doc["titulo"]["pt-br"] = "Aprenda MalhaCraft agora"  # traduziu a marca
    resultado = val.validar_celula(_celula(tmp_path, doc), com_diff=False)
    assert resultado.estado == "FAIL"
    assert any("glossário" in p and "Meshcraft" in p for p in resultado.problemas)


def test_template_e_catalogo_nas_duas_direcoes(tmp_path):
    resultado = val.validar_celula(
        _celula(tmp_path, _doc_ok(), template=TEMPLATE_OK + ' {% t "cadastro.nada" %}'),
        com_diff=False,
    )
    assert resultado.estado == "FAIL"
    assert any("usada e não definida" in p for p in resultado.problemas)

    doc = _doc_ok()
    doc["orfa"] = _spec("Unused", "Sem uso", "Sin uso")
    resultado = val.validar_celula(_celula(tmp_path, doc), com_diff=False)
    assert resultado.estado == "FAIL"
    assert any("definida e não usada" in p for p in resultado.problemas)


def test_chave_dinamica_no_template_reprova_o_lint(tmp_path):
    resultado = val.validar_celula(
        _celula(tmp_path, _doc_ok(), template=TEMPLATE_OK + " {% t variavel %}"),
        com_diff=False,
    )
    assert resultado.estado == "FAIL"
    assert any("LITERAL" in p for p in resultado.problemas)


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
# Anti-burla do _fonte (D8/D4) — PASS, FAIL e ERROR, num repositório git
# hermético (nunca o repo real; nunca `git stash` — ARMADILHAS §6.1.1).
# ---------------------------------------------------------------------------
def _git(cwd, *args):
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(cwd),
        check=True,
        capture_output=True,
    )


@pytest.fixture
def repo_burla(tmp_path):
    _celula(tmp_path, _doc_ok())
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "v1")
    return tmp_path


def _regravar(repo, doc):
    (repo / "traducoes" / "cadastro.yaml").write_text(
        yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8"
    )


def test_anti_burla_reprova_rehash_sem_traduzir(repo_burla):
    doc = _doc_ok()
    doc["titulo"]["en"] = "Learn Meshcraft today"
    doc["titulo"]["_fonte"] = cat.hash_da_fonte(doc["titulo"]["en"])  # a burla
    _regravar(repo_burla, doc)
    resultado = val.validar_celula(repo_burla, base_ref="HEAD")
    assert resultado.estado == "FAIL"
    assert any("anti-burla" in p for p in resultado.problemas)


def test_anti_burla_aceita_traducao_junto(repo_burla):
    doc = _doc_ok()
    doc["titulo"] = _spec(
        "Learn Meshcraft today",
        "Aprenda Meshcraft hoje",
        "Aprende Meshcraft hoy",
    )
    _regravar(repo_burla, doc)
    resultado = val.validar_celula(repo_burla, base_ref="HEAD")
    assert resultado.estado == "PASS", resultado.problemas


def test_anti_burla_aceita_pendente_declarado(repo_burla):
    doc = _doc_ok()
    doc["titulo"]["en"] = "Learn Meshcraft today"
    doc["titulo"]["_fonte"] = "pendente"
    _regravar(repo_burla, doc)
    resultado = val.validar_celula(repo_burla, base_ref="HEAD")
    assert resultado.estado == "PASS", resultado.problemas


def test_anti_burla_aceita_marcador_de_revisao(repo_burla):
    doc = _doc_ok()
    doc["titulo"]["en"] = "Learn Meshcraft today"
    novo_hash = cat.hash_da_fonte(doc["titulo"]["en"])
    doc["titulo"]["_fonte"] = novo_hash
    texto = yaml.safe_dump(doc, allow_unicode=True).replace(
        f"_fonte: {novo_hash}",
        f"_fonte: {novo_hash}  {val.MARCADOR_REVISAO}",
    )
    (repo_burla / "traducoes" / "cadastro.yaml").write_text(texto, encoding="utf-8")
    resultado = val.validar_celula(repo_burla, base_ref="HEAD")
    assert resultado.estado == "PASS", resultado.problemas


def test_anti_burla_ref_incalculavel_e_error_nunca_skip(repo_burla):
    resultado = val.validar_celula(repo_burla, base_ref="refs/nao-existe")
    assert resultado.estado == "ERROR"
    assert any("diff incalculável" in p for p in resultado.problemas)


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
# BOOT (entrada b): inválido não sobe; válido congela imutável em memória.
# ---------------------------------------------------------------------------
@pytest.fixture
def estado_protegido(monkeypatch):
    monkeypatch.setattr(cat, "_CATALOGO", cat._CATALOGO)
    monkeypatch.setattr(cat, "_BASES", cat._BASES)
    monkeypatch.setattr(cat, "CONTADOR_DE_FALTAS", {})


def test_boot_recusa_catalogo_invalido(tmp_path, estado_protegido):
    doc = _doc_ok()
    del doc["titulo"]["es"]
    with pytest.raises(ImproperlyConfigured, match="não sobe"):
        val.validar_e_instalar(_celula(tmp_path, doc))


def test_boot_recusa_variantes_incoerentes(tmp_path, estado_protegido, monkeypatch):
    # A tabela de variantes virou código (fase 4) — e o boot continua
    # fail-closed sobre ela, como era sobre o registro em arquivo.
    monkeypatch.setattr(cat, "VARIANTES", {"pt-pt": "pt-ao"})
    with pytest.raises(ImproperlyConfigured, match="não sobe"):
        val.validar_e_instalar(_celula(tmp_path, _doc_ok()))


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
