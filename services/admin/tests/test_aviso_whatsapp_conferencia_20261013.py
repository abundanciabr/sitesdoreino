"""Conferência dos avisos por chamado, sem enviar mensagens a pessoas reais."""
import json
import uuid

import pytest
from django.test import Client

from apps.atendimento import service, views
from apps.atendimento.models import Assunto, Aviso, Conversa, Responsavel

SID = 'conferencia-avisos-20261013'


@pytest.fixture
def canal(monkeypatch):
    service.config(SID)
    monkeypatch.setattr(views.CatalogoClient, 'site_por_host', lambda *a: {'id': SID})
    monkeypatch.setattr(views.IdentidadeClient, 'sessao_completa', lambda *a: {
        'autenticado': True, 'id': 'pessoa-ficticia-conferencia', 'nome_exibido': 'Teste técnico'})
    monkeypatch.setattr(service, 'orcamento', lambda *a: None)
    responsaveis = [Responsavel.objects.create(site_id=SID, nome='Responsável fictício ' + str(i),
        telefone='550000000000' + str(i)) for i in (1, 2)]
    chamadas = []
    confirmacoes = []
    def pedir(site_id, acao='', payload=None):
        assert site_id == SID
        if not acao:
            return {'mensagens': confirmacoes}, ''
        chamadas.append(payload.copy())
        return {'status': 'enviado'}, ''
    monkeypatch.setattr(service, 'pedir_whatsapp', pedir)
    return responsaveis, chamadas, confirmacoes


def novo_chamado():
    r = Client().post('/interno/atendimento-aluno/', json.dumps({
        'acao': 'mensagem', 'texto': 'O site apresentou um erro.',
        'referencia': uuid.uuid4().hex, 'conversa': str(uuid.uuid4())}),
        content_type='application/json')
    assert r.status_code == 200
    return Conversa.objects.get(pk=r.json()['conversa']['id'])


def test_novo_chamado_avisa_os_dois_sem_duplicar_ao_repetir_varredura(canal):
    responsaveis, chamadas, _ = canal
    conversa = novo_chamado()
    service.manutencao_avisos()
    service.manutencao_avisos()
    assert {p['destinatario'] for p in chamadas} == {r.telefone for r in responsaveis}
    assert len(chamadas) == 2
    assert Aviso.objects.filter(conversa=conversa).count() == 2


def test_reabertura_gera_novo_aviso_para_os_dois(canal):
    _, chamadas, _ = canal
    conversa = novo_chamado()
    service.manutencao_avisos()
    conversa.estado = 'encerrado'
    conversa.save()
    r = Client().post('/interno/atendimento-aluno/', json.dumps({
        'texto': 'Ainda preciso de ajuda com o erro.', 'conversa': str(conversa.pk),
        'referencia': uuid.uuid4().hex}), content_type='application/json')
    assert r.status_code == 200
    service.manutencao_avisos()
    assert len(chamadas) == 4 and len({p['referencia'] for p in chamadas}) == 4


def test_responsavel_inativo_e_outro_site_nao_recebem(canal):
    responsaveis, chamadas, _ = canal
    responsaveis[1].ativo = False
    responsaveis[1].save()
    Responsavel.objects.create(site_id='outro-site', nome='Outro', telefone='5500000000009')
    novo_chamado()
    service.manutencao_avisos()
    assert [p['destinatario'] for p in chamadas] == [responsaveis[0].telefone]


def test_confirmacoes_atualizam_entregue_e_lido_sem_reenviar(canal):
    _, chamadas, confirmacoes = canal
    novo_chamado()
    service.manutencao_avisos()
    confirmacoes.extend({'referencia': p['referencia'], 'status': estado}
        for p, estado in zip(chamadas, ('entregue', 'lido')))
    service.manutencao_avisos()
    assert len(chamadas) == 2
    assert set(Aviso.objects.values_list('estado', flat=True)) == {'entregue', 'lido'}


def test_falha_confirmada_tenta_de_novo_com_mesma_referencia(canal):
    _, chamadas, _ = canal
    conversa = novo_chamado()
    service.manutencao_avisos()
    Aviso.objects.filter(conversa=conversa).update(estado='falhou')
    service.manutencao_avisos()
    assert len(chamadas) == 4
    assert [p['referencia'] for p in chamadas[:2]] == [p['referencia'] for p in chamadas[2:]]


def test_resultado_desconhecido_consulta_sem_duplicar(canal):
    _, chamadas, _ = canal
    conversa = novo_chamado()
    service.manutencao_avisos()
    Aviso.objects.filter(conversa=conversa).update(estado='desconhecido')
    service.manutencao_avisos()
    assert len(chamadas) == 2


def test_todos_os_101_chamados_recebem_aviso_apos_duas_varreduras(canal):
    responsaveis, chamadas, _ = canal
    assunto = Assunto.objects.get(site_id=SID, nome='Site')
    Conversa.objects.bulk_create([Conversa(site_id=SID, pessoa_id='ficticio-' + str(i),
        assunto=assunto, encaminhada=True, estado='aguardando') for i in range(101)])
    service.manutencao_avisos()
    service.manutencao_avisos()
    assert Aviso.objects.values('conversa_id').distinct().count() == 101
    assert len(chamadas) == 101 * len(responsaveis)
