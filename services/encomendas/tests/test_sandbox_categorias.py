import importlib
from types import SimpleNamespace

import pytest
from django.apps import apps
from django.db import connection
from django.urls import reverse

from apps.encomendas import sandbox
from apps.encomendas.models import ProjetoSandbox, ParticipacaoSandbox
from apps.core import telas_sandbox, sessao

@pytest.mark.django_db
def test_cinco_categorias_onze_projetos_e_preservacao_de_trabalho_antigo():
    projetos = sandbox.semear_projetos(site_id='escola-a')
    assert len(projetos) == 11
    assert set(p.categoria for p in projetos) == {'espadas_objetos','pets','cabelos','chapeus','personagens'}
    projeto = projetos[0]
    projeto.prazo_dias=2; projeto.ajustes_previstos=1; projeto.recompensa=0; projeto.save()
    p = sandbox.aceitar(site_id='escola-a',pessoa_id='aluno-teste',projeto_id=projeto.pk)
    snapshot = dict(p.termos)
    ProjetoSandbox.objects.filter(pk=projeto.pk).update(slug='animacao-corrida',categoria='')
    migration=importlib.import_module('apps.encomendas.migrations.0014_categorias_sandbox')
    migration.organizar(apps,SimpleNamespace(connection=connection))
    projeto.refresh_from_db(); p.refresh_from_db()
    assert not projeto.ativo and p.termos == snapshot and p.status=='em_producao'
    assert ProjetoSandbox.objects.filter(site_id='escola-a',ativo=True).count()==11
    with pytest.raises(sandbox.ErroSandbox):
        sandbox.aceitar(site_id='escola-a',pessoa_id='outro',projeto_id=projeto.pk)

@pytest.mark.django_db
def test_catalogo_mostra_apenas_categoria_escolhida_e_nao_aceita_animacao(client,monkeypatch):
    sandbox.semear_projetos(site_id='escola-a')
    monkeypatch.setattr(sessao,'quem_e',lambda req:'aluno-teste')
    monkeypatch.setattr(sessao,'site_desta_instalacao',lambda:'escola-a')
    monkeypatch.setattr(telas_sandbox,'_aluno_atual',lambda req,pessoa,site:True)
    monkeypatch.setenv('IDS_DO_PLANTAO','equipe')
    resposta=client.get(reverse('sandbox_catalogo'),{'categoria':'chapeus'})
    assert resposta.status_code==200
    assert set(p.categoria for p in resposta.context['projetos'])=={'chapeus'}
    assert len(resposta.context['categorias'])==5
    assert 'Chapéus' in resposta.content.decode()
    assert 'Ciclo de corrida' not in resposta.content.decode()
    assert client.get(reverse('sandbox_catalogo'),{'categoria':'animacoes'}).status_code==404
