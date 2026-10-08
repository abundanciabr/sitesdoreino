import pytest
from django.test import Client
from django.urls import resolve, Resolver404
from apps.gamificacao.models import ConquistaDefinicao, Concessao, Pessoa, PerfilJogador, HistoricoDaConcessao
from apps.gamificacao.criterios import avaliar, medalhas_da_pessoa
from apps.gamificacao.interruptores import listar_conquistas, mudar_conquista, ConquistaDesconhecida
from apps.gamificacao.validacao import conceder, ValidacaoRecusada, reconhecimentos_da_escola
from apps.core.api import _conquistas_por_pessoa, _celebracoes
from apps.gamificacao.handlers import ao_portfolio_conferido

pytestmark=pytest.mark.django_db

@pytest.mark.parametrize("path", ["marcos", "marcos/enviar", "forja", "forja/registrar", "contribuicoes", "contribuicoes/gesto", "interno", "interno/decidir", "interno/contribuicoes", "interno/contribuicoes/gesto"])
def test_rotas_retiradas(path):
    with pytest.raises(Resolver404): resolve('/'+path)

def test_telas_restantes_sem_recursos_antigos(monkeypatch):
    monkeypatch.setattr('apps.core.views.quem_e', lambda request: 'aluno')
    monkeypatch.setattr('apps.core.views.site_atual', lambda: 'escola')
    for url in ['/', '/medalhas']:
        response=Client().get(url)
        assert response.status_code == 200
        html=response.content.decode()
        for antigo in ['Marcos reais', 'Forja', 'Contribuições', '/contribuicoes', '/marcos', '/forja']:
            assert antigo not in html

@pytest.mark.parametrize('slug,classe,criterio', [
    ('marco-antigo', 'marco', {'tipo':'manual'}),
    ('dez-forjas', 'medalha', {'tipo':'forjas_seladas', 'alvo':10}),
    ('primeira-contribuicao', 'medalha', {'tipo':'contribuicoes_aceitas','alvo':1}),
    ('outra-forja', 'medalha', {'tipo':'forjas_seladas','alvo':1}),
])
def test_nao_aparece_nao_concede_nao_religa_preserva_historico(slug,classe,criterio):
    pessoa=Pessoa.objects.create(id_da_plataforma='aluno',email='teste@example.invalid')
    perfil=PerfilJogador.objects.create(pessoa=pessoa,site_id='escola',xp_total=200,cristais_saldo=15)
    antiga=ConquistaDefinicao.objects.create(site_id='escola',slug=slug,nome='Antiga',classe=classe,familia='carreira' if classe=='marco' else 'oficio',criterio=criterio,ativa=True)
    concessao=Concessao.objects.create(pessoa=pessoa,conquista=antiga,site_id='escola')
    assert listar_conquistas('escola') == []
    assert medalhas_da_pessoa(perfil) == []
    assert list(reconhecimentos_da_escola('escola')) == []
    assert _conquistas_por_pessoa('escola',['aluno']) == {}
    assert avaliar('aluno','escola') == []
    with pytest.raises(ConquistaDesconhecida): mudar_conquista(site_id='escola',slug=slug,ativa=True)
    with pytest.raises(ValidacaoRecusada): conceder(pessoa=pessoa,site_id='escola',conquista=antiga)
    assert Concessao.objects.filter(pk=concessao.pk).exists()
    perfil.refresh_from_db()
    assert (perfil.xp_total,perfil.cristais_saldo) == (200,15)

def test_evento_portfolio_nao_cria_pessoa_nem_conquista():
    ao_portfolio_conferido({'ator_id':'professor','event_id':'evento','data':{'site_id':'escola','aluno_id':'aluno'}})
    assert Pessoa.objects.count() == 0
    assert Concessao.objects.count() == 0

def test_medalha_restante_sem_tipo_no_criterio_continua_visivel():
    pessoa=Pessoa.objects.create(id_da_plataforma='aluno',email='teste@example.invalid')
    medalha=ConquistaDefinicao.objects.create(site_id='escola',slug='mao-amiga',nome='Mão amiga',classe='medalha',familia='comunidade',criterio={},ativa=True)
    conceder(pessoa=pessoa,site_id='escola',conquista=medalha)
    assert [c.slug for c in listar_conquistas('escola')] == ['mao-amiga']
    assert [c.slug for c in _conquistas_por_pessoa('escola',['aluno'])['aluno']] == ['mao-amiga']

def test_celebracoes_preservadas_mas_antigas_ocultas():
    perfil=PerfilJogador(celebracoes_pendentes=[{'tipo':'marco-validado','referencia':'primeiro-cliente'}, {'tipo':'conquista-concedida','referencia':'dez-forjas'}, {'tipo':'nivel-alcancado','referencia':'3'}])
    result=_celebracoes(perfil)
    assert [r.referencia for r in result] == ['3']
    assert len(perfil.celebracoes_pendentes) == 3

def test_migracao_desliga_definicoes_sem_apagar_registros():
    import importlib
    from types import SimpleNamespace
    from django.apps import apps
    from django.db import connection
    from apps.gamificacao.models import Forja, ItemCosmetico
    pessoa=Pessoa.objects.create(id_da_plataforma='aluno',email='teste@example.invalid')
    perfil=PerfilJogador.objects.create(pessoa=pessoa,site_id='escola',xp_total=200,cristais_saldo=15)
    antiga=ConquistaDefinicao.objects.create(site_id='escola',slug='primeiro-cliente',nome='Antiga',classe='marco',familia='carreira',criterio={'tipo':'manual'},ativa=True)
    Concessao.objects.create(pessoa=pessoa,conquista=antiga,site_id='escola')
    Forja.objects.create(pessoa=pessoa,site_id='escola',desafio_ref='item',medidor=2)
    ItemCosmetico.objects.create(site_id='escola',slug='titulo-forjador',nome='Forjador',tipo='titulo',ativa=True)
    migration=importlib.import_module('apps.gamificacao.migrations.0011_desativar_marcos_forja_contribuicoes')
    migration.desativar(apps,SimpleNamespace(connection=connection))
    antiga.refresh_from_db();perfil.refresh_from_db()
    assert not antiga.ativa
    assert not ItemCosmetico.objects.get(slug='titulo-forjador').ativa
    assert Concessao.objects.count() == 1
    assert Forja.objects.get().medidor == 2
    assert (perfil.xp_total,perfil.cristais_saldo) == (200,15)
