import json
import uuid
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.core import signing
from django.http import Http404
from django.test import RequestFactory
from django.utils import timezone

from apps.atendimento import caixa, contexto, escala, gestao, medicao, service, textos_fixos, views
from apps.atendimento.models import AgendaDoProduto, Assunto, Conversa, Mensagem, Reabertura, ConsumoDoAtendimento

pytestmark = pytest.mark.django_db
SID = 'suporte-escala-teste'


@pytest.fixture
def assunto(monkeypatch):
    service.config(SID)
    monkeypatch.setattr(views, 'site', lambda r: SID)
    monkeypatch.setattr(gestao, 'identidade_atendente', lambda r: ('equipe-1', 'Equipe'))
    monkeypatch.setattr(contexto, 'consultar', lambda c: {'crm': {}, 'agenda': [], 'catalogo': [], 'atualizado_em_texto': 'hoje'})
    monkeypatch.setattr(service, 'orcamento', lambda c: None)
    monkeypatch.setattr(medicao, 'alunos_ativos', lambda *a: 20)
    return Assunto.objects.get(site_id=SID, nome='Site')


def criar(assunto, texto='Olá', **kwargs):
    c = Conversa.objects.create(site_id=assunto.site_id, assunto=assunto, pessoa_id=kwargs.pop('pessoa_id', uuid.uuid4().hex), **kwargs)
    escala.classificar(c, texto)
    c.save()
    Mensagem.objects.create(conversa=c, referencia='pergunta', autor='aluno', texto=texto, tipo=c.tipo)
    return c


@pytest.mark.parametrize('tipo,texto', [
    (1, 'Quando começa o desafio?'), (2, 'Esqueci minha senha'), (3, 'Onde está a aula 3?'),
    (4, 'Não recebi o acesso'), (5, 'Meu pagamento passou?'), (6, 'Meu Pix expirou'),
    (7, 'Cartão recusado'), (8, 'Paguei e não liberou'), (9, 'Como subo de faixa?'),
    (10, 'Como exportar no Blender?'), (11, 'Tem curso avançado?'), (12, 'O vídeo não abre'),
    (13, 'Quero reembolso'), (14, 'Vou no Procon'), (15, 'Apaguem meus dados'), (16, 'Olá'),
])
def test_classifica_16_tipos_sem_ia(assunto, monkeypatch, tipo, texto):
    monkeypatch.setattr(service.modelo, 'responder', lambda **kw: pytest.fail('classificação chamou IA'))
    c = criar(assunto, texto)
    assert c.tipo == tipo
    if tipo in (13, 14, 15):
        assert c.cor == 'vermelho' and c.prioridade == 'alta'


def test_cobrar_nunca_verde_e_data_sem_produto_fica_amarela(assunto):
    assert criar(assunto, 'Gere um Pix novo').cor == 'vermelho'
    assert criar(assunto, 'Quando começa o desafio?').cor == 'amarelo'


@pytest.mark.parametrize('texto', ['Quando começa o desafio?', 'Esqueci minha senha', 'Onde está a aula?',
    'Não recebi o acesso', 'Meu pagamento passou?', 'Cartão recusado', 'Como subo de faixa?', 'Olá'])
def test_rascunhos_fixos_orcamento_zero_sem_envio(assunto, monkeypatch, texto):
    monkeypatch.setattr(service.modelo, 'responder', lambda **kw: pytest.fail('texto fixo chamou IA'))
    c = criar(assunto, texto)
    d = contexto.preparar(c)
    assert d['resposta'] and d['fixo']
    assert c.mensagens.count() == 1


def test_ensaio_200_30_em_um_clique_zero_ia_e_repeticao_idempotente(assunto, monkeypatch):
    monkeypatch.setattr(service.modelo, 'responder', lambda **kw: pytest.fail('lote chamou IA'))
    AgendaDoProduto.objects.create(site_id=SID, produto_id='evento-a', produto_nome='Evento A', inicio=timezone.now()+timedelta(days=1))
    for n in range(200):
        criar(assunto, 'Quando começa o desafio?' if n < 30 else 'Minha demanda individual '+str(n),
            interesse={'produto_id': 'evento-a', 'nome': 'Evento A'})
    grupos = caixa.grupos(SID, 'equipe-1')
    assert len(grupos) == 1 and len(grupos[0]['conversas']) == 30
    assert not Mensagem.objects.filter(autor='equipe').exists()
    g = grupos[0]
    req = RequestFactory().post('/atendimento/decisoes/', {'lote': g['token'], 'tempo_token': g['tempo_token']})
    req.admin = {'id': 'equipe-1', 'nome': 'Equipe'}
    assert caixa.caixa(req).status_code == 302
    assert Mensagem.objects.filter(autor='equipe', texto=g['texto']).count() == 30
    assert caixa.caixa(req).status_code == 302
    assert Mensagem.objects.filter(autor='equipe').count() == 30
    assert all(m.tempo_humano_seg is not None for m in Mensagem.objects.filter(autor='equipe'))


@pytest.mark.parametrize('mudanca', ['mensagem', 'agenda', 'responsavel', 'produto', 'estado'])
def test_lote_mudado_recusa_todos(assunto, mudanca):
    agenda = AgendaDoProduto.objects.create(site_id=SID, produto_id='evento-a', produto_nome='Evento A', inicio=timezone.now())
    for n in range(2):
        c = criar(assunto, 'Quando começa o desafio?', interesse={'produto_id': 'evento-a'})
    g = caixa.grupos(SID, 'equipe-1')[0]
    if mudanca == 'mensagem':
        Mensagem.objects.create(conversa=c, referencia='nova', autor='aluno', texto='Quero reembolso')
    elif mudanca == 'agenda':
        agenda.inicio += timedelta(days=1); agenda.save()
    else:
        campo, valor = {'responsavel': ('atendente_id', 'outro'), 'produto': ('interesse', {'produto_id': 'evento-b'}), 'estado': ('estado', 'encerrado')}[mudanca]
        setattr(c, campo, valor); c.save()
    with pytest.raises(ValueError):
        caixa.aprovar(SID, 'equipe-1', 'Equipe', g['token'], g['tempo_token'])
    assert not Mensagem.objects.filter(autor='equipe').exists()


def test_lote_isola_sites_responsavel_vermelhos_e_exige_sessao(assunto):
    criar(assunto)
    criar(assunto, 'Olá', atendente_id='outra-equipe')
    criar(assunto, 'Quero reembolso')
    outro = Assunto.objects.create(site_id='outro-site', nome='Site')
    criar(outro)
    g = caixa.grupos(SID, 'equipe-1')[0]
    assert len(g['conversas']) == 1
    with pytest.raises(ValueError):
        caixa.aprovar('outro-site', 'equipe-1', 'Equipe', g['token'], g['tempo_token'])
    with pytest.raises(ValueError):
        caixa.aprovar(SID, 'outra-equipe', 'Equipe', g['token'], g['tempo_token'])
    with pytest.raises(ValueError):
        caixa.aprovar(SID, 'equipe-1', 'Equipe', g['token']+'alterado', g['tempo_token'])
    with pytest.raises(Http404):
        caixa.caixa(RequestFactory().get('/atendimento/decisoes/'))


def test_recebimento_nao_conta_como_resposta_e_nao_impede_lote(assunto):
    c = criar(assunto)
    service.encaminhar(c)
    assert not service.avaliacao_disponivel(c)
    assert len(caixa.grupos(SID, 'equipe-1')) == 1


def test_reabertura_preserva_rodada_resolucao_e_nota(assunto):
    c = criar(assunto)
    c.primeira_resposta_em = timezone.now()
    c.avaliacao = 5
    escala.encerrar(c, resolvido=True); c.save()
    escala.reabrir(c, 'nova mensagem', c.pessoa_id); c.save()
    assert c.rodada == 2 and c.prioridade == 'alta' and c.resolvida_em is None
    r = Reabertura.objects.get(conversa=c)
    assert r.anterior['avaliacao'] == 5 and r.anterior['resolucao'] == 'confirmada'
    assert r.anterior['primeira_resposta_em']
    assert not escala.reabrir(c, 'repetido', c.pessoa_id)
    assert c.reaberturas.count() == 1


def test_inferencia_de_7_dias_nao_resolve_silencio_nem_retorno(assunto):
    c = criar(assunto)
    c.primeira_resposta_em = timezone.now()-timedelta(days=9)
    c.encerrada_em = timezone.now()-timedelta(days=8)
    c.estado='encerrado'; c.motivo_encerramento='equipe'; c.save()
    Mensagem.objects.filter(conversa=c).update(criada_em=timezone.now()-timedelta(days=10))
    silencio = criar(assunto)
    Conversa.objects.filter(pk=silencio.pk).update(estado='encerrado',encerrada_em=c.encerrada_em,
        primeira_resposta_em=c.primeira_resposta_em,motivo_encerramento='sem_resposta')
    escala.manutencao()
    c.refresh_from_db(); silencio.refresh_from_db()
    assert c.resolucao == 'sem_retorno_7d' and silencio.resolvida_em is None


def test_medicao_com_dados_fixos_e_rodada_anterior(assunto):
    c = criar(assunto)
    inicio = timezone.now()-timedelta(days=10)
    Conversa.objects.filter(pk=c.pk).update(criada_em=inicio)
    c.refresh_from_db()
    c.primeira_resposta_em=inicio+timedelta(minutes=10)
    c.encerrada_em=inicio+timedelta(minutes=20)
    c.resolvida_em=c.encerrada_em; c.resolucao='confirmada'; c.estado='encerrado'; c.avaliacao=4; c.save()
    escala.reabrir(c,'não resolveu',c.pessoa_id); c.save()
    Mensagem.objects.create(conversa=c,referencia='humana',autor='equipe',texto='Conferido',tipo=16,tempo_humano_seg=120)
    d = medicao.calcular(SID,inicio-timedelta(seconds=1))
    assert d['total'] == 2 and d['confirmadas'] == 1 and d['reaberturas'] == 1
    assert d['por_tipo'][0]['tempo_humano_min'] == 2
    assert d['por_tipo'][0]['primeira_resposta_min'] == 10
    assert d['por_tipo'][0]['resolucao_min'] == 20
    assert d['por_tipo'][0]['satisfacao'] == 4
    assert d['pedidos_por_100'] == 10


def test_custo_desconhecido_fica_associado_sem_chamada_real(assunto,monkeypatch):
    from apps.agentes.models import Consumo
    c = criar(assunto)
    def chamar(**kw):
        Consumo.objects.create(modelo='teste',origem='suporte',custo_estimado_usd=Decimal('0.01'),desconhecido=True)
        raise RuntimeError('simulação de resposta desconhecida')
    monkeypatch.setattr(service.modelo,'responder',chamar)
    with pytest.raises(RuntimeError):
        escala.chamar_modelo(c)
    assert ConsumoDoAtendimento.objects.filter(conversa=c).count() == 1
    d = medicao.calcular(SID,timezone.now()-timedelta(days=1))
    assert d['custo_usd'] == Decimal('0.01') and d['custos_desconhecidos'] == 1


def test_telas_novas_renderizam_e_privacidade_do_aluno(assunto):
    c = criar(assunto)
    request = RequestFactory().get('/atendimento/decisoes/')
    request.admin={'id':'equipe-1','nome':'Equipe'}
    html = caixa.caixa(request).content.decode()
    assert 'Caixa de decisões' in html and 'Aprovar e enviar' in html
    c.sugestao={'contexto':{'crm':{'email':'privado@example.test'}},'resposta':'rascunho interno'}
    bruto = json.dumps(views.serializar(c))
    assert 'rascunho interno' not in bruto and 'privado@example.test' not in bruto


def test_tempo_humano_soma_respostas_por_pedido(assunto):
    c = criar(assunto)
    for n in range(2):
        Mensagem.objects.create(conversa=c, referencia=str(n), autor='equipe', texto='Resposta',
            tipo=16, rodada=1, tempo_humano_seg=120)
    d = medicao.calcular(SID, timezone.now()-timedelta(days=1))
    assert d['por_tipo'][0]['tempo_humano_min'] == 4
    assert d['por_tipo'][0]['tempo_humano_amostra'] == 1


def test_lote_personaliza_sem_ia_e_separa_produto_e_pergunta(assunto, monkeypatch):
    monkeypatch.setattr(service.modelo, 'responder', lambda **kw: pytest.fail('lote chamou IA'))
    for produto in ('a', 'b'):
        AgendaDoProduto.objects.create(site_id=SID, produto_id=produto, produto_nome=produto, inicio=timezone.now())
    for nome in ('Ana Exemplo', 'Bruno Exemplo', 'Carla Exemplo', 'Davi Exemplo', 'Eva Exemplo'):
        criar(assunto, 'Quando começa o desafio?', nome=nome, interesse={'produto_id': 'a'})
    criar(assunto, 'Quando começa o desafio?', interesse={'produto_id': 'b'})
    criar(assunto, 'Qual dia começa o desafio?', interesse={'produto_id': 'a'})
    grupos = caixa.grupos(SID, 'equipe-1')
    assert sorted(len(g['conversas']) for g in grupos) == [1, 1, 5]
    g = next(g for g in grupos if len(g['conversas']) == 5)
    assert caixa.aprovar(SID, 'equipe-1', 'Equipe', g['token'], g['tempo_token']) == 5
    for d in g['destinatarios']:
        enviada = d['conversa'].mensagens.get(autor='equipe')
        assert enviada.texto == d['texto']
        assert enviada.texto.startswith(d['conversa'].nome.split()[0]+',')


def test_base_corrigida_invalida_lote_e_nao_chama_ia(assunto, monkeypatch):
    from apps.atendimento.models import Conhecimento
    c = criar(assunto, 'Como exportar no Blender?')
    base = Conhecimento.objects.create(site_id=SID, assunto=assunto, pergunta='Como exportar no Blender?', resposta='Use Arquivo > Exportar.')
    monkeypatch.setattr(service.modelo, 'responder', lambda **kw: pytest.fail('base exata chamou IA'))
    assert contexto.preparar(c)['resposta'] == base.resposta
    c = criar(assunto, 'Onde está a aula?')
    base = Conhecimento.objects.create(site_id=SID, assunto=assunto, pergunta='Onde está a aula?', resposta='Abra a área de cursos.')
    g = caixa.grupos(SID, 'equipe-1')[0]
    base.revisao += 1; base.resposta='Confira o curso na sua área.'; base.save()
    with pytest.raises(ValueError):
        caixa.aprovar(SID, 'equipe-1', 'Equipe', g['token'], g['tempo_token'])
    assert not Mensagem.objects.filter(autor='equipe').exists()


def test_prioridade_prazo_e_classificacao_antiga_nao_sobrescreve_nova(assunto):
    normal = criar(assunto)
    irritado = criar(assunto, 'Que absurdo! O vídeo não abre')
    comprador = criar(assunto)
    escala.registrar_classificacao(comprador, 'Olá', {'crm': {'compras': [{'pago_em_iso': timezone.now().isoformat()}]}})
    vermelho = criar(assunto, 'Quero reembolso')
    atrasado = criar(assunto)
    Mensagem.objects.filter(conversa=atrasado).update(criada_em=timezone.now()-timedelta(hours=25))
    request = RequestFactory().get('/atendimento/')
    request.admin={'id':'equipe-1','nome':'Equipe'}
    linhas = gestao.contexto_fila(request, SID)['conversas']
    assert [c.pk for c in linhas] == [vermelho.pk, atrasado.pk, irritado.pk, comprador.pk, normal.pk]
    assert linhas[1].vencido
    Mensagem.objects.create(conversa=normal, referencia='nova', autor='aluno', texto='Quero reembolso')
    escala.registrar_classificacao(normal, 'Quero reembolso')
    escala.registrar_classificacao(normal, 'Olá')
    normal.refresh_from_db()
    assert normal.cor == 'vermelho'


@pytest.mark.parametrize('texto', ['Quero reembolso', 'Vou no Procon', 'Apaguem meus dados'])
def test_vermelho_nunca_recebe_resposta_automatica(assunto, monkeypatch, texto):
    assunto.modo='conversa'; assunto.save()
    c = criar(assunto, texto, estado='robo', processar=True)
    monkeypatch.setattr(service.modelo, 'responder', lambda **kw: pytest.fail('vermelho chamou IA'))
    assert service.processar_uma()
    c.refresh_from_db()
    assert c.sugestao['resposta'] and c.estado == 'aguardando'
    assert not c.mensagens.filter(referencia__startswith='auto-').exists()


def test_resolucao_sim_nao_e_nova_mensagem_preservam_historico(assunto):
    c = criar(assunto, pessoa_id='aluno-api')
    identidade = {'autenticado': True, 'id': c.pessoa_id, 'nome_exibido': 'Aluno de teste'}
    def acao(nome, **extra):
        req = RequestFactory().post('/interno/atendimento-aluno/', json.dumps(
            {'acao': nome, 'conversa': str(c.pk), **extra}), content_type='application/json')
        return views._conversar(req, identidade)
    assert acao('resolvido').status_code == 422
    m = Mensagem.objects.create(conversa=c, referencia='resposta', autor='equipe', texto='Resposta conferida.')
    c.primeira_resposta_em=m.criada_em
    escala.encerrar(c); c.save()
    assert acao('resolvido').status_code == 200
    c.refresh_from_db()
    assert c.resolucao == 'confirmada'
    assert acao('nao_resolvido').status_code == 200
    c.refresh_from_db()
    assert c.resolvida_em is None and c.rodada == 2 and c.prioridade == 'alta'
    assert c.reaberturas.get().anterior['resolucao'] == 'confirmada'
    Mensagem.objects.create(conversa=c, referencia='segunda-resposta', autor='equipe', texto='Outro esclarecimento.')
    escala.encerrar(c); c.save()
    assert acao('mensagem', referencia=uuid.uuid4().hex, texto='Ainda preciso de ajuda').status_code == 200
    c.refresh_from_db()
    assert c.rodada == 3 and c.reaberturas.count() == 2


def test_retorno_ou_nova_conversa_em_7_dias_nao_inventa_resolucao(assunto):
    c = criar(assunto)
    inicio = timezone.now()-timedelta(days=10)
    Conversa.objects.filter(pk=c.pk).update(criada_em=inicio, estado='encerrado',
        primeira_resposta_em=inicio+timedelta(hours=1), encerrada_em=inicio+timedelta(hours=2), motivo_encerramento='equipe')
    Mensagem.objects.filter(conversa=c).update(criada_em=inicio)
    nova = criar(assunto, pessoa_id=c.pessoa_id)
    Conversa.objects.filter(pk=nova.pk).update(criada_em=inicio+timedelta(days=2))
    escala.manutencao()
    c.refresh_from_db()
    assert c.resolvida_em is None
    d = medicao.calcular(SID, inicio-timedelta(seconds=1))
    assert d['retornos_7d'] == 1 and d['amostra_7d'] == 1 and d['taxa_retorno'] == 100
