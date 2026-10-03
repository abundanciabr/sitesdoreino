"""O painel consulta dados reais e envia mudanças com a identidade da sessão."""
import uuid

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.auditoria.models import Registro
from apps.core.crm_client import CRMClient

BASE = "http://leads:8000/api/leads"
SESSAO = "http://identidade:8000/interno/sessao/completa"
ID = str(uuid.UUID("24e45be2-77bb-4a32-a388-78d2ce9adcad"))
LEAD = str(uuid.UUID("92f0c4e1-25f4-480f-a64a-1b68d259c563"))


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("LEADS_API_URL", BASE)
    monkeypatch.setenv("LEADS_API_TOKEN", "token-de-teste")
    monkeypatch.setenv("IDENTIDADE_API_URL", "http://identidade:8000/interno")
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-identidade-teste")
    settings.ADMIN_EMAILS = "dono@example.com"


def dentro(csrf=False):
    respx.get(SESSAO).mock(return_value=httpx.Response(200, json={"autenticado": True, "id": "operador-real", "nome_exibido": "Dono", "email": "dono@example.com", "papel": None}))
    c = Client(enforce_csrf_checks=csrf)
    c.defaults["HTTP_COOKIE"] = "meshcraft_sessao=teste"
    return c


def oportunidade(**mudancas):
    return {"id": ID, "lead_id": LEAD, "etapa": "nova", "situacao": "aberta", "titular": {"id": "crm-recuperacao"}, "contato": {"id": LEAD, "nome": "Ana", "email": "ana@example.com"}, "proximo_passo": {"descricao": "Recuperar Pix vencido", "executar_ate": "2026-10-01T15:00:00-03:00", "evidencia_esperada": "Resposta registrada"}, "historico": [{"registrado_em": "2026-10-01T18:00:00Z", "autor_id": "sistema", "descricao": "Pix venceu"}], **mudancas}


@respx.mock
def test_crm_quadro_renderiza_dados_e_filtros():
    rota = respx.get(BASE + "/crm").mock(return_value=httpx.Response(200, json={"itens": [oportunidade()], "resumo": {"contatos": 100, "eventos": 188, "abertas": 1, "atrasadas": 1, "ganhas": 0}, "pagina": 1, "total": 1, "tem_mais": False}))
    r = dentro().get(reverse("crm"), {"q": "Ana", "etapa": "nova"})
    assert r.status_code == 200
    assert "Ana" in r.content.decode() and "188" in r.content.decode()
    assert reverse("crm_oportunidade", args=[ID]) in r.content.decode()
    assert rota.calls.last.request.url.params["q"] == "Ana"


@respx.mock
def test_fonte_indisponivel_nao_inventa_zero():
    respx.get(BASE + "/crm").mock(return_value=httpx.Response(503))
    r = dentro().get(reverse("crm"))
    assert r.status_code == 503
    assert "Não foi possível consultar" in r.content.decode()
    assert "crm-numeros\">" not in r.content.decode()


@respx.mock
def test_ficha_historico_e_horario_local():
    respx.get(BASE + "/crm/" + ID).mock(return_value=httpx.Response(200, json=oportunidade()))
    r = dentro().get(reverse("crm_oportunidade", args=[ID]))
    assert r.status_code == 200
    assert "01/10/2026 15:00" in r.content.decode()
    assert "Pix venceu" in r.content.decode()
    assert reverse("contato", args=[LEAD]) in r.content.decode()


@respx.mock
def test_salvar_passo_usa_autor_da_sessao_e_fuso():
    rota = respx.patch(BASE + "/crm/" + ID).mock(return_value=httpx.Response(200, json=oportunidade()))
    r = dentro().post(reverse("crm_salvar", args=[ID]), {"gesto": "passo", "etapa": "negociacao", "descricao": "Retornar amanhã", "prazo": "2026-10-04T10:00", "autor_id": "forjado"})
    assert r.status_code == 302
    import json
    body = json.loads(rota.calls.last.request.content)
    assert body["autor_id"] == "operador-real"
    assert body["proximo_passo"]["executar_ate"] == "2026-10-04T10:00:00-03:00"
    assert Registro.objects.get(alvo=ID).desfecho == Registro.OK


@respx.mock
def test_nota_vazia_nao_grava():
    rota = respx.post(BASE + "/crm/" + ID + "/history").mock(return_value=httpx.Response(201, json=oportunidade()))
    respx.get(BASE + "/crm/" + ID).mock(return_value=httpx.Response(200, json=oportunidade()))
    r = dentro().post(reverse("crm_salvar", args=[ID]), {"gesto": "nota", "nota": " "})
    assert r.status_code == 422 and not rota.called


@respx.mock
def test_recusa_preserva_texto_e_audita():
    respx.patch(BASE + "/crm/" + ID).mock(return_value=httpx.Response(409, json={"detail": "Oportunidade encerrada"}))
    respx.get(BASE + "/crm/" + ID).mock(return_value=httpx.Response(200, json=oportunidade()))
    r = dentro().post(reverse("crm_salvar", args=[ID]), {"gesto": "passo", "etapa": "nova", "descricao": "Texto preservado", "prazo": "2026-10-04T10:00"})
    assert r.status_code == 422
    assert "Texto preservado" in r.content.decode() and "Oportunidade encerrada" in r.content.decode()
    assert Registro.objects.get(alvo=ID).desfecho == Registro.RECUSADO_PELA_CELULA


@respx.mock
def test_nao_permite_ganha_manual():
    rota = respx.post(BASE + "/crm/" + ID + "/close").mock(return_value=httpx.Response(200, json=oportunidade()))
    respx.get(BASE + "/crm/" + ID).mock(return_value=httpx.Response(200, json=oportunidade()))
    r = dentro().post(reverse("crm_salvar", args=[ID]), {"gesto": "encerrar", "resultado": "ganha", "motivo": "Teste", "evidencia": "Teste"})
    assert r.status_code == 422 and not rota.called


@respx.mock
def test_csrf_protege_escrita():
    r = dentro(csrf=True).post(reverse("crm_salvar", args=[ID]), {"gesto": "nota", "nota": "Texto"})
    assert r.status_code == 403


@respx.mock
def test_visitante_nao_chega_aos_contatos():
    for name in ("crm", "contatos"):
        assert Client().get(reverse(name)).status_code == 302


@respx.mock
def test_cliente_recusa_resposta_sem_forma():
    respx.get(BASE + "/crm").mock(return_value=httpx.Response(200, json=[]))
    assert CRMClient().quadro()[0] == CRMClient.NAO_RESPONDEU
