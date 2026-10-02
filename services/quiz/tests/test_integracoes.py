"""Adaptadores GA4, Meta, TikTok, Klaviyo e ActiveCampaign, provados com dublê HTTP.

Nenhuma chamada de rede: o transporte é injetado.
"""

import hashlib
import json
import uuid
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.quiz.integracoes import (
    activecampaign,
    ga4,
    klaviyo,
    meta,
    servico,
    tiktok,
)
from apps.quiz.integracoes.models import IntegracaoEnvio
from apps.quiz.integracoes.nucleo import Requisicao, hash_email
from apps.quiz.models import Submission, TelemetryEvent
from tests.test_smoke import quiz_a, site_a  # noqa: F401

pytestmark = pytest.mark.django_db

TODAS = {
    "GA4_MEASUREMENT_ID": "G-TESTE123",
    "GA4_API_SECRET": "segredo-ga4-xyz",
    "META_PIXEL_ID": "111222",
    "META_CAPI_TOKEN": "token-meta-secreto",
    "META_TEST_EVENT_CODE": "TEST123",
    "TIKTOK_PIXEL_CODE": "PIXTT",
    "TIKTOK_ACCESS_TOKEN": "token-tiktok-secreto",
    "KLAVIYO_API_KEY": "pk_klaviyo_secreta",
    "KLAVIYO_LIST_ID": "LISTA1",
    "AC_API_URL": "https://conta.api-us1.com",
    "AC_API_TOKEN": "token-ac-secreto",
    "AC_LIST_ID": "7",
}
SEGREDOS = [v for k, v in TODAS.items() if any(m in k for m in ("TOKEN", "SECRET", "KEY"))]


class Duble:
    """Transporte falso: grava as requisições e responde o que o serviço espera."""

    def __init__(self, falhar_em=None, status_falha=500, corpo_falha="boom"):
        self.chamadas: list[Requisicao] = []
        self.falhar_em = falhar_em
        self.status_falha = status_falha
        self.corpo_falha = corpo_falha

    def __call__(self, req):
        self.chamadas.append(req)
        if self.falhar_em and self.falhar_em in req.url:
            return self.status_falha, self.corpo_falha
        if "profile-import" in req.url:
            return 200, {"data": {"id": "PERFIL1"}}
        if "contact/sync" in req.url:
            return 200, {"contact": {"id": "42"}}
        if req.metodo == "GET" and "/tags" in req.url:
            return 200, {"tags": []}
        if req.url.endswith("/tags"):
            return 201, {"tag": {"id": "9"}}
        if "tiktok" in req.url:
            return 200, {"code": 0}
        return 200, {}


@pytest.fixture
def submissao(quiz_a):
    versao = quiz_a.versions.get()
    versao.experience = {"band_offers": {"alto": "oferta-b2"}}
    versao.save()
    return Submission.objects.create(
        quiz=quiz_a,
        version=versao,
        session_id=uuid.uuid4(),
        site_id=quiz_a.site_id,
        score=10,
        result_key="alto",
        answers={},
        lead_email="  Lead@Exemplo.COM ",
        lead_name="Ana Souza",
        utm={"source": "meta", "campaign": "lancamento"},
        context={"v": "B2", "fmt": "video", "seg": "iniciante", "src": "ig", "med": "cpc", "cpg": "c1", "ctv": "v3"},
    )


def evento(sub):
    return servico.evento_da_submissao(sub)


# ------------------------------------------------------------ payloads


def test_hash_do_email_e_normalizado():
    esperado = hashlib.sha256(b"lead@exemplo.com").hexdigest()
    assert hash_email("  Lead@Exemplo.COM ") == esperado


def test_ga4_payload_com_contexto_e_client_id_opaco(submissao):
    corpo = ga4.montar(evento(submissao))
    nome = corpo["events"][0]
    params = nome["params"]
    assert nome["name"] == "quiz_complete"
    for chave, valor in {"version": "original", "fmt": "video", "seg": "iniciante",
                         "src": "ig", "med": "cpc", "cpg": "c1", "ctv": "v3",
                         "utm_source": "meta", "utm_campaign": "lancamento"}.items():
        assert params[chave] == valor
    assert "exemplo" not in json.dumps(corpo).lower()
    assert corpo["client_id"] == ga4.montar(evento(submissao))["client_id"]
    assert str(submissao.session_id) not in corpo["client_id"]


def test_ga4_saida_da_oferta(submissao):
    TelemetryEvent.objects.create(
        session_id=submissao.session_id, site_id=submissao.site_id,
        quiz_slug="crivo", version_key="original", event_type="checkout_exit",
        element_id="alto", metadata={"demonstracao": True},
        occurred_at=timezone.now(),
    )
    ev = servico.evento_da_saida(TelemetryEvent.objects.get())
    corpo = ga4.montar(ev)
    assert corpo["events"][0]["name"] == "quiz_offer_exit"
    assert corpo["events"][0]["params"]["demonstracao"] is True
    assert corpo["events"][0]["params"]["offer_id"] == "oferta-b2"


def test_meta_lead_com_event_id_da_submissao_e_email_com_hash(submissao):
    corpo = meta.montar(evento(submissao), "TEST123")
    dado = corpo["data"][0]
    assert dado["event_name"] == "Lead"
    assert dado["event_id"] == str(submissao.id)
    assert dado["user_data"]["em"] == [hash_email("lead@exemplo.com")]
    assert dado["custom_data"]["seg"] == "iniciante"
    assert corpo["test_event_code"] == "TEST123"
    assert "test_event_code" not in meta.montar(evento(submissao))
    assert "lead@exemplo.com" not in json.dumps(corpo).lower()


def test_tiktok_complete_registration(submissao):
    corpo = tiktok.montar(evento(submissao), "PIXTT")
    dado = corpo["data"][0]
    assert dado["event"] == "CompleteRegistration"
    assert dado["event_id"] == str(submissao.id)
    assert dado["user"]["email"] == hash_email("lead@exemplo.com")
    assert corpo["event_source_id"] == "PIXTT"


def test_klaviyo_profile_e_evento_idempotente(submissao):
    ev = evento(submissao)
    perfil = klaviyo.montar_profile(ev)["data"]["attributes"]
    assert perfil["email"] == "lead@exemplo.com"
    assert perfil["properties"] == {
        "origem": "ig", "versao": "original", "segmento": "iniciante",
        "formato": "video", "resultado": "alto", "oferta": "oferta-b2", "quiz": "crivo",
    }
    corpo = klaviyo.montar_evento(ev)["data"]["attributes"]
    assert corpo["metric"]["data"]["attributes"]["name"] == "Quiz concluído"
    assert corpo["unique_id"] == str(submissao.id)


def test_activecampaign_tags_e_sync(submissao):
    ev = evento(submissao)
    assert activecampaign.tags(ev) == [
        "quiz:crivo", "versao:original", "seg:iniciante", "oferta:oferta-b2",
    ]
    assert activecampaign.montar_contato(ev)["contact"]["email"] == "lead@exemplo.com"
    duble = Duble()
    activecampaign.enviar(ev, TODAS, duble)
    urls = [c.url for c in duble.chamadas]
    assert urls[0].endswith("/api/3/contact/sync")
    assert any(u.endswith("/contactTags") for u in urls)
    assert any(u.endswith("/notes") for u in urls)
    assert any(u.endswith("/contactLists") for u in urls)
    assert all(c.headers["Api-Token"] == TODAS["AC_API_TOKEN"] for c in duble.chamadas)


# ---------------------------------------------------- envio e idempotência


def test_envio_aceita_e_nao_reenvia(submissao):
    duble = Duble()
    primeira = servico.enviar_pendentes(TODAS, duble)
    assert primeira == {f"{s}:aceito": 1 for s in ("ga4", "meta", "tiktok", "klaviyo", "activecampaign")}
    assert IntegracaoEnvio.objects.filter(status="aceito").count() == 5
    n = len(duble.chamadas)
    segunda = servico.enviar_pendentes(TODAS, duble)
    assert segunda == {}
    assert len(duble.chamadas) == n


def test_servico_sem_variavel_fica_nao_configurado_sem_erro(submissao):
    duble = Duble()
    env = {k: v for k, v in TODAS.items() if k.startswith("GA4")}
    contagem = servico.enviar_pendentes(env, duble)
    assert contagem["ga4:aceito"] == 1
    assert contagem["meta:nao_configurado"] == 1
    reg = IntegracaoEnvio.objects.get(servico="meta")
    assert reg.status == "nao_configurado" and reg.ultimo_erro == "" and reg.tentativas == 0
    assert all("facebook" not in c.url for c in duble.chamadas)
    # ligando depois, o mesmo evento segue
    servico.enviar_pendentes(TODAS, duble)
    assert IntegracaoEnvio.objects.get(servico="meta").status == "aceito"


def test_falha_reenvia_com_limite_e_nao_vaza_token(submissao):
    duble = Duble(falhar_em="graph.facebook.com", corpo_falha=f"erro {TODAS['META_CAPI_TOKEN']}")
    env = {k: v for k, v in TODAS.items() if k.startswith("META")}
    for _ in range(servico.MAX_TENTATIVAS + 2):
        servico.enviar_pendentes(env, duble)
    reg = IntegracaoEnvio.objects.get(servico="meta")
    assert reg.status == "falhou"
    assert reg.tentativas == servico.MAX_TENTATIVAS
    assert "token-meta-secreto" not in reg.ultimo_erro
    assert "http 500" in reg.ultimo_erro
    estado = servico.estado_integracoes(env)
    assert estado["meta"]["configurado"] is True
    assert estado["meta"]["ultima_falha"]["erro"] == reg.ultimo_erro
    assert estado["ga4"]["configurado"] is False


def test_excecao_do_transporte_nao_vaza_segredo(submissao):
    def explode(req):
        raise RuntimeError(f"falha em {req.url}")

    env = {k: v for k, v in TODAS.items() if k.startswith("GA4")}
    servico.enviar_pendentes(env, explode)
    reg = IntegracaoEnvio.objects.get(servico="ga4")
    assert reg.status == "falhou"
    assert "segredo-ga4-xyz" not in reg.ultimo_erro


def test_sem_consentimento_nao_envia_dado_pessoal(submissao):
    submissao.context = {**submissao.context, "consentimento": "false"}
    submissao.save()
    duble = Duble()
    contagem = servico.enviar_pendentes(TODAS, duble)
    assert contagem["ga4:aceito"] == 1
    for s in ("meta", "tiktok", "klaviyo", "activecampaign"):
        assert contagem[f"{s}:sem_consentimento"] == 1
    assert len(duble.chamadas) == 1


def test_saida_da_oferta_vai_so_ao_ga4(submissao):
    TelemetryEvent.objects.create(
        session_id=submissao.session_id, site_id=submissao.site_id,
        quiz_slug="crivo", version_key="original", event_type="checkout_exit",
        element_id="alto", metadata={}, occurred_at=timezone.now(),
    )
    contagem = servico.enviar_pendentes(TODAS, Duble())
    assert contagem["ga4:aceito"] == 2  # conclusão + saída
    assert contagem["meta:aceito"] == 1


# ---------------------------------------------------------------- comando


def test_comando_dry_run_mascara_e_nao_envia(submissao, monkeypatch):
    for k, v in TODAS.items():
        monkeypatch.setenv(k, v)
    saida = StringIO()
    call_command("enviar_integracoes", "--dry-run", stdout=saida)
    texto = saida.getvalue()
    assert "dry-run:" in texto
    for segredo in SEGREDOS:
        assert segredo not in texto
    assert "lead@exemplo.com" not in texto.lower()
    assert IntegracaoEnvio.objects.count() == 0


def test_comando_sem_variaveis_nao_chama_rede(submissao, monkeypatch):
    for k in TODAS:
        monkeypatch.delenv(k, raising=False)
    saida = StringIO()
    call_command("enviar_integracoes", stdout=saida)
    assert "meta:nao_configurado: 1" in saida.getvalue()
    call_command("enviar_integracoes", "--servico", "ga4", stdout=StringIO())
    assert set(IntegracaoEnvio.objects.values_list("status", flat=True)) == {"nao_configurado"}


def test_registro_unico_por_servico_e_evento(submissao):
    from django.db import IntegrityError, transaction

    IntegracaoEnvio.objects.create(servico="ga4", chave_evento="x")
    with pytest.raises(IntegrityError), transaction.atomic():
        IntegracaoEnvio.objects.create(servico="ga4", chave_evento="x")


# ---------------------------------------------------------------- retargeting


def test_publico_retargeting_exclui_compradores_e_quem_nao_consentiu(quiz_a):
    versao = quiz_a.versions.get()

    def nova(email, **ctx):
        return Submission.objects.create(
            quiz=quiz_a, version=versao, session_id=uuid.uuid4(),
            site_id=quiz_a.site_id, score=1, result_key="baixo", answers={},
            lead_email=email, context=ctx,
        )

    nova("a@x.com")
    nova("compra@x.com")
    nova("nega@x.com", consentimento="0")
    nova("A@x.com")  # repetido: um item só
    publico = servico.publico_retargeting("original", compradores=lambda: ["Compra@x.com"])
    assert [p["email"] for p in publico] == ["a@x.com"]
    assert servico.publico_retargeting("B2") == []
