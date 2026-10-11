"""Prova da limpeza autorizada: backup recuperável, zero requisitos e escopo."""
import gzip
import hashlib
import importlib
import json
from datetime import date
from uuid import uuid4
from types import SimpleNamespace
from pathlib import Path

import pytest
from django.apps import apps
from django.core import serializers
from django.db import connection
from django.utils import timezone

from apps.gamificacao.inicio import etapas_inicio
from apps.gamificacao.jornada import situacao
from apps.gamificacao.models import (
    AnexoDaJornada, BackupDoReinicioDasFaixas, FaixaDoAluno, HistoricoDaFaixa,
    JornadaPessoal, LancamentoDeXP, PerfilJogador, Pessoa, RecebimentoDeclarado,
    RegistroDaJornada, RendimentoRealLivro, VersaoDoRecebimento,
)

pytestmark = pytest.mark.django_db
SITE = 'site-reinicio'
migracao = importlib.import_module('apps.gamificacao.migrations.0018_reinicio_faixas_20261011')


def preparar(site=SITE, pessoa_id='teste-reinicio'):
    p, _ = Pessoa.objects.get_or_create(id_da_plataforma=pessoa_id,
                                      defaults={'email': pessoa_id + '@example.test'})
    agora = timezone.now()
    j = JornadaPessoal.objects.create(pessoa=p, site_id=site, revisao=8, meta_cents=50000,
        inicio={'motivo': 'ugc', 'sonho': 'SONHO PRIVADO', 'objetivo': 'Chapéu',
                'compromisso': 'Praticar', 'confirmado_em': agora.isoformat(),
                'item_pronto_em': agora.isoformat()},
        declaracoes={'2': True, '3': True, '4': True},
        confirmacoes_sequenciais={'2': 'sim', '3': 'sim', '4': 'sim'},
        celebracao_pendente={'ordem': 13})
    conteudo = b'o cubo\nv 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n'
    anexo = AnexoDaJornada.objects.create(pessoa=p, site_id=site, passo=2,
        nome='teste.obj', conteudo=conteudo, tamanho=len(conteudo), sha256=hashlib.sha256(conteudo).hexdigest())
    for ordem in range(1, 14):
        FaixaDoAluno.objects.create(pessoa=p, site_id=site, ordem=ordem,
            estado='alcancada', origem='item', alcancada_em=agora)
        HistoricoDaFaixa.objects.create(pessoa=p, site_id=site, ordem=ordem,
            estado_novo='alcancada', origem='item', ocorrido_em=agora)
    RegistroDaJornada.objects.create(pessoa=p, site_id=site, acao='declaracao', dados={'privado': 'teste'})
    r = RecebimentoDeclarado.objects.create(pessoa=p, site_id=site, chave=uuid4(),
        valor_cents=50000, origem='fora', estado='confirmado', recebido_em=date.today(), print_bytes=b'print-privado')
    VersaoDoRecebimento.objects.create(pessoa=p, site_id=site, recebimento=r,
        revisao=0, print_bytes=b'print-privado', print_sha256='abc', dados={'valor': 50000})
    RendimentoRealLivro.objects.create(pessoa=p, site_id=site, event_id=str(uuid4()),
        rendimento_id='recebimento', valor_cents=50000, ocorrido_em=agora)
    for slug, valor in [('bonus-inicio-etapa-1', 100), ('bonus-faixa-amarela', 5000), ('forum-mensagem', 79)]:
        LancamentoDeXP.objects.create(pessoa=p, site_id=site, pontos=valor,
            regra_slug=slug, origem_event_id=str(uuid4()), occurred_at=agora,
            dia_local=date.today(), status='definitivo')
    PerfilJogador.objects.create(pessoa=p, site_id=site, xp_total=5179, nivel=3,
        cristais_saldo=7, celebracoes_pendentes=[{'tipo': 'nivel-alcancado', 'referencia': '3'},
                                             {'tipo': 'conquista-concedida', 'referencia': 'medalha-preservada'}])
    return p, j, anexo


def reiniciar():
    return migracao.reiniciar_site(apps, connection, SITE)


def test_zerar_todos_requisitos_sem_apagar_financeiro_ou_outro_site():
    p, j, anexo = preparar()
    preparar(site='outro-site', pessoa_id='outro-teste')
    copia = reiniciar()
    j.refresh_from_db()
    assert j.revisao == 9 and j.inicio == {} and j.meta_cents is None
    assert j.declaracoes == j.confirmacoes_sequenciais == j.celebracao_pendente == {}
    assert situacao(p.pk, SITE)['atual']['ordem'] == 1
    assert situacao(p.pk, SITE)['total_cents'] == 0
    passos = etapas_inicio(p.pk, SITE, j)
    assert [p['concluida'] for p in passos] == [False] * 4
    assert [p['liberada'] for p in passos] == [True, False, False, False]
    for modelo in (AnexoDaJornada, RegistroDaJornada, HistoricoDaFaixa, FaixaDoAluno):
        assert modelo.objects.filter(site_id=SITE).count() == 0
        assert modelo.objects.filter(site_id='outro-site').exists()
    financeiro = RecebimentoDeclarado.objects.get(site_id=SITE)
    assert financeiro.valor_cents == 50000 and financeiro.estado == 'confirmado'
    assert bytes(financeiro.print_bytes) == b'print-privado' and financeiro.fora_da_progressao
    assert VersaoDoRecebimento.objects.filter(site_id=SITE).count() == 1
    assert RendimentoRealLivro.objects.get(site_id=SITE).valor_cents == 50000
    perfil = PerfilJogador.objects.get(pessoa=p, site_id=SITE)
    assert (perfil.xp_total, perfil.nivel, perfil.cristais_saldo) == (79, 1, 7)
    assert perfil.celebracoes_pendentes == [{'tipo': 'conquista-concedida', 'referencia': 'medalha-preservada'}]
    assert copia.aplicado_em and copia.contagens['AnexoDaJornada'] == 1


def test_backup_restaura_bytes_e_registros_exatos_em_banco_isolado():
    p, j, anexo = preparar()
    conteudo = bytes(anexo.conteudo)
    copia = reiniciar()
    pacote = bytes(copia.conteudo)
    assert hashlib.sha256(pacote).hexdigest() == copia.sha256
    bruto = gzip.decompress(pacote).decode()
    assert len(json.loads(bruto)) == sum(v for k, v in copia.contagens.items() if k not in ('pessoas', 'xp_das_faixas'))
    for registro in serializers.deserialize('json', bruto):
        registro.save()
    assert bytes(AnexoDaJornada.objects.get(pk=anexo.pk).conteudo) == conteudo
    assert JornadaPessoal.objects.get(pk=j.pk).inicio['sonho'] == 'SONHO PRIVADO'
    assert JornadaPessoal.objects.get(pk=j.pk).revisao == 8
    assert PerfilJogador.objects.get(pessoa=p, site_id=SITE).xp_total == 5179


def test_falha_na_conferencia_do_backup_nao_apaga_nada(monkeypatch):
    p, j, anexo = preparar()
    monkeypatch.setattr(migracao.gzip, 'decompress', lambda dados: b'corrompido')
    with pytest.raises(RuntimeError, match='limpeza cancelada'):
        reiniciar()
    assert AnexoDaJornada.objects.filter(pk=anexo.pk).exists()
    assert JornadaPessoal.objects.get(pk=j.pk).revisao == 8
    assert not BackupDoReinicioDasFaixas.objects.filter(site_id=SITE).exists()


def test_repetir_limpeza_nao_apaga_novo_progresso_e_xp_novo_e_idempotente(client, monkeypatch):
    p, j, anexo = preparar()
    reiniciar()
    monkeypatch.setenv('SITE_ID', SITE)
    monkeypatch.setattr('apps.core.inventario._sessao', lambda cookie: {'autenticado': True, 'id': p.pk})
    antigo = client.post('/inventario/', {'acao': 'inicio-motivo', 'revisao': 8,
        'motivo': 'ugc', 'concluir': 'sim'}, HTTP_COOKIE='meshcraft_sessao=TESTE')
    assert antigo.status_code == 400
    assert 'outra aba' in antigo.json()['detail']
    atual = client.get('/inventario/', HTTP_COOKIE='meshcraft_sessao=TESTE').json()
    novo = client.post('/inventario/', {'acao': 'inicio-motivo', 'revisao': atual['revisao'],
        'motivo': 'ugc', 'concluir': 'sim'}, HTTP_COOKIE='meshcraft_sessao=TESTE')
    assert novo.status_code == 200
    assert PerfilJogador.objects.get(pessoa=p, site_id=SITE).xp_total == 179
    reiniciar()
    assert JornadaPessoal.objects.get(pk=j.pk).inicio['motivo'] == 'ugc'
    from apps.gamificacao.bonus_inicio import conceder
    assert conceder(p.pk, SITE, 1) == 0
    assert PerfilJogador.objects.get(pessoa=p, site_id=SITE).xp_total == 179


def test_relatorio_so_admin_sem_dados_privados(client, monkeypatch):
    preparar()
    reiniciar()
    monkeypatch.setenv('SITE_ID', SITE)
    monkeypatch.setattr('apps.core.reinicio_faixas.quem_e', lambda request: 'admin-teste')
    monkeypatch.setattr('apps.core.reinicio_faixas.e_admin', lambda request, pessoa: False)
    assert client.get('/interno/reinicio-faixas/').status_code == 403
    monkeypatch.setattr('apps.core.reinicio_faixas.e_admin', lambda request, pessoa: True)
    resposta = client.get('/interno/reinicio-faixas/')
    assert resposta.status_code == 200
    assert resposta.json()['todos_com_inicio_limpo'] and resposta.json()['backup_conferido']
    assert 'SONHO PRIVADO' not in resposta.content.decode()
    assert 'conteudo' not in resposta.json()
    assert 'private' in resposta['Cache-Control'] and 'no-store' in resposta['Cache-Control']
    assert client.post('/interno/reinicio-faixas/').status_code == 405


def test_migracao_sem_site_com_dados_recusa_sem_apagar(monkeypatch):
    p, j, anexo = preparar()
    monkeypatch.delenv('SITE_ID', raising=False)
    with pytest.raises(RuntimeError, match='SITE_ID ausente'):
        migracao.aplicar(apps, SimpleNamespace(connection=connection))
    assert AnexoDaJornada.objects.filter(pk=anexo.pk).exists()
    assert not BackupDoReinicioDasFaixas.objects.exists()


def test_migracao_transformada_pelo_runtime_unificado_executa_no_banco():
    caminho = Path(__file__).resolve().parents[2] / 'aplicacao' / 'preparar.py'
    if not caminho.exists():
        pytest.skip('Preparador unificado disponível na cópia completa do repositório.')
    spec = importlib.util.spec_from_file_location('preparador_reinicio_teste', caminho)
    preparador = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(preparador)
    codigo = Path(migracao.__file__).read_text(encoding='utf-8')
    codigo = preparador._reescrever(codigo, 'gamificacao', {'gamificacao'}, set())
    codigo = preparador._preservar_tabelas_migracoes(codigo, 'gamificacao')
    contexto = {'__name__': 'migracao_transformada_para_teste'}
    exec(compile(codigo, str(caminho), 'exec'), contexto)
    p, j, anexo = preparar()

    def modelo(label, nome):
        assert label == 'gamificacao_gamificacao'
        return apps.get_model('gamificacao', nome)

    copia = contexto['reiniciar_site'](SimpleNamespace(get_model=modelo), connection, SITE)
    assert copia.aplicado_em
    assert not AnexoDaJornada.objects.filter(pk=anexo.pk).exists()
    assert situacao(p.pk, SITE)['atual']['ordem'] == 1
