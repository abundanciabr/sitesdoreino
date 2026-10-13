import json
from datetime import timedelta

import pytest
from django.test import RequestFactory
from django.utils import timezone

from apps.agentes.models import RotinaSuperEquipe
from apps.agentes.super_equipe import _entregas
from apps.agentes.super_equipe_entregas import consultar, registrar, sanitizar
from apps.agentes.super_equipe_perfis import contexto_do_perfil
from apps.agentes.views_super_equipe import super_equipe


def prova():
    return {'id': 'a'*12, 'commit': 'b'*40, 'candidata': 'c'*40,
            'senha': 'nao_exportar', 'operacao': {
                'ensaios': {'aplicacao': {'tempos_segundos': {'backup_codigo': 2.1}}},
                'evidencia_publicador': {'id': 'a'*12, 'candidata': 'c'*40,
                    'coletada_em': timezone.now().isoformat(),
                    'artefato': {'pacote_id': 'd'*64, 'codigo_sha256': 'e'*64, 'caminho': '/privado'},
                    'ensaio': {'estado': 'aprovado', 'casos': 2, 'aprovados': 1, 'falhas': 0, 'ignorados': 1,
                               'relatorio_sha256': 'f'*64, 'resultados': [
                                   {'caso': 'test_acesso', 'resultado': 'aprovado'},
                                   {'caso': 'email@privado.invalid', 'resultado': 'ignorado'}]},
                    'pos_ativacao': {'confirmacao_atual': True, 'pacote_confere': True,
                                    'imagem_confere': True, 'sha_aprovada': 'c'*40}}}}


def test_sanitiza_sem_transformar_tempo_backup_em_restauracao():
    dados = sanitizar(prova())
    assert dados['artefato']['pacote_id'] == 'd'*64
    assert dados['backup']['tempo_codigo_segundos'] == 2.1
    assert dados['backup']['restauracao_comprovada'] is None
    assert 'privado' not in json.dumps(dados) and 'senha' not in dados
    assert dados['ensaio']['resultados'][1]['caso'] == 'nome_nao_exportado'


@pytest.mark.django_db
def test_historia_idempotente_e_jez_recebe_fonte_sem_retomar_rotina():
    rotina = RotinaSuperEquipe.objects.create(host='meshcraft.top', ativa=False)
    dados = prova()
    registrar('meshcraft.top', dados)
    registrar('meshcraft.top', dados)
    rotina.refresh_from_db()
    assert len(rotina.entregas_operacionais['a'*12]) == 1
    assert rotina.ativa is False
    fontes = _entregas('meshcraft.top')
    contexto = contexto_do_perfil('jez_humble', 'Avalie a entrega', {'entregas': fontes}, {})
    assert contexto['fontes']['entregas']['canal_operacional']['itens'][0]['artefato']['codigo_sha256'] == 'e'*64
    dados['operacao']['evidencia_publicador']['coletada_em'] = (timezone.now()-timedelta(hours=1)).isoformat()
    registrar('meshcraft.top', dados)
    rotina.refresh_from_db()
    assert len(rotina.entregas_operacionais['a'*12]) == 2
    assert consultar(rotina)['itens'][0]['confirmacao_atual'] is False


def test_recusa_prova_de_outra_candidata():
    dados = prova()
    dados['operacao']['evidencia_publicador']['candidata'] = '0'*40
    with pytest.raises(ValueError):
        sanitizar(dados)


def test_backup_e_proveniencia_tem_campos_restritos():
    dados = prova()
    fonte = dados['operacao']['evidencia_publicador']
    fonte['backup'] = {'identidade': '20261013-011004Z-cccccccccccc-1627307', 'concluido': True,
                      'restauracao_comprovada': True, 'bases': 19, 'bases_restauradas': 19,
                      'segredo': 'descartar'}
    fonte['proveniencia'] = {'arvore_git': '1'*40, 'prova_identidade': '2'*64,
                            'arvore_confere': True, 'codigo_confere': True, 'caminho': '/privado'}
    salvo = sanitizar(dados)
    assert salvo['backup']['bases_restauradas'] == 19
    assert salvo['backup']['restauracao_comprovada'] is True
    assert salvo['proveniencia']['codigo_confere'] is True
    assert 'segredo' not in salvo['backup'] and 'caminho' not in salvo['proveniencia']


@pytest.mark.django_db
def test_importacao_no_admin_e_negativa_para_equipe():
    pedido = RequestFactory().post('/admin/super-equipe/', {'acao': 'registrar_entregas', 'consultas': json.dumps(prova())})
    pedido.admin = {'equipe_apenas': True}
    assert super_equipe(pedido).status_code == 403
    assert not RotinaSuperEquipe.objects.exists()
    pedido.admin = {'email': 'admin@teste.invalid'}
    assert super_equipe(pedido).status_code == 302
    assert RotinaSuperEquipe.objects.get().entregas_operacionais['a'*12]
