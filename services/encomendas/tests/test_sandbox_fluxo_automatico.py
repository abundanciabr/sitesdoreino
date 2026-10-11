from copy import deepcopy
from types import SimpleNamespace
import importlib
import uuid

import pytest
from django.apps import apps
from django.db import connection
from django.urls import reverse

from apps.core import ia_sandbox, sessao
from apps.encomendas import sandbox, analises_sandbox as analises
from apps.encomendas.models import OutboxMarketplace, MovimentoMeshcoin
from apps.encomendas.sandbox_models import ArquivoSandbox, EntregaSandbox, AnaliseEntregaSandbox, MensagemSandbox, ParticipacaoSandbox

pytestmark = pytest.mark.django_db

@pytest.fixture
def p():
    projeto = sandbox.semear_projetos(site_id='TESTE-fluxo')[0]
    p = sandbox.aceitar(site_id=projeto.site_id, pessoa_id='TESTE-aluno', projeto_id=projeto.pk, prazo_horas=24)
    p.termos = {**p.termos, 'briefing': 'Uma malha', 'referencias': [], 'entregaveis': [], 'criterios': ''}
    p.save()
    return p

def enviar(p, teste=False):
    f = ArquivoSandbox.objects.create(site_id=p.site_id, participacao=p, nome='amostra.glb',
        chave=uuid.uuid4().hex, sha256='a'*64, tamanho=100, mime='model/gltf-binary')
    return sandbox.entregar(site_id=p.site_id, pessoa_id=p.pessoa_id, participacao_id=p.pk,
        arquivos=[f.pk], teste_mantenedor=teste)

def concluir(e, monkeypatch, resultado='atende', invalido=False, sem_decisao=False):
    f = e.arquivos.get().analise
    f.estado = 'falha' if invalido else 'concluida'
    f.falha = 'Arquivo inválido' if invalido else ''
    f.resultado = {'arquivos': [{'arquivo': 'amostra.glb', 'estado': f.estado, 'medidas': {'triangulos': 398}, 'imagens': []}]}
    f.save()
    resposta = {'requisitos': [{'id': '1', 'encontrado': 'Malha medida: 398 triângulos', 'nao_encontrado': '', 'inconclusivo': '', 'evidencias': ['amostra.glb']}],
        'interpretacao_visual_ia': 'Sem imagem fornecida.'}
    if not sem_decisao:
        resposta['avaliacao'] = {'resultado': resultado, 'justificativa': 'Evidência do arquivo desta versão.'}
    monkeypatch.setattr(ia_sandbox, 'avaliar_entrega', lambda *args: resposta)
    analises.processar_entrega(e.analise.pk)
    return AnaliseEntregaSandbox.objects.get(entrega=e)

def eventos():
    return OutboxMarketplace.objects.filter(event='encomendas.sandbox-trabalho-concluido')

def test_envio_emite_conquista_antes_da_analise_e_sem_mesh(p, monkeypatch):
    e = enviar(p)
    assert eventos().count() == 1
    assert eventos().get().payload['ocorrido_em'] == e.criada_em.isoformat()
    assert e.analise.estado == 'na_fila'
    concluir(e, monkeypatch)
    p.refresh_from_db()
    assert p.status == 'aprovado' and p.aprovado_por == 'analise-automatica'
    analises.processar_entrega(e.analise.pk)
    assert eventos().count() == 1 and not MovimentoMeshcoin.objects.exists()

def test_teste_preserva_aluno_status_credito_e_contexto(p, monkeypatch):
    original = enviar(p)
    a = concluir(original, monkeypatch, resultado='precisa_ajustes')
    antes = list(p.mensagens.values_list('pk', 'texto'))
    teste = enviar(p, teste=True)
    concluir(teste, monkeypatch)
    p.refresh_from_db()
    assert p.status == 'entregue' and p.aprovado_em is None
    assert sandbox.ultima_entrega_do_aluno(p).pk == original.pk
    assert ia_sandbox._retrato(p)['versao_atual'] == 1
    assert ia_sandbox._retrato(p, teste)['teste_mantenedor'] is True
    assert sandbox.pode_entregar(p)
    assert eventos().count() == 1
    assert all(p.mensagens.filter(pk=pk, texto=texto).exists() for pk, texto in antes)
    assert p.mensagens.filter(texto__contains='Teste do mantenedor:').exists()
    nova = enviar(p)
    assert eventos().count() == 2
    assert eventos().filter(payload__ocorrido_em=nova.criada_em.isoformat()).exists()

def test_teste_sem_entrega_original_nao_concede_xp(p, monkeypatch):
    e = enviar(p, teste=True)
    concluir(e, monkeypatch)
    p.refresh_from_db()
    assert p.status == 'em_producao' and not eventos().exists()
    assert sandbox.ultima_entrega_do_aluno(p) is None

def test_invalido_nao_vira_aprovacao_mesmo_com_resposta_incorreta(p, monkeypatch):
    e = enviar(p)
    a = concluir(e, monkeypatch, invalido=True)
    assert a.resultado['avaliacao']['resultado'] == 'inconclusiva'
    p.refresh_from_db()
    assert p.status == 'entregue' and sandbox.pode_entregar(p)
    assert p.mensagens.filter(texto__contains='Leitura incompleta').exists()

def test_sem_conclusao_fundamentada_responde_falha_e_reagenda(p, monkeypatch):
    e = enviar(p)
    a = concluir(e, monkeypatch, sem_decisao=True)
    assert a.estado == 'falha_ia' and a.tentar_em is not None
    assert p.mensagens.filter(texto__contains='encontrou uma falha').exists()

def test_reprocessar_legado_guarda_analise_e_mensagens(p, monkeypatch, settings, tmp_path):
    settings.MARKETPLACE_UPLOAD_ROOT = tmp_path
    e = enviar(p)
    a = concluir(e, monkeypatch, resultado='inconclusiva')
    a.resultado.pop('avaliacao')
    a.save()
    anterior = deepcopy(a.resultado)
    falas = list(p.mensagens.values_list('pk', 'texto'))
    analises.repetir(e)
    a.refresh_from_db()
    assert a.historico[0]['resultado'] == anterior
    assert a.historico[0]['medidas_programas'][0]['conteudo']['arquivos'][0]['medidas']['triangulos'] == 398
    concluir(e, monkeypatch)
    assert all(p.mensagens.filter(pk=pk, texto=texto).exists() for pk, texto in falas)
    assert p.mensagens.filter(texto__startswith='Avaliação automática da versão 1:').count() == 2
    assert eventos().count() == 1

def test_reanalise_antiga_nao_aprova_entrega_mais_nova(p, monkeypatch):
    original = enviar(p)
    concluir(original, monkeypatch, resultado='precisa_ajustes')
    nova = enviar(p)
    a = original.analise
    a.estado = 'na_fila'
    a.save()
    concluir(original, monkeypatch)
    p.refresh_from_db()
    assert p.status == 'entregue' and nova.analise.estado == 'na_fila'

def test_so_equipe_pode_identificar_novo_teste(p, client, monkeypatch):
    monkeypatch.setattr(sessao, 'quem_e', lambda r: p.pessoa_id)
    monkeypatch.setattr(sessao, 'site_desta_instalacao', lambda: p.site_id)
    monkeypatch.setenv('IDS_DO_PLANTAO', 'TESTE-equipe')
    url = reverse('sandbox_entregar', args=[p.pk])
    assert client.post(url, {'teste_mantenedor': 'sim'}).status_code == 404
    assert not p.entregas.exists()

def test_migracao_identifica_somente_testes_confirmados_sem_reescrever(p):
    ParticipacaoSandbox.objects.filter(pk=p.pk).update(id='64a163d4-23aa-483d-a4c5-155f254225aa')
    p.pk = uuid.UUID('64a163d4-23aa-483d-a4c5-155f254225aa')
    for n in range(1, 8):
        EntregaSandbox.objects.create(site_id=p.site_id, participacao=p, versao=n, comentario=f'Original {n}')
    mig = importlib.import_module('apps.encomendas.migrations.0030_avaliacao_automatica_e_testes')
    mig.identificar_testes(apps, SimpleNamespace(connection=connection))
    assert list(p.entregas.filter(teste_mantenedor=True).order_by('versao').values_list('versao', flat=True)) == [2, 3, 4, 5, 6]
    assert p.entregas.count() == 7
    assert list(p.entregas.order_by('versao').values_list('comentario', flat=True)) == [f'Original {n}' for n in range(1, 8)]

    mig.registrar_envio_original(apps, SimpleNamespace(connection=connection))
    mig.registrar_envio_original(apps, SimpleNamespace(connection=connection))
    assert eventos().count() == 1
    assert eventos().get().payload['ocorrido_em'] == p.entregas.get(versao=1).criada_em.isoformat()


def test_envio_novo_nao_e_suprimido_por_conclusao_anterior_ao_reinicio(p):
    from datetime import timedelta
    from django.utils import timezone
    from apps.encomendas import faixas_eventos
    antiga = timezone.now() - timedelta(days=7)
    faixas_eventos.sandbox_trabalho_concluido(p, ocorrido_em=antiga)
    e = enviar(p)
    faixas_eventos.sandbox_trabalho_concluido(p, ocorrido_em=e.criada_em, entrega=e)
    assert eventos().count() == 2
    assert eventos().filter(payload__ocorrido_em=antiga.isoformat()).count() == 1
    assert eventos().filter(payload__ocorrido_em=e.criada_em.isoformat()).count() == 1
