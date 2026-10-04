"""Aceite de contato pelo WhatsApp no formulário do quiz e nos eventos."""

import pytest

from apps.quiz import consentimento
from apps.quiz.models import ConsentimentoDoContato, OutboxEvent
from tests.test_crm_respostas_e_captura import abrir, capturar, opcao, perguntas, quiz  # noqa: F401
from tests.test_importar_quiz import documento, site  # noqa: F401
from tests.test_smoke import HOST_A, site_a, site_b  # noqa: F401

pytestmark = pytest.mark.django_db


def concluir(client, quiz, telefone="11 98888-7777", **extra):  # noqa: F811
    p1, p2 = perguntas(quiz)
    return client.post(
        f"/{quiz.slug}/",
        {
            f"pergunta_{p1.id}": opcao(p1, "Vender online").id,
            f"pergunta_{p2.id}": opcao(p2, "Menos de 1 hora").id,
            "email": "ana@exemplo.com",
            "nome": "Ana",
            "telefone": telefone,
            **extra,
        },
        HTTP_HOST=HOST_A,
    )


def evento(nome):
    return OutboxEvent.objects.filter(event=nome).order_by("id")


def test_formulario_mostra_a_caixa_desmarcada_com_texto_simples(client, quiz):  # noqa: F811
    resposta = client.get(f"/{quiz.slug}/", HTTP_HOST=HOST_A)
    html = resposta.content.decode()
    assert 'name="aceita_whatsapp"' in html
    assert consentimento.TEXTO_WHATSAPP in html
    trecho = html.split('name="aceita_whatsapp"', 1)[1].split(">", 1)[0]
    assert "checked" not in trecho


def test_concluir_sem_marcar_envia_aceito_falso(client, quiz):  # noqa: F811
    abrir(client, quiz)
    assert concluir(client, quiz).status_code == 302
    dados = evento("quiz.completado").get().payload
    assert dados["consentimento"]["whatsapp"]["aceito"] is False
    assert dados["consentimento"]["whatsapp"]["registrado_em"] is None
    assert dados["consentimento"]["whatsapp"]["texto"] == consentimento.TEXTO_WHATSAPP


def test_concluir_marcando_envia_aceito_com_texto_e_versao(client, quiz):  # noqa: F811
    abrir(client, quiz)
    assert concluir(client, quiz, aceita_whatsapp="1").status_code == 302
    dados = evento("quiz.completado").get().payload
    bloco = dados["consentimento"]["whatsapp"]
    assert bloco["aceito"] is True
    assert bloco["versao_texto"] == consentimento.VERSAO_TEXTO
    assert bloco["registrado_em"]
    assert dados["lead"]["phone"] == "11 98888-7777"
    registro = ConsentimentoDoContato.objects.get()
    assert registro.aceita_whatsapp and registro.site_id == quiz.site_id


def test_marcar_sem_telefone_nao_vale(client, quiz):  # noqa: F811
    abrir(client, quiz)
    assert concluir(client, quiz, telefone="", aceita_whatsapp="1").status_code == 302
    dados = evento("quiz.completado").get().payload
    assert dados["consentimento"]["whatsapp"]["aceito"] is False


def test_erro_no_formulario_preserva_a_caixa_marcada(client, quiz):  # noqa: F811
    abrir(client, quiz)
    p1, p2 = perguntas(quiz)
    resposta = client.post(
        f"/{quiz.slug}/",
        {
            f"pergunta_{p1.id}": opcao(p1, "Vender online").id,
            f"pergunta_{p2.id}": opcao(p2, "Menos de 1 hora").id,
            "email": "",
            "telefone": "11 98888-7777",
            "aceita_whatsapp": "1",
        },
        HTTP_HOST=HOST_A,
    )
    assert resposta.status_code == 422
    trecho = resposta.content.decode().split('name="aceita_whatsapp"', 1)[1].split(">", 1)[0]
    assert "checked" in trecho


def publicar_paradas():
    from datetime import timedelta

    from django.utils import timezone

    from apps.quiz.tasks import SILENCIO_DA_CAPTURA, publicar_capturas_paradas

    return publicar_capturas_paradas(timezone.now() + SILENCIO_DA_CAPTURA + timedelta(minutes=1))


def test_captura_parcial_leva_o_aceite(client, quiz):  # noqa: F811
    abrir(client, quiz)
    resposta = capturar(client, quiz, telefone="11 98888-7777", aceita_whatsapp="1")
    assert resposta.status_code == 201
    assert publicar_paradas() == 1
    dados = evento("quiz.captura_parcial").get().payload
    assert dados["consentimento"]["whatsapp"]["aceito"] is True


def test_mudar_a_escolha_antes_do_aviso_vai_no_proprio_aviso(client, quiz):  # noqa: F811
    abrir(client, quiz)
    capturar(client, quiz, telefone="11 98888-7777")
    capturar(client, quiz, telefone="11 98888-7777", aceita_whatsapp="1")
    assert not evento("quiz.consentimento").exists()
    publicar_paradas()
    dados = evento("quiz.captura_parcial").get().payload
    assert dados["consentimento"]["whatsapp"]["aceito"] is True


def test_mudar_a_escolha_depois_do_aviso_publica_quiz_consentimento(client, quiz):  # noqa: F811
    abrir(client, quiz)
    capturar(client, quiz, telefone="11 98888-7777")
    publicar_paradas()
    assert evento("quiz.captura_parcial").get().payload["consentimento"]["whatsapp"]["aceito"] is False
    # Repetir sem mudar nada não publica.
    capturar(client, quiz, telefone="11 98888-7777")
    assert not evento("quiz.consentimento").exists()

    capturar(client, quiz, telefone="11 98888-7777", aceita_whatsapp="1")
    capturar(client, quiz, telefone="11 98888-7777")
    mudancas = list(evento("quiz.consentimento"))
    assert [m.payload["consentimento"]["whatsapp"]["aceito"] for m in mudancas] == [True, False]
    dados = mudancas[0].payload
    assert dados["site_id"] == quiz.site_id
    assert dados["lead"]["phone"] == "11 98888-7777"
    assert dados["captura_id"]
    # Só uma captura parcial, como antes.
    assert evento("quiz.captura_parcial").count() == 1


def test_concluir_depois_de_aceitar_na_captura_usa_a_escolha_final(client, quiz):  # noqa: F811
    abrir(client, quiz)
    capturar(client, quiz, telefone="11 98888-7777", aceita_whatsapp="1")
    assert concluir(client, quiz).status_code == 302  # desmarcou antes de enviar
    dados = evento("quiz.completado").get().payload
    assert dados["consentimento"]["whatsapp"]["aceito"] is False
    assert ConsentimentoDoContato.objects.get().aceita_whatsapp is False
