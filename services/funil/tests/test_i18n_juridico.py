"""D8.3 do PLANO-I18N: a guarda de razão de comprimento é RELATÓRIO
(avisos), e o marcador jurídico sem aspas cai no loader estrito (D2.7).

Os helpers vêm de `test_i18n_catalogo` — a mesma célula de mentira, o mesmo
template.
"""

import pytest
from test_i18n_catalogo import TEMPLATE_OK, _celula, _doc_ok

from apps.i18n import catalogo as cat
from apps.i18n import validador as val


def test_marcador_booleano_nu_cai_no_loader_estrito():
    # `_juridico: true` SEM aspas vira bool e morre na regra "toda folha é str"
    # (D2.7) — a mensagem já manda escrever entre aspas.
    with pytest.raises(cat.ErroDeCatalogo, match="não é string"):
        cat.carregar_yaml_estrito("termos:\n  _juridico: true\n")


# ---------------------------------------------------------------------------
# D8.3 — razão de comprimento AVISA, nunca reprova.
# ---------------------------------------------------------------------------
def test_comprimento_desproporcional_avisa_sem_reprovar(tmp_path):
    doc = _doc_ok()
    doc["titulo"]["pt-br"] = (
        "Aprenda Meshcraft agora mesmo com aulas ao vivo, projetos guiados, "
        "certificado e uma comunidade inteira de criadores para te ajudar"
    )
    resultado = val.validar_celula(_celula(tmp_path, doc))
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
    resultado = val.validar_celula(_celula(tmp_path, doc))
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
    )
    assert resultado.estado == "PASS", resultado.problemas
    assert not any("cadastro.curto" in a for a in resultado.avisos)
