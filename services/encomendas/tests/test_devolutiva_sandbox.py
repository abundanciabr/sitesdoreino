from datetime import timedelta
import importlib
from types import SimpleNamespace
import uuid

import pytest
from django.apps import apps
from django.db import connection
from django.urls import reverse
from django.utils import timezone

from apps.core import ia_sandbox, sessao
from apps.encomendas import sandbox, analises_sandbox as analises, devolutiva_sandbox as devolutiva
from apps.encomendas.sandbox_models import (
    AnaliseEntregaSandbox, ArquivoSandbox, MensagemSandbox, ParticipacaoSandbox, RespostaSandbox,
)


@pytest.fixture
def p(db):
    projeto = sandbox.semear_projetos(site_id='TESTE-devolutiva')[0]
    return sandbox.aceitar(site_id=projeto.site_id, pessoa_id='TESTE-aluno',
                           projeto_id=projeto.pk, prazo_horas=24)


def enviar(p):
    arquivo = ArquivoSandbox.objects.create(site_id=p.site_id, participacao=p, nome='modelo.glb',
        chave=uuid.uuid4().hex, sha256='a' * 64, tamanho=100, mime='model/gltf-binary')
    return sandbox.entregar(site_id=p.site_id, participacao_id=p.pk,
                            pessoa_id=p.pessoa_id, arquivos=[arquivo.pk])


def resultado_incompleto(e):
    f = e.arquivos.get().analise
    f.estado = 'concluida'
    f.resultado = {'arquivos': [
        {'arquivo': 'modelo.glb', 'estado': 'nao_examinado', 'medidas': {},
         'falha': 'Não foi possível examinar o modelo.', 'imagens': []},
    ]}
    f.save()
    return f


def concluir(e, monkeypatch):
    resultado_incompleto(e)
    monkeypatch.setattr(ia_sandbox, 'avaliar_entrega', lambda *args: {
        'requisitos': [{'id': '1', 'encontrado': False, 'nao_encontrado': False,
                        'inconclusivo': True, 'evidencias': ['modelo.glb não examinado']}],
        'avaliacao': {'resultado': 'inconclusiva', 'justificativa': 'Modelo não examinado.'},
        'interpretacao_visual_ia': 'Sem imagem examinável.'})
    analises.processar_entrega(e.analise.pk)
    return AnaliseEntregaSandbox.objects.get(entrega=e)


def test_recebimento_imediato_e_resultado_incompleto_sem_depender_do_chat(p, monkeypatch):
    e = enviar(p)
    assert p.mensagens.filter(ator_id='analise-automatica').count() == 1
    assert 'entrou na fila' in p.mensagens.get().texto
    analises.preparar(e)
    assert p.mensagens.count() == 1
    a = concluir(e, monkeypatch)
    assert a.estado == 'concluida' and a.resultado['tem_falhas']
    assert a.resultado['requisitos'][0]['encontrado'] == ''
    assert 'Não foi possível verificar' in a.resultado['requisitos'][0]['inconclusivo']
    respostas = p.mensagens.filter(ator_id='analise-automatica')
    assert respostas.count() == 2
    assert respostas.filter(texto__contains='modelo.glb').exists()
    assert 'incompleta' in devolutiva.situacao(a)
    analises.processar_entrega(a.pk)
    devolutiva.conclusao(a)
    assert respostas.count() == 2
    p.refresh_from_db()
    assert p.status == 'entregue' and p.aprovado_em is None


def test_falha_ia_deixa_resposta_ao_aluno_e_tenta_novamente(p, monkeypatch):
    e = enviar(p)
    resultado_incompleto(e)
    def falhar(*args):
        raise RuntimeError('credencial-secreta-nao-exibir')
    monkeypatch.setattr(ia_sandbox, 'avaliar_entrega', falhar)
    analises.processar_entrega(e.analise.pk)
    a = AnaliseEntregaSandbox.objects.get(entrega=e)
    assert a.estado == 'falha_ia' and a.tentar_em > timezone.now()
    assert p.mensagens.filter(texto__contains='encontrou uma falha').count() == 1
    assert not p.mensagens.filter(texto__contains='credencial-secreta').exists()


def test_respostas_esgotadas_e_adiadas_nao_ocupam_o_lote(p, monkeypatch):
    for i in range(12):
        RespostaSandbox.objects.create(site_id=p.site_id, participacao=p, origem=f'falha:{i}',
            papel='ia', estado='falha', tentativas=3)
        RespostaSandbox.objects.create(site_id=p.site_id, participacao=p, origem=f'adiada:{i}',
            papel='ia', tentar_em=timezone.now() + timedelta(hours=1))
    mensagem = MensagemSandbox.objects.create(site_id=p.site_id, participacao=p,
        ator_id=p.pessoa_id, papel='aluno', texto='Pergunta do aluno')
    pronta = ia_sandbox.enfileirar(p, 'mensagem:'+str(mensagem.pk), 'ia')
    chamadas = []
    monkeypatch.setattr(ia_sandbox, 'processar_resposta', chamadas.append)
    ia_sandbox.rodada_respostas()
    assert chamadas == [pronta.pk]


def test_analises_adiadas_nao_ocupam_o_lote(p, monkeypatch):
    from apps.encomendas.sandbox_models import EntregaSandbox
    for i in range(1, 12):
        e = EntregaSandbox.objects.create(site_id=p.site_id, participacao=p, versao=i)
        AnaliseEntregaSandbox.objects.create(site_id=p.site_id, entrega=e, estado='falha_ia',
            tentar_em=timezone.now() + timedelta(hours=1))
    e = EntregaSandbox.objects.create(site_id=p.site_id, participacao=p, versao=12)
    pronta = AnaliseEntregaSandbox.objects.create(site_id=p.site_id, entrega=e)
    chamadas = []
    monkeypatch.setattr(analises, 'processar_entrega', chamadas.append)
    analises.rodada()
    assert chamadas == [pronta.pk]


def test_nova_versao_apos_leitura_incompleta_preserva_original(p, monkeypatch):
    e = enviar(p)
    p.refresh_from_db()
    assert not sandbox.pode_entregar(p)
    concluir(e, monkeypatch)
    p.prazo_ate = timezone.now() - timedelta(hours=2)
    p.save(update_fields=['prazo_ate'])
    assert sandbox.pode_entregar(p)
    e2 = enviar(p)
    p.refresh_from_db()
    assert p.atraso_em is None
    assert e2.versao == 2 and e.arquivos.count() == 1
    assert e2.analise.estado == 'na_fila'
    assert not sandbox.pode_entregar(p)
    p.status = 'aprovado'
    assert not sandbox.pode_entregar(p)


def test_tela_explicita_incompleta_campos_legados_e_reenvio(p, client, monkeypatch):
    e = enviar(p)
    a = concluir(e, monkeypatch)
    a.resultado['requisitos'][0].update(encontrado='False', nao_encontrado='False', inconclusivo='True')
    a.save()
    monkeypatch.setattr(sessao, 'quem_e', lambda r: p.pessoa_id)
    monkeypatch.setattr(sessao, 'site_desta_instalacao', lambda: p.site_id)
    resposta = client.get(reverse('sandbox_trabalho', args=[p.pk]))
    html = resposta.content.decode()
    assert resposta.status_code == 200
    assert 'Análise incompleta' in html and 'id="entrega-form"' in html
    assert 'Análise automática</strong>' in html
    assert 'False' not in html and 'True' not in html
    assert 'Não foi possível verificar' in html
    monkeypatch.setattr(sessao, 'quem_e', lambda r: 'outro-aluno')
    monkeypatch.setenv('IDS_DO_PLANTAO', 'TESTE-equipe')
    assert client.get(reverse('sandbox_trabalho', args=[p.pk])).status_code == 404


def test_resposta_do_caso_indicado_unica_e_preservada_na_recuperacao(p, monkeypatch):
    modulo = importlib.import_module('apps.encomendas.migrations.0029_devolutiva_trabalho_64a163d4')
    ParticipacaoSandbox.objects.filter(pk=p.pk).update(id=modulo.TRABALHO)
    p.pk = uuid.UUID(modulo.TRABALHO)
    e = enviar(p)
    a = concluir(e, monkeypatch)
    # A migração trata um ZIP histórico com PDF, anterior aos formatos atuais.
    a.resultado['medidas_programas'] = [{'conteudo': {'arquivos': [
        {'arquivo': 'guia.pdf', 'estado': 'nao_examinado'},
    ]}}]
    a.save(update_fields=['resultado'])
    modulo.responder(apps, SimpleNamespace(connection=connection))
    modulo.responder(apps, SimpleNamespace(connection=connection))
    assert MensagemSandbox.objects.filter(participacao=p, texto__startswith='Revimos').count() == 1
    assert p.entregas.count() == 1 and e.arquivos.count() == 1
