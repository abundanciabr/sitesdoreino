"""A tomografia lê entregas privadas e só importa pela sessão admin."""

import json

import httpx
import pytest
import respx
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, RequestFactory
from django.urls import reverse

from apps.agentes.models import Entrega
from apps.agentes.trabalhos import robo_de
from apps.agentes.views import entrega_detalhe
from apps.core import tomografia_turmas
from apps.core.models import MembroDaEquipe


pytestmark = pytest.mark.django_db
IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
COOKIE = "meshcraft_sessao=sessao-de-ensaio"
URL = "tomografia_turmas_20261013"


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-de-ensaio")
    settings.ADMIN_EMAILS = "admin@exemplo.com"
    settings.URL_DE_ENTRADA = "/entrar/google"


def _cliente(email, *, csrf=False):
    respx.get(SESSAO).mock(return_value=httpx.Response(200, json={
        "autenticado": True, "id": "id-opaco", "nome_exibido": "Pessoa",
        "papel": None, "email": email,
    }))
    cliente = Client(enforce_csrf_checks=csrf)
    cliente.defaults["HTTP_COOKIE"] = COOKIE
    return cliente


def _arquivo(dados):
    return SimpleUploadedFile(
        "relatorio.json", json.dumps(dados, ensure_ascii=False).encode("utf-8"),
        content_type="application/json",
    )


def _dados_exemplo():
    return {
        "titulo": "Tomografia de teste", "total_mensagens": 7,
        "aviso_cobertura": "Cobertura limitada",
        "turmas": [
            {"id": "t1", "nome": "Turma um", "mensagens": 7, "identificadores": 2, "periodo": "mês de teste", "estado": "disponível"},
            {"id": "piloto", "nome": "Turma sem conversa", "estado": "sem dados", "leitura": "Fonte incompleta"},
        ],
        "achados": [{
            "id": "a", "area": "Técnica", "titulo": "Um achado", "sinal": "atrito",
            "resumo": "Observação", "turmas": [{"id": "t1", "leitura": "Apareceu"}],
            "evidencias": [{"id": "T1-M00001", "turma": "t1", "texto": "<img src=x onerror=alert(1)> " + "continuação extensa " * 80}],
        }],
    }


@respx.mock
def test_admin_importa_e_le_ultima_versao_privada_sem_criar_tarefa():
    MembroDaEquipe.objects.create(nome="Administrador", email="admin@exemplo.com")
    cliente = _cliente("admin@exemplo.com")
    resposta = cliente.post(reverse(URL), {"arquivo": _arquivo(_dados_exemplo())})
    assert resposta.status_code == 302
    entrega = Entrega.objects.get(tipo=tomografia_turmas.TIPO)
    assert entrega.titulo == tomografia_turmas.TITULO
    assert entrega.robo.membro.email == "admin@exemplo.com"
    assert entrega.tarefa_id is None and entrega.execucao_id is None
    assert entrega.versao == 1
    segunda = _dados_exemplo()
    segunda["titulo"] = "Nova versão"
    cliente.post(reverse(URL), {"arquivo": _arquivo(segunda)})
    assert Entrega.objects.filter(tipo=tomografia_turmas.TIPO).count() == 2
    html = cliente.get(reverse(URL)).content.decode()
    assert "Nova versão" in html and "Versão privada 2" in html


@respx.mock
def test_aluno_nao_le_nem_importa():
    cliente = _cliente("aluno@exemplo.com")
    assert cliente.get(reverse(URL)).status_code == 403
    assert cliente.post(reverse(URL), {"arquivo": _arquivo(_dados_exemplo())}).status_code == 403
    assert not Entrega.objects.filter(tipo=tomografia_turmas.TIPO).exists()


@respx.mock
def test_post_precisa_de_csrf():
    MembroDaEquipe.objects.create(nome="Administrador", email="admin@exemplo.com")
    cliente = _cliente("admin@exemplo.com", csrf=True)
    assert cliente.post(reverse(URL), {"arquivo": _arquivo(_dados_exemplo())}).status_code == 403
    assert not Entrega.objects.filter(tipo=tomografia_turmas.TIPO).exists()


@respx.mock
def test_json_invalido_nao_substitui_versao_anterior():
    MembroDaEquipe.objects.create(nome="Administrador", email="admin@exemplo.com")
    cliente = _cliente("admin@exemplo.com")
    cliente.post(reverse(URL), {"arquivo": _arquivo(_dados_exemplo())})
    invalido = SimpleUploadedFile("ruim.json", b'{"turmas": ', content_type="application/json")
    resposta = cliente.post(reverse(URL), {"arquivo": invalido})
    assert resposta.status_code == 400
    assert "Nenhuma versão foi criada" in resposta.content.decode()
    assert Entrega.objects.filter(tipo=tomografia_turmas.TIPO).count() == 1
    assert "Tomografia de teste" in cliente.get(reverse(URL)).content.decode()


@respx.mock
def test_evidencia_e_html_escapados_sem_cortar_o_texto():
    MembroDaEquipe.objects.create(nome="Administrador", email="admin@exemplo.com")
    cliente = _cliente("admin@exemplo.com")
    dados = _dados_exemplo()
    dados["sumario"] = ["<script>alert('x')</script>"]
    cliente.post(reverse(URL), {"arquivo": _arquivo(dados)})
    html = cliente.get(reverse(URL)).content.decode()
    assert "&lt;script&gt;" in html and "<script>alert('x')</script>" not in html
    assert "&lt;img src=x onerror=alert(1)&gt;" in html and "<img src=x" not in html
    assert "continuação extensa " * 80 in html
    assert "T1-M00001" in html and "Fonte incompleta" in html


def test_entrega_generica_da_tomografia_nao_abre_para_equipe():
    membro = MembroDaEquipe.objects.create(nome="Pessoa da equipe", email="equipe@exemplo.com")
    entrega = Entrega.objects.create(
        robo=robo_de(membro), tipo=tomografia_turmas.TIPO,
        titulo=tomografia_turmas.TITULO, conteudo=json.dumps(_dados_exemplo()),
    )
    request = RequestFactory().get(f"/equipe/robo/entregas/{entrega.pk}")
    request.admin = {"nome": "Pessoa da equipe", "email": membro.email, "equipe_apenas": True}
    assert entrega_detalhe(request, entrega.pk).status_code == 403


@respx.mock
def test_atlas_recolhivel_mostra_notas_casos_e_separa_inferencia_de_fato():
    MembroDaEquipe.objects.create(nome="Administrador", email="admin@exemplo.com")
    cliente = _cliente("admin@exemplo.com")
    dados = _dados_exemplo()
    dados["achados"][0].update({
        "interpretacao": "Interpretação principal",
        "causas_observadas": ["Causa vista no grupo"],
        "hipoteses": ["Hipótese ainda não testada"],
        "estado_desfecho": "Desfecho desconhecido",
    })
    dados["atlas"] = [{
        "escopo": "Recorte sintético", "periodo": "período sintético", "mensagens_lidas": 3,
        "achados": [{
            "id": "nota-1", "area": "Aprendizagem", "titulo": "Nota extensa",
            "sinal": "avanco", "resumo": "Fato visto",
            "interpretacao": "Leitura da nota <script>injetar()</script>",
            "causas_observadas": ["Aula citada"],
            "hipoteses": ["Talvez tenha influenciado"],
            "estado_desfecho": "Sem resposta final",
            "evidencias": [{"id": "T2-M00123", "turma": "t2", "tipo": "autorrelato", "texto": "Citação íntegra <b>texto</b>"}],
        }],
        "casos": [{"titulo": "Caso A", "leitura": "Ligação entre mensagens", "ids": ["T2-M00123", "T2-M00124"]}],
        "surpresas": ["Mudança inesperada"],
    }]
    assert cliente.post(reverse(URL), {"arquivo": _arquivo(dados)}).status_code == 302
    html = cliente.get(reverse(URL)).content.decode()
    assert '<section class="section" id="atlas"' in html
    assert '<details class="atlas-recorte"' in html
    for trecho in ("Recorte sintético", "Nota extensa", "Interpretação principal", "Causa vista no grupo", "Hipótese ainda não testada", "Desfecho desconhecido", "Aula citada", "Talvez tenha influenciado", "Sem resposta final", "T2-M00123", "T2-M00124", "Mudança inesperada"):
        assert trecho in html
    assert "&lt;script&gt;injetar()&lt;/script&gt;" in html
    assert "&lt;b&gt;texto&lt;/b&gt;" in html and "<b>texto</b>" not in html
