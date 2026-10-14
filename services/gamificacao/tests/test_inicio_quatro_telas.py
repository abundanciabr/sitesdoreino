"""As quatro telas exigem gestos separados, avaliação e registros privados."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.gamificacao.bonus_faixas import configurar as configurar_faixas, conceder as conceder_faixas
from apps.gamificacao.bonus_inicio import configurar as configurar_tarefas
from apps.gamificacao.jornada import situacao
from apps.gamificacao.models import (AnexoDaJornada, AvaliacaoDaJornada, JornadaPessoal,
    LancamentoDeXP, PerfilJogador, RegraDePontuacao)

pytestmark = pytest.mark.django_db
SITE, PESSOA = 'site-inicio-quatro', 'aluna-inicio-quatro'


@pytest.fixture(autouse=True)
def conta(monkeypatch):
    monkeypatch.setenv('SITE_ID', SITE)
    monkeypatch.setattr('apps.core.inventario._sessao', lambda cookie: {'autenticado': True, 'id': PESSOA})
    monkeypatch.setattr('apps.core.views.quem_e', lambda request: PESSOA)
    monkeypatch.setattr('apps.gamificacao.avaliacao_inicio.avaliar', lambda *args, **kwargs: {
        'resultado': 'reconhecida', 'feedback': 'O conteúdo desta etapa foi examinado.',
        'evidencia': {'teste': True}})
    configurar_faixas(SITE)


def arquivo(nome='primeiro.obj'):
    lado = b'2' if nome != 'primeiro.obj' else b'1'
    return SimpleUploadedFile(nome, b'v 0 0 0\nv ' + lado + b' 0 0\nv 0 1 0\nf 1 2 3\n')


def ler(client):
    return client.get(reverse('inventario'), HTTP_COOKIE='meshcraft_sessao=A').json()


def post(client, acao, **dados):
    if acao == 'inicio-motivo':
        dados.setdefault('concluir', 'sim')
    if acao == 'inicio-compromisso':
        dados.setdefault('assumir', 'sim')
        dados.setdefault('proximo_passo', 'criar_item')
    if acao == 'inicio-item':
        dados.setdefault('item_nome', 'Meu item')
        dados.setdefault('item_acao', 'Modelei a forma principal')
    return client.post(reverse('inventario'), {'acao': acao, 'revisao': ler(client)['revisao'], **dados},
        HTTP_COOKIE='meshcraft_sessao=A')


def ate(client, ordem):
    if ordem >= 2:
        assert post(client, 'inicio-motivo', motivo='ugc').status_code == 200
    if ordem >= 3:
        assert post(client, 'inicio-compromisso').status_code == 200
    if ordem >= 4:
        assert post(client, 'inicio-item').status_code == 200


def test_cadeados_seguem_quatro_avaliacoes_reais(client):
    assert [e['bloqueada'] for e in ler(client)['inicio']['etapas']] == [False, True, True, True]
    assert not JornadaPessoal.objects.exists()
    for nome in ('inicio-objetivo', 'inicio-item', 'inicio-envio'):
        assert client.get(reverse(nome)).url == reverse('inicio-motivo')
    assert post(client, 'inicio-item').status_code == 400
    assert post(client, 'inicio-envio', arquivo=arquivo()).status_code == 400
    assert not AnexoDaJornada.objects.exists()
    rascunho = post(client, 'inicio-motivo', motivo='ugc', concluir='nao')
    assert rascunho.status_code == 200 and ler(client)['inicio']['etapas'][1]['bloqueada']
    assert post(client, 'inicio-motivo', motivo='ugc').status_code == 200
    incompleto = post(client, 'inicio-compromisso', assumir='nao')
    assert not incompleto.json()['inicio']['etapas'][1]['concluida']
    assert incompleto.json()['atual_ordem'] == 1
    aceito = post(client, 'inicio-compromisso')
    assert aceito.json()['atual_ordem'] == 2
    assert aceito.json()['inicio']['etapas'][1]['resultado'] == 'reconhecida'
    assert post(client, 'inicio-item').json()['atual_ordem'] == 3
    assert post(client, 'inicio-envio', arquivo=arquivo()).json()['atual_ordem'] == 4
    assert [e['concluida'] for e in ler(client)['inicio']['etapas']] == [True] * 4


@pytest.mark.parametrize('regra', ['inativa', 'pendente'])
def test_sem_xp_definitivo_primeiro_gesto_ainda_libera_avaliacao(client, regra):
    configurar_tarefas(SITE)
    alteracao = {'ativa': False} if regra == 'inativa' else {'quarentena_horas': 24}
    RegraDePontuacao.objects.filter(site_id=SITE, slug='bonus-inicio-etapa-1').update(**alteracao)
    resposta = post(client, 'inicio-motivo', motivo='ugc')
    assert resposta.status_code == 200 and resposta.json()['conquista_xp'] == 0
    assert ler(client)['inicio']['etapas'][0]['concluida'] is True
    assert post(client, 'inicio-compromisso').status_code == 200
    assert AvaliacaoDaJornada.objects.filter(ordem=2, resultado='reconhecida').exists()


def test_quarta_tarefa_sem_micro_xp_avaliacao_real_ainda_reconhece(client):
    ate(client, 4)
    configurar_tarefas(SITE)
    RegraDePontuacao.objects.filter(site_id=SITE, slug='bonus-inicio-etapa-4').update(ativa=False)
    resposta = post(client, 'inicio-envio', arquivo=arquivo())
    assert resposta.status_code == 200
    assert resposta.json()['conquista_xp_tarefa'] == 0
    assert resposta.json()['conquista_xp_faixa'] == 15000
    assert resposta.json()['atual_ordem'] == 4
    assert AnexoDaJornada.objects.count() == 1
    assert post(client, 'inicio-envio').json()['conquista_xp_faixa'] == 0


def test_legado_preservado_nao_fabrica_avaliacao(client):
    from apps.core.perfil import perfil_de
    perfil_de(PESSOA, SITE)
    JornadaPessoal.objects.create(pessoa_id=PESSOA, site_id=SITE,
        inicio={'motivo': 'ugc', 'objetivo': 'Peça antiga', 'item_pronto_em': '2026-10-01T11:00:00-03:00'},
        declaracoes={'2': '2026-10-01T12:00:00-03:00'})
    AnexoDaJornada.objects.create(pessoa_id=PESSOA, site_id=SITE, passo=2,
        nome='obra.obj', conteudo=b'v 0 0 0\n', tamanho=8, sha256='legado')
    assert not AvaliacaoDaJornada.objects.exists()
    assert post(client, 'inicio-envio').status_code == 400
    assert JornadaPessoal.objects.get().declaracoes['2']
    assert AnexoDaJornada.objects.count() == 1


def test_quatro_gestos_separados_e_sem_salto(client):
    assert client.get(reverse('inicio-envio')).url == reverse('inicio-motivo')
    assert post(client, 'inicio-compromisso').status_code == 400
    assert post(client, 'inicio-item').status_code == 400
    assert post(client, 'inicio-envio', arquivo=arquivo()).status_code == 400
    ate(client, 3)
    assert client.get(reverse('inicio-envio')).url == reverse('inicio-item')
    assert post(client, 'inicio-item').json()['atual_ordem'] == 3
    assert client.get(reverse('inicio-envio')).status_code == 200
    assert post(client, 'inicio-envio', arquivo=arquivo()).json()['atual_ordem'] == 4
    assert AnexoDaJornada.objects.count() == 1


def test_reassumir_objetivo_preserva_item_arquivo_e_historico(client):
    ate(client, 4)
    assert post(client, 'inicio-envio', arquivo=arquivo()).status_code == 200
    anexo_id = AnexoDaJornada.objects.get().id
    avaliacoes = AvaliacaoDaJornada.objects.count()
    assert post(client, 'inicio-plano', objetivo='Nova forma', compromisso='Praticarei', assumir='nao').status_code == 200
    assert AnexoDaJornada.objects.get().id == anexo_id
    assert AvaliacaoDaJornada.objects.count() == avaliacoes
    assert JornadaPessoal.objects.get().inicio['item_pronto_em']


def test_anexo_legado_continua_privado_sem_reconhecimento_automatico(client, monkeypatch):
    ate(client, 4)
    resposta = post(client, 'inicio-envio', arquivo=arquivo())
    anexo = AnexoDaJornada.objects.get()
    url = reverse('arquivo-inventario', args=[anexo.id])
    assert resposta.status_code == 200
    assert client.get(url, HTTP_COOKIE='meshcraft_sessao=A').status_code == 200
    monkeypatch.setattr('apps.core.inventario._sessao', lambda cookie: {'autenticado': True, 'id': 'outra-aluna'})
    assert client.get(url, HTTP_COOKIE='meshcraft_sessao=B').status_code == 404


def test_xp_de_cada_gesto_e_faixa_somente_depois_da_analise(client):
    assert post(client, 'inicio-motivo', motivo='ugc', concluir='nao').json().get('conquista_url') is None
    assert not LancamentoDeXP.objects.exists()
    motivo = post(client, 'inicio-motivo', motivo='ugc')
    assert motivo.json()['conquista_xp_tarefa'] == 100
    assert post(client, 'inicio-motivo', motivo='ugc').json()['conquista_xp'] == 0
    amarelo = post(client, 'inicio-compromisso')
    assert amarelo.json()['conquista_xp_tarefa'] == 100
    assert amarelo.json()['conquista_xp_faixa'] == 5000
    azul = post(client, 'inicio-item')
    assert azul.json()['conquista_xp_tarefa'] == 100
    assert azul.json()['conquista_xp_faixa'] == 10000
    vermelho = post(client, 'inicio-envio', arquivo=arquivo())
    assert vermelho.json()['conquista_xp_tarefa'] == 100
    assert vermelho.json()['conquista_xp_faixa'] == 15000
    assert post(client, 'inicio-envio').json()['conquista_xp'] == 0
    assert sorted(LancamentoDeXP.objects.values_list('pontos', flat=True)) == [100] * 4 + [5000, 10000, 15000]


def test_bonus_de_faixa_ja_pago_nao_e_duplicado(client):
    ate(client, 3)
    assert conceder_faixas(PESSOA, SITE, [3]) == 10000
    resposta = post(client, 'inicio-item')
    assert resposta.json()['conquista_xp_faixa'] == 0
    assert LancamentoDeXP.objects.filter(pontos=10000).count() == 1


def test_regra_inativa_nao_anuncia_xp_inexistente(client):
    configurar_tarefas(SITE)
    RegraDePontuacao.objects.filter(site_id=SITE, slug='bonus-inicio-etapa-1').update(ativa=False)
    resposta = post(client, 'inicio-motivo', motivo='ugc')
    assert resposta.json()['conquista_xp'] == 0
    assert not LancamentoDeXP.objects.filter(pontos=100).exists()


def test_nova_versao_apos_conclusao_avanca_revisao_sem_duplicar_faixa(client):
    ate(client, 4)
    assert post(client, 'inicio-envio', arquivo=arquivo()).status_code == 200
    revisao = JornadaPessoal.objects.get().revisao
    resposta = post(client, 'inicio-envio', arquivo=arquivo('nova-versao.obj'))
    assert resposta.status_code == 200 and resposta.json()['revisao'] == revisao + 1
    assert AnexoDaJornada.objects.count() == 2
    assert LancamentoDeXP.objects.filter(pontos=15000).count() == 1
    atrasado = client.post(reverse('inventario'), {'acao': 'inicio-envio', 'revisao': revisao},
        HTTP_COOKIE='meshcraft_sessao=A')
    assert atrasado.status_code == 400


def test_comprovante_adulterado_ou_de_outra_conta_nao_anuncia_credito(client, monkeypatch):
    resposta = post(client, 'inicio-motivo', motivo='ugc')
    url = resposta.json()['conquista_url']
    assert client.get(url).context['conquista_xp'] == 100
    antes = LancamentoDeXP.objects.count()
    adulterado = url[:-1] + ('A' if url[-1] != 'A' else 'B')
    assert client.get(adulterado).context['conquista_xp'] == 0
    from apps.core.perfil import perfil_de
    perfil_de('outra-aluna', SITE)
    JornadaPessoal.objects.create(pessoa_id='outra-aluna', site_id=SITE, inicio={'motivo': 'jogo'})
    monkeypatch.setattr('apps.core.views.quem_e', lambda request: 'outra-aluna')
    assert client.get(url).context['conquista_xp'] == 0
    assert LancamentoDeXP.objects.count() == antes
