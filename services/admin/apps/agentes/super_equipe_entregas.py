"""Fotografias sanitizadas da consulta do canal de entregas, com histórico."""
import hashlib
import json
import math
import re

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import RotinaSuperEquipe


def _sha(valor, tamanho=64):
    return valor if isinstance(valor, str) and re.fullmatch(r"[0-9a-f]{%d}" % tamanho, valor) else None


def _data(valor):
    if not isinstance(valor, str) or len(valor) > 40:
        return None
    try:
        data = parse_datetime(valor)
        return data.isoformat() if data and timezone.is_aware(data) else None
    except ValueError:
        return None


def _segundos(valor):
    return valor if type(valor) in (int, float) and math.isfinite(valor) and valor >= 0 else None


def sanitizar(registro):
    if not isinstance(registro, dict) or not _sha(registro.get('id'), 12):
        raise ValueError('Consulta sem ID válido de entrega.')
    operacao = registro.get('operacao') or {}
    prova = operacao.get('evidencia_publicador') or {}
    if not isinstance(operacao, dict) or not isinstance(prova, dict):
        raise ValueError('Consulta operacional inválida.')
    candidata = _sha(registro.get('candidata'), 40)
    if not candidata or prova.get('id') != registro['id'] or prova.get('candidata') != candidata:
        raise ValueError('A prova precisa corresponder ao ID e à candidata da consulta.')
    artefato, ensaio, depois = (prova.get(n) or {} for n in ('artefato', 'ensaio', 'pos_ativacao'))
    if not all(isinstance(x, dict) for x in (artefato, ensaio, depois)):
        raise ValueError('Prova operacional inválida.')
    resultados = []
    casos = ensaio.get('resultados') or []
    if not isinstance(casos, list):
        raise ValueError('Resultados do ensaio inválidos.')
    for item in casos[:500]:
        if not isinstance(item, dict) or item.get('resultado') not in ('aprovado', 'falhou', 'ignorado', 'erro'):
            continue
        nome = item.get('caso', '')
        resultados.append({'caso': nome if isinstance(nome, str) and re.fullmatch(r'test_[A-Za-z0-9_]{1,180}', nome)
                           else 'nome_nao_exportado', 'resultado': item['resultado']})
    ensaio_limpo = {'estado': ensaio.get('estado') if ensaio.get('estado') in ('aprovado', 'falhou', 'indisponivel') else 'indisponivel',
                    'relatorio_sha256': _sha(ensaio.get('relatorio_sha256')), 'resultados': resultados}
    for nome in ('aprovados', 'casos', 'falhas', 'ignorados'):
        valor = ensaio.get(nome)
        ensaio_limpo[nome] = valor if type(valor) is int and 0 <= valor <= 100000 else None
    tempos = operacao.get('ensaios') or {}
    if not isinstance(tempos, dict) or not isinstance(tempos.get('aplicacao', {}), dict):
        raise ValueError('Tempos do ensaio inválidos.')
    tempos = (tempos.get('aplicacao') or {}).get('tempos_segundos') or {}
    if not isinstance(tempos, dict):
        raise ValueError('Tempos do ensaio inválidos.')
    backup_tempo = tempos.get('backup_codigo')
    if type(backup_tempo) not in (int, float) or not math.isfinite(backup_tempo) or backup_tempo < 0:
        backup_tempo = None
    depois_limpo = {nome: depois.get(nome) if type(depois.get(nome)) is bool else None
                    for nome in ('imagem_confere', 'pacote_confere', 'confirmacao_atual')}
    depois_limpo.update(sha_aprovada=_sha(depois.get('sha_aprovada'), 40),
                        publicada_em=_data(depois.get('publicada_em')), verificada_em=_data(depois.get('verificada_em')))
    origem, backup = prova.get('proveniencia') or {}, prova.get('backup') or {}
    if not isinstance(origem, dict) or not isinstance(backup, dict):
        raise ValueError('Origem ou backup inválidos.')
    backup_id = backup.get('identidade')
    if not isinstance(backup_id, str) or not re.fullmatch(r'[0-9]{8}-[0-9]{6}Z-[0-9a-f]{12}-[0-9]{1,12}', backup_id):
        backup_id = None
    backup_limpo = {'tempo_codigo_segundos': backup_tempo, 'identidade': backup_id,
                    'concluido': backup.get('concluido') if type(backup.get('concluido')) is bool else None,
                    'restauracao_comprovada': backup.get('restauracao_comprovada') if type(backup.get('restauracao_comprovada')) is bool else None,
                    'sha_manifesto': _sha(backup.get('sha_manifesto')),
                    'limite': 'Restauração, quando comprovada, ocorreu somente em banco isolado na VPS; produção não foi restaurada.'}
    for nome in ('bases', 'bases_restauradas', 'tabelas_conferidas', 'divergencias'):
        valor = backup.get(nome)
        backup_limpo[nome] = valor if type(valor) is int and 0 <= valor <= 100000 else None
    proveniencia = {'arvore_git': _sha(origem.get('arvore_git'), 40),
                    'prova_identidade': _sha(origem.get('prova_identidade')),
                    'versao_anterior': _sha(origem.get('versao_anterior'), 40)}
    for nome in ('arvore_confere', 'codigo_confere', 'pacote_confere'):
        proveniencia[nome] = origem.get(nome) if type(origem.get(nome)) is bool else None
    duracoes = operacao.get('tempos_segundos') or {}
    if not isinstance(duracoes, dict):
        raise ValueError('Tempos da operação inválidos.')
    fluxo = {nome: _data(valor) for nome, valor in (
        ('recebida_em', registro.get('recebida_em')),
        ('iniciada_em', operacao.get('iniciada_em')),
        ('concluida_em', operacao.get('concluida_em')))}
    fluxo['tempos_segundos'] = {nome: _segundos(duracoes.get(nome)) for nome in (
        'espelhamento', 'ensaio_aplicacao', 'promocao', 'registro_aplicacao',
        'ativacao_aplicacao', 'conferencia_aplicacao')}
    fluxo['ensaio_segundos'] = {nome: _segundos(tempos.get(nome)) for nome in (
        'backup_codigo', 'imagem', 'montagem', 'reaproveitamento', 'testes_comerciais')}
    fluxo['ensaio_reaproveitado'] = (operacao.get('ensaios') or {}).get('aplicacao', {}).get('reaproveitado')
    if type(fluxo['ensaio_reaproveitado']) is not bool:
        fluxo['ensaio_reaproveitado'] = None
    return {'id': registro['id'], 'commit': _sha(registro.get('commit'), 40), 'candidata': candidata,
            'coletada_em': _data(prova.get('coletada_em')),
            'artefato': {'codigo_sha256': _sha(artefato.get('codigo_sha256')), 'pacote_id': _sha(artefato.get('pacote_id'))},
            'backup': backup_limpo, 'proveniencia': proveniencia, 'fluxo': fluxo,
            'ensaio': ensaio_limpo, 'pos_ativacao': depois_limpo,
            'limite': 'Fotografia datada da consulta SSH; confirmação técnica não comprova jornada de aluno.'}


def registrar(host, registros):
    if not isinstance(registros, list):
        registros = [registros]
    if not 1 <= len(registros) <= 20:
        raise ValueError('Informe de uma a vinte consultas de entrega.')
    fotografias = [sanitizar(r) for r in registros]
    with transaction.atomic():
        rotina, _ = RotinaSuperEquipe.objects.get_or_create(host=host)
        rotina = RotinaSuperEquipe.objects.select_for_update().get(pk=rotina.pk)
        dados = rotina.entregas_operacionais.copy()
        for fotografia in fotografias:
            assinatura = hashlib.sha256(json.dumps(fotografia, sort_keys=True).encode()).hexdigest()
            anteriores = dados.setdefault(fotografia['id'], [])
            if not any(x.get('assinatura') == assinatura for x in anteriores):
                anteriores.append({'assinatura': assinatura, 'recebida_em': timezone.now().isoformat(),
                                    'fonte': 'Consulta SSH sitesdoreino-robo consultar ID', **fotografia})
        rotina.entregas_operacionais = dados
        rotina.save(update_fields=['entregas_operacionais'])
    return fotografias


def consultar(rotina):
    dados = rotina.entregas_operacionais if rotina else {}
    itens = [f[-1].copy() for f in dados.values() if isinstance(f, list) and f]
    agora = timezone.now()
    for item in itens:
        data = parse_datetime(item.get('coletada_em') or '')
        recente = bool(data and timezone.is_aware(data) and -60 <= (agora-data).total_seconds() <= 300)
        item['atualidade'] = 'recente' if recente else 'historica'
        item['confirmacao_atual'] = recente and item['pos_ativacao'].get('confirmacao_atual') is True
    return {'estado': 'medido' if itens else 'indisponivel', 'itens': itens,
            'limite': 'Última fotografia por entrega; anteriores preservadas. Não atualiza automaticamente nem reativa a rotina.'}
