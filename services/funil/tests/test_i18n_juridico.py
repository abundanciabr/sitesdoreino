"""D8.2 (namespace jurídico com revisão humana declarada) e D8.3 (guarda de
razão de comprimento como RELATÓRIO) do PLANO-I18N.

A decisão de desenho central, provada nos dois lados aqui: a declaração de
revisão é **por idioma**, nunca por chave — revisar o inglês não valida o
espanhol. E ela **expira no diff**: texto jurídico que muda num idioma exige
declaração nova daquele idioma.

Os helpers vêm de `test_i18n_catalogo` de propósito — a mesma célula de
mentira, o mesmo registro, o mesmo template: regra nova não pode precisar de
um mundo próprio para passar.
"""

import warnings

import pytest
import yaml
from django.core.exceptions import ImproperlyConfigured
from test_i18n_catalogo import RAIZ_REAL, TEMPLATE_OK, _celula, _doc_ok, _git

from apps.i18n import catalogo as cat
from apps.i18n import validador as val

EN_TERMOS = "You agree to the Meshcraft terms of use."
PTBR_TERMOS = "Você concorda com os termos de uso do Meshcraft."
ES_TERMOS = "Aceptas los términos de uso de Meshcraft."

REVISAO_COMPLETA = {
    "en": "Davi Xavier 2026-08-23",
    "pt-br": "Davi Xavier 2026-08-23",
    "es": "Davi Xavier 2026-08-23",
}

TEMPLATE_COM_TERMOS = TEMPLATE_OK + ' {% t "cadastro.termos" %}'


def _doc_juridico(**trocas) -> dict:
    """`_doc_ok()` + uma chave com efeito legal, do jeito que a R12 mandaria
    escrever (o glossário exige `Meshcraft` literal nas três línguas)."""
    doc = _doc_ok()
    doc["termos"] = {
        "_fonte": cat.hash_da_fonte(EN_TERMOS),
        cat.CHAVE_JURIDICO: cat.VALOR_JURIDICO,
        cat.CHAVE_REVISAO_HUMANA: dict(REVISAO_COMPLETA),
        "en": EN_TERMOS,
        "pt-br": PTBR_TERMOS,
        "es": ES_TERMOS,
    }
    doc["termos"].update(trocas)
    for chave, valor in list(doc["termos"].items()):
        if valor is None:
            del doc["termos"][chave]
    return doc


def _celula_juridica(tmp_path, doc):
    return _celula(tmp_path, doc, template=TEMPLATE_COM_TERMOS)


def _validar(tmp_path, doc):
    return val.validar_celula(_celula_juridica(tmp_path, doc), com_diff=False)


# ---------------------------------------------------------------------------
# O portão: sem revisão humana declarada, texto jurídico não passa — e a
# célula NÃO SOBE (D4 fail-closed + D8.2 na mesma implementação).
# ---------------------------------------------------------------------------
def test_juridico_sem_revisao_reprova(tmp_path):
    resultado = _validar(tmp_path, _doc_juridico(**{cat.CHAVE_REVISAO_HUMANA: None}))
    assert resultado.estado == "FAIL"
    assert any(
        "exige revisão humana declarada" in p and "peça ao mantenedor" in p
        for p in resultado.problemas
    )


def test_boot_recusa_texto_juridico_sem_revisao(tmp_path):
    # A prova de que a lei tem dente: com texto legal sem revisão, o
    # AppConfig.ready() estoura e o processo não sobe.
    doc = _doc_juridico(**{cat.CHAVE_REVISAO_HUMANA: None})
    with pytest.raises(ImproperlyConfigured, match="não sobe"):
        val.validar_e_instalar(_celula_juridica(tmp_path, doc))


def test_juridico_com_revisao_declarada_passa(tmp_path):
    resultado = _validar(tmp_path, _doc_juridico())
    assert resultado.estado == "PASS", resultado.problemas
    assert "cadastro.termos" in resultado.chaves


# ---------------------------------------------------------------------------
# A decisão do desenho, nos DOIS lados: revisão é POR IDIOMA.
# ---------------------------------------------------------------------------
def test_revisao_de_um_idioma_nao_vale_pelos_outros(tmp_path):
    so_ingles = {"en": REVISAO_COMPLETA["en"]}
    resultado = _validar(
        tmp_path, _doc_juridico(**{cat.CHAVE_REVISAO_HUMANA: so_ingles})
    )
    assert resultado.estado == "FAIL"
    faltantes = {
        idioma
        for idioma in ("pt-br", "es")
        if any(
            f"`{idioma}`" in p and "NÃO vale pelos outros" in p
            for p in resultado.problemas
        )
    }
    assert faltantes == {"pt-br", "es"}

    completo = dict(so_ingles, **{"pt-br": "Davi Xavier 2026-08-23"})
    completo["es"] = "Davi Xavier 2026-08-23"
    resultado = _validar(
        tmp_path, _doc_juridico(**{cat.CHAVE_REVISAO_HUMANA: completo})
    )
    assert resultado.estado == "PASS", resultado.problemas


def test_revisao_em_string_unica_reprova(tmp_path):
    # Uma declaração só para a chave inteira é exatamente o que NÃO queremos.
    resultado = _validar(
        tmp_path, _doc_juridico(**{cat.CHAVE_REVISAO_HUMANA: "Davi Xavier 2026-08-23"})
    )
    assert resultado.estado == "FAIL"
    assert any("um por idioma" in p for p in resultado.problemas)


def test_revisao_orfa_reprova(tmp_path):
    revisao = dict(REVISAO_COMPLETA, fr="Alguém 2026-08-23")
    resultado = _validar(tmp_path, _doc_juridico(**{cat.CHAVE_REVISAO_HUMANA: revisao}))
    assert resultado.estado == "FAIL"
    assert any("declaração órfã" in p for p in resultado.problemas)


def test_revisao_sem_juridico_reprova(tmp_path):
    doc = _doc_ok()
    doc["titulo"][cat.CHAVE_REVISAO_HUMANA] = {"en": "Davi Xavier 2026-08-23"}
    resultado = val.validar_celula(_celula(tmp_path, doc), com_diff=False)
    assert resultado.estado == "FAIL"
    assert any("só existe para texto jurídico" in p for p in resultado.problemas)


# ---------------------------------------------------------------------------
# Valor do marcador e estado degradado.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("valor", ["false", "", "sim", "True"])
def test_valor_invalido_do_marcador_reprova(tmp_path, valor):
    resultado = _validar(tmp_path, _doc_juridico(**{cat.CHAVE_JURIDICO: valor}))
    assert resultado.estado == "FAIL"
    assert any(
        "só aceita a string" in p and "REMOVA a chave" in p for p in resultado.problemas
    )


def test_marcador_booleano_nu_cai_no_loader_estrito():
    # `_juridico: true` SEM aspas vira bool e morre na regra "toda folha é str"
    # (D2.7) — a mensagem já manda escrever entre aspas.
    with pytest.raises(cat.ErroDeCatalogo, match="não é string"):
        cat.carregar_yaml_estrito("termos:\n  _juridico: true\n")


def test_juridico_com_fonte_pendente_reprova(tmp_path):
    resultado = _validar(tmp_path, _doc_juridico(_fonte=cat.FONTE_PENDENTE))
    assert resultado.estado == "FAIL"
    assert any("estado degradado" in p for p in resultado.problemas)


def test_declaracao_sem_data_ou_vazia_reprova(tmp_path):
    for ruim in ("", "revisado", "2026-08-23", "   "):
        revisao = dict(REVISAO_COMPLETA, **{"pt-br": ruim})
        resultado = _validar(
            tmp_path, _doc_juridico(**{cat.CHAVE_REVISAO_HUMANA: revisao})
        )
        assert resultado.estado == "FAIL", ruim
        assert any("não é revisão auditável" in p for p in resultado.problemas), ruim


# ---------------------------------------------------------------------------
# A revisão EXPIRA no diff: texto jurídico que muda num idioma exige
# declaração nova daquele idioma (repositório git hermético; nunca stash —
# ARMADILHAS §6.1.1).
# ---------------------------------------------------------------------------
@pytest.fixture
def repo_juridico(tmp_path):
    _celula_juridica(tmp_path, _doc_juridico())
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "v1")
    return tmp_path


def _regravar(repo, doc):
    (repo / "traducoes" / "cadastro.yaml").write_text(
        yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8"
    )


def test_texto_juridico_alterado_sem_nova_revisao_reprova(repo_juridico):
    doc = _doc_juridico(**{"pt-br": "Você aceita os termos de uso do Meshcraft."})
    _regravar(repo_juridico, doc)
    resultado = val.validar_celula(repo_juridico, base_ref="HEAD")
    assert resultado.estado == "FAIL"
    assert any("`pt-br` mudou e a revisão humana não" in p for p in resultado.problemas)


def test_texto_juridico_alterado_com_nova_revisao_passa(repo_juridico):
    doc = _doc_juridico(
        **{
            "pt-br": "Você aceita os termos de uso do Meshcraft.",
            cat.CHAVE_REVISAO_HUMANA: dict(
                REVISAO_COMPLETA, **{"pt-br": "Davi Xavier 2026-09-01"}
            ),
        }
    )
    _regravar(repo_juridico, doc)
    resultado = val.validar_celula(repo_juridico, base_ref="HEAD")
    assert resultado.estado == "PASS", resultado.problemas


def test_texto_juridico_intacto_nao_exige_re_revisao(repo_juridico):
    doc = _doc_juridico()
    doc["titulo"]["pt-br"] = "Aprenda Meshcraft já"  # mexe em chave NÃO jurídica
    doc["titulo"]["_fonte"] = cat.hash_da_fonte(doc["titulo"]["en"])
    _regravar(repo_juridico, doc)
    resultado = val.validar_celula(repo_juridico, base_ref="HEAD")
    assert resultado.estado == "PASS", resultado.problemas


# ---------------------------------------------------------------------------
# D8.3 — razão de comprimento AVISA, nunca reprova.
# ---------------------------------------------------------------------------
def test_comprimento_desproporcional_avisa_sem_reprovar(tmp_path):
    doc = _doc_ok()
    doc["titulo"]["pt-br"] = (
        "Aprenda Meshcraft agora mesmo com aulas ao vivo, projetos guiados, "
        "certificado e uma comunidade inteira de criadores para te ajudar"
    )
    resultado = val.validar_celula(_celula(tmp_path, doc), com_diff=False)
    assert resultado.estado == "PASS", resultado.problemas  # relatório, não gate
    assert any(
        "cadastro.titulo" in a and "`pt-br`" in a and "NÃO reprova" in a
        for a in resultado.avisos
    )


def test_comprimento_truncado_avisa(tmp_path):
    doc = _doc_ok()
    doc["saudacao"]["en"] = "Hello {nome}, welcome to the online academy"
    doc["saudacao"]["_fonte"] = cat.hash_da_fonte(doc["saudacao"]["en"])
    doc["saudacao"]["pt-br"] = "{nome}"  # truncamento
    doc["saudacao"]["es"] = "Hola {nome}, bienvenido a la academia online"
    resultado = val.validar_celula(_celula(tmp_path, doc), com_diff=False)
    assert resultado.estado == "PASS", resultado.problemas
    assert any("cadastro.saudacao" in a and "`pt-br`" in a for a in resultado.avisos)


def test_rotulo_curto_nao_gera_aviso_falso(tmp_path):
    # "E-mail" → "Correo electrónico" é 3× e está CERTO: abaixo do piso a
    # variação natural domina, e um relatório barulhento vira relatório ignorado.
    doc = _doc_ok()
    doc["curto"] = {
        "_fonte": cat.hash_da_fonte("E-mail"),
        "en": "E-mail",
        "pt-br": "E-mail",
        "es": "Correo electrónico",
    }
    resultado = val.validar_celula(
        _celula(tmp_path, doc, template=TEMPLATE_OK + ' {% t "cadastro.curto" %}'),
        com_diff=False,
    )
    assert resultado.estado == "PASS", resultado.problemas
    assert not any("cadastro.curto" in a for a in resultado.avisos)


def test_relatorio_de_comprimento_da_celula_real(recwarn):
    """Entrada (a) do relatório D8.3: os avisos do catálogo REAL sobem no
    `make ci` pelo sumário de warnings do pytest — nenhum hoje, e se um
    aparecer, aparece no PR sem ninguém precisar procurar."""
    resultado = val.validar_celula(RAIZ_REAL, com_diff=False)
    assert resultado.estado == "PASS", resultado.problemas
    for aviso in resultado.avisos:
        warnings.warn(f"[i18n D8.3] {aviso}", stacklevel=1)
