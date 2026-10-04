"""Permissão de contato pelo WhatsApp: aceite do quiz, recusa, descadastro e os bloqueios."""
import uuid
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.test import Client
from django.utils import timezone

from apps.consentimentos import handlers, servico
from apps.consentimentos.models import ConsentimentoWhatsapp
from apps.conversas.models import Conversa, Descadastro
from apps.eventos.management.commands import consume_eventos
from apps.jornadas import despacho
from apps.jornadas.models import Preferencia
from apps.whatsapp.models import ConfiguracaoWhatsApp
from test_conversas import (  # noqa: F401  (meio_dia fixa o relógio da régua do agente: 08h-20h)
    ESCRITA, LEITURA, SITE, _api, _conversa_ligada, _gateway_aberto, base, meio_dia,
)
from test_jornadas_whatsapp import _entrega, _liberar

pytestmark = pytest.mark.django_db(transaction=True)

TELEFONE = "11 98888-7777"
TEXTO = "Aceito receber mensagens da equipe pelo WhatsApp neste número."


def _evento(aceito=True, sessao="s1", telefone=TELEFONE, site=SITE, registrado_em=None, email="ana@exemplo.com"):
    return {
        "site_id": site,
        "quiz_slug": "objetivo",
        "sessao": sessao,
        "submissao_id": str(uuid.uuid4()),
        "lead": {"email": email, "name": "Ana", "phone": telefone},
        "consentimento": {"whatsapp": {
            "aceito": aceito, "texto": TEXTO, "versao_texto": "whatsapp-v1",
            "registrado_em": registrado_em if registrado_em is not None else (
                timezone.now().isoformat() if aceito else None),
        }},
    }


def test_consumidor_escuta_os_tres_eventos_do_quiz():
    for stream in ("eventos.quiz.completado", "eventos.quiz.captura_parcial", "eventos.quiz.consentimento"):
        assert stream in consume_eventos.STREAMS


def test_sem_registro_nao_ha_permissao():
    atual = servico.situacao(SITE, TELEFONE)
    assert atual.permite is False and atual.estado == "sem_autorizacao"


def test_aceite_do_quiz_autoriza_o_numero_com_e_sem_nono_digito():
    handlers.ao_quiz_completado(_evento(), str(uuid.uuid4()))
    assert servico.situacao(SITE, TELEFONE).permite
    assert servico.situacao(SITE, "+55 11 8888-7777").permite  # sem o nono dígito
    assert servico.situacao("outro-site", TELEFONE).permite is False
    linha = ConsentimentoWhatsapp.objects.get()
    assert linha.endereco == "5511988887777" and linha.texto == TEXTO and linha.origem == "quiz.completado"


def test_evento_sem_bloco_ou_sem_telefone_nao_registra():
    sem_bloco = _evento()
    del sem_bloco["consentimento"]
    handlers.ao_quiz_completado(sem_bloco, str(uuid.uuid4()))
    handlers.ao_quiz_completado(_evento(telefone=""), str(uuid.uuid4()))
    assert not ConsentimentoWhatsapp.objects.exists()


def test_mesmo_evento_duas_vezes_grava_uma_linha():
    evento_id = str(uuid.uuid4())
    handlers.ao_quiz_completado(_evento(), evento_id)
    handlers.ao_quiz_completado(_evento(), evento_id)
    assert ConsentimentoWhatsapp.objects.count() == 1


def test_desmarcar_na_mesma_sessao_retira_e_em_outro_quiz_nao():
    handlers.ao_quiz_captura_parcial(_evento(sessao="s1"), str(uuid.uuid4()))
    # Outro quiz, caixa em branco: não é pedido para parar.
    handlers.ao_quiz_completado(_evento(aceito=False, sessao="s2"), str(uuid.uuid4()))
    assert servico.situacao(SITE, TELEFONE).permite
    # Mesma sessão: a conclusão desmarcada é a escolha final.
    handlers.ao_quiz_completado(_evento(aceito=False, sessao="s1"), str(uuid.uuid4()))
    atual = servico.situacao(SITE, TELEFONE)
    assert atual.permite is False and atual.estado == "recusado"


def test_conclusao_desmarcada_vale_mesmo_se_a_captura_chega_depois():
    antes = (timezone.now() - timedelta(minutes=5)).isoformat()
    handlers.ao_quiz_completado(_evento(aceito=False, sessao="s9"), str(uuid.uuid4()))
    handlers.ao_quiz_captura_parcial(_evento(sessao="s9", registrado_em=antes), str(uuid.uuid4()))
    assert servico.situacao(SITE, TELEFONE).permite is False


def test_recusa_atrasada_no_consumidor_nao_vence_aceite_posterior_da_sessao():
    agora = timezone.now()
    hora = lambda minutos: (agora - timedelta(minutes=minutos)).isoformat()  # noqa: E731
    handlers.ao_quiz_captura_parcial(_evento(sessao="s5", registrado_em=hora(20)), str(uuid.uuid4()))
    # Desmarcou (T-10) e remarcou (T-5); o consumidor só processa agora.
    handlers.ao_quiz_consentimento(_evento(aceito=False, sessao="s5", registrado_em=hora(10)), str(uuid.uuid4()))
    handlers.ao_quiz_consentimento(_evento(sessao="s5", registrado_em=hora(5)), str(uuid.uuid4()))
    assert servico.situacao(SITE, TELEFONE).permite is True


def test_descadastro_depois_do_aceite_retira_e_novo_aceite_devolve():
    handlers.ao_quiz_completado(_evento(sessao="s1"), str(uuid.uuid4()))
    Descadastro.objects.create(site_id=SITE, canal="whatsapp", endereco="5511988887777",
                               registrado_em=timezone.now() + timedelta(seconds=1))
    atual = servico.situacao(SITE, TELEFONE)
    assert atual.permite is False and atual.estado == "descadastrado"
    depois = (timezone.now() + timedelta(minutes=1)).isoformat()
    handlers.ao_quiz_completado(_evento(sessao="s3", registrado_em=depois), str(uuid.uuid4()))
    assert servico.situacao(SITE, TELEFONE).permite


def test_aceite_vai_para_a_preferencia_das_jornadas(monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", "http://identidade.test")
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-teste")
    monkeypatch.setattr(
        "apps.conversas.descadastro.httpx.post",
        lambda url, **kw: SimpleNamespace(status_code=200, json=lambda: {"id": "pessoa-9"}),
    )
    handlers.ao_quiz_completado(_evento(), str(uuid.uuid4()))
    prefs = Preferencia.objects.filter(destinatario_id="pessoa-9", site_id=SITE, canal="whatsapp")
    assert {p.classe: p.aceita for p in prefs} == {"relacional": True, "engajamento": True}
    assert ConsentimentoWhatsapp.objects.get().pessoa_id == "pessoa-9"


def test_api_consulta_mascarada_e_equipe_registra(base):  # noqa: F811
    cliente = Client()
    url = f"/consentimentos/whatsapp?site_id={SITE}&telefone=5511988887777"
    antes = _api(cliente, "GET", url, token=LEITURA).json()
    assert antes["permite_proativo"] is False and antes["estado"] == "sem_autorizacao"
    assert "988887777" not in antes["telefone_mascarado"]
    corpo = {"site_id": SITE, "telefone": TELEFONE, "aceito": True, "texto": "Pediu por telefone"}
    assert _api(cliente, "POST", "/consentimentos/whatsapp", corpo, token=LEITURA).status_code == 403
    depois = _api(cliente, "POST", "/consentimentos/whatsapp", corpo).json()
    assert depois["permite_proativo"] is True and depois["origem"] == "equipe"
    corpo["aceito"] = False
    assert _api(cliente, "POST", "/consentimentos/whatsapp", corpo).json()["estado"] == "recusado"
    assert _api(cliente, "GET", url, token=None).status_code == 401
    assert _api(cliente, "GET", f"/consentimentos/whatsapp?site_id={SITE}&telefone=abc",
                token=LEITURA).status_code == 422


def test_fora_da_janela_sem_aceite_nao_sai_nem_com_modelo(base, monkeypatch):  # noqa: F811
    conversa = _conversa_ligada(base)
    Conversa.objects.filter(pk=conversa.pk).update(janela_aberta_ate=timezone.now() - timedelta(minutes=1))
    ConfiguracaoWhatsApp.objects.filter(pk=base["config"].pk).update(transporte="WHATSAPP-BUSINESS")
    posts = []
    _gateway_aberto(monkeypatch, posts)
    cliente = Client()
    pedido = {"site_id": SITE, "chave_idempotencia": "m1", "modelo": {"nome": "retomada", "idioma": "pt_BR"}}
    sem = _api(cliente, "POST", f"/conversas/{conversa.id}/mensagens", pedido).json()
    assert sem["resultado"] == "sem_consentimento" and not posts
    assert "não autorizou" in sem["detalhe"]
    handlers.ao_quiz_completado(_evento(telefone="5511988887777"), str(uuid.uuid4()))
    com = _api(cliente, "POST", f"/conversas/{conversa.id}/mensagens", pedido).json()
    assert com["resultado"] == "enviada" and len(posts) == 1


def test_dentro_da_janela_responde_sem_aceite(base, monkeypatch):  # noqa: F811
    conversa = _conversa_ligada(base)
    posts = []
    _gateway_aberto(monkeypatch, posts)
    pedido = {"site_id": SITE, "texto": "Olá! Sou o assistente da equipe.", "chave_idempotencia": "r1"}
    resposta = _api(Client(), "POST", f"/conversas/{conversa.id}/mensagens", pedido).json()
    assert resposta["resultado"] == "enviada"


def _jornada_pronta(monkeypatch):
    entrega = _entrega()  # classe relacional
    _liberar(monkeypatch)
    monkeypatch.setattr(despacho, "_telefone_da_pessoa",
                        lambda **kwargs: ("+55 11 90000-0001", "pt-br", ""))
    from apps.whatsapp import service

    enviadas = []
    monkeypatch.setattr(service, "consultar_mensagem", lambda **kwargs: None)
    monkeypatch.setattr(service, "enviar_mensagem",
                        lambda **kwargs: enviadas.append(kwargs) or SimpleNamespace(status="enviado", erro=""))
    return entrega, enviadas


def test_jornada_relacional_pelo_whatsapp_sem_aceite_fica_barrada(monkeypatch):
    entrega, enviadas = _jornada_pronta(monkeypatch)
    despacho.processar_entrega(inscricao_id=entrega.inscricao_id, passo_id=entrega.passo_id)
    entrega.refresh_from_db()
    assert entrega.resultado == "barrada_por_preferencia" and not enviadas
    assert "nao autorizou" in entrega.motivo


def test_jornada_relacional_com_aceite_sai(monkeypatch):
    entrega, enviadas = _jornada_pronta(monkeypatch)
    servico.registrar(site_id=entrega.inscricao.site_id, telefone="+55 11 90000-0001",
                      aceito=True, origem="quiz.completado")
    despacho.processar_entrega(inscricao_id=entrega.inscricao_id, passo_id=entrega.passo_id)
    entrega.refresh_from_db()
    assert entrega.resultado == "enviada" and len(enviadas) == 1


def test_envio_de_modelo_aprovado_consulta_a_permissao():
    from apps.whatsapp.descadastro import esta_descadastrado

    assert esta_descadastrado(site_id=SITE, telefone="5511988887777") is True
    servico.registrar(site_id=SITE, telefone=TELEFONE, aceito=True, origem="equipe")
    assert esta_descadastrado(site_id=SITE, telefone="5511988887777") is False
