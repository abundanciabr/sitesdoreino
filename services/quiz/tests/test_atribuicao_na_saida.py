"""Q30/Q31/Q33: a saída do quiz leva à oferta os 7 parâmetros internos, as
UTMs e a tentativa opaca (qa) + o quiz (qz), para a compra ficar ligada à
versão e à campanha. Nada de dado pessoal na URL."""

from urllib.parse import parse_qs, urlsplit

import pytest

from apps.quiz.models import Submission
from tests.test_campanhas_direcionadas import (  # noqa: F401
    abrir,
    campanha,
    concluir,
)
from tests.test_importar_quiz import documento, site  # noqa: F401

pytestmark = pytest.mark.django_db


def test_saida_leva_os_sete_internos_as_utms_e_qa(client, campanha):
    extra = (
        "&fmt=text&seg=empreendedor&src=tiktok&med=video&cpg=maio&ctv=anuncio3"
        "&utm_term=roblox"
    )
    entrada = abrir(client, campanha, extra=extra)
    envio = concluir(client, campanha, entrada, alto=True)
    submissao = Submission.objects.get()
    client.get(envio["Location"], HTTP_HOST=campanha.site.host)
    resp = client.post(
        f"/{campanha.slug}/sair",
        {"resposta": str(submissao.id), "quiz_attempt": entrada["session_id"]},
        HTTP_HOST=campanha.site.host,
    )
    assert resp.status_code == 302
    consulta = {k: v[0] for k, v in parse_qs(urlsplit(resp["Location"]).query).items()}
    assert consulta["v"] == "B2"
    assert consulta["fmt"] == "text"
    assert consulta["seg"] == "empreendedor"
    assert consulta["src"] == "tiktok"
    assert consulta["med"] == "video"
    assert consulta["cpg"] == "maio"
    assert consulta["ctv"] == "anuncio3"
    assert consulta["utm_source"] == "tiktok"
    assert consulta["utm_medium"] == "video"
    assert consulta["utm_campaign"] == "maio"
    assert consulta["utm_content"] == "anuncio3"
    assert consulta["utm_term"] == "roblox"
    assert consulta["qa"] == entrada["session_id"] == str(submissao.session_id)
    assert consulta["qz"] == campanha.slug
    assert "@" not in resp["Location"]
    assert "teste" not in resp["Location"]
