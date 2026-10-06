from datetime import timedelta

import pytest
from django.urls import reverse

from apps.core import sessao, telas_sandbox
from apps.core.templatetags.sandbox_moeda import mesh
from apps.encomendas import sandbox
from apps.encomendas.models import ParticipacaoSandbox


@pytest.mark.django_db
@pytest.mark.parametrize('horas', [24, 48, 72])
def test_confirmacao_nao_inicia_antes_do_aceite_e_registra_prazo(client, monkeypatch, horas):
    site = 'escola-confirmacao'
    projeto = sandbox.semear_projetos(site_id=site)[0]
    monkeypatch.setattr(sessao, 'quem_e', lambda request: 'aluno-confirmacao')
    monkeypatch.setattr(sessao, 'site_desta_instalacao', lambda: site)
    monkeypatch.setattr(telas_sandbox, '_aluno_atual', lambda *args: True)
    monkeypatch.setenv('IDS_DO_PLANTAO', 'equipe')
    confirmacao = client.get(reverse('sandbox_confirmar', args=[projeto.pk]))
    assert confirmacao.status_code == 200
    html = confirmacao.content.decode()
    assert 'sem qualquer pagamento ou envolvimento financeiro' in html
    assert 'Ⓜ$10.000,00 MESH' in html
    assert 'type="checkbox" name="aceito_termos" value="sim" required' in html
    assert not ParticipacaoSandbox.objects.filter(site_id=site).exists()
    aceitar = reverse('sandbox_aceitar', args=[projeto.pk])
    assert client.post(aceitar, {'prazo_horas': horas}).status_code == 400
    assert client.post(aceitar, {'prazo_horas': 96, 'aceito_termos': 'sim'}).status_code == 400
    assert not ParticipacaoSandbox.objects.filter(site_id=site).exists()
    resposta = client.post(aceitar, {'prazo_horas': horas, 'aceito_termos': 'sim'})
    assert resposta.status_code == 302
    trabalho = ParticipacaoSandbox.objects.get(site_id=site)
    assert trabalho.prazo_ate - trabalho.aceite_em == timedelta(hours=horas)
    assert trabalho.termos['prazo_horas'] == horas
    assert trabalho.termos['sem_pagamento'] is True
    assert trabalho.termos['termos_simulacao'] == sandbox.TERMOS_SIMULACAO
    assert trabalho.termos['recompensa'] == '10000.00'
    tela = client.get(reverse('sandbox_trabalho', args=[trabalho.pk]))
    assert tela.status_code == 200
    assert 'id="tempo-restante"' in tela.content.decode()
    assert 'Confirmar entrega' in tela.content.decode()


def test_formato_experiencia_mesh():
    assert mesh('10000.00') == 'Ⓜ$10.000,00 MESH'
    assert mesh('0') == 'Ⓜ$0,00 MESH'
