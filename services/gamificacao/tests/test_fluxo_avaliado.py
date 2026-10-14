"""A faixa acompanha uma avaliação real; o envio e a falha ficam sem prêmio."""

from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.gamificacao.models import (AnexoDaJornada, AvaliacaoDaJornada,
                                     JornadaPessoal, LancamentoDeXP, PerfilJogador)


pytestmark = pytest.mark.django_db
SITE, PESSOA = 'site-fluxo-avaliado', 'aluna-fluxo-avaliado'
URL = '/trilha/inventario/api/'


@pytest.fixture(autouse=True)
def conta(monkeypatch):
    from apps.gamificacao.bonus_faixas import configurar
    configurar(SITE)
    monkeypatch.setenv('SITE_ID', SITE)
    monkeypatch.setattr('apps.core.inventario._sessao',
        lambda cookie: {'autenticado': True, 'id': PESSOA})
    monkeypatch.setattr('apps.core.views.quem_e', lambda request: PESSOA)


def ler(client):
    return client.get(URL, HTTP_COOKIE='meshcraft_sessao=A')


def enviar(client, acao, **campos):
    revisao = ler(client).json()['revisao']
    return client.post(URL, {'acao': acao, 'revisao': revisao, **campos},
        HTTP_COOKIE='meshcraft_sessao=A')


def imagem():
    fluxo = BytesIO()
    Image.new('RGB', (40, 30), 'blue').save(fluxo, format='PNG')
    return SimpleUploadedFile('primeiro.png', fluxo.getvalue(), content_type='image/png')


def ate_azul(client, monkeypatch):
    assert enviar(client, 'inicio-motivo', motivo='ugc', concluir='sim').status_code == 200
    resposta = enviar(client, 'inicio-compromisso', assumir='sim', proximo_passo='criar_item')
    assert resposta.status_code == 200, resposta.content
    monkeypatch.setattr('apps.gamificacao.avaliacao_inicio.avaliar',
        lambda *args, **kwargs: {'resultado': 'reconhecida',
            'feedback': 'Você descreveu o boné e explicou que mudou a cor da aba.',
            'evidencia': {'relato': 'boné; mudou a cor da aba'}})
    resposta = enviar(client, 'inicio-item', item_nome='Boné', item_acao='Mudei a cor da aba')
    assert resposta.status_code == 200, resposta.content
    return resposta


@pytest.mark.parametrize('motivo', ['freelancer', 'ugc', 'jogo', 'aprender'])
def test_quatro_caminhos_e_compromisso_avaliado(client, motivo):
    anterior = ler(client)
    assert anterior.status_code == 200
    assert not JornadaPessoal.objects.exists()
    motivo_enviado = enviar(client, 'inicio-motivo', motivo=motivo, concluir='sim')
    assert motivo_enviado.status_code == 200
    rascunho = enviar(client, 'inicio-compromisso', compromisso_etapa='2')
    assert rascunho.status_code == 200
    assert rascunho.json()['atual_ordem'] == 1
    reconhecido = enviar(client, 'inicio-compromisso', assumir='sim')
    assert reconhecido.status_code == 200
    assert reconhecido.json()['inicio']['etapas'][1]['resultado'] == 'reconhecida'
    assert reconhecido.json()['atual_ordem'] == 2
    dados = reconhecido.json()
    assert dados['conquista_xp_tarefa'] == 100
    assert dados['conquista_xp_faixa'] == 5000
    assert dados['conquista_xp'] == 5100
    assert 'comprovante=' in dados['conquista_url']
    assert PerfilJogador.objects.get(pessoa_id=PESSOA, site_id=SITE).xp_total == 5200
    recibo = client.get(dados['conquista_url'] + '&embutido=1', HTTP_COOKIE='meshcraft_sessao=A')
    assert recibo.status_code == 200
    assert recibo.context['inicio_embutido'] is True
    assert 'data-xp="5100"' in recibo.content.decode()
    assert len(AvaliacaoDaJornada.objects.filter(ordem=2)) == 1
    assert 'proximo_passo_resposta' not in JornadaPessoal.objects.get().inicio
    assert len(LancamentoDeXP.objects.filter(pontos=5000)) == 1


def test_relato_avaliado_antes_da_azul_e_imagem_antes_da_vermelha(client, monkeypatch):
    resposta = ate_azul(client, monkeypatch)
    assert resposta.json()['atual_ordem'] == 3
    assert resposta.json()['inicio']['etapas'][2]['resultado'] == 'reconhecida'
    assert PerfilJogador.objects.get(pessoa_id=PESSOA, site_id=SITE).xp_total >= 15100
    antes = LancamentoDeXP.objects.count()
    monkeypatch.setattr('apps.gamificacao.avaliacao_inicio.avaliar',
        lambda *args, **kwargs: {'resultado': 'incompleta',
            'feedback': 'A imagem ainda não permite identificar o boné descrito.',
            'evidencia': {'imagem_examinada': True}})
    falha = enviar(client, 'inicio-envio', arquivo=imagem())
    assert falha.status_code == 200
    assert falha.json()['atual_ordem'] == 3
    assert AnexoDaJornada.objects.count() == 1
    assert LancamentoDeXP.objects.count() == antes + 1  # microbônus do envio; sem faixa vermelha
    assert not LancamentoDeXP.objects.filter(pontos=15000).exists()
    repetida = enviar(client, 'inicio-envio')
    assert repetida.status_code == 200
    assert LancamentoDeXP.objects.count() == antes + 1


def test_falha_tecnica_na_analise_preserva_anexo_e_permitem_nova_tentativa(client, monkeypatch):
    ate_azul(client, monkeypatch)
    def falhar(*args, **kwargs):
        return {'resultado': 'falha', 'feedback': 'Não foi possível examinar a imagem.', 'evidencia': {}}
    monkeypatch.setattr('apps.gamificacao.avaliacao_inicio.avaliar', falhar)
    resposta = enviar(client, 'inicio-envio', arquivo=imagem())
    assert resposta.status_code == 200
    assert resposta.json()['atual_ordem'] == 3
    assert not LancamentoDeXP.objects.filter(pontos=15000).exists()
    assert AnexoDaJornada.objects.count() == 1
    monkeypatch.setattr('apps.gamificacao.avaliacao_inicio.avaliar',
        lambda *args, **kwargs: {'resultado': 'reconhecida',
            'feedback': 'A imagem do boné mostra a aba azul e o corpo cinza.',
            'evidencia': {'imagem_examinada': True}})
    nova = enviar(client, 'inicio-envio')
    assert nova.status_code == 200
    assert nova.json()['atual_ordem'] == 4
    assert LancamentoDeXP.objects.filter(pontos=15000).count() == 1


def test_retorno_obsoleto_depois_de_troca_de_caminho_nao_premia(client, monkeypatch):
    ate_azul(client, monkeypatch)
    def retornar_tarde(*args, **kwargs):
        jornada = JornadaPessoal.objects.get(pessoa_id=PESSOA, site_id=SITE)
        jornada.inicio = {**jornada.inicio, 'motivo': 'jogo'}
        jornada.revisao += 1
        jornada.save(update_fields=['inicio', 'revisao'])
        return {'resultado': 'reconhecida',
            'feedback': 'Esta versão antiga parecia atender ao pedido original.',
            'evidencia': {'imagem_examinada': True}}
    monkeypatch.setattr('apps.gamificacao.avaliacao_inicio.avaliar', retornar_tarde)
    resposta = enviar(client, 'inicio-envio', arquivo=imagem())
    assert resposta.status_code == 200
    assert not AvaliacaoDaJornada.objects.filter(ordem=4).exists()
    assert not LancamentoDeXP.objects.filter(pontos=15000).exists()
    assert AnexoDaJornada.objects.count() == 1



def test_tentativa_incompleta_nao_celebra_uma_faixa_anterior(client, monkeypatch):
    ate_azul(client, monkeypatch)
    antes = LancamentoDeXP.objects.count()
    monkeypatch.setattr('apps.gamificacao.avaliacao_inicio.avaliar',
        lambda *args, **kwargs: {'resultado': 'incompleta',
            'feedback': 'Conte qual ação você realizou no item desta tentativa.',
            'evidencia': {'relato': 'ainda sem ação concreta'}})
    resposta = enviar(client, 'inicio-item', item_nome='Boné', item_acao='Vou criar depois')
    assert resposta.status_code == 200
    dados = resposta.json()
    assert dados['atual_ordem'] == 3  # conquista anterior preservada
    assert dados['avaliacao_atual']['resultado'] == 'incompleta'
    assert dados['avaliacao_atual']['conquistada'] is False
    assert dados['conquista_xp'] == 0
    assert 'conquista_url' not in dados
    assert LancamentoDeXP.objects.count() == antes


def test_resposta_antiga_nao_bloqueia_nem_duplica_amarela(client):
    enviar(client, 'inicio-motivo', motivo='ugc', concluir='sim')
    enviar(client, 'inicio-compromisso', assumir='sim', proximo_passo='criar_item')
    resposta = enviar(client, 'inicio-compromisso', assumir='sim', proximo_passo='esperar')
    assert resposta.status_code == 200
    dados = resposta.json()
    assert dados['atual_ordem'] == 2
    assert dados['avaliacao_atual']['resultado'] == 'reconhecida'
    assert dados['avaliacao_atual']['conquistada'] is True
    assert dados['conquista_xp'] == 0
    assert LancamentoDeXP.objects.filter(pontos=5000).count() == 1
