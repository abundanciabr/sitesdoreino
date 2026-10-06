from decimal import Decimal

import pytest
from django.urls import reverse

from apps.core import sessao, telas_sandbox
from apps.encomendas import sandbox
from apps.encomendas.models import ParticipacaoSandbox


@pytest.mark.django_db
def test_guia_aceita_projeto_configurado_e_preserva_um_ativo(client, monkeypatch):
    site = 'escola-guia'
    projeto = sandbox.semear_projetos(site_id=site)[0]
    projeto.prazo_dias = 2
    projeto.ajustes_previstos = 1
    projeto.recompensa = Decimal('0.00')
    projeto.save()
    monkeypatch.setattr(sessao, 'quem_e', lambda request: 'aluno-guia')
    monkeypatch.setattr(sessao, 'site_desta_instalacao', lambda: site)
    monkeypatch.setattr(telas_sandbox, '_aluno_atual', lambda *args: True)
    monkeypatch.setenv('IDS_DO_PLANTAO', 'equipe')
    pagina = client.get(reverse('sandbox_catalogo'))
    assert pagina.status_code == 200
    html = pagina.content.decode()
    assert '1. Escolha o que quer criar' in html
    assert '2. Escolha seu projeto' in html
    assert 'Aceitar e começar' in html
    assert 'type="checkbox"' not in html
    aceitar = reverse('sandbox_aceitar', args=[projeto.pk])
    assert aceitar in html
    resposta = client.post(aceitar, {'aceito_termos': 'sim'})
    assert resposta.status_code == 302
    trabalho = ParticipacaoSandbox.objects.get(site_id=site, pessoa_id='aluno-guia')
    assert reverse('sandbox_trabalho', args=[trabalho.pk]) in resposta.url
    assert trabalho.termos['recompensa'] == '0.00'
    assert client.post(aceitar, {'aceito_termos': 'sim'}).status_code == 400
    pagina = client.get(reverse('sandbox_catalogo'))
    assert 'Continuar meu trabalho' in pagina.content.decode()
    assert 'class="start-button">Aceitar' not in pagina.content.decode()
    assert ParticipacaoSandbox.objects.filter(site_id=site, pessoa_id='aluno-guia').count() == 1
