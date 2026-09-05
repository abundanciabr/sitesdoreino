"""Teste-guarda: o acesso ao plantão é fail-CLOSED por `CURSOS_PROFESSORES`.

Lei: `PLANO-CELULA-CURSOS.md` §6 ("Quem entra: a lista `CURSOS_PROFESSORES`,
fail-closed (lista vazia = ninguém), e a `identidade` só reconhece, nunca
autoriza") e §9 (constituição da célula: "eh_professor... não depende de
eh_aluno nem de matricula_conferida"). Molde de forma:
`tests/test_acesso_pela_matricula.py` (a sala do aluno) — aqui a régua é
diferente por DESENHO: `CURSOS_PROFESSORES` vazio, e-mail fora dela, e a
`identidade` fora do ar dão a MESMA resposta (403), nunca o convite fail-OPEN
da sala do aluno e nunca 500.
"""

from __future__ import annotations

import httpx
import pytest
from django.urls import reverse

from tests.conftest import ANA, COOKIE, dublar_matricula, dublar_sessao, url_da_situacao

pytestmark = pytest.mark.django_db

FRASE_DE_ACESSO_RESTRITO = "restrita ao plantão"


def _acessar_plantao(client):
    return client.get(reverse("plantao"), HTTP_COOKIE=COOKIE)


def _acessar_ficha(client, envio_id: int):
    return client.get(reverse("plantao-ficha", args=[envio_id]), HTTP_COOKIE=COOKIE)


# ------------------------------------------- CURSOS_PROFESSORES vazio = 403
def test_lista_ausente_e_403_mesmo_para_quem_e_aluno(
    env_dos_pares, rede, esqueleto, client, monkeypatch
):
    monkeypatch.delenv("CURSOS_PROFESSORES", raising=False)
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"], "aluno")
    resposta = _acessar_plantao(client)
    assert resposta.status_code == 403
    assert FRASE_DE_ACESSO_RESTRITO in resposta.content.decode()


def test_lista_vazia_e_403(env_dos_pares, rede, esqueleto, client, monkeypatch):
    monkeypatch.setenv("CURSOS_PROFESSORES", "")
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"], "aluno")
    assert _acessar_plantao(client).status_code == 403


def test_lista_so_com_virgulas_e_403(
    env_dos_pares, rede, esqueleto, client, monkeypatch
):
    monkeypatch.setenv("CURSOS_PROFESSORES", " , , ")
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"], "aluno")
    assert _acessar_plantao(client).status_code == 403


def test_as_duas_listas_vazias_e_403(
    env_dos_pares, rede, esqueleto, client, monkeypatch
):
    """O plantão tem DUAS portas desde 05/09/2026, e vazio continua sendo ninguém.

    Este é o guarda que a prova por mutação sabota: com `CURSOS_PROFESSORES` e
    `ADMIN_EMAILS` as duas vazias, a união é vazia e a resposta é 403. Uma
    variável esquecida no servidor nunca pode virar permissão para o site
    inteiro dar laudo nos outros.
    """
    monkeypatch.setenv("CURSOS_PROFESSORES", "")
    monkeypatch.setenv("ADMIN_EMAILS", "")
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"], "aluno")
    assert _acessar_plantao(client).status_code == 403


# ------------------------------------------------ ADMIN_EMAILS também abre
def test_admin_do_site_fora_de_cursos_professores_entra(
    env_dos_pares, rede, esqueleto, client, monkeypatch
):
    """Decisão do mantenedor em 05/09/2026: "qualquer admin do site pode abrir".

    A MESMA lista que já abre o `/admin/` (`ADMIN_EMAILS`) passou a abrir o
    plantão, e a lista própria da célula continua existindo ao lado. Isto NÃO é
    o `papel_do_site`: reconhecer continua não sendo autorizar, e quem autoriza
    continua sendo uma lista de e-mails decidida aqui dentro, fail-CLOSED.
    """
    monkeypatch.delenv("CURSOS_PROFESSORES", raising=False)
    monkeypatch.setenv("ADMIN_EMAILS", ANA["email"])
    dublar_sessao(rede, ANA)
    # O mantenedor não tem matrícula, e não precisa: `eh_professor` não depende
    # da `alunos`, exatamente como para a professora da lista própria.
    dublar_matricula(rede, ANA["email"], "cadastrado")
    resposta = _acessar_plantao(client)
    assert resposta.status_code == 200
    assert "Fila de revisão" in resposta.content.decode()


# --------------------------------------------- e-mail fora da lista = 403
def test_email_fora_da_lista_e_403(env_dos_pares, rede, esqueleto, client, monkeypatch):
    monkeypatch.setenv("CURSOS_PROFESSORES", "outra@exemplo.com")
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"], "aluno")
    resposta = _acessar_plantao(client)
    assert resposta.status_code == 403
    assert FRASE_DE_ACESSO_RESTRITO in resposta.content.decode()


def test_visitante_sem_cookie_e_403(env_dos_pares, esqueleto, client, monkeypatch):
    monkeypatch.setenv("CURSOS_PROFESSORES", ANA["email"])
    resposta = client.get(reverse("plantao"))
    assert resposta.status_code == 403


# --------------------------------------------- e-mail na lista = 200
def test_email_na_lista_e_200(env_dos_pares, rede, esqueleto, client, monkeypatch):
    monkeypatch.setenv("CURSOS_PROFESSORES", f"outra@exemplo.com, {ANA['email']}")
    dublar_sessao(rede, ANA)
    # A professora não precisa de matrícula: `eh_professor` não depende da
    # `alunos`. Mesmo respondendo "cadastrado" (sem matrícula ativa), o
    # plantão continua aberto para ela.
    dublar_matricula(rede, ANA["email"], "cadastrado")
    resposta = _acessar_plantao(client)
    assert resposta.status_code == 200
    assert "Fila de revisão" in resposta.content.decode()


def test_a_comparacao_e_case_insensitive_e_ignora_espaco(
    env_dos_pares, rede, esqueleto, client, monkeypatch
):
    monkeypatch.setenv("CURSOS_PROFESSORES", f"  {ANA['email'].upper()}  ")
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"], "cadastrado")
    assert _acessar_plantao(client).status_code == 200


def test_professora_nao_precisa_de_matricula_ativa(
    env_dos_pares, rede, esqueleto, client, monkeypatch
):
    """A `alunos` respondendo fora do ar não fecha o plantão: só a `identidade`
    decide se a professora é reconhecida; a matrícula é assunto do aluno."""
    monkeypatch.setenv("CURSOS_PROFESSORES", ANA["email"])
    dublar_sessao(rede, ANA)
    rota = rede.get(url_da_situacao(ANA["email"]))
    rota.mock(side_effect=httpx.ConnectError("alunos caiu"))
    assert _acessar_plantao(client).status_code == 200


# --------------------------------------- identidade fora do ar = 403, nunca 500
@pytest.mark.parametrize(
    "nome, falha",
    [
        ("fora do ar", httpx.ConnectError("identidade caiu")),
        ("500", httpx.Response(500)),
        ("200 sem json", httpx.Response(200, text="<html>")),
    ],
)
def test_identidade_fora_do_ar_e_403_nunca_500(
    env_dos_pares, rede, esqueleto, client, monkeypatch, nome, falha
):
    monkeypatch.setenv("CURSOS_PROFESSORES", ANA["email"])
    rota = rede.get(f"http://identidade:8000/interno/sessao/completa")
    if isinstance(falha, Exception):
        rota.mock(side_effect=falha)
    else:
        rota.mock(return_value=falha)
    resposta = _acessar_plantao(client)
    assert resposta.status_code == 403, nome


@pytest.mark.parametrize("ausente", ["IDENTIDADE_API_URL", "IDENTIDADE_API_TOKEN"])
def test_env_do_par_da_identidade_ausente_e_403_nunca_500(
    env_dos_pares, esqueleto, client, monkeypatch, ausente
):
    monkeypatch.setenv("CURSOS_PROFESSORES", ANA["email"])
    monkeypatch.delenv(ausente)
    assert _acessar_plantao(client).status_code == 403


# --------------------------------------------- a ficha herda o mesmo portão
def test_a_ficha_do_laudo_tambem_e_fail_closed(
    env_dos_pares, rede, envio_na_fila, client, monkeypatch
):
    monkeypatch.delenv("CURSOS_PROFESSORES", raising=False)
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"], "aluno")
    resposta = _acessar_ficha(client, envio_na_fila.id)
    assert resposta.status_code == 403


def test_a_ficha_abre_para_quem_esta_na_lista(
    env_dos_pares, rede, envio_na_fila, client, monkeypatch
):
    monkeypatch.setenv("CURSOS_PROFESSORES", ANA["email"])
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"], "aluno")
    resposta = _acessar_ficha(client, envio_na_fila.id)
    assert resposta.status_code == 200
    assert "Emitir laudo" in resposta.content.decode()
