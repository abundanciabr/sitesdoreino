"""As quatro telas exigem gestos separados e preservam registros privados."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.gamificacao.checklist_trilha import montar_checklists
from apps.gamificacao.jornada import situacao
from apps.gamificacao.models import AnexoDaJornada, JornadaPessoal, RegistroDaJornada, LancamentoDeXP, PerfilJogador, RegraDePontuacao
from apps.gamificacao.bonus_faixas import configurar as configurar_faixas, conceder as conceder_faixas
from apps.gamificacao.bonus_inicio import configurar as configurar_tarefas


pytestmark = pytest.mark.django_db
SITE, PESSOA = 'site-inicio-quatro', 'aluna-inicio-quatro'


@pytest.fixture(autouse=True)
def conta(monkeypatch):
    monkeypatch.setenv('SITE_ID', SITE)
    monkeypatch.setattr('apps.core.inventario._sessao', lambda cookie: {'autenticado': True, 'id': PESSOA})
    monkeypatch.setattr('apps.core.views.quem_e', lambda request: PESSOA)


def arquivo():
    return SimpleUploadedFile('primeiro.obj', b'v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n')


def post(client, acao, **dados):
    if acao == 'inicio-motivo':
        dados.setdefault('concluir', 'sim')
    url = reverse('inventario')
    revisao = client.get(url, HTTP_COOKIE='meshcraft_sessao=A').json()['revisao']
    return client.post(url, {'acao': acao, 'revisao': revisao, **dados}, HTTP_COOKIE='meshcraft_sessao=A')


def checklist():
    return [item['estado'] for item in montar_checklists(PESSOA, SITE, situacao(PESSOA, SITE))[2]['itens']]


def test_quatro_gestos_separados_e_sem_salto(client):
    assert reverse('inicio-envio') == '/inicio/envio/'
    assert client.get(reverse('inicio-envio')).url == reverse('inicio-motivo')
    assert post(client, 'inicio-plano', objetivo='Meu objeto', compromisso='Praticarei', assumir='sim').status_code == 400
    assert post(client, 'inicio-item').status_code == 400
    assert post(client, 'inicio-envio', arquivo=arquivo()).status_code == 400
    assert AnexoDaJornada.objects.count() == 0

    assert post(client, 'inicio-motivo', motivo='ugc').status_code == 200
    assert client.get(reverse('inicio-item')).url == reverse('inicio-objetivo')
    assert post(client, 'inicio-plano', objetivo='Meu objeto', compromisso='Praticarei', assumir='sim').status_code == 200
    assert client.get(reverse('inicio-envio')).url == reverse('inicio-item')
    assert checklist() == ['concluido', 'concluido', 'pendente', 'pendente']

    pronto = post(client, 'inicio-item')
    assert pronto.status_code == 200 and pronto.json()['inicio']['item_pronto'] is True
    assert pronto.json()['atual_ordem'] == 1
    assert checklist() == ['concluido', 'concluido', 'concluido', 'pendente']
    assert client.get(reverse('inicio-envio')).status_code == 200

    envio = post(client, 'inicio-envio', arquivo=arquivo(), aprendi='Aprendi a forma')
    assert envio.status_code == 200 and envio.json()['atual_ordem'] == 2
    assert checklist() == ['concluido'] * 4
    jornada = JornadaPessoal.objects.get(pessoa_id=PESSOA, site_id=SITE)
    assert jornada.declaracoes.get('2') and jornada.confirmacoes_sequenciais.get('2')
    assert AnexoDaJornada.objects.count() == 1
    assert post(client, 'inicio-envio').status_code == 200
    assert AnexoDaJornada.objects.count() == 1
    assert RegistroDaJornada.objects.filter(acao='declaracao').count() == 1


def test_reassumir_objetivo_preserva_item_arquivo_e_historico(client):
    assert post(client, 'inicio-motivo', motivo='jogo').status_code == 200
    assert post(client, 'inicio-plano', objetivo='Primeira forma', compromisso='Praticarei', assumir='sim').status_code == 200
    assert post(client, 'inicio-item').status_code == 200
    assert post(client, 'inicio-envio', arquivo=arquivo()).status_code == 200
    anexo_id = AnexoDaJornada.objects.get().id
    assert post(client, 'inicio-plano', objetivo='Nova forma', compromisso='Praticarei', assumir='nao').status_code == 200
    assert situacao(PESSOA, SITE)['atual']['ordem'] == 1
    assert client.get(reverse('inicio-envio')).url == reverse('inicio-objetivo')
    assert checklist() == ['concluido', 'pendente', 'concluido', 'andamento']
    assert JornadaPessoal.objects.get().inicio['item_pronto_em']
    assert AnexoDaJornada.objects.get().id == anexo_id
    assert RegistroDaJornada.objects.filter(acao='declaracao').count() == 1
    assert post(client, 'inicio-plano', objetivo='Nova forma', compromisso='Praticarei', assumir='sim').status_code == 200
    assert client.get(reverse('inicio-envio')).status_code == 200
    assert situacao(PESSOA, SITE)['atual']['ordem'] == 2


def test_declaracao_antiga_supre_item_pronto_sem_publicar_arquivo(client, monkeypatch):
    assert post(client, 'inicio-motivo', motivo='ugc').status_code == 200
    assert post(client, 'inicio-plano', objetivo='Peça antiga', compromisso='Vou terminar', assumir='sim').status_code == 200
    jornada = JornadaPessoal.objects.get()
    jornada.declaracoes = {'2': '2026-10-01T10:00:00-03:00'}
    jornada.save(update_fields=['declaracoes'])
    inventario = client.get(reverse('inventario'), HTTP_COOKIE='meshcraft_sessao=A').json()
    assert inventario['inicio']['item_pronto'] is True
    assert client.get(reverse('inicio-envio')).status_code == 200
    assert post(client, 'inicio-envio', arquivo=arquivo()).status_code == 200
    anexo = AnexoDaJornada.objects.get()
    url = reverse('arquivo-inventario', args=[anexo.id])
    assert client.get(url, HTTP_COOKIE='meshcraft_sessao=A').status_code == 200
    monkeypatch.setattr('apps.core.inventario._sessao', lambda cookie: {'autenticado': True, 'id': 'outra-aluna'})
    assert client.get(url, HTTP_COOKIE='meshcraft_sessao=B').status_code == 404


def test_xp_real_por_tarefa_uma_vez_e_bonus_amarela_separado(client):
    configurar_faixas(SITE)
    rascunho = post(client, 'inicio-motivo', motivo='ugc', concluir='nao')
    assert rascunho.status_code == 200 and 'conquista_url' not in rascunho.json()
    assert client.get(reverse('inicio-objetivo')).url == reverse('inicio-motivo')
    assert not LancamentoDeXP.objects.exists()

    motivo = post(client, 'inicio-motivo', motivo='ugc', concluir='sim')
    assert motivo.json()['conquista_xp'] == 100
    assert motivo.json()['conquista_xp_tarefa'] == 100
    assert client.get(motivo.json()['conquista_url']).context['conquista_xp'] == 100
    assert client.get(reverse('inicio-conquista', args=[1])).context['conquista_ja_recebida'] is True
    assert post(client, 'inicio-motivo', motivo='ugc', concluir='sim').json()['conquista_xp'] == 0

    plano = post(client, 'inicio-plano', objetivo='Uma peça', compromisso='Praticarei', assumir='sim')
    assert plano.json()['conquista_xp'] == 100
    assert post(client, 'inicio-item').json()['conquista_xp'] == 100
    assert post(client, 'inicio-item').json()['conquista_xp'] == 0

    envio = post(client, 'inicio-envio', arquivo=arquivo())
    assert envio.json()['conquista_xp_tarefa'] == 100
    assert envio.json()['conquista_xp_faixa'] == 5000
    assert envio.json()['conquista_xp'] == 5100
    celebracao = client.get(envio.json()['conquista_url'])
    assert celebracao.status_code == 200 and celebracao.context['conquista_xp'] == 5100
    assert celebracao.context['conquista_xp_faixa'] == 5000
    assert post(client, 'inicio-envio').json()['conquista_xp'] == 0
    assert PerfilJogador.objects.get(pessoa_id=PESSOA, site_id=SITE).xp_total == 5400
    assert sorted(LancamentoDeXP.objects.values_list('pontos', flat=True)) == [100, 100, 100, 100, 5000]


def test_bonus_de_faixa_ja_pago_nao_e_duplicado(client):
    configurar_faixas(SITE)
    assert post(client, 'inicio-motivo', motivo='ugc').status_code == 200
    assert post(client, 'inicio-plano', objetivo='Uma peça', compromisso='Praticarei', assumir='sim').status_code == 200
    assert post(client, 'inicio-item').status_code == 200
    assert conceder_faixas(PESSOA, SITE, [2]) == 5000
    envio = post(client, 'inicio-envio', arquivo=arquivo())
    assert envio.json()['conquista_xp_tarefa'] == 100
    assert envio.json()['conquista_xp_faixa'] == 0
    assert envio.json()['conquista_xp'] == 100
    assert PerfilJogador.objects.get(pessoa_id=PESSOA, site_id=SITE).xp_total == 5400


def test_regra_inativa_nao_anuncia_xp_inexistente(client):
    configurar_tarefas(SITE)
    RegraDePontuacao.objects.filter(site_id=SITE, slug='bonus-inicio-etapa-1').update(ativa=False)
    resposta = post(client, 'inicio-motivo', motivo='ugc')
    assert resposta.status_code == 200 and resposta.json()['conquista_xp'] == 0
    celebracao = client.get(resposta.json()['conquista_url'])
    assert celebracao.context['conquista_sem_credito'] is True
    assert celebracao.context['conquista_xp'] == 0
    assert not LancamentoDeXP.objects.exists()


def test_nova_versao_apos_conclusao_avanca_revisao_sem_duplicar_declaracao(client):
    assert post(client, 'inicio-motivo', motivo='ugc').status_code == 200
    assert post(client, 'inicio-plano', objetivo='Primeira forma', compromisso='Praticarei', assumir='sim').status_code == 200
    assert post(client, 'inicio-item').status_code == 200
    assert post(client, 'inicio-envio', arquivo=arquivo()).status_code == 200
    revisao = JornadaPessoal.objects.get().revisao
    outro = SimpleUploadedFile('nova-versao.obj', b'v 0 0 0\nv 2 0 0\nv 0 2 0\nf 1 2 3\n')
    resposta = post(client, 'inicio-envio', arquivo=outro)
    assert resposta.status_code == 200 and resposta.json()['revisao'] == revisao + 1
    assert AnexoDaJornada.objects.count() == 2
    assert RegistroDaJornada.objects.filter(acao='declaracao').count() == 1
    atrasado = client.post(reverse('inventario'),
                           {'acao': 'inicio-envio', 'revisao': revisao},
                           HTTP_COOKIE='meshcraft_sessao=A')
    assert atrasado.status_code == 400


def test_comprovante_adulterado_ou_de_outra_conta_nao_anuncia_credito(client, monkeypatch):
    resposta = post(client, 'inicio-motivo', motivo='ugc')
    url = resposta.json()['conquista_url']
    assert resposta.json()['conquista_xp'] == 100
    antes = LancamentoDeXP.objects.count()
    assert client.get(url).context['conquista_xp'] == 100
    assert client.get(url).context['conquista_xp'] == 100
    assert LancamentoDeXP.objects.count() == antes

    adulterado = url[:-1] + ('A' if url[-1] != 'A' else 'B')
    invalido = client.get(adulterado)
    assert invalido.context['conquista_xp'] == 0
    assert invalido.context['conquista_ja_recebida'] is True

    from apps.core.perfil import perfil_de
    perfil_de('outra-aluna', SITE)
    JornadaPessoal.objects.create(pessoa_id='outra-aluna', site_id=SITE, inicio={'motivo': 'jogo'})
    monkeypatch.setattr('apps.core.views.quem_e', lambda request: 'outra-aluna')
    outra = client.get(url)
    assert outra.status_code == 200 and outra.context['conquista_xp'] == 0
    assert outra.context['conquista_sem_credito'] is True
    assert LancamentoDeXP.objects.count() == antes
