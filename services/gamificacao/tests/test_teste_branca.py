"""Reinício próprio recuperável, sem atingir outras contas ou finanças."""
import hashlib
from datetime import date

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.core.perfil import perfil_de
from apps.core.teste_branca import chave
from apps.gamificacao.models import (
    AnexoDaJornada, BackupDoReinicioDasFaixas, JornadaPessoal, LancamentoDeXP,
    PerfilJogador, RecebimentoDeclarado,
)

pytestmark = pytest.mark.django_db
P, SITE, URL = 'admin-teste-checks', 'site-checks', '/interno/teste-faixa-branca/'
COOKIE = {'HTTP_COOKIE': 'meshcraft_sessao=teste'}


@pytest.fixture(autouse=True)
def conta(monkeypatch):
    monkeypatch.setenv('SITE_ID', SITE)
    monkeypatch.setattr('apps.core.inventario._sessao', lambda cookie: {'autenticado': True, 'id': P})
    monkeypatch.setattr('apps.core.teste_branca.e_admin', lambda request, pessoa: True)


def guardar(client, acao, **dados):
    atual = client.get('/inventario/', **COOKIE).json()
    return client.post('/inventario/', {'acao': acao, 'revisao': atual['revisao'], **dados}, **COOKIE)


def operar(client, acao):
    j = JornadaPessoal.objects.get(pessoa_id=P, site_id=SITE)
    return client.post(URL, {'acao': acao, 'revisao': j.revisao, 'pessoa_id': 'outra-conta'}, **COOKIE)


def test_reinicio_e_restauracao_preservam_historico_xp_arquivo_financeiro_e_outra_conta(client):
    guardar(client, 'inicio-motivo', motivo='ugc', motivo_pessoal='Meu motivo privado', concluir='sim')
    antigo = dict(JornadaPessoal.objects.get(pessoa_id=P, site_id=SITE).inicio)
    antigo_xp = LancamentoDeXP.objects.get(pessoa_id=P, site_id=SITE)
    outra = perfil_de('outra-conta', SITE)
    JornadaPessoal.objects.create(pessoa_id=outra.pessoa_id, site_id=SITE, inicio={'motivo': 'estudio'})
    financeiro = RecebimentoDeclarado.objects.create(pessoa_id=P, site_id=SITE, valor_cents=50000,
        origem='fora', estado='confirmado', recebido_em=date.today(), print_bytes=b'privado')
    before = RecebimentoDeclarado.objects.filter(pk=financeiro.pk).values().get()
    assert 'preparar' in client.get(URL, **COOKIE).content.decode().lower()
    assert 'pronta para testar' in operar(client, 'reiniciar').content.decode()
    copia = BackupDoReinicioDasFaixas.objects.get(site_id=SITE, chave=chave(P))
    assert hashlib.sha256(bytes(copia.conteudo)).hexdigest() == copia.sha256
    dados = client.get('/inventario/', **COOKIE).json()
    assert [e['concluida'] for e in dados['inicio']['etapas']] == [False] * 4
    assert [e['liberada'] for e in dados['inicio']['etapas']] == [True, False, False, False]
    assert PerfilJogador.objects.get(pessoa_id=P, site_id=SITE).xp_total == 0
    antigo_xp.refresh_from_db(); assert antigo_xp.status == 'estornado'
    guardar(client, 'inicio-motivo', motivo='jogo', concluir='sim')
    operar(client, 'reiniciar')
    assert client.get('/inventario/', **COOKIE).json()['inicio']['motivo'] == 'jogo'
    assert guardar(client, 'inicio-compromisso', assumir='sim', compromisso_checks='["curso", "aulas", "desafios", "motivo"]').json()['conquista_xp'] == 100
    assert guardar(client, 'inicio-item').status_code == 200
    modelo = SimpleUploadedFile('cubo.obj', b'v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n')
    assert guardar(client, 'inicio-envio', arquivo=modelo).status_code == 200
    assert client.get('/inventario/', **COOKIE).json()['atual_ordem'] == 2
    assert 'restaurado' in operar(client, 'restaurar').content.decode()
    assert JornadaPessoal.objects.get(pessoa_id=P, site_id=SITE).inicio == antigo
    assert PerfilJogador.objects.get(pessoa_id=P, site_id=SITE).xp_total == 100
    assert LancamentoDeXP.objects.filter(pessoa_id=P, site_id=SITE).count() == 5
    assert AnexoDaJornada.objects.filter(pessoa_id=P, site_id=SITE).count() == 1
    assert not AnexoDaJornada.objects.filter(pessoa_id=P, site_id=SITE, passo=2).exists()
    assert RecebimentoDeclarado.objects.filter(pk=financeiro.pk).values().get() == before
    assert JornadaPessoal.objects.get(pessoa_id=outra.pessoa_id, site_id=SITE).inicio == {'motivo': 'estudio'}
    operar(client, 'restaurar')
    assert PerfilJogador.objects.get(pessoa_id=P, site_id=SITE).xp_total == 100


def test_acesso_csrf_conflito_e_backup_corrompido_nao_alteram_avanco(client, monkeypatch):
    guardar(client, 'inicio-motivo', motivo='ugc', concluir='sim')
    monkeypatch.setattr('apps.core.teste_branca.e_admin', lambda request, pessoa: False)
    assert client.get(URL, **COOKIE).status_code == 403
    assert operar(client, 'reiniciar').status_code == 403
    monkeypatch.setattr('apps.core.teste_branca.e_admin', lambda request, pessoa: True)
    from django.test import Client
    assert Client(enforce_csrf_checks=True).post(URL, {'acao': 'reiniciar'}, **COOKIE).status_code == 403
    assert 'outra aba' in client.post(URL, {'acao': 'reiniciar', 'revisao': -1}, **COOKIE).content.decode()
    assert not BackupDoReinicioDasFaixas.objects.filter(chave=chave(P)).exists()
    operar(client, 'reiniciar')
    guardar(client, 'inicio-motivo', motivo='jogo', concluir='sim')
    BackupDoReinicioDasFaixas.objects.filter(chave=chave(P)).update(sha256='0' * 64)
    assert 'não conferiu' in operar(client, 'restaurar').content.decode()
    assert JornadaPessoal.objects.get(pessoa_id=P, site_id=SITE).inicio['motivo'] == 'jogo'
    assert PerfilJogador.objects.get(pessoa_id=P, site_id=SITE).xp_total == 100
