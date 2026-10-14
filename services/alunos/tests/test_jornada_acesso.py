import uuid
from types import SimpleNamespace
import pytest
from django.utils import timezone
from datetime import timedelta
from ninja.errors import HttpError
from apps.matriculas.models import Matricula, OutboxEvent
from apps.matriculas.services import entrar_na_fila, decidir_na_fila, situacao_de
from apps.matriculas.avisos_acesso import token_de_acesso
from apps.core.jornada_acesso import consumir, Consumir

pytestmark=pytest.mark.django_db

def pedido():
    return entrar_na_fila(site_id="meshcraft", email="aluno@example.test", nome_completo="Aluno",whatsapp="11987654321")[0]

def decidir(linha,decisao="liberar",**extra):
    return decidir_na_fila(id_da_linha=str(linha.pk),decisao=decisao,decidido_por="equipe",motivo="Explicação do suporte",product_id="curso",**extra)[0]

def test_recibo_sem_optin_e_sem_reenvio_historico():
    linha=pedido();pedido()
    assert linha.recibo_event_id
    assert OutboxEvent.objects.filter(event="escola.pedido-recebido").count()==1

def test_link_sem_expiracao_uso_unico_e_sem_alterar_matricula(monkeypatch):
    linha=decidir(pedido())
    Matricula.objects.filter(pk=linha.pk).update(decidido_em=timezone.now()-timedelta(days=2000))
    token=token_de_acesso(linha)
    monkeypatch.setenv("TOKENS_ACEITOS_IDENTIDADE","par-identidade")
    req=SimpleNamespace(auth="par-identidade")
    assert consumir(req,Consumir(token=token))["email"]==linha.email
    with pytest.raises(HttpError): consumir(req,Consumir(token=token))
    linha.refresh_from_db();assert linha.status=="ativa"

def test_link_revogado_status_outro_par_e_alteracao_de_contato(monkeypatch):
    linha=decidir(pedido());token=token_de_acesso(linha)
    monkeypatch.setenv("TOKENS_ACEITOS_IDENTIDADE","par-identidade")
    with pytest.raises(HttpError): consumir(SimpleNamespace(auth="outro"),Consumir(token=token[:-1]+("a" if token[-1]!="a" else "b")))
    Matricula.objects.filter(pk=linha.pk).update(email="outro@example.test")
    with pytest.raises(HttpError): consumir(SimpleNamespace(auth="par-identidade"),Consumir(token=token))
    Matricula.objects.filter(pk=linha.pk).update(email=linha.email,status="suspensa")
    with pytest.raises(HttpError): consumir(SimpleNamespace(auth="par-identidade"),Consumir(token=token))

@pytest.mark.parametrize("final",["liberar","recusar"])
def test_recusa_inicial_encaminha_uma_vez_suporte_resolve_idempotente(final):
    linha=decidir(pedido(),"recusar")
    assert linha.suporte_event_id and not linha.suporte_resolvido_em
    assert situacao_de(linha.email)["na_fila"]["estado"]=="aguardando"
    assert pedido().status=="recusada"
    decidir_na_fila(id_da_linha=str(linha.pk),decisao="recusar",decidido_por="equipe")
    assert OutboxEvent.objects.filter(event="escola.suporte-solicitado").count()==1
    resolvida=decidir(linha,final,pelo_suporte=True)
    assert resolvida.suporte_resolvido_em
    decidir(resolvida,final,pelo_suporte=True)
    assert OutboxEvent.objects.filter(event="escola.suporte-resolvido").count()==1
    assert bool(token_de_acesso(resolvida))==(final=="liberar")
