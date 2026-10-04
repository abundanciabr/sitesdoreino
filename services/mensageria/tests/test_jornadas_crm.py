"""Jornada de uma oportunidade do CRM consulta o que já aconteceu antes de insistir.

Compra aprovada encerra a jornada; pessoa da equipe na conversa, assistente
respondendo ou lead que acabou de falar seguram o passo; descadastro barra o
canal; CRM fora do ar não deixa nada sair às cegas. Cada envio vira último
contato da oportunidade e entra na conversa do lead.
"""

from types import SimpleNamespace

import pytest
from django.apps import apps as django_apps
from django.utils.dateparse import parse_datetime

from apps.jornadas import crm, despacho, motor
from apps.jornadas.models import Entrega, Inscricao, JornadaVersao, Preferencia, TextoDoPasso

from test_jornadas_motor import PESSOA, SITE, quando, uma_jornada

pytestmark = pytest.mark.django_db

OPORTUNIDADE = "6f1c2d3e-0000-4000-8000-000000000001"
OUTRA = "6f1c2d3e-0000-4000-8000-000000000002"
LEAD = "7a7a7a7a-0000-4000-8000-0000000000aa"


class CrmFalso:
    """A célula `leads` do outro lado: responde como os ramos da onda 1."""

    def __init__(self, *, situacao="aberta", atendido_por=None, acompanhamento=None,
                 telefone="+55 11 98888-7777", patch_status=200):
        self.situacao = situacao
        self.atendido_por = atendido_por
        self.acompanhamento = acompanhamento if acompanhamento is not None else {
            "pode_insistir": True, "motivo": "aberta"}
        self.telefone = telefone
        self.patch_status = patch_status
        self.pedidos = []

    def __call__(self, metodo, caminho, corpo=None):
        self.pedidos.append((metodo, caminho, corpo))
        oportunidade = caminho.split("/")[2]
        if metodo == "GET" and caminho.endswith("/acompanhamento"):
            if self.acompanhamento == "sem_api":
                return 404, {"detail": "Not Found"}
            return 200, {**self.acompanhamento, "oportunidade_id": oportunidade}
        if metodo == "GET":
            return 200, {"id": oportunidade, "lead_id": LEAD, "situacao": self.situacao,
                         "atendido_por": self.atendido_por, "telefone": self.telefone,
                         "email": "Lead@Exemplo.com.br", "site_id": SITE}
        if metodo == "PATCH":
            return self.patch_status, {}
        raise AssertionError(caminho)

    @property
    def contatos(self):
        return [corpo for metodo, _, corpo in self.pedidos if metodo == "PATCH"]


@pytest.fixture
def leads(monkeypatch):
    falso = CrmFalso()
    monkeypatch.setattr(crm, "_pedir", falso)
    return falso


def anota(saiu):
    def despachar(inscricao, passo, canal):
        saiu.append((inscricao.oportunidade_id, passo.ordem, canal))
        return True

    return despachar


def da_oportunidade(jornada, oportunidade=OPORTUNIDADE, momento=None):
    return motor.inscrever(
        jornada, destinatario_id=PESSOA, site_id=SITE, momento=momento or quando(16, 10),
        oportunidade_id=oportunidade, lead_id=LEAD,
    )


# ---------------------------------------------------------------------------
# Jornada de aluno não muda
# ---------------------------------------------------------------------------


def test_jornada_sem_oportunidade_nao_vai_ao_crm(monkeypatch):
    monkeypatch.setattr(crm, "_pedir", lambda *a, **k: pytest.fail("foi ao CRM"))
    jornada = uma_jornada()
    motor.inscrever(jornada, destinatario_id=PESSOA, site_id=SITE, momento=quando(16, 10))
    saiu = []
    motor.varrer(despachar=anota(saiu), momento=quando(16, 10))
    assert len(saiu) == 1


def test_a_mesma_pessoa_com_duas_oportunidades_tem_dois_relogios():
    jornada = uma_jornada()
    primeira = da_oportunidade(jornada)
    segunda = da_oportunidade(jornada, oportunidade=OUTRA)
    assert primeira.pk != segunda.pk
    assert (primeira.contexto_id, segunda.contexto_id) == (OPORTUNIDADE, OUTRA)
    assert primeira.lead_id == LEAD


# ---------------------------------------------------------------------------
# 1. Antes de cada acompanhamento
# ---------------------------------------------------------------------------


def test_compra_aprovada_nao_envia_e_encerra_a_jornada_da_oportunidade(leads):
    leads.acompanhamento = {"pode_insistir": False, "motivo": "compra_aprovada"}
    jornada = uma_jornada(atrasos=(0, 2))
    outra_jornada = uma_jornada(slug="recuperacao", atrasos=(1,))
    inscricao = da_oportunidade(jornada)
    irma = da_oportunidade(outra_jornada)
    de_outra_oferta = da_oportunidade(jornada, oportunidade=OUTRA)
    saiu = []

    passada = motor.varrer(
        despachar=anota(saiu), momento=quando(16, 10),
        conferir=lambda i, p, a: crm.conferir(i, p, a) if i.oportunidade_id == OPORTUNIDADE
        else crm.Conferencia(),
    )

    assert [s for s in saiu if s[0] == OPORTUNIDADE] == []
    assert passada.encerradas_pelo_crm == 1
    entrega = Entrega.objects.get(inscricao=inscricao)
    assert (entrega.resultado, entrega.motivo) == ("pulada", "CRM: compra aprovada")
    for linha in (inscricao, irma):
        linha.refresh_from_db()
        assert linha.estado == "cancelada"
        assert linha.motivo_de_saida == "CRM: compra aprovada"
    de_outra_oferta.refresh_from_db()
    assert de_outra_oferta.estado != "cancelada"  # a outra oferta segue a vida dela


def test_oportunidade_encerrada_encerra_mesmo_sem_a_api_de_compra(leads):
    leads.acompanhamento = "sem_api"
    leads.situacao = "encerrada"
    inscricao = da_oportunidade(uma_jornada(atrasos=(0, 2)))
    saiu = []
    motor.varrer(despachar=anota(saiu), momento=quando(16, 10))
    inscricao.refresh_from_db()
    assert saiu == [] and inscricao.estado == "cancelada"
    assert inscricao.motivo_de_saida == "CRM: oportunidade encerrada"


def test_pessoa_da_equipe_atendendo_segura_o_passo_e_registra_o_motivo(leads):
    leads.atendido_por = {"tipo": "pessoa", "nome": "Ana"}
    inscricao = da_oportunidade(uma_jornada(atrasos=(0, 2)))
    saiu = []
    motor.varrer(despachar=anota(saiu), momento=quando(16, 10))
    assert saiu == []
    entrega = Entrega.objects.get(inscricao=inscricao)
    assert entrega.resultado == "pulada"
    assert entrega.motivo == "CRM: uma pessoa da equipe atende esta oportunidade"
    inscricao.refresh_from_db()
    assert inscricao.estado == "andando" and inscricao.passo_atual == 1
    assert inscricao.ultima_conferencia.startswith("CRM: uma pessoa")


def test_agente_atendendo_nao_segura_a_jornada(leads):
    leads.atendido_por = {"tipo": "agente", "nome": "Assistente da equipe"}
    da_oportunidade(uma_jornada())
    saiu = []
    motor.varrer(despachar=anota(saiu), momento=quando(16, 10))
    assert len(saiu) == 1


def test_crm_fora_do_ar_nada_sai_e_o_passo_espera(monkeypatch):
    monkeypatch.delenv("LEADS_API_URL", raising=False)
    inscricao = da_oportunidade(uma_jornada())
    saiu = []
    passada = motor.varrer(despachar=anota(saiu), momento=quando(16, 10))
    assert saiu == [] and passada.esperando_crm == 1
    assert not Entrega.objects.exists()
    inscricao.refresh_from_db()
    assert inscricao.estado == "andando" and inscricao.passo_atual == 0
    assert inscricao.proximo_em == quando(16, 10) + crm.ESPERA_SEM_CRM
    assert "LEADS_API_URL" in inscricao.ultima_conferencia


def test_crm_respondendo_erro_tambem_espera(monkeypatch):
    monkeypatch.setattr(crm, "_pedir", lambda *a, **k: (502, None))
    da_oportunidade(uma_jornada())
    passada = motor.varrer(despachar=anota([]), momento=quando(16, 10))
    assert passada.esperando_crm == 1
    assert Inscricao.objects.get().ultima_conferencia == "CRM respondeu HTTP 502 para a oportunidade"


# ---------------------------------------------------------------------------
# 3. Preferências, janela e tetos continuam valendo
# ---------------------------------------------------------------------------


def test_preferencia_e_janela_continuam_com_a_regua(leads):
    Preferencia.objects.create(destinatario_id=PESSOA, site_id=SITE, canal="sino",
                               classe="relacional", aceita=False)
    da_oportunidade(uma_jornada())
    motor.varrer(despachar=anota([]), momento=quando(16, 10))
    assert Entrega.objects.get().resultado == "barrada_por_preferencia"


def test_fora_da_janela_de_horario_o_passo_e_reagendado(leads):
    inscricao = da_oportunidade(uma_jornada(), momento=quando(16, 22))
    saiu = []
    motor.varrer(despachar=anota(saiu), momento=quando(16, 22))
    assert saiu == []
    entrega = Entrega.objects.get()
    assert entrega.resultado == "barrada_pela_regua"
    inscricao.refresh_from_db()
    assert inscricao.proximo_em == entrega.reagendado_para


# ---------------------------------------------------------------------------
# 2. Cada envio vira último contato
# ---------------------------------------------------------------------------


def test_envio_atualiza_o_ultimo_contato_da_oportunidade(leads, django_capture_on_commit_callbacks):
    inscricao = da_oportunidade(uma_jornada())
    with django_capture_on_commit_callbacks(execute=True):
        motor.varrer(despachar=anota([]), momento=quando(16, 10))
    entrega = Entrega.objects.get(inscricao=inscricao)
    assert entrega.resultado == "enviada"
    [contato] = leads.contatos
    assert parse_datetime(contato["ultimo_contato_em"]) == quando(16, 10)
    assert contato["autor_id"] == "jornada:boas-vindas"
    assert "sino" in contato["nota"]
    assert ("PATCH", f"/crm/{OPORTUNIDADE}/acompanhamento", contato) in leads.pedidos
    entrega.refresh_from_db()
    assert entrega.crm_registrado_em is not None
    assert crm.registrar_pendentes(agora=quando(16, 11)) == 0  # uma vez só


def test_contato_que_o_crm_nao_recebeu_e_retomado(leads, django_capture_on_commit_callbacks):
    leads.patch_status = 503
    da_oportunidade(uma_jornada())
    with django_capture_on_commit_callbacks(execute=True):
        motor.varrer(despachar=anota([]), momento=quando(16, 10))
    assert Entrega.objects.get().crm_registrado_em is None
    leads.patch_status = 200
    assert crm.registrar_pendentes(agora=quando(16, 11)) == 1
    assert Entrega.objects.get().crm_registrado_em is not None


# ---------------------------------------------------------------------------
# WhatsApp: confere de novo no envio de verdade e usa o telefone do quiz
# ---------------------------------------------------------------------------


def _entrega_whatsapp(oportunidade=OPORTUNIDADE):
    jornada = uma_jornada(canais=("whatsapp",), publicar=False)
    passo = jornada.versoes.get().passos.get()
    TextoDoPasso.objects.create(passo=passo, idioma="pt-br", assunto_visivel="Passo",
                                corpo="Oi! Ficou alguma dúvida sobre o curso?")
    JornadaVersao.objects.filter(pk=passo.jornada_versao_id).update(publicada_em=quando(15))
    inscricao = da_oportunidade(jornada, oportunidade=oportunidade)
    return Entrega.objects.create(
        inscricao=inscricao, passo=passo, canal="whatsapp", resultado="pendente",
        whatsapp_intencao=True, previsto_para=quando(16),
    )


@pytest.fixture
def whatsapp(monkeypatch):
    from apps.whatsapp import service

    monkeypatch.setattr(despacho.regua, "avaliar", lambda **k: SimpleNamespace(barrada=False))
    monkeypatch.setattr(despacho, "_telefone_da_pessoa",
                        lambda **k: pytest.fail("lead usa o telefone do CRM"))
    monkeypatch.setattr(service, "consultar_mensagem", lambda **k: None)
    # A permissão do WhatsApp tem testes próprios (test_consentimentos*.py): aqui o aceite já existe.
    monkeypatch.setattr("apps.consentimentos.servico.permite_whatsapp_proativo", lambda *a, **k: True)
    enviadas = []

    def enviar(**kwargs):
        enviadas.append(kwargs)
        return SimpleNamespace(status="aceito", erro="", provider_id="wamid-1",
                               destinatario="5511988887777", corpo=kwargs["corpo"])

    monkeypatch.setattr(service, "enviar_mensagem", enviar)
    return enviadas


def test_whatsapp_da_oportunidade_sai_pelo_telefone_do_quiz(leads, whatsapp):
    entrega = _entrega_whatsapp()
    despacho.processar_entrega(inscricao_id=entrega.inscricao_id, passo_id=entrega.passo_id)
    assert [e["destinatario"] for e in whatsapp] == ["5511988887777"]
    entrega.refresh_from_db()
    assert entrega.resultado == "aceita_pelo_gateway"
    assert entrega.crm_registrado_em is not None
    assert len(leads.contatos) == 1 and "whatsapp" in leads.contatos[0]["nota"]


def test_compra_aprovada_entre_a_varredura_e_o_envio_nao_sai(leads, whatsapp):
    leads.acompanhamento = {"pode_insistir": False, "motivo": "compra_aprovada"}
    entrega = _entrega_whatsapp()
    despacho.processar_entrega(inscricao_id=entrega.inscricao_id, passo_id=entrega.passo_id)
    assert whatsapp == []
    entrega.refresh_from_db()
    assert (entrega.resultado, entrega.motivo) == ("pulada", "CRM: compra aprovada")
    assert Inscricao.objects.get().estado == "cancelada"


def test_crm_fora_do_ar_no_envio_deixa_a_intencao_pendente(monkeypatch, whatsapp):
    monkeypatch.delenv("LEADS_API_URL", raising=False)
    entrega = _entrega_whatsapp()
    despacho.processar_entrega(inscricao_id=entrega.inscricao_id, passo_id=entrega.passo_id)
    assert whatsapp == []
    entrega.refresh_from_db()
    assert entrega.resultado == "pendente" and "LEADS_API_URL" in entrega.motivo


def test_lead_sem_telefone_deixa_falha_visivel(leads, whatsapp):
    leads.telefone = ""
    entrega = _entrega_whatsapp()
    despacho.processar_entrega(inscricao_id=entrega.inscricao_id, passo_id=entrega.passo_id)
    assert whatsapp == []
    entrega.refresh_from_db()
    assert (entrega.resultado, entrega.motivo) == ("falhou", "lead sem telefone no CRM")


# ---------------------------------------------------------------------------
# Caixa de conversas (entra junto com o ramo crm-agentes/mensageria-conversas)
# ---------------------------------------------------------------------------

com_conversas = pytest.mark.skipif(
    not django_apps.is_installed("apps.conversas"),
    reason="caixa de conversas ainda não está nesta célula",
)


def _conversa(**campos):
    from apps.conversas.models import Conversa

    padrao = {"site_id": SITE, "canal": "whatsapp", "endereco": "5511988887777",
              "lead_id": LEAD, "ligacao": "ligada", "estado": "agente"}
    return Conversa.objects.create(**{**padrao, **campos})


@com_conversas
def test_conversa_assumida_por_pessoa_segura_o_passo(leads):
    _conversa(estado="pessoa", assumida_por="ana")
    da_oportunidade(uma_jornada())
    saiu = []
    motor.varrer(despachar=anota(saiu), momento=quando(16, 10))
    assert saiu == []
    assert Entrega.objects.get().motivo == "CRM: uma pessoa da equipe assumiu a conversa no whatsapp"


@com_conversas
def test_lead_que_respondeu_ha_pouco_segura_o_passo(leads):
    _conversa(ultima_entrada_em=quando(16, 8))
    da_oportunidade(uma_jornada())
    motor.varrer(despachar=anota([]), momento=quando(16, 10))
    assert Entrega.objects.get().motivo == "CRM: o lead respondeu há pouco no whatsapp"


@com_conversas
def test_assistente_respondendo_agora_segura_o_passo(leads):
    from apps.conversas.models import MensagemDaConversa

    conversa = _conversa(ultima_entrada_em=quando(14, 8))
    MensagemDaConversa.objects.create(conversa=conversa, direcao="saida", autor="agente",
                                      texto="...", estado_envio="enviado",
                                      ocorrida_em=quando(16, 9))
    da_oportunidade(uma_jornada())
    motor.varrer(despachar=anota([]), momento=quando(16, 10))
    assert Entrega.objects.get().motivo == "CRM: o assistente está conversando com o lead agora"


@com_conversas
def test_descadastro_barra_so_o_canal_pedido(leads):
    from apps.conversas.models import Descadastro

    Descadastro.objects.create(site_id=SITE, canal="whatsapp", endereco="5511988887777",
                               registrado_em=quando(15))
    inscricao = da_oportunidade(uma_jornada(canais=("sino", "whatsapp")))
    saiu = []
    motor.varrer(despachar=anota(saiu), momento=quando(16, 10))
    assert [canal for *_, canal in saiu] == ["sino"]
    barrada = Entrega.objects.get(inscricao=inscricao, canal="whatsapp")
    assert barrada.resultado == "barrada_por_preferencia"
    assert barrada.motivo == "o lead pediu para parar no whatsapp"


@com_conversas
def test_envio_do_whatsapp_aparece_na_conversa_do_lead(leads, whatsapp):
    from apps.conversas.models import Conversa

    entrega = _entrega_whatsapp()
    despacho.processar_entrega(inscricao_id=entrega.inscricao_id, passo_id=entrega.passo_id)
    conversa = Conversa.objects.get(site_id=SITE, canal="whatsapp")
    assert conversa.lead_id == LEAD
    [mensagem] = conversa.mensagens.all()
    assert (mensagem.direcao, mensagem.autor) == ("saida", "sistema")
    assert mensagem.texto == "Oi! Ficou alguma dúvida sobre o curso?"
    assert mensagem.chave_idempotencia == f"jornada:{entrega.inscricao_id}:{entrega.passo_id}"


def test_sem_caixa_de_conversas_o_registro_na_conversa_e_indisponivel(monkeypatch):
    monkeypatch.setattr(crm, "_caixa_de_conversas", lambda: None)
    entrega = _entrega_whatsapp()
    assert crm.registrar_na_conversa(entrega, telefone="+55 11 98888-7777", corpo="x",
                                     mensagem_whatsapp=None) is False


# ---------------------------------------------------------------------------
# Quem fala com o cliente: o robô comercial. A jornada só termina junto com a compra.
# ---------------------------------------------------------------------------


def test_nenhum_evento_do_sistema_inscreve_lead_com_oportunidade():
    """Inscrever com `oportunidade_id` é decisão do mantenedor, não de um evento:
    o robô comercial já aborda, acompanha e recupera, e a jornada em cima disso
    seria mensagem em dobro."""
    import inspect

    from apps.eventos import handlers

    fontes = [
        inspect.getsource(getattr(handlers, nome))
        for nome in dir(handlers)
        if nome.startswith("ao_") and callable(getattr(handlers, nome))
    ]
    assert fontes
    assert not any("oportunidade_id" in fonte for fonte in fontes)


def aviso_de_compra(oportunidade_ref=None, site=SITE):
    dados = {
        "site_id": site, "payment_id": "pay-op", "order_id": "ord-op", "amount_cents": 1000,
        "method": "pix", "customer": {"email": "cliente@example.com", "name": "Cliente"},
    }
    if oportunidade_ref:
        dados["oportunidade_ref"] = oportunidade_ref
    return dados


def test_pagamento_aprovado_encerra_na_hora_a_jornada_da_oportunidade(monkeypatch):
    from apps.eventos import handlers

    monkeypatch.setattr(handlers, "enviar_notificacao", lambda *a, **k: None)
    jornada = uma_jornada(atrasos=(0, 2))
    daquela = da_oportunidade(jornada)
    de_outra_oferta = da_oportunidade(jornada, oportunidade=OUTRA)
    de_aluno = motor.inscrever(uma_jornada(slug="aluno"), destinatario_id=PESSOA,
                               site_id=SITE, momento=quando(16, 10))

    handlers.ao_pagamento_aprovado(aviso_de_compra(OPORTUNIDADE))

    daquela.refresh_from_db()
    assert (daquela.estado, daquela.motivo_de_saida) == ("cancelada", "CRM: compra aprovada")
    assert daquela.proximo_em is None
    for outra in (de_outra_oferta, de_aluno):
        outra.refresh_from_db()
        assert outra.estado == "andando"


def test_pagamento_aprovado_de_outro_site_nao_encerra_a_jornada(monkeypatch):
    from apps.eventos import handlers

    monkeypatch.setattr(handlers, "enviar_notificacao", lambda *a, **k: None)
    daquela = da_oportunidade(uma_jornada(atrasos=(0, 2)))
    handlers.ao_pagamento_aprovado(aviso_de_compra(OPORTUNIDADE, site="outro-site"))
    daquela.refresh_from_db()
    assert daquela.estado == "andando"


def test_pagamento_aprovado_sem_oportunidade_nao_mexe_em_jornada(monkeypatch):
    from apps.eventos import handlers

    monkeypatch.setattr(handlers, "enviar_notificacao", lambda *a, **k: None)
    daquela = da_oportunidade(uma_jornada(atrasos=(0, 2)))
    handlers.ao_pagamento_aprovado(aviso_de_compra())
    daquela.refresh_from_db()
    assert daquela.estado == "andando"
