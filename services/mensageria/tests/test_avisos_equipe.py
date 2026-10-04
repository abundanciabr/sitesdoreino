"""`POST /avisos-equipe`: o e-mail do aviso da equipe sai uma vez por chave."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from django.test import Client

from apps.eventos.models import EnvioRegistrado

pytestmark = pytest.mark.django_db

BASE = "/api/mensageria"
TOKEN_LEITURA = "token-que-so-le"
TOKEN_PUBLICACAO = "token-que-publica"


@pytest.fixture(autouse=True)
def pares(settings):
    settings.TOKENS_SOMENTE_LEITURA = {TOKEN_LEITURA}
    settings.TOKENS_PUBLICACAO = {TOKEN_PUBLICACAO}


def postar(corpo: dict, token: str = TOKEN_PUBLICACAO):
    return Client().post(
        BASE + "/avisos-equipe",
        data=json.dumps(corpo),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )


def corpo(**mudancas):
    return {
        "site_id": "site-a",
        "chave": "aviso-equipe-1-abc",
        "destinatario": " Livia@Exemplo.com ",
        "assunto": "Uma conversa precisa de você",
        "corpo": "Abrir: https://meshcraft.top/admin/crm/",
        **mudancas,
    }


def test_a_mesma_chave_registra_um_envio_e_enfileira_uma_vez(django_capture_on_commit_callbacks):
    with patch("apps.eventos.avisos_equipe.enviar_notificacao") as enviar:
        with django_capture_on_commit_callbacks(execute=True):
            primeira = postar(corpo())
        with django_capture_on_commit_callbacks(execute=True):
            segunda = postar(corpo())
    assert primeira.status_code == 200 and primeira.json()["criado"] is True
    assert segunda.status_code == 200 and segunda.json()["criado"] is False
    assert primeira.json()["envio_id"] == segunda.json()["envio_id"]
    envio = EnvioRegistrado.objects.get()
    assert (envio.tipo, envio.canal, envio.event) == ("aviso_equipe", "email", "aviso.equipe")
    assert envio.destinatario == "livia@exemplo.com"
    enviar.assert_called_once_with(envio.id)


def test_chave_longa_continua_idempotente():
    with patch("apps.eventos.avisos_equipe.enviar_notificacao"):
        chave = "x" * 300
        assert postar(corpo(chave=chave)).json()["criado"] is True
        assert postar(corpo(chave=chave)).json()["criado"] is False
    assert len(EnvioRegistrado.objects.get().order_id) <= 100


def test_destinatario_sem_email_ou_sem_corpo_e_422():
    assert postar(corpo(destinatario="livia")).status_code == 422
    assert postar(corpo(corpo="  ")).status_code == 422
    assert postar(corpo(chave=" ")).status_code == 422
    assert not EnvioRegistrado.objects.exists()


def test_quem_so_le_nao_manda_aviso():
    assert postar(corpo(), token=TOKEN_LEITURA).status_code == 403
    assert not EnvioRegistrado.objects.exists()
