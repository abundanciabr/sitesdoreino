"""Refazer o quiz a partir do resultado.

Quem volta à sessão concluída cai no próprio resultado (tests/test_telemetria.py).
Sem saída, a segunda aba que enviou respostas novas ficava presa no resultado
velho: o envio da mesma sessão é idempotente. O botão Refazer abre uma sessão
nova. O envio antigo continua no banco; só o cookie deixa de apontar para ele.
"""

import pytest
from django.test import Client

from apps.quiz.models import Submission
from tests.test_smoke import HOST_A, quiz_a, site_a  # noqa: F401

pytestmark = pytest.mark.django_db


def _navegador():
    return Client(enforce_csrf_checks=True)


def _enviar(navegador, quiz, pontos, email):
    pergunta = quiz.versions.get().questions.get(order=1)
    return navegador.post(
        f"/{quiz.slug}/",
        {
            f"pergunta_{pergunta.id}": pergunta.options.get(points=pontos).id,
            "email": email,
            "csrfmiddlewaretoken": navegador.cookies["quiz_csrf"].value,
        },
        HTTP_HOST=HOST_A,
    )


def _refazer(navegador, quiz, **extra):
    return navegador.post(f"/{quiz.slug}/refazer", extra, HTTP_HOST=HOST_A)


def test_quem_volta_sem_clicar_ve_o_resultado_e_a_saida_para_refazer(quiz_a):
    navegador = _navegador()
    navegador.get(f"/{quiz_a.slug}/", HTTP_HOST=HOST_A)
    envio = _enviar(navegador, quiz_a, 10, "lead@exemplo.com")

    volta = navegador.get(f"/{quiz_a.slug}/", HTTP_HOST=HOST_A, follow=True)

    assert volta.redirect_chain == [(envio["Location"], 302)]
    pagina = volta.content.decode()
    assert "Alto" in pagina
    assert f'<form method="post" action="/{quiz_a.slug}/refazer"' in pagina
    assert 'name="csrfmiddlewaretoken"' in pagina
    assert "Refazer o quiz" in pagina
    # `{# #}` do Django só vale numa linha; o de várias linhas vira texto na tela.
    assert "#}" not in pagina


def test_a_segunda_aba_sai_do_resultado_velho_e_grava_um_novo(quiz_a):
    """Duas abas dividem o cookie. A aba B abriu o formulário antes de a aba A
    enviar; o envio da B cai no resultado da A. Refazer é a saída: formulário
    vazio, sessão nova e um resultado novo, sem apagar o primeiro."""
    navegador = _navegador()
    navegador.get(f"/{quiz_a.slug}/?utm_source=ig", HTTP_HOST=HOST_A)
    primeiro = _enviar(navegador, quiz_a, 10, "aba-a@exemplo.com")
    aba_b = _enviar(navegador, quiz_a, 0, "aba-b@exemplo.com")
    assert aba_b["Location"] == primeiro["Location"]
    antigo = Submission.objects.get()

    refazer = _refazer(
        navegador,
        quiz_a,
        csrfmiddlewaretoken=navegador.cookies["quiz_csrf"].value,
    )

    assert refazer.status_code == 302
    assert refazer["Location"] == f"/{quiz_a.slug}/"
    formulario = navegador.get(refazer["Location"], HTTP_HOST=HOST_A)
    assert formulario.status_code == 200
    pagina = formulario.content.decode()
    assert 'name="email" value=""' in pagina
    assert " checked" not in pagina

    novo_envio = _enviar(navegador, quiz_a, 0, "aba-b@exemplo.com")

    novo = Submission.objects.exclude(pk=antigo.pk).get()
    assert novo_envio["Location"].endswith(f"?lead={novo.id}")
    assert novo.session_id != antigo.session_id
    assert novo.result_key == "baixo"
    assert novo.utm == {"source": "ig"}
    antigo.refresh_from_db()
    assert antigo.result_key == "alto"
    assert antigo.lead_email == "aba-a@exemplo.com"
    resultado = navegador.get(novo_envio["Location"], HTTP_HOST=HOST_A)
    assert "Baixo" in resultado.content.decode()


def test_refazer_so_anda_por_post_com_token(quiz_a):
    """Pré-carregamento de link e formulário de outro site não desfazem a volta
    ao resultado de ninguém."""
    navegador = _navegador()
    navegador.get(f"/{quiz_a.slug}/", HTTP_HOST=HOST_A)
    envio = _enviar(navegador, quiz_a, 10, "lead@exemplo.com")

    por_get = navegador.get(f"/{quiz_a.slug}/refazer", HTTP_HOST=HOST_A)
    sem_token = _refazer(navegador, quiz_a)

    assert por_get.status_code == 405
    assert sem_token.status_code == 403
    volta = navegador.get(f"/{quiz_a.slug}/", HTTP_HOST=HOST_A)
    assert volta.status_code == 302
    assert volta["Location"] == envio["Location"]
