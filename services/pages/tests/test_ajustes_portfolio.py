import json
from io import BytesIO

import httpx
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse
from PIL import Image

from apps.portfolio import colegas, imagens, vitrine
from apps.portfolio.models import Portfolio, Peca, PedidoAosColegas, RespostaDoColega, PedidoDeConferencia, ProjetoAutoral
from conftest import ANA, SITE, OUTRO_SITE, COOKIE, ADMIN, URL_DA_SESSAO, dublar_matricula, dublar_administrador

pytestmark = pytest.mark.django_db


def imagem():
    output = BytesIO()
    Image.new('RGB', (24, 24), 'green').save(output, 'PNG')
    return SimpleUploadedFile('imagem.png', output.getvalue(), content_type='image/png')


def preparar():
    p = Portfolio.objects.create(site_id=SITE, aluno_id=ANA['id'])
    selecionada = imagens.guardar(imagem(), site_id=SITE, aluno_id=ANA['id'], legenda='Minha peça', base_url='https://meshcraft.top/')
    selecionada.mostrar_na_pagina_publica = True
    selecionada.duvida = 'Anotação pessoal que não compartilhei'
    selecionada.checklist_preparacao = [{'chave': 'privado', 'marcado': True}]
    selecionada.save()
    privada = imagens.adicionar_material(imagem(), site_id=SITE, aluno_id=ANA['id'], peca_id=selecionada.pk, categoria='uv')
    p.apresentacao_comercial = {'pagina': {'titulo': 'Objetos de cenário', 'materiais_ids': [str(selecionada.imagem_enviada.pk)]}}
    p.save()
    return p, selecionada, privada


def test_feedback_compartilha_so_selecao_e_colega_responde(aluna, site_declarado, rede):
    p, peca, privada = preparar()
    cliente = Client()
    r = cliente.post(reverse('pedir_conferencia'), {'duvida_aluno': 'As formas estão claras?'}, HTTP_COOKIE=COOKIE)
    assert r.status_code == 302
    pedido = PedidoAosColegas.objects.get(portfolio=p)
    assert PedidoDeConferencia.objects.count() == 0
    assert pedido.materiais['imagens_ids'] == [str(peca.imagem_enviada.pk)]
    assert 'Anotação pessoal' not in json.dumps(pedido.materiais)
    assert 'checklist' not in json.dumps(pedido.materiais)
    assert cliente.post(r['Location'], {'pontos_fortes': 'Autocomentário'}, HTTP_COOKIE=COOKIE).status_code == 422
    colega = {**ANA, 'id': 'p_colega', 'email': 'colega@exemplo.com', 'nome_exibido': 'Joana'}
    rede.get(URL_DA_SESSAO).mock(return_value=httpx.Response(200, json=colega))
    dublar_matricula(rede, colega['email'])
    dublar_administrador(rede, False)
    assert cliente.get(reverse('colegas'), HTTP_COOKIE=COOKIE).status_code == 200
    pagina = cliente.get(r['Location'], HTTP_COOKIE=COOKIE)
    assert pagina.status_code == 200 and 'Deixe seu feedback' in pagina.content.decode()
    assert cliente.get(reverse('imagem_portfolio', kwargs={'imagem_id': peca.imagem_enviada.pk}), HTTP_COOKIE=COOKIE).status_code == 200
    assert cliente.get(reverse('imagem_portfolio', kwargs={'imagem_id': privada.pk}), HTTP_COOKIE=COOKIE).status_code == 404
    assert Client().get(reverse('imagem_portfolio', kwargs={'imagem_id': peca.imagem_enviada.pk})).status_code == 404
    assert cliente.post(r['Location'], {'pontos_fortes': 'As formas estão legíveis', 'melhorar': 'Testar outra luz'}, HTTP_COOKIE=COOKIE).status_code == 302
    resposta = RespostaDoColega.objects.get(pedido=pedido)
    assert resposta.nome == 'Joana' and resposta.autor_id == colega['id']
    rede.get(URL_DA_SESSAO).mock(return_value=httpx.Response(200, json=ANA))
    assert 'As formas estão legíveis' in cliente.get(r['Location'], HTTP_COOKIE=COOKIE).content.decode()
    assert cliente.post(r['Location'], {'acao': 'encerrar'}, HTTP_COOKIE=COOKIE).status_code == 302
    rede.get(URL_DA_SESSAO).mock(return_value=httpx.Response(200, json=colega))
    assert cliente.get(reverse('imagem_portfolio', kwargs={'imagem_id': peca.imagem_enviada.pk}), HTTP_COOKIE=COOKIE).status_code == 404
    assert cliente.post(r['Location'], {'melhorar': 'Depois de encerrar'}, HTTP_COOKIE=COOKIE).status_code == 422
    pedido.refresh_from_db()
    assert pedido.encerrado and pedido.respostas.count() == 1


def test_feedback_nao_abre_outro_site_e_nao_exige_peca(aluna, site_declarado):
    p = Portfolio.objects.create(site_id=OUTRO_SITE, aluno_id='outro')
    pedido = colegas.pedir(p, pergunta='Pergunta de outro site')
    cliente = Client()
    url = reverse('feedback_colegas', kwargs={'pedido_id': pedido.pk})
    assert cliente.get(url, HTTP_COOKIE=COOKIE).status_code == 404
    assert cliente.post(url, {'melhorar': 'Intrusão'}, HTTP_COOKIE=COOKIE).status_code == 404
    pagina = cliente.get(reverse('colegas'), HTTP_COOKIE=COOKIE).content.decode()
    assert 'Pergunta de outro site' not in pagina
    assert cliente.post(reverse('pedir_conferencia'), {'duvida_aluno': 'Como começar?'}, HTTP_COOKIE=COOKIE).status_code == 302
    assert PedidoAosColegas.objects.filter(portfolio__aluno_id=ANA['id']).count() == 1


def test_feedback_de_projeto_nao_inclui_outros_trabalhos(aluna, site_declarado):
    p, peca, _ = preparar()
    projeto = ProjetoAutoral.objects.create(portfolio=p, titulo='Meu projeto')
    peca.projeto = projeto
    peca.save()
    Peca.objects.create(portfolio=p, ordem=2, link='https://exemplo.test/fora.png', legenda='Fora do projeto', mostrar_na_pagina_publica=True)
    cliente = Client()
    r = cliente.post(reverse('projeto', kwargs={'projeto_id': projeto.pk}), {'acao': 'feedback', 'duvida_aluno': 'Sobre este projeto'}, HTTP_COOKIE=COOKIE)
    assert r.status_code == 302
    pedido = PedidoAosColegas.objects.get(projeto=projeto)
    assert [obra['id'] for obra in pedido.materiais['obras']] == [peca.pk]
    assert pedido.materiais['imagens_ids'] == [str(peca.imagem_enviada.pk)]


def test_robo_na_montagem_recebe_apenas_trabalhos_escolhidos(aluna, site_declarado, rede):
    p, peca, _ = preparar()
    outra = Peca.objects.create(portfolio=p, ordem=2, link='https://exemplo.test/nao.png', legenda='Não selecionada')
    api = rede.post(ADMIN + '/robo-dos-alunos/gerar').mock(return_value=httpx.Response(200, json={
        'conteudo': {'pagina': {'titulo': 'Título criado pela IA', 'subtitulo': 'Texto para meus objetos',
                              'legendas': [{'peca_id': str(peca.pk), 'texto': 'Descrição criada pela IA'}]}}, 'visao': True}))
    cliente = Client()
    pagina = cliente.get(reverse('apresentacao_publica'), HTTP_COOKIE=COOKIE).content.decode()
    assert 'Gerar textos com IA' in pagina and 'data-address-preview' in pagina
    r = cliente.post(reverse('gerar_exemplo'), {'campo': 'completo', 'selecao_trabalhos': '1',
        'trabalhos_ids': [str(peca.pk)], 'orientacao': 'Destacar meus objetos',
        'materiais_selecao': '1', 'materiais_ids': [str(peca.imagem_enviada.pk)]}, HTTP_COOKIE=COOKIE)
    assert r.status_code == 200 and r.json()['conteudo']['pagina']['titulo'] == 'Título criado pela IA'
    dados = json.loads(api.calls.last.request.content)['contexto']
    assert [item['id'] for item in dados['trabalhos']] == [str(peca.pk)]
    assert len(dados['imagens']) == 1 and dados['imagens'][0]['data_url'].startswith('data:image/webp;base64,')
    assert outra.legenda not in json.dumps(dados)
    p.refresh_from_db()
    assert not p.vitrine_publicada and p.apresentacao_comercial['pagina']['titulo'] == 'Objetos de cenário'
    api.mock(return_value=httpx.Response(503, json={'erro': 'Robô temporariamente indisponível'}))
    assert cliente.post(reverse('gerar_exemplo'), {'campo': 'completo'}, HTTP_COOKIE=COOKIE).status_code == 503
    p.refresh_from_db()
    assert p.apresentacao_comercial['pagina']['titulo'] == 'Objetos de cenário'


def test_endereco_rascunho_retomado_sem_mudar_publicado(aluna, site_declarado):
    p = Portfolio.objects.create(site_id=SITE, aluno_id=ANA['id'])
    vitrine.publicar(site_id=SITE, aluno_id=ANA['id'], texto='ana-atual')
    cliente = Client()
    r = cliente.post(reverse('apresentacao_publica'), {'acao': 'auto', 'apelido': 'Ára Meu!', 'pagina_titulo': 'Meu título'},
                     HTTP_COOKIE=COOKIE, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
    assert r.status_code == 200 and r.json()['salvo']
    p.refresh_from_db()
    assert p.apelido == 'ana-atual' and p.apresentacao_comercial['pagina']['apelido_rascunho'] == 'Ára Meu!'
    html = cliente.get(reverse('apresentacao_publica'), HTTP_COOKIE=COOKIE).content.decode()
    assert 'value="Ára Meu!"' in html and 'data-address-base="http://testserver/portfolio/"' in html
    assert 'apelido_rascunho' not in vitrine.snapshot_rascunho(p)['conteudo']['pagina']
