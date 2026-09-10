"""A autorização da central acontece no servidor, por ação e recurso."""

import json

import pytest
from django.core.exceptions import PermissionDenied

from apps.core import autorizacao_central


@pytest.fixture
def responsabilidades(settings):
    settings.CENTRAL_RESPONSAVEIS = json.dumps(
        {
            "estrategia": "estrategia@exemplo.com",
            "operacoes": "operacoes@exemplo.com",
            "ensino": "ensino@exemplo.com",
            "comercial": "comercial@exemplo.com",
        }
    )


def test_a_conta_da_funcao_autoriza_a_acao_no_recurso(responsabilidades):
    autorizacao_central.exigir(
        {"email": "ESTRATEGIA@EXEMPLO.COM"},
        responsabilidade="estrategia",
        acao="definir",
        recurso="compromisso semanal",
    )


def test_administrador_geral_nao_burla_a_funcao_da_acao(responsabilidades, settings):
    settings.ADMIN_EMAILS = "administrador@exemplo.com"

    with pytest.raises(PermissionDenied, match="Estratégia"):
        autorizacao_central.exigir(
            {"email": "administrador@exemplo.com"},
            responsabilidade="estrategia",
            acao="definir",
            recurso="compromisso semanal",
        )


def test_uma_conta_de_outra_funcao_e_recusada_no_servidor(responsabilidades):
    with pytest.raises(PermissionDenied, match="Estratégia"):
        autorizacao_central.exigir(
            {"email": "operacoes@exemplo.com"},
            responsabilidade="estrategia",
            acao="definir",
            recurso="compromisso semanal",
        )


@pytest.mark.parametrize(
    "configuracao",
    [
        "",
        "nao-e-json",
        '{"estrategia":"estrategia@exemplo.com"}',
        '{"estrategia":"a@exemplo.com","operacoes":"a@exemplo.com","ensino":"c@exemplo.com","comercial":"d@exemplo.com"}',
    ],
)
def test_configuracao_ausente_ou_invalida_recusa_toda_acao(settings, configuracao):
    settings.CENTRAL_RESPONSAVEIS = configuracao

    with pytest.raises(PermissionDenied, match="Estratégia"):
        autorizacao_central.exigir(
            {"email": "estrategia@exemplo.com"},
            responsabilidade="estrategia",
            acao="definir",
            recurso="compromisso semanal",
        )


def test_nao_aceita_acao_ou_recurso_vazios(responsabilidades):
    with pytest.raises(ValueError, match="ação"):
        autorizacao_central.exigir(
            {"email": "estrategia@exemplo.com"},
            responsabilidade="estrategia",
            acao="",
            recurso="compromisso semanal",
        )

    with pytest.raises(ValueError, match="recurso"):
        autorizacao_central.exigir(
            {"email": "estrategia@exemplo.com"},
            responsabilidade="estrategia",
            acao="definir",
            recurso="",
        )
