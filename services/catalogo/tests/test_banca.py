from unittest.mock import patch
import pytest
from apps.paginas.models import Page, PageDraft, BancaRegistro, Experimento, Variante
from apps.paginas.banca import fotografia, conferir_experimento
from apps.sites.models import Site
from ninja.errors import HttpError


@pytest.fixture
def pagina(db):
    site = Site.objects.create(host='banca.exemplo', name='Banca', active=True)
    page = Page.objects.create(site=site, slug='oferta')
    PageDraft.objects.create(page=page, secoes=[{'nome': 'cubo', 'ordem': 0, 'slots': {'headline': 'Texto A'}}])
    page.publicar()
    return page


@pytest.fixture
def exp(pagina):
    exp = Experimento.objects.create(page=pagina, secao='cubo', slot='headline', hipotese='Texto B',
        metrica_principal='checkout_iniciado', taxa_base=.1, mde=.02, n_por_braco_planejado=100, dias_planejados=14)
    Variante.objects.create(experimento=exp, variante_id='a', peso=5000, valor='Texto A')
    Variante.objects.create(experimento=exp, variante_id='b', peso=5000, valor='Texto B')
    return exp


def test_fotografia_muda_com_rascunho_sem_mudar_publicada(pagina):
    publicada = fotografia(pagina)
    draft = pagina.rascunho
    draft.secoes[0]['slots']['headline'] = 'Outra edição'
    draft.save()
    assert fotografia(pagina)['assinatura'] == publicada['assinatura']
    assert fotografia(pagina, 'rascunho')['assinatura'] != publicada['assinatura']


def test_banca_exige_ambos_os_bracos_e_nao_nota(exp):
    BancaRegistro.objects.create(site=exp.page.site, rodada='config')
    with pytest.raises(HttpError, match='variante a'):
        conferir_experimento(exp)
    for codigo in ['a', 'b']:
        foto = fotografia(exp.page, 'variante', str(exp.pk), codigo)
        BancaRegistro.objects.create(site=exp.page.site, page=exp.page, rodada=codigo,
                                    assinatura=foto['assinatura'], completa=True)
    conferir_experimento(exp)
    variante = exp.variantes.get(variante_id='b')
    variante.valor = 'Outro B'
    variante.save()
    with pytest.raises(HttpError, match='variante b'):
        conferir_experimento(exp)


def test_controle_usa_texto_publicado_atual(exp):
    antes = fotografia(exp.page, 'variante', str(exp.pk), 'a')['assinatura']
    draft = exp.page.rascunho
    draft.secoes[0]['slots']['headline'] = 'Novo controle'
    draft.save()
    exp.page.publicar()
    assert fotografia(exp.page, 'variante', str(exp.pk), 'a')['assinatura'] != antes


def test_apenas_admin_pode_emitir_comprovante(client, pagina, settings, monkeypatch):
    settings.TOKENS_ACEITOS = {'admin-teste', 'funil-teste'}
    monkeypatch.setenv('TOKENS_ACEITOS_ADMIN', 'admin-teste')
    url = f'/api/catalogo/sites/{pagina.site_id}/paginas/{pagina.slug}/banca'
    foto = fotografia(pagina)
    corpo = {'rodada': 'r1', 'assinatura': foto['assinatura'], 'perfis_digest': 'perfis',
             'corpus_digest': 'corpus', 'leituras': 6, 'sintese': True}
    assert client.post(url, corpo, content_type='application/json', HTTP_AUTHORIZATION='Bearer funil-teste').status_code == 403
    assert client.post(url, corpo, content_type='application/json', HTTP_AUTHORIZATION='Bearer admin-teste').status_code == 200
    corpo['rodada'] = 'r2'
    corpo['assinatura'] = 'desatualizada'
    assert client.post(url, corpo, content_type='application/json', HTTP_AUTHORIZATION='Bearer admin-teste').status_code == 409


def test_banca_fechada_para_experimento_na_api(client, exp, settings):
    settings.TOKENS_ACEITOS = {'teste'}
    BancaRegistro.objects.create(site=exp.page.site, rodada='config')
    url = f'/api/catalogo/sites/{exp.page.site_id}/paginas/oferta/experimentos/{exp.pk}/estado'
    resposta = client.post(url, {'estado': 'ativo'}, content_type='application/json', HTTP_AUTHORIZATION='Bearer teste')
    assert resposta.status_code == 409
    exp.refresh_from_db()
    assert exp.estado == 'rascunho'
