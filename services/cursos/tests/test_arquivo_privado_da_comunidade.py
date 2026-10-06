from urllib.parse import urlsplit

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.cursos.models import Envio
from tests.conftest import (
    ANA, BETO, AUTOAVALIACAO, COOKIE, README,
    dublar_matricula, dublar_sessao,
)

pytestmark = pytest.mark.django_db


def test_arquivo_de_entrega_so_abre_para_dono_e_professora(
    aluna, ana_pronta, rede, client, monkeypatch, tmp_path
):
    monkeypatch.setenv("COMUNIDADE_ARQUIVOS_DIR", str(tmp_path))
    aula = ana_pronta.aula
    resposta = client.post(
        reverse("entregar-checkpoint-do-curso", args=[
            aula.curso.slug, aula.bloco.parte, aula.numero,
        ]),
        {
            "arquivo_privado": SimpleUploadedFile("peca.blend", b"versao um"),
            "readme": README,
            "autoavaliacao": AUTOAVALIACAO,
        },
        HTTP_COOKIE=COOKIE,
    )
    assert resposta.status_code == 302
    envio = Envio.objects.get()
    endereco = urlsplit(envio.links[0]["url"]).path
    assert "arquivo/" in endereco
    dono = client.get(endereco, HTTP_COOKIE=COOKIE)
    assert dono.status_code == 200
    assert b"".join(dono.streaming_content) == b"versao um"

    dublar_sessao(rede, BETO)
    dublar_matricula(rede, BETO["email"], "aluno")
    assert client.get(endereco, HTTP_COOKIE=COOKIE).status_code == 404
    monkeypatch.setenv("CURSOS_PROFESSORES", BETO["email"])
    assert client.get(endereco, HTTP_COOKIE=COOKIE).status_code == 200
    monkeypatch.setenv("CURSOS_PROFESSORES", "")

    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"], "cadastrado")
    assert client.get(endereco, HTTP_COOKIE=COOKIE).status_code == 200
