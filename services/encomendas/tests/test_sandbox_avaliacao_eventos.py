"""Contrato da avaliação publicado para jornada e suporte."""
import uuid
from datetime import timedelta

import pytest

from apps.encomendas import faixas_eventos, sandbox
from apps.encomendas import analises_sandbox as analises
from apps.encomendas.models import OutboxMarketplace
from apps.encomendas.sandbox_models import AnaliseEntregaSandbox, ArquivoSandbox, EntregaSandbox
from django.utils import timezone


pytestmark = pytest.mark.django_db


@pytest.fixture
def participacao():
    projeto = sandbox.semear_projetos(site_id='TESTE-avaliacao-eventos')[0]
    return sandbox.aceitar(site_id=projeto.site_id, pessoa_id='TESTE-aluno',
                           projeto_id=projeto.pk, prazo_horas=24)


def enviar(participacao, *, teste=False):
    arquivo = ArquivoSandbox.objects.create(
        site_id=participacao.site_id, participacao=participacao,
        nome='modelo.glb', chave=uuid.uuid4().hex, sha256='a' * 64,
        tamanho=100, mime='model/gltf-binary')
    return sandbox.entregar(site_id=participacao.site_id, participacao_id=participacao.pk,
                            pessoa_id=participacao.pessoa_id, arquivos=[arquivo.pk],
                            teste_mantenedor=teste)


def eventos():
    return OutboxMarketplace.objects.filter(event=faixas_eventos.EV_AVALIACAO)


def test_envio_somente_pendente_sem_bonus_e_snapshot_unico(participacao):
    entrega = enviar(participacao)
    assert not OutboxMarketplace.objects.filter(event=faixas_eventos.EV_CONCLUSAO).exists()
    assert eventos().count() == 1
    payload = eventos().get().payload
    assert payload['estado'] == 'pendente' and payload['resultado'] == ''
    assert payload['versao'] == 1 and payload['atual'] is True
    assert payload['analise_id'] == str(entrega.analise.pk)
    assert payload['entrega_criada_em'] == entrega.criada_em.isoformat()
    assert payload['atualizado_em'] == entrega.analise.atualizada_em.isoformat()
    assert payload['ocorrido_em'] == payload['atualizado_em']
    assert payload['historico'] is False
    assert payload['url'] == f'/encomendas/sandbox/trabalhos/{participacao.pk}/'
    faixas_eventos.sandbox_avaliacao_atualizada(entrega.analise)
    assert eventos().count() == 1


def test_teste_mantenedor_nao_publica_e_nao_substitui_aluno(participacao):
    original = enviar(participacao)
    teste = enviar(participacao, teste=True)
    assert eventos().count() == 1
    assert faixas_eventos.sandbox_avaliacao_atualizada(teste.analise) == (None, False)
    assert eventos().get().payload['entrega_id'] == str(original.pk)


def test_conclusao_antiga_mantem_resultado_mas_nao_e_atual(participacao):
    antiga = enviar(participacao)
    analise = AnaliseEntregaSandbox.objects.get(entrega=antiga)
    analise.estado = 'concluida'
    analise.resultado = {'avaliacao': {'resultado': 'precisa_ajustes',
                                      'justificativa': 'Faltou a vista lateral.'},
                       'medidas_programas': []}
    analise.save()
    nova = enviar(participacao)
    faixas_eventos.sandbox_avaliacao_atualizada(analise)
    payload = eventos().get(payload__estado='concluida').payload
    assert payload['resultado'] == 'precisa_ajustes'
    assert payload['atual'] is False
    assert payload['entrega_id'] == str(antiga.pk)
    assert payload['entrega_criada_em'] == antiga.criada_em.isoformat()
    assert nova.versao == 2 and 'histórico' in payload['explicacao']


def test_atende_com_lacuna_publica_inconclusiva(participacao):
    entrega = enviar(participacao)
    analise = entrega.analise
    analise.estado = 'concluida'
    analise.resultado = {'avaliacao': {'resultado': 'atende', 'justificativa': 'Parecia completo.'},
                        'medidas_programas': [{'arquivo': 'modelo.glb', 'estado': 'falha'}]}
    analise.save()
    faixas_eventos.sandbox_avaliacao_atualizada(analise)
    payload = eventos().get(payload__estado='concluida').payload
    assert payload['resultado'] == 'inconclusiva' and payload['atual'] is True
    with pytest.raises(sandbox.ErroSandbox):
        sandbox.aprovar(site_id=participacao.site_id, participacao_id=participacao.pk,
                        aprovador_id='equipe')


def test_aprovacao_manual_nao_contorna_avaliacao(participacao):
    enviar(participacao)
    with pytest.raises(sandbox.ErroSandbox):
        sandbox.aprovar(site_id=participacao.site_id, participacao_id=participacao.pk,
                        aprovador_id='equipe')


def test_resposta_velha_de_ia_nao_sobrescreve_tentativa_nova(participacao, monkeypatch):
    entrega = enviar(participacao)
    arquivo = entrega.arquivos.get().analise
    arquivo.estado = 'concluida'
    arquivo.resultado = {'arquivos': [{'arquivo': 'modelo.glb', 'estado': 'concluida',
                                      'medidas': {'triangulos': 398}, 'imagens': []}]}
    arquivo.save()
    chamadas = 0

    def comparar(_analise):
        nonlocal chamadas
        chamadas += 1
        if chamadas == 1:
            AnaliseEntregaSandbox.objects.filter(pk=entrega.analise.pk).update(
                atualizada_em=timezone.now() - timedelta(minutes=9))
            analises.processar_entrega(entrega.analise.pk)
            return None  # A primeira resposta atrasada falhou depois do sucesso novo.
        return {'avaliacao': {'resultado': 'atende', 'justificativa': 'Modelo examinado.'},
                'medidas_programas': [{'arquivo': 'modelo.glb', 'estado': 'concluida',
                                       'conteudo': arquivo.resultado}], 'requisitos': []}

    monkeypatch.setattr(analises, 'comparar', comparar)
    analises.processar_entrega(entrega.analise.pk)
    atual = AnaliseEntregaSandbox.objects.get(pk=entrega.analise.pk)
    assert chamadas == 2
    assert atual.estado == 'concluida' and atual.tentativas == 2
    assert atual.resultado['avaliacao']['resultado'] == 'atende'
    assert eventos().filter(payload__estado='concluida').count() == 1
    assert not eventos().filter(payload__estado='falha').exists()


def test_snapshot_historico_uma_vez_sem_credito(participacao):
    entrega = EntregaSandbox.objects.create(site_id=participacao.site_id,
        participacao=participacao, versao=1, comentario='Entrega anterior')
    analise = AnaliseEntregaSandbox.objects.create(site_id=participacao.site_id,
        entrega=entrega, estado='concluida', resultado={
            'avaliacao': {'resultado': 'atende', 'justificativa': 'Arquivo examinado.'},
            'medidas_programas': []})
    assert not eventos().exists()
    analises.rodada()
    assert eventos().count() == 1
    payload = eventos().get().payload
    assert payload['analise_id'] == str(analise.pk)
    assert payload['historico'] is True and payload['resultado'] == 'atende'
    analises.rodada()
    assert eventos().count() == 1
    assert not OutboxMarketplace.objects.filter(event=faixas_eventos.EV_CONCLUSAO).exists()
