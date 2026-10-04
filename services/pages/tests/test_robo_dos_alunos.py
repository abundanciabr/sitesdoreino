import json
import httpx
import pytest
from django.test import Client
from django.urls import reverse
from apps.portfolio.models import Peca, Portfolio
from test_jornada_autoral import como, quiz_falso
from conftest import ANA, SITE, ADMIN

pytestmark = pytest.mark.django_db

def test_gerar_e_regerar_sao_rascunhos_e_usam_so_o_aluno(aluna, site_declarado, rede, quiz_falso):
    meu = Portfolio.objects.create(site_id=SITE, aluno_id=ANA["id"], apresentacao_publica="Texto salvo")
    outro = Portfolio.objects.create(site_id=SITE, aluno_id="outro")
    Peca.objects.create(portfolio=meu, ordem=1, link="https://exemplo.com/modelo.png", legenda="Meu cabelo")
    Peca.objects.create(portfolio=outro, ordem=1, link="https://exemplo.com/modelo.png", legenda="Segredo de outro aluno")
    api = rede.post(ADMIN + "/robo-dos-alunos/gerar").mock(side_effect=[
        httpx.Response(200, json={"texto": "Primeiro exemplo"}),
        httpx.Response(200, json={"texto": "Outro exemplo"}),
        httpx.Response(503, json={"erro": "Tente mais tarde"}),
    ])
    cliente = Client()
    dados = {"campo": "apresentacao_publica", "apresentacao_publica": "Rascunho em edição", "servico_publico": "Campo preservado"}
    url = reverse("gerar_exemplo")
    assert cliente.post(url, dados, **como()).json()["texto"] == "Primeiro exemplo"
    dados["apresentacao_publica"] = "Primeiro exemplo"
    assert cliente.post(url, dados, **como()).json()["texto"] == "Outro exemplo"
    assert cliente.post(url, dados, **como()).status_code == 503
    corpo = json.loads(api.calls[0].request.content)
    assert corpo["contexto"]["trabalhos"][0]["legenda"] == "Meu cabelo"
    assert "Segredo de outro aluno" not in json.dumps(corpo)
    assert corpo["contexto"]["textos_em_edicao"]["servico_publico"] == "Campo preservado"
    meu.refresh_from_db()
    assert meu.apresentacao_publica == "Texto salvo" and not meu.vitrine_publicada
    html = cliente.get(reverse("apresentacao_publica") + "?avancado=1", **como()).content.decode()
    assert "Gerar página e kit" in html and "Meu kit de vendas" in html
    script = cliente.get(reverse("script_robo"), **como())
    assert script.status_code == 200 and "javascript" in script["Content-Type"]

def test_campo_invalido_e_sem_login_nao_geram(aluna, site_declarado, rede, quiz_falso):
    api = rede.post(ADMIN + "/robo-dos-alunos/gerar")
    assert Client().post(reverse("gerar_exemplo"), {"campo": "outro"}, **como()).status_code == 422
    assert not api.called
    assert Client(enforce_csrf_checks=True).post(reverse("gerar_exemplo"), {"campo": "apresentacao_publica"}, **como()).status_code == 403
