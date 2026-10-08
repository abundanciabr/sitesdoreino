from datetime import timedelta
import hashlib
import json
from pathlib import Path
import uuid

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.encomendas import sandbox, analises_sandbox as analises, xp_sandbox
from apps.encomendas.sandbox_models import (AnaliseArquivoSandbox, AnaliseEntregaSandbox,
                                           ArquivoSandbox, RespostaSandbox, MensagemSandbox)
from apps.core import ia_sandbox, telas_sandbox, sessao
from apps.core.templatetags.sandbox_texto import conversa


@pytest.fixture
def participacao(db):
    projeto = sandbox.semear_projetos(site_id='TESTE-pratica')[0]
    projeto.prazo_dias = 2
    projeto.save()
    return sandbox.aceitar(site_id='TESTE-pratica', pessoa_id='TESTE-aluno', projeto_id=projeto.pk)


def entrega(p, body=b'imagem', name='TESTE.png'):
    file = ArquivoSandbox.objects.create(participacao=p, nome=name, chave=uuid.uuid4().hex,
        sha256=hashlib.sha256(body).hexdigest(), tamanho=len(body), mime='application/octet-stream')
    return sandbox.entregar(site_id=p.site_id, participacao_id=p.pk, pessoa_id=p.pessoa_id, arquivos=[file.pk])


@pytest.mark.django_db
def test_fila_compara_snapshot_preserva_escola_e_credito_unico(participacao, monkeypatch, settings, tmp_path):
    settings.MARKETPLACE_UPLOAD_ROOT = tmp_path
    e = entrega(participacao)
    file = e.arquivos.get()
    (tmp_path / file.chave).write_bytes(b'imagem')
    a = e.analise
    f = file.analise
    analises.publicar_pedido(f)
    directory = analises.pasta() / f.chave_cache
    (directory / 'estado.json').write_text(json.dumps({'estado': 'concluida'}))
    (directory / 'resultado.json').write_text(json.dumps({'arquivos': [{'arquivo': file.nome,
        'estado': 'concluida', 'medidas': {'largura_px': 512}, 'imagens': []}]}))
    vistos = {}
    def avaliar(p,e,reqs,ev,imgs):
        vistos.update(reqs=reqs, ev=ev, termos=p.termos)
        return {'requisitos': [{'id': r['id'], 'encontrado': 'Imagem examinada',
            'nao_encontrado': '', 'inconclusivo': 'Sem abertura do fonte',
            'evidencias': [file.nome + ': 512px']} for r in reqs], 'interpretacao_visual_ia': 'Imagem parcial'}
    monkeypatch.setattr(ia_sandbox,'avaliar_entrega',avaliar)
    participacao.projeto.briefing='Modificação posterior que não pertence ao aceite'
    participacao.projeto.save()
    analises.processar_entrega(a.pk)
    a.refresh_from_db()
    assert a.estado == 'concluida'
    assert a.resultado['versao'] == 1
    assert vistos['termos']['briefing'] == participacao.termos['briefing']
    assert a.resultado['requisitos'][0]['requisito'] == participacao.termos['briefing']
    participacao.refresh_from_db()
    assert participacao.status == 'entregue' and not participacao.aprovado_em
    sandbox.aprovar(site_id=participacao.site_id, participacao_id=participacao.pk, aprovador_id='TESTE-escola')
    sandbox.aprovar(site_id=participacao.site_id, participacao_id=participacao.pk, aprovador_id='TESTE-escola')
    assert participacao.movimento_meshcoin.valor == 10000
    assert xp_sandbox.aplicar(participacao,'aprovada',participacao.pk,timezone.now()) == []


@pytest.mark.django_db
def test_ajuste_nova_versao_cache_mesmo_conteudo_sem_analise_antiga(participacao):
    e1 = entrega(participacao)
    a1=e1.analise
    a1.estado='concluida'
    a1.resultado={'versao':1,'interpretacao_visual_ia':'ANTIGA'}
    a1.save()
    sandbox.pedir_ajuste(site_id=participacao.site_id,participacao_id=participacao.pk,autor_id='TESTE-escola',texto='Ajuste do briefing')
    e2=entrega(participacao)
    assert e1.arquivos.get().analise.chave_cache == e2.arquivos.get().analise.chave_cache
    assert e2.analise.estado == 'na_fila' and not e2.analise.resultado
    retrato=ia_sandbox._retrato(participacao)
    assert retrato['versao_atual'] == 2 and retrato['comparacao_versao_atual'] == {}
    assert 'ANTIGA' not in str(retrato['evidencias_versao_atual'])
    assert RespostaSandbox.objects.filter(origem__startswith='ajuste:').count()==1


@pytest.mark.django_db
def test_cliente_simulado_resposta_unica_falha_preserva_pergunta(participacao,monkeypatch):
    fala=sandbox.mensagem(site_id=participacao.site_id,participacao_id=participacao.pk,ator_id=participacao.pessoa_id,papel='aluno',texto='Para qual uso?')
    job=ia_sandbox.enfileirar(participacao,'mensagem:'+str(fala.pk),'cliente')
    assert ia_sandbox.enfileirar(participacao,job.origem,'cliente').pk==job.pk
    monkeypatch.setattr(ia_sandbox,'_consultar_modelo',lambda *a:None)
    ia_sandbox.processar_resposta(job.pk)
    job.refresh_from_db()
    assert job.estado=='falha' and MensagemSandbox.objects.filter(pk=fala.pk).exists()
    job.tentar_em=None
    job.save()
    capture={}
    def modelo(retrato,historico):
        capture.update(retrato)
        return 'Cliente simulado: uso conforme o briefing aceito.'
    monkeypatch.setattr(ia_sandbox,'_consultar_modelo',modelo)
    ia_sandbox.processar_resposta(job.pk)
    ia_sandbox.processar_resposta(job.pk)
    assert participacao.mensagens.filter(papel='cliente').count()==1
    assert capture['interlocutor']=='cliente' and capture['prazo_ate'].endswith('-03:00')
    assert participacao.status=='em_producao'


@pytest.mark.django_db
def test_cliente_recebe_distincao_entre_atraso_e_revisao_pontual(participacao):
    entrega(participacao)
    participacao.refresh_from_db()
    participacao.prazo_ate=timezone.now()-timedelta(minutes=1)
    participacao.save(update_fields=['prazo_ate'])
    retrato=ia_sandbox._retrato(participacao)
    assert retrato['entrega_pontual_aguardando_revisao'] is True
    assert retrato['atraso_registrado'] is False
    participacao.atraso_em=timezone.now()
    participacao.save(update_fields=['atraso_em'])
    retrato=ia_sandbox._retrato(participacao)
    assert retrato['atraso_registrado'] is True
    assert retrato['entrega_pontual_aguardando_revisao'] is False


@pytest.mark.django_db
def test_ia_fora_do_ar_preserva_medidas_repeticao(participacao,monkeypatch,settings,tmp_path):
    settings.MARKETPLACE_UPLOAD_ROOT=tmp_path
    e=entrega(participacao)
    f=e.arquivos.get().analise
    f.estado='concluida'
    f.resultado={'arquivos':[{'arquivo':'TESTE.png','estado':'concluida','medidas':{'largura_px':300},'imagens':[]}]}
    f.save()
    monkeypatch.setattr(ia_sandbox,'avaliar_entrega',lambda *a:(_ for _ in ()).throw(RuntimeError('SEGREDO')))
    analises.processar_entrega(e.analise.pk)
    a=AnaliseEntregaSandbox.objects.get(entrega=e)
    assert a.estado=='falha_ia' and 'SEGREDO' not in a.falha
    assert analises.evidencias(e)[0][0]['conteudo']==f.resultado
    analises.repetir(e)
    a.refresh_from_db()
    assert a.estado=='na_fila' and a.tentar_em is None


@pytest.mark.django_db
def test_privacidade_previas_e_tela_enquanto_analisa(participacao,client,monkeypatch,settings,tmp_path):
    settings.MARKETPLACE_UPLOAD_ROOT=tmp_path
    e=entrega(participacao)
    f=e.arquivos.get()
    a=f.analise
    a.estado='concluida'
    a.save()
    name='a'*24+'.png'
    directory=analises.pasta()/a.chave_cache/'previas'
    directory.mkdir(parents=True)
    (directory/name).write_bytes(b'PNG TESTE')
    atual={'id':participacao.pessoa_id,'site':participacao.site_id}
    monkeypatch.setattr(sessao,'quem_e',lambda r:atual['id'])
    monkeypatch.setattr(sessao,'site_desta_instalacao',lambda:atual['site'])
    monkeypatch.setenv('IDS_DO_PLANTAO','TESTE-escola')
    url=reverse('sandbox_previa_analise',args=[f.pk,name])
    response=client.get(url)
    assert response.status_code==200 and response['Cache-Control']=='private, no-store'
    assert b''.join(response.streaming_content)==b'PNG TESTE'
    atual['id']='TESTE-outro'
    assert client.get(url).status_code==404
    atual.update(id=participacao.pessoa_id,site='outro-site')
    assert client.get(url).status_code==404
    atual['site']=participacao.site_id
    response=client.get(reverse('sandbox_trabalho',args=[participacao.pk]))
    assert response.status_code==200
    assert 'Análise da versão 1' in response.content.decode()
    assert 'Cliente simulado (IA)' in response.content.decode()
    assert 'Brasília' in response.content.decode()
    assert 'Nenhum XP' in response.content.decode()


def test_formatacao_preserva_endereco_e_nao_executa_html():
    url='https://meshcraft.top/'+'a'*400
    rendered=str(conversa('## Confira\n**Arquivo** `'+url+'`\n<script>alert(1)</script>'))
    assert url in rendered and '<strong>Arquivo</strong>' in rendered
    assert '<script>' not in rendered and '&lt;script&gt;' in rendered
