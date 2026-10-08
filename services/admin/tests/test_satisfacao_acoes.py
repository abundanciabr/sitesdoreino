import json
from copy import deepcopy
from urllib.parse import parse_qs, urlsplit

import httpx
import respx
from django.test import Client
from django.urls import reverse
from tests.test_crm_satisfacao import entrar, ambiente, QUIZ
from tests.test_satisfacao_painel import fontes, avaliacao


@respx.mock
def test_botao_de_excluir_abre_confirmacao_da_avaliacao_sem_apagar():
    fontes()
    cliente = entrar()
    dados = {"site_id":"escola", "aluno_id":"aluno-1", "avaliacao":"pesquisa-1"}
    painel = cliente.get(reverse('crm_satisfacao'), dados)
    assert 'Arquivar avaliação' in painel.content.decode() and 'Excluir definitivamente' in painel.content.decode()
    pagina = cliente.get(reverse('crm_satisfacao_confirmar_exclusao'), dados)
    assert pagina.status_code == 200
    for texto in ('Aluno da prova', 'Modelagem 3D', '10/10', 'respostas e as revisões', 'name="confirmacao"', 'Cancelar'):
        assert texto in pagina.content.decode()
    assert all(call.request.method == 'GET' for call in respx.calls)
    invalida = cliente.get(reverse('crm_satisfacao_confirmar_exclusao'), {**dados, "avaliacao":"outra-pesquisa"})
    assert invalida.status_code == 404


@respx.mock
def test_post_arquivo_e_exclusao_carregam_avaliacao_certa_e_confirmacao():
    cliente = entrar()
    rota = respx.post(QUIZ+'/interno/nps/acoes').mock(return_value=httpx.Response(200,json={"acao":"ok"}))
    dados = {"site_id":"escola", "aluno_id":"aluno-1", "avaliacao":"pesquisa-1"}
    for acao in ('arquivar', 'restaurar'):
        pagina = cliente.post(reverse('crm_satisfacao_arquivo'), {**dados,"acao":acao})
        assert pagina.status_code == 302
        enviada = json.loads(rota.calls.last.request.content)
        assert enviada['site_id'] == 'escola' and enviada['tentativa_id'] == 'pesquisa-1' and enviada['acao'] == acao
    chamadas = len(rota.calls)
    assert cliente.post(reverse('crm_satisfacao_apagar'), dados).status_code == 400
    assert len(rota.calls) == chamadas
    pagina = cliente.post(reverse('crm_satisfacao_apagar'), {**dados,"confirmacao":"excluir"})
    assert pagina.status_code == 302
    assert json.loads(rota.calls.last.request.content)['confirmacao'] == 'excluir'
    assert parse_qs(urlsplit(pagina.url).query)['acao'] == ['excluir']


@respx.mock
def test_arquivadas_permite_restaurar_e_preserva_filtro_nos_links():
    item = deepcopy(avaliacao())
    item['arquivada_em'] = '2026-10-08T15:00:00Z'
    lista, historico = fontes(item)
    pagina = entrar().get(reverse('crm_satisfacao'), {"site_id":"escola", "arquivadas":"1"})
    assert 'Restaurar avaliação' in pagina.content.decode()
    assert 'Esta avaliação está arquivada.' in pagina.content.decode()
    assert lista.calls.last.request.url.params['arquivadas'] == '1'
    assert parse_qs(urlsplit(pagina.context['itens'][0]['url']).query)['arquivadas'] == ['1']


@respx.mock
def test_acoes_exigem_admin_csrf_post_e_falha_nao_mostra_sucesso():
    for nome in ('crm_satisfacao_arquivo','crm_satisfacao_confirmar_exclusao','crm_satisfacao_apagar'):
        assert Client().get(reverse(nome)).status_code in (302,404)
        assert entrar('aluno@example.test').get(reverse(nome)).status_code == 404
    assert entrar().get(reverse('crm_satisfacao_arquivo')).status_code == 405
    assert entrar().get(reverse('crm_satisfacao_apagar')).status_code == 405
    dados = {"site_id":"escola", "aluno_id":"aluno-1", "avaliacao":"pesquisa-1","acao":"arquivar"}
    assert entrar(csrf=True).post(reverse('crm_satisfacao_arquivo'), dados).status_code == 403
    rota = respx.post(QUIZ+'/interno/nps/acoes').mock(return_value=httpx.Response(503))
    pagina = entrar().post(reverse('crm_satisfacao_arquivo'), dados)
    assert pagina.status_code == 503 and 'A ação não foi concluída' in pagina.content.decode()
    assert 'Avaliação arquivada.' not in pagina.content.decode()
