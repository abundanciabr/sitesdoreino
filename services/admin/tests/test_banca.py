import json
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from django.test import RequestFactory
from apps.agentes import banca, banca_fontes, executor
from apps.agentes.models import Execucao
from apps.agentes.banca_assinatura import assinatura
from apps.core.models import RascunhoDeConfiguracao


def foto(texto='Aprenda modelagem 3D', versao=1):
    conteudo = {'site_id': 's1', 'page_id': 'p1', 'slug': 'oferta', 'idioma': 'pt-br',
                'version': versao, 'secoes': [{'nome': 'cubo', 'slots': {'headline': texto}}]}
    return {'conteudo': conteudo, 'assinatura': assinatura(conteudo), 'origem': 'publicada',
            'experimento_id': '', 'variante': ''}


def corpus():
    return {'itens': [{'id': 'real1', 'texto': 'Não sei como começar', 'fonte': 'suporte'}],
            'digest': 'corpus1', 'cobertura': [], 'selecao_versao': banca_fontes.VERSAO_SELECAO}


def leitura(codigo='iniciante'):
    return {'compra': 'indeciso', 'porque': 'Falta detalhe', 'onde_parou': 'Primeiro passo',
            'secao_decisao': 'cubo.headline', 'trecho_decisao': 'Aprenda modelagem 3D',
            'evidencia_decisao': 'real1' if codigo == 'calibrado' else '',
            'objecoes': [{'secao': 'cubo.headline', 'trecho': 'Aprenda modelagem 3D',
                         'objecao': 'Como começo?', 'faltou': 'Primeiro passo',
                         'evidencia_id': 'real1' if codigo == 'calibrado' else ''}]}


def test_citacao_fabricada_e_recusada():
    dados = leitura()
    dados['objecoes'][0]['trecho'] = 'Renda garantida'
    with pytest.raises(ValueError, match='Citação'):
        banca.validar_leitura(dados, foto(), corpus(), 'iniciante')


def test_calibrado_exige_evidencia_existente():
    with pytest.raises(ValueError, match='evidência'):
        banca.validar_leitura(leitura(), foto(), corpus(), 'calibrado')
    assert banca.validar_leitura(leitura('calibrado'), foto(), corpus(), 'calibrado')


def test_compra_sem_objecao_ainda_exige_citacao():
    dados = leitura()
    dados['objecoes'] = []
    dados['trecho_decisao'] = 'Texto inventado'
    with pytest.raises(ValueError, match='decisão'):
        banca.validar_leitura(dados, foto(), corpus(), 'iniciante')


def test_comparacao_declara_mudanca_da_banca():
    a = {'fotografia': foto(), 'corpus': corpus(), 'resultados': {'iniciante': leitura()}, 'modelo': 'm1'}
    b = {**a, 'fotografia': foto('Outro texto', 2), 'modelo': 'm2'}
    resultado = banca.comparar(a, b)
    assert resultado['texto'][0]['depois'] == 'Outro texto'
    assert not resultado['mesma_banca']


def test_minimizacao_remove_identificadores_e_segredos():
    texto = banca_fontes.anonimizar('Maria Silva: maria@example.com CPF 123.456.789-09 telefone (11) 99999-8888 senha: abcdef', ['Maria Silva'])
    for segredo in ['Maria', 'Silva', 'example', '123.456', '99999', 'abcdef']:
        assert segredo not in texto


def test_testes_tecnicos_nao_sao_objeções_reais():
    assert banca_fontes.parece_teste('Teste técnico autorizado pelo mantenedor: conferir suporte')
    assert banca_fontes.parece_teste('Quando começa o curso?', ['Aluno Teste'])
    assert not banca_fontes.parece_teste('Testei um programa 3D e não consegui usar')
    assert banca_fontes.MENU_AUTOMATICO.search('Escolha uma opção ou escreva sua dúvida')


@pytest.mark.django_db
def test_pedido_sem_corpus_nao_inventa_calibracao():
    with pytest.raises(ValueError, match='Colete'):
        banca.pedir('s1', 'oferta', 'publicada', '', '', 'chave', 'Equipe')
    assert not Execucao.objects.filter(tipo=Execucao.Tipo.BANCA).exists()


@pytest.mark.django_db
def test_duplo_clique_preserva_fotografia_e_perfis():
    RascunhoDeConfiguracao.objects.create(tipo='banca_corpus', site_id='s1', alvo='c1', conteudo=corpus())
    with patch.object(banca, 'fotografia', return_value=foto()), patch.object(banca.modelo, 'conexao', return_value=SimpleNamespace(modelo_forte='teste')):
        primeiro = banca.pedir('s1', 'oferta', 'publicada', '', '', 'chave', 'Equipe')
        segundo = banca.pedir('s1', 'oferta', 'publicada', '', '', 'chave', 'Equipe')
    assert primeiro.pk == segundo.pk
    assert len(primeiro.estado['perfis']) == 6
    assert 'leitor_ptbr' in primeiro.estado['perfis']


@pytest.mark.django_db
def test_sete_chamadas_independentes_e_sintese_sem_repetir():
    RascunhoDeConfiguracao.objects.create(tipo='banca_corpus', site_id='s1', alvo='c1', conteudo=corpus())
    with patch.object(banca, 'fotografia', return_value=foto()), patch.object(banca.modelo, 'conexao', return_value=SimpleNamespace(modelo_forte='teste')):
        trabalho = banca.pedir('s1', 'oferta', 'publicada', '', '', 'sete', 'Equipe')
    entradas = []
    def responder(**kwargs):
        entrada = json.loads(kwargs['itens'][0]['content'])
        entradas.append(entrada)
        codigo = list(banca.PERFIS)[len(entradas)-1] if len(entradas) <= 6 else 'sintese'
        dados = leitura(codigo) if codigo != 'sintese' else {'resumo': 'Hipóteses', 'divergencias': 'Nenhuma', 'limites': 'Simulação',
            'consertos': [{'titulo': 'Explicar início', 'porque_priorizar': 'Dúvida', 'referencias': ['iniciante:0'],
                          'conserto': 'Explicar', 'hipotese': 'Clareza aumenta entradas', 'metrica': 'checkout_iniciado'}]}
        return SimpleNamespace(texto=json.dumps(dados), completa=True, id='resposta',
                               consumo=SimpleNamespace(pk=len(entradas), custo_estimado_usd='0.01'))
    with patch.object(banca.modelo, 'responder', side_effect=responder), patch.object(banca.CatalogoClient, '_falar', return_value=('ok', {'registrada': True})):
        executor.rodar_uma('banca-teste')
    trabalho.refresh_from_db()
    assert trabalho.situacao == Execucao.Situacao.CONCLUIDA
    assert len(entradas) == 7
    assert all('leituras' not in e for e in entradas[:6])
    assert len(entradas[-1]['leituras']) == 6
    assert not executor.rodar_uma('banca-teste')


@pytest.mark.django_db
def test_painel_renderiza_com_fontes_indisponiveis():
    from apps.agentes.banca_painel import painel
    request = RequestFactory().get('/paginas/?banca=1')
    request.admin = {'nome': 'Equipe'}
    with patch.object(banca.CatalogoClient, '_falar', return_value=('nao_respondeu', None)):
        resposta = painel(request, {'id': 's1'})
    assert resposta.status_code == 400
    assert 'Banca de clientes simulados' in resposta.content.decode()
    assert 'private' in resposta['Cache-Control']
