"""Fila persistente por versão, cache privado por conteúdo e leitura sem bloquear o aluno."""
from datetime import timedelta
import hashlib
import json
import os
from pathlib import Path
import re

from django.db import transaction
from django.utils import timezone

from .sandbox_models import AnaliseArquivoSandbox, AnaliseEntregaSandbox, EntregaSandbox


def pasta():
    from apps.core.telas_marketplace import _pasta_privada
    return _pasta_privada() / 'analises-v1'


def salvar(path, data):
    temp = path.with_suffix('.parcial')
    temp.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    temp.replace(path)


def preparar(entrega):
    analysis, _ = AnaliseEntregaSandbox.objects.get_or_create(entrega=entrega)
    for file in entrega.arquivos.all():
        key = hashlib.sha256((entrega.participacao.site_id + ':' + file.sha256 + ':' +
                              Path(file.nome).suffix.lower() + ':v1').encode()).hexdigest()
        AnaliseArquivoSandbox.objects.get_or_create(arquivo=file, defaults={
            'sha256': file.sha256, 'chave_cache': key})
    return analysis


def publicar_pedido(analysis):
    file = analysis.arquivo
    if not re.fullmatch('[a-f0-9]{32}', file.chave) or file.sha256 != analysis.sha256:
        analysis.estado = 'falha'
        analysis.falha = 'Arquivo sem chave privada compatível ou conteúdo divergente; não foi aberto.'
        analysis.save()
        return
    directory = pasta() / analysis.chave_cache
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    # O proprietário já existente do armazenamento opera a ponte no host.
    # Não amplia permissões de leitura de anexos nem entrega o Docker à aplicação.
    owner = directory.parent.parent.stat()
    if hasattr(os, 'chown') and os.geteuid() == 0:
        os.chown(directory.parent, owner.st_uid, owner.st_gid)
        os.chown(directory, owner.st_uid, owner.st_gid)
    if not (directory / 'pedido.json').exists():
        salvar(directory / 'pedido.json', {'chave': file.chave, 'sha256': file.sha256, 'nome': file.nome})
    status = directory / 'estado.json'
    if not status.exists():
        if timezone.now() - analysis.atualizada_em > timedelta(minutes=12):
            analysis.estado = 'falha'
            analysis.falha = 'O analisador não respondeu. Você pode tentar novamente.'
            analysis.save()
        return
    data = json.loads(status.read_text())
    state = data['estado']
    if state == 'processando' and timezone.now() - analysis.atualizada_em > timedelta(minutes=12):
        analysis.estado = 'falha'
        analysis.falha = 'O processamento foi interrompido. Você pode tentar novamente.'
        analysis.save()
        return
    if state == 'concluida':
        analysis.resultado = json.loads((directory / 'resultado.json').read_text())
        original = json.loads((directory / 'pedido.json').read_text())['nome']
        for membro in analysis.resultado.get('arquivos', []):
            if membro['arquivo'] == original or membro['arquivo'].startswith(original + ' / '):
                membro['arquivo'] = file.nome + membro['arquivo'][len(original):]
    if state != analysis.estado:
        analysis.estado = state
        analysis.falha = data.get('falha', '')
        analysis.save()


def evidencias(entrega, incluir_imagens=False):
    results, images = [], []
    for analysis in AnaliseArquivoSandbox.objects.filter(arquivo__entrega=entrega).select_related('arquivo'):
        file = analysis.arquivo
        item = {'arquivo_id': str(file.pk), 'arquivo': file.nome, 'sha256': analysis.sha256,
                'versao': entrega.versao, 'estado': analysis.estado, 'falha': analysis.falha,
                'conteudo': analysis.resultado}
        if file.sha256 != analysis.sha256:
            item.update(estado='falha', falha='Conteúdo mudou: análise anterior descartada.', conteudo={})
        results.append(item)
        if incluir_imagens and item['estado'] == 'concluida':
            for member in analysis.resultado.get('arquivos', []):
                for img in member.get('imagens', []):
                    name = img.get('arquivo', '')
                    if re.fullmatch('[a-f0-9]{24}(?:-(?:frontal|lateral|perspectiva))?\\.png', name):
                        path = pasta() / analysis.chave_cache / 'previas' / name
                        if path.is_file() and path.stat().st_size <= 8 * 1024 * 1024:
                            images.append({'arquivo': file.nome, 'membro': member['arquivo'],
                                           'vista': img['vista'], 'caminho': path})
    return results, images


def requisitos(termos):
    rows = []
    for campo in ('briefing', 'referencias', 'entregaveis', 'criterios'):
        value = termos.get(campo) or []
        values = value if isinstance(value, list) else re.split('[;\\n]', str(value))
        for texto in values:
            texto = str(texto).strip()
            if texto:
                rows.append({'id': str(len(rows) + 1), 'origem': campo, 'requisito': texto})
    return rows


def comparar(analysis):
    entrega = analysis.entrega
    from apps.core.ia_sandbox import avaliar_entrega
    found, images = evidencias(entrega, incluir_imagens=True)
    reqs = requisitos(entrega.participacao.termos)
    answer = avaliar_entrega(entrega.participacao, entrega, reqs, found, images)
    # IDs e requisitos vêm do aceite, nunca do texto gerado pelo modelo.
    answers = {str(row['id']): row for row in answer.get('requisitos', [])}
    rows = []
    for req in reqs:
        row = answers.get(req['id'], {})
        rows.append({**req, 'encontrado': str(row.get('encontrado', '')),
                     'nao_encontrado': str(row.get('nao_encontrado', '')),
                     'inconclusivo': str(row.get('inconclusivo', 'Sem evidência suficiente.')),
                     'evidencias': row.get('evidencias', [])})
    return {'versao': entrega.versao, 'entrega_id': str(entrega.pk), 'requisitos': rows,
            'tem_falhas': any(item['estado'] == 'falha' or any(m.get('estado') == 'falha' or m.get('aviso')
                for m in item.get('conteudo', {}).get('arquivos', [])) for item in found),
            'medidas_programas': found, 'interpretacao_visual_ia': str(answer.get('interpretacao_visual_ia', '')),
            'imagens_examinadas': [{k: v for k, v in im.items() if k != 'caminho'} for im in images[:12]],
            'imagens_nao_enviadas_ia': max(0, len(images) - 12)}


def processar_entrega(identificador):
    with transaction.atomic():
        a = AnaliseEntregaSandbox.objects.select_for_update().select_related('entrega__participacao').get(pk=identificador)
        if a.estado == 'concluida' or (a.tentar_em and a.tentar_em > timezone.now()):
            return
        if a.estado == 'comparando' and timezone.now() - a.atualizada_em < timedelta(minutes=8):
            return
        files = list(AnaliseArquivoSandbox.objects.filter(arquivo__entrega=a.entrega).select_related('arquivo'))
        for file in files:
            if file.estado not in ('concluida', 'falha'):
                publicar_pedido(file)
        if not files or any(f.estado not in ('concluida', 'falha') for f in files):
            a.estado = 'examinando'
            a.save()
            return
        a.estado = 'comparando'
        a.tentativas += 1
        a.save()
    try:
        result = comparar(a)
    except Exception:
        result = None
    with transaction.atomic():
        atual = AnaliseEntregaSandbox.objects.select_for_update().get(pk=a.pk)
        if result is None:
            atual.estado = 'falha_ia'
            atual.falha = 'A comparação por IA está indisponível. As medidas dos arquivos continuam disponíveis. Tente novamente.'
            atual.tentar_em = timezone.now() + timedelta(minutes=min(30, 2 ** min(atual.tentativas, 5)))
        else:
            atual.estado = 'concluida'
            atual.falha = ''
            atual.resultado = result
            atual.tentar_em = None
        atual.save()
    if result is not None and not a.entrega.participacao.entregas.filter(versao__gt=a.entrega.versao).exists():
        from apps.core.ia_sandbox import enfileirar
        enfileirar(a.entrega.participacao, 'entrega:' + str(a.entrega_id), 'cliente')


def rodada():
    # Inclui versões anteriores ainda sem análise sem tocar registros existentes.
    for entrega in EntregaSandbox.objects.filter(analise__isnull=True).order_by('criada_em')[:10]:
        preparar(entrega)
    for a in AnaliseEntregaSandbox.objects.exclude(estado='concluida').order_by('atualizada_em')[:10]:
        try:
            processar_entrega(a.pk)
        except Exception:
            AnaliseEntregaSandbox.objects.filter(pk=a.pk).update(
                estado='falha', falha='Não foi possível processar esta versão. Tente novamente.', atualizada_em=timezone.now())


def repetir(entrega):
    with transaction.atomic():
        a = AnaliseEntregaSandbox.objects.select_for_update().get(entrega=entrega)
        if a.estado in ('comparando', 'examinando', 'na_fila') or (a.estado == 'concluida' and not a.resultado.get('tem_falhas')):
            return
        for f in AnaliseArquivoSandbox.objects.filter(arquivo__entrega=entrega):
            if f.estado != 'falha' and not any(m.get('estado') == 'falha' or m.get('aviso') for m in f.resultado.get('arquivos', [])):
                continue
            directory = pasta() / f.chave_cache
            # Preserva arquivos e resultados: somente renomeia o estado da tentativa.
            state = directory / 'estado.json'
            if state.exists():
                state.rename(directory / ('estado-anterior-' + timezone.now().strftime('%Y%m%d%H%M%S%f') + '.json'))
            f.estado = 'na_fila'
            f.falha = ''
            f.save()
        a.estado = 'na_fila'
        a.falha = ''
        a.tentar_em = None
        a.save()
