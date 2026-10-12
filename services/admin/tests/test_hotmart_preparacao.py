import uuid
from unittest.mock import patch

import pytest
from django.test import Client, RequestFactory

from apps.core.hotmart import painel, teste_administrativo as tela_teste, resumo
from apps.hotmart import operacao
from apps.hotmart.models import EventoHotmart, ProdutoHotmart, TesteHotmart as Ensaio

ADMIN = {'email': 'admin@example.org', 'nome': 'Administrador'}
CURSOS = [{'slug': 'curso-teste', 'nome': 'Curso de teste', 'produto_id': 'produto-local', 'estado': 'publicado'}]


@pytest.fixture
def aprovado():
    return EventoHotmart.objects.create(evento_id='aprovado', evento='PURCHASE_APPROVED', dados={'data': {
        'buyer': {'name': 'Comprador', 'email': 'comprador@example.org', 'phone': '5511987654321'},
        'product': {'id': 123, 'name': 'Produto Hotmart'}, 'purchase': {'transaction': 'HP123'}}})


def preparar(registro, **mudancas):
    dados = {'chave': str(uuid.uuid4()), 'curso_slug': 'curso-teste', 'email': 'sim', **mudancas}
    return operacao.preparar_teste(site_id='site', cursos=CURSOS, registro=registro, dados=dados, admin=ADMIN)


def test_associacao_explicita_sem_ativar_compras():
    dados = {'produto_hotmart': '123', 'nome': 'Produto', 'curso_slug': 'curso-teste'}
    operacao.salvar_produto('site', CURSOS, dados)
    operacao.salvar_produto('site', CURSOS, {**dados, 'nome': 'Nome atualizado'})
    assert ProdutoHotmart.objects.count() == 1
    assert ProdutoHotmart.objects.get().produto_site == 'produto-local'
    assert Ensaio.objects.count() == 0


@pytest.mark.parametrize('identificador', ['0', '-1', 'abc', '', '9' * 31, '²'])
def test_produtos_de_teste_ou_ids_invalidos_nao_viram_associacao(identificador):
    with pytest.raises(ValueError):
        operacao.salvar_produto('site', CURSOS, {'produto_hotmart': identificador, 'nome': 'X', 'curso_slug': 'curso-teste'})
    assert not ProdutoHotmart.objects.exists()


def test_preview_usa_admin_e_preserva_comprador(aprovado):
    teste = preparar(aprovado, whatsapp='sim', telefone='+1 (212) 555-0198', telefone_proprio='sim')
    assert teste.plano['email'] == ADMIN['email']
    assert teste.plano['telefone'] == '+12125550198'
    assert 'comprador@example.org' not in teste.plano['corpo']
    assert teste.plano['link'] == 'https://meshcraft.top/cursos/curso-teste/'
    assert teste.resultado == {}
    aprovado.refresh_from_db()
    assert aprovado.dados['data']['buyer']['email'] == 'comprador@example.org'


def test_mapping_resolve_curso_sem_escolha_manual(aprovado):
    operacao.salvar_produto('site', CURSOS, {'produto_hotmart': '123', 'nome': 'X', 'curso_slug': 'curso-teste'})
    teste = preparar(aprovado, curso_slug='')
    assert teste.plano['associacao_aplicada'] is True


def test_plano_com_email_aninhado_aparece_no_resumo():
    registro = EventoHotmart(evento='SWITCH_PLAN', dados={'data': {'subscription': {
        'user': {'email': 'aluno@example.org'}, 'product': {'id': 456, 'name': 'Plano'}}}})
    assert resumo(registro)['email'] == 'aluno@example.org'
    assert resumo(registro)['produto'] == 'Plano'


@pytest.mark.parametrize('campo,valor', [('curso_slug', 'curso-alheio'), ('whatsapp', 'sim')])
def test_nao_prepara_destino_ou_curso_incompleto(aprovado, campo, valor):
    with pytest.raises(ValueError):
        preparar(aprovado, **{campo: valor})
    assert not Ensaio.objects.exists()


def test_reembolso_nao_prepara_liberacao(aprovado):
    aprovado.evento = 'PURCHASE_REFUNDED'
    with pytest.raises(ValueError):
        preparar(aprovado)


@pytest.mark.parametrize('admin', [{'email': ADMIN['email'], 'robo': True}, {'email': 'outro@example.org'}])
def test_executor_somente_para_admin_dono(aprovado, admin):
    teste = preparar(aprovado)
    with patch.object(operacao, 'pedir') as pedir, pytest.raises(ValueError):
        operacao.executar_teste(teste, admin)
    pedir.assert_not_called()


def test_matricula_antes_da_mensagem_e_retomada_idempotente(aprovado):
    teste = preparar(aprovado)
    chamadas = []
    def pedir(cliente, caminho, *, corpo=None):
        chamadas.append((type(cliente).__name__, corpo))
        return {'status': 'ativa', 'em_teste': True} if len(chamadas) == 1 else {'envios': [{'canal': 'email', 'estado': 'pendente'}]}
    with patch.object(operacao, 'contexto_do_site', return_value=('site', CURSOS)), patch.object(operacao, 'pedir', side_effect=pedir):
        teste = operacao.executar_teste(teste, ADMIN)
        operacao.executar_teste(teste, ADMIN)
    assert [c[0] for c in chamadas] == ['AlunosClient', 'MensageriaClient', 'MensageriaClient']
    assert {c[1]['chave'] for c in chamadas} == {str(teste.pk)}
    assert all(c[1]['email'] == ADMIN['email'] for c in chamadas)


def test_falha_de_matricula_nao_solicita_mensagem(aprovado):
    teste = preparar(aprovado)
    with patch.object(operacao, 'contexto_do_site', return_value=('site', CURSOS)), patch.object(operacao, 'pedir', side_effect=ValueError('sem confirmação')) as pedir:
        teste = operacao.executar_teste(teste, ADMIN)
    assert pedir.call_count == 1
    assert teste.resultado == {'erro': 'sem confirmação'}


def test_curso_remapeado_exige_previa_atualizada(aprovado):
    teste = preparar(aprovado)
    cursos = [{**CURSOS[0], 'produto_id': 'outro-produto'}]
    with patch.object(operacao, 'contexto_do_site', return_value=('site', cursos)), patch.object(operacao, 'pedir') as pedir, pytest.raises(ValueError):
        operacao.executar_teste(teste, ADMIN)
    pedir.assert_not_called()


def test_telas_privadas_e_previa_sem_efeitos(aprovado):
    teste = preparar(aprovado)
    assert Client().get(f'/integracoes/hotmart/testes/{teste.pk}/').status_code == 302
    request = RequestFactory().get('/integracoes/hotmart/')
    request.admin = ADMIN
    with patch.object(operacao, 'contexto_do_site', return_value=('site', CURSOS)):
        resposta = painel(request)
    assert resposta.status_code == 200
    assert 'automação para alunos desligada'.encode() in resposta.content
    request = RequestFactory().get('/integracoes/hotmart/testes/' + str(teste.pk) + '/')
    request.admin = ADMIN
    with patch.object(operacao, 'pedir') as pedir:
        resposta = tela_teste(request, teste.pk)
    pedir.assert_not_called()
    assert ADMIN['email'].encode() in resposta.content
