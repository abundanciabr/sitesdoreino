import hashlib
import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.core import sessao, telas_sandbox, ia_sandbox
from apps.encomendas import sandbox, limpeza_sandbox, analises_sandbox, devolutiva_sandbox
from apps.encomendas.models import OutboxMarketplace
from apps.encomendas.sandbox_models import (ParticipacaoSandbox, EntregaSandbox, ArquivoSandbox,
    MensagemSandbox, RespostaSandbox, AnaliseArquivoSandbox, AnaliseEntregaSandbox, MovimentoMeshcoin)


@pytest.fixture
def trabalho(db, monkeypatch, settings, tmp_path):
    atual = {'id': 'aluno', 'site': 'escola-a'}
    monkeypatch.setattr(sessao, 'quem_e', lambda request: atual['id'])
    monkeypatch.setattr(sessao, 'site_desta_instalacao', lambda: atual['site'])
    monkeypatch.setenv('IDS_DO_PLANTAO', 'admin')
    settings.MARKETPLACE_UPLOAD_ROOT = tmp_path
    projeto = sandbox.semear_projetos(site_id='escola-a')[0]
    p = sandbox.aceitar(site_id='escola-a', pessoa_id='aluno', projeto_id=projeto.pk, prazo_horas=24)
    entrega = EntregaSandbox.objects.create(site_id=p.site_id, participacao=p, versao=1, teste_mantenedor=False)
    chave = uuid.uuid4().hex
    conteudo = b'arquivo descartavel do teste automatizado'
    (tmp_path / chave).write_bytes(conteudo)
    arquivo = ArquivoSandbox.objects.create(site_id=p.site_id, participacao=p, entrega=entrega,
        nome='teste.glb', chave=chave, sha256=hashlib.sha256(conteudo).hexdigest(), tamanho=len(conteudo), mime='model/gltf-binary')
    AnaliseArquivoSandbox.objects.create(site_id=p.site_id, arquivo=arquivo, chave_cache='a'*64, sha256=arquivo.sha256, estado='concluida')
    analise = AnaliseEntregaSandbox.objects.create(site_id=p.site_id, entrega=entrega, estado='na_fila')
    msg = MensagemSandbox.objects.create(site_id=p.site_id, participacao=p, ator_id='aluno', papel='aluno', texto='Teste')
    RespostaSandbox.objects.create(site_id=p.site_id, participacao=p, origem='mensagem:'+str(msg.pk), papel='ia')
    p.status = 'entregue'
    p.prazo_ate = timezone.now() - timedelta(days=1)
    p.atraso_em = timezone.now()
    p.mensagens_recolhidas_ate = timezone.now()
    p.save()
    return p, atual, arquivo, analise


def etapa(client, p, resposta=None):
    caminho = reverse('sandbox_limpar_testes', args=[p.pk])
    if resposta is None:
        return client.get(caminho)
    return client.post(caminho, {'etapa': resposta.context['etapa'], 'confirmacao': resposta.context['confirmacao']})


def test_duas_confirmacoes_apagam_so_este_trabalho_sem_backup(client, trabalho, tmp_path, django_capture_on_commit_callbacks):
    p, _, arquivo, analise = trabalho
    outro = sandbox.aceitar(site_id=p.site_id, pessoa_id='outra-pessoa', projeto_id=p.projeto_id, prazo_horas=48)
    fala_outro = MensagemSandbox.objects.create(site_id=p.site_id, participacao=outro, ator_id='outra-pessoa', papel='aluno', texto='Preservar')
    MovimentoMeshcoin.objects.create(site_id=p.site_id, participacao=p, pessoa_id=p.pessoa_id, valor=Decimal('7'), aprovador_id='historico')
    eventos_antes = list(OutboxMarketplace.objects.values())
    aceite, termos, prazo = p.aceite_em, p.termos, p.prazo_ate
    primeiro = etapa(client, p)
    assert primeiro.status_code == 200 and primeiro.context['etapa'] == 1
    assert p.entregas.count() == 1 and p.mensagens.count() == 1
    segundo = etapa(client, p, primeiro)
    assert segundo.status_code == 200 and segundo.context['etapa'] == 2
    assert p.entregas.count() == 1 and (tmp_path/arquivo.chave).exists()
    with django_capture_on_commit_callbacks(execute=True):
        final = etapa(client, p, segundo)
    assert final.status_code == 302
    for model, filtro in [(EntregaSandbox, {'participacao':p}), (ArquivoSandbox, {'participacao':p}),
                         (MensagemSandbox, {'participacao':p}), (RespostaSandbox, {'participacao':p}),
                         (AnaliseEntregaSandbox, {'pk':analise.pk}), (AnaliseArquivoSandbox, {'arquivo_id':arquivo.pk})]:
        assert not model.objects.filter(**filtro).exists()
    assert list(tmp_path.iterdir()) == []  # Nenhuma cópia, lixeira ou arquivo original.
    assert MensagemSandbox.objects.filter(pk=fala_outro.pk).exists()
    assert list(OutboxMarketplace.objects.values()) == eventos_antes
    assert MovimentoMeshcoin.objects.get(participacao=p).valor == Decimal('7')
    p.refresh_from_db()
    assert p.status == 'em_producao' and p.atraso_em is None and p.mensagens_recolhidas_ate is None
    assert p.aceite_em == aceite and p.termos == termos and p.prazo_ate > prazo
    assert 23.9 < (p.prazo_ate-timezone.now()).total_seconds()/3600 <= 24
    assert client.get(reverse('sandbox_baixar', args=[arquivo.pk])).status_code == 404
    pagina = client.get(reverse('sandbox_trabalho', args=[p.pk])).content.decode()
    assert 'Nenhum arquivo enviado ainda.' in pagina and 'A primeira entrega aparecerá aqui.' in pagina
    assert 'A conversa começa aqui.' in pagina and 'Limpar testes' in pagina
    assert etapa(client, p, segundo).status_code == 400  # Repetir a requisição não apaga o teste seguinte.


@pytest.mark.parametrize('pessoa,site,status', [(None,'escola-a',302),('outro','escola-a',404),('aluno','escola-b',404)])
def test_outras_pessoas_e_sites_nao_apagam(client, trabalho, pessoa, site, status):
    p, atual, _, _ = trabalho
    atual.update(id=pessoa, site=site)
    assert etapa(client,p).status_code == status
    assert client.post(reverse('sandbox_limpar_testes',args=[p.pk]), {'etapa':2}).status_code == status
    assert p.entregas.count() == 1


def test_admin_pode_abrir_as_confirmacoes(client, trabalho):
    p, atual, _, _ = trabalho
    atual['id']='admin'
    assert etapa(client,p).status_code == 200


def test_nao_pode_pular_etapa_nem_reutilizar_token_de_outra_pessoa(client, trabalho):
    p, atual, _, _ = trabalho
    primeira=etapa(client,p)
    caminho=reverse('sandbox_limpar_testes',args=[p.pk])
    token=primeira.context['confirmacao']
    assert client.post(caminho, {'etapa':2,'confirmacao':token}).status_code == 400
    assert client.post(caminho, {'etapa':2,'confirmacao':'inventado'}).status_code == 400
    atual['id']='admin'
    assert client.post(caminho, {'etapa':1,'confirmacao':token}).status_code == 400
    assert p.entregas.count() == 1


def test_csrf_e_cancelamento_preservam_dados(client,trabalho):
    p,_,_,_=trabalho
    primeira=etapa(client,p)
    assert Client(enforce_csrf_checks=True).post(reverse('sandbox_limpar_testes',args=[p.pk]),
        {'etapa':1,'confirmacao':primeira.context['confirmacao']}).status_code==403
    assert client.get(reverse('sandbox_trabalho',args=[p.pk])).status_code==200
    assert p.entregas.count()==1 and p.mensagens.count()==1


def test_resposta_da_ia_em_andamento_nao_volta_apos_limpeza(trabalho,monkeypatch):
    p,_,_,_=trabalho
    job=RespostaSandbox.objects.get(participacao=p)
    def resposta(*args):
        limpeza_sandbox.limpar(p,p.prazo_ate.isoformat())
        return 'Resposta antiga que nao deve reaparecer'
    monkeypatch.setattr(ia_sandbox,'_consultar_modelo',resposta)
    ia_sandbox.processar_resposta(job.pk)
    assert not p.mensagens.exists() and not RespostaSandbox.objects.filter(participacao=p).exists()


def test_analise_em_andamento_nao_volta_apos_limpeza(trabalho,monkeypatch):
    p,_,_,a=trabalho
    entrega=a.entrega
    msg=p.mensagens.first()
    def comparar(*args):
        limpeza_sandbox.limpar(p,p.prazo_ate.isoformat())
        return {'avaliacao':{'resultado':'atende','justificativa':'Amostra'}}
    monkeypatch.setattr(analises_sandbox,'comparar',comparar)
    analises_sandbox.processar_entrega(a.pk)
    assert not p.entregas.exists() and not p.mensagens.exists()
    assert devolutiva_sandbox.registrar(entrega,'resultado','Antigo') is None
    assert ia_sandbox.enfileirar(p,'entrega:'+str(entrega.pk),'cliente') is None
    assert ia_sandbox.enfileirar(p,'mensagem:'+str(msg.pk),'ia') is None
    assert ia_sandbox.enfileirar(p,'atraso:'+p.prazo_ate.isoformat(),'cliente') is None
    assert not RespostaSandbox.objects.filter(participacao=p).exists()


def test_chave_de_arquivo_fora_da_pasta_nao_remove_arquivo_alheio(trabalho,tmp_path):
    p,_,arquivo,_=trabalho
    ArquivoSandbox.objects.filter(pk=arquivo.pk).update(chave='../fora')
    with pytest.raises(sandbox.ErroSandbox):
        limpeza_sandbox.limpar(p,p.prazo_ate.isoformat())
    assert p.entregas.count()==1 and (tmp_path/arquivo.chave).exists()
