"""A migração 0034 põe a crase no texto já gravado no banco, e só nele.

Como em `test_reembolso_no_banco.py`, o documento é construído à mão: em banco
novo a semente já vem corrigida e a migração não encontraria nada para trocar.
"""

import importlib

import pytest

from apps.core.models import Documento

_migracao = importlib.import_module(
    "apps.core.migrations.0034_a_crase_em_como_funciona_a_entrada"
)


class _AppsFalso:
    @staticmethod
    def get_model(app_label, model_name):
        assert (app_label, model_name) == ("core", "Documento")
        return Documento


CORPO_ANTIGO = (
    "## Depois de ser aluno\n\n"
    "- **Reembolsado**: a plataforma é exclusiva para alunos que estão fazendo algum\n"
    "  curso, e em caso de reembolso o aluno perde o acesso a mesma.\n\n"
    "## O fim\n"
)
CORPO_NOVO = CORPO_ANTIGO.replace("acesso a mesma", "acesso à mesma")


def _criar(corpo):
    Documento.objects.filter(nome="como-funciona-a-entrada").delete()
    return Documento.objects.create(
        nome="como-funciona-a-entrada",
        titulo="Como funciona a entrada",
        publico=True,
        ordem=1,
        corpo=corpo,
    )


def _corpo(documento):
    return Documento.objects.get(pk=documento.pk).corpo


@pytest.mark.django_db
def test_a_crase_entra_onde_o_texto_antigo_esta():
    documento = _criar(CORPO_ANTIGO)

    _migracao.colocar_a_crase(_AppsFalso, None)

    assert _corpo(documento) == CORPO_NOVO


@pytest.mark.django_db
def test_texto_ja_corrigido_ou_reescrito_nao_e_tocado():
    for corpo in (CORPO_NOVO, "Escrevi isso do meu jeito: perde o acesso.\n"):
        documento = _criar(corpo)

        _migracao.colocar_a_crase(_AppsFalso, None)

        assert _corpo(documento) == corpo


@pytest.mark.django_db
def test_banco_sem_o_documento_nao_estoura():
    Documento.objects.filter(nome="como-funciona-a-entrada").delete()

    _migracao.colocar_a_crase(_AppsFalso, None)
    _migracao.tirar_a_crase(_AppsFalso, None)

    assert not Documento.objects.filter(nome="como-funciona-a-entrada").exists()


@pytest.mark.django_db
def test_a_reversa_devolve_o_texto_antigo_e_so_onde_ele_foi_corrigido():
    documento = _criar(CORPO_NOVO)

    _migracao.tirar_a_crase(_AppsFalso, None)
    assert _corpo(documento) == CORPO_ANTIGO

    _migracao.tirar_a_crase(_AppsFalso, None)
    assert _corpo(documento) == CORPO_ANTIGO
