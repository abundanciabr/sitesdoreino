"""Fila persistente por versão, cache privado por conteúdo e leitura sem bloquear o aluno."""
from datetime import timedelta
import hashlib
import json
import os
from pathlib import Path
import re

from django.db import transaction
from django.db.models import CharField, Exists, OuterRef, Q, Value
from django.db.models.functions import Cast, Concat
from django.utils import timezone

from .sandbox_models import AnaliseArquivoSandbox, AnaliseEntregaSandbox, EntregaSandbox, ParticipacaoSandbox
from . import devolutiva_sandbox as devolutiva


def pasta():
    from apps.core.telas_marketplace import _pasta_privada
    return _pasta_privada() / 'analises-v1'


def salvar(path, data):
    temp = path.with_suffix('.parcial')
    temp.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    temp.replace(path)


@transaction.atomic
def preparar(entrega):
    analysis, criada = AnaliseEntregaSandbox.objects.get_or_create(entrega=entrega, defaults={'site_id': entrega.site_id})
    for file in entrega.arquivos.all():
        key = hashlib.sha256((entrega.participacao.site_id + ':' + file.sha256 + ':' +
                              Path(file.nome).suffix.lower() + ':v1').encode()).hexdigest()
        AnaliseArquivoSandbox.objects.get_or_create(arquivo=file, defaults={
            'site_id': file.site_id, 'sha256': file.sha256, 'chave_cache': key})
    if criada:
        devolutiva.recebimento(entrega)
        from .faixas_eventos import sandbox_avaliacao_atualizada
        sandbox_avaliacao_atualizada(analysis)
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
        rows.append({**req, 'encontrado': devolutiva.texto_campo(row.get('encontrado'), 'encontrado'),
                     'nao_encontrado': devolutiva.texto_campo(row.get('nao_encontrado'), 'nao_encontrado'),
                     'inconclusivo': devolutiva.texto_campo(row.get('inconclusivo'), 'inconclusivo'),
                     'evidencias': row.get('evidencias', [])})
    avaliacao = answer.get('avaliacao') or {}
    if avaliacao.get('resultado') not in ('atende', 'precisa_ajustes', 'inconclusiva') or not isinstance(avaliacao.get('justificativa'), str) or not avaliacao['justificativa'].strip():
        raise ValueError('Avaliação automática sem conclusão fundamentada')
    sem_exame = (not found or devolutiva.lacunas({'medidas_programas': found})
                  or not any(item.get('conteudo', {}).get('arquivos') for item in found))
    arquivos_lidos = [item['arquivo'] for item in found if item.get('estado') == 'concluida']
    sem_prova = (not reqs or set(answers) != {r['id'] for r in reqs}
                 or any(not row['encontrado'] or row['nao_encontrado'] or row['inconclusivo']
                        or not isinstance(row['evidencias'], list) or not row['evidencias']
                        or not any(nome in str(prova) for prova in row['evidencias'] for nome in arquivos_lidos)
                        for row in rows))
    if avaliacao['resultado'] == 'atende' and (sem_exame or sem_prova):
        avaliacao = {'resultado': 'inconclusiva', 'justificativa': 'A leitura ou as evidências dos requisitos ficaram incompletas. Nenhuma conquista foi concedida; tente analisar novamente.'}
    return {'avaliacao': avaliacao, 'versao': entrega.versao, 'entrega_id': str(entrega.pk), 'requisitos': rows,
            'tem_falhas': bool(devolutiva.lacunas({'medidas_programas': found})),
            'medidas_programas': found, 'interpretacao_visual_ia': str(answer.get('interpretacao_visual_ia', '')),
            'imagens_examinadas': [{k: v for k, v in im.items() if k != 'caminho'} for im in images[:12]],
            'imagens_nao_enviadas_ia': max(0, len(images) - 12)}


def processar_entrega(identificador):
    with transaction.atomic():
        participacao_id = AnaliseEntregaSandbox.objects.filter(pk=identificador).values_list('entrega__participacao_id', flat=True).first()
        if participacao_id is None:
            return
        ParticipacaoSandbox.objects.select_for_update().get(pk=participacao_id)
        a = AnaliseEntregaSandbox.objects.select_for_update().select_related('entrega__participacao').filter(pk=identificador).first()
        if a is None:
            return
        if a.estado == 'concluida' or (a.tentar_em and a.tentar_em > timezone.now()):
            return
        if a.estado == 'comparando' and timezone.now() - a.atualizada_em < timedelta(minutes=8):
            return
        files = list(AnaliseArquivoSandbox.objects.filter(arquivo__entrega=a.entrega).select_related('arquivo'))
        for file in files:
            if file.estado not in ('concluida', 'falha'):
                publicar_pedido(file)
        if not files or any(f.estado not in ('concluida', 'falha') for f in files):
            if a.estado != 'examinando':
                a.estado = 'examinando'
                a.save()
                from .faixas_eventos import sandbox_avaliacao_atualizada
                sandbox_avaliacao_atualizada(a)
            return
        a.estado = 'comparando'
        a.tentativas += 1
        a.save()
        from .faixas_eventos import sandbox_avaliacao_atualizada
        sandbox_avaliacao_atualizada(a)
    try:
        result = comparar(a)
    except Exception:
        result = None
    with transaction.atomic():
        p = ParticipacaoSandbox.objects.select_for_update().get(pk=a.entrega.participacao_id)
        atual = AnaliseEntregaSandbox.objects.select_for_update().filter(pk=a.pk).first()
        if atual is None:
            return  # A limpeza cancelou esta análise enquanto a IA respondia.
        if atual.estado != 'comparando' or atual.tentativas != a.tentativas:
            return  # Outra tentativa tomou esta análise; a resposta antiga não publica nada.
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
        atual.entrega = a.entrega
        from .faixas_eventos import sandbox_avaliacao_atualizada
        sandbox_avaliacao_atualizada(atual)
        if result is None:
            devolutiva.indisponivel(atual)
        else:
            devolutiva.conclusao(atual)
            from .sandbox import ultima_entrega_do_aluno, aprovar
            ultima = ultima_entrega_do_aluno(p)
            if not a.entrega.teste_mantenedor and ultima and ultima.pk == a.entrega_id:
                if result.get('avaliacao', {}).get('resultado') == 'atende' and not devolutiva.lacunas(result):
                    aprovar(site_id=p.site_id, participacao_id=p.pk, aprovador_id='analise-automatica')
    if result is not None:
        from apps.core.ia_sandbox import enfileirar
        enfileirar(a.entrega.participacao, 'entrega:' + str(a.entrega_id) + ':' + str(len(atual.historico)), 'cliente')


def rodada():
    # Inclui versões anteriores ainda sem análise sem tocar registros existentes.
    for entrega in EntregaSandbox.objects.filter(analise__isnull=True).order_by('criada_em')[:10]:
        preparar(entrega)
    agora = timezone.now()
    prontas = (AnaliseEntregaSandbox.objects.exclude(estado='concluida')
        .filter(Q(tentar_em__isnull=True) | Q(tentar_em__lte=agora))
        .exclude(estado='comparando', atualizada_em__gt=agora - timedelta(minutes=8)))
    for a in prontas.order_by('atualizada_em', 'pk')[:10]:
        try:
            processar_entrega(a.pk)
        except Exception:
            with transaction.atomic():
                ParticipacaoSandbox.objects.select_for_update().get(pk=a.entrega.participacao_id)
                atual = AnaliseEntregaSandbox.objects.select_for_update().select_related('entrega__participacao').filter(pk=a.pk).first()
                existente = atual is not None
                if atual is not None:
                    atual.estado = 'falha'
                    atual.falha = 'Não foi possível processar esta versão. Tente novamente.'
                    atual.save()
                    from .faixas_eventos import sandbox_avaliacao_atualizada
                    sandbox_avaliacao_atualizada(atual)
            if existente and not a.entrega.participacao.entregas.filter(versao__gt=a.entrega.versao).exists():
                devolutiva.indisponivel(a)
    # Registros anteriores à publicação do fato entram no contexto sem gerar crédito retroativo.
    from .faixas_eventos import EV_AVALIACAO, sandbox_avaliacao_atualizada
    from .models import EventoMarketplace
    prefixo = f'faixas:{EV_AVALIACAO}:'
    emissao = EventoMarketplace.objects.filter(chave__startswith=Concat(
        Value(prefixo), Cast(OuterRef('pk'), output_field=CharField()), Value(':')))
    antigas = (AnaliseEntregaSandbox.objects.filter(entrega__teste_mantenedor=False)
               .annotate(publicada=Exists(emissao)).filter(publicada=False)
               .select_related('entrega__participacao').order_by('atualizada_em', 'pk')[:10])
    for antiga in antigas:
        with transaction.atomic():
            ParticipacaoSandbox.objects.select_for_update().get(pk=antiga.entrega.participacao_id)
            atual = (AnaliseEntregaSandbox.objects.select_for_update()
                     .select_related('entrega__participacao').filter(pk=antiga.pk).first())
            if atual is not None:
                sandbox_avaliacao_atualizada(atual, historico=True)


def repetir(entrega):
    with transaction.atomic():
        a = AnaliseEntregaSandbox.objects.select_for_update().get(entrega=entrega)
        if a.estado in ('comparando', 'examinando', 'na_fila') or (a.estado == 'concluida' and a.resultado.get('avaliacao', {}).get('resultado') in ('atende', 'precisa_ajustes') and not a.resultado.get('tem_falhas') and not devolutiva.lacunas(a.resultado)):
            return
        a.historico = [*a.historico, {'estado': a.estado, 'resultado': a.resultado, 'falha': a.falha,
            'atualizada_em': a.atualizada_em.isoformat(), 'medidas_programas': evidencias(entrega)[0]}]
        for f in AnaliseArquivoSandbox.objects.filter(arquivo__entrega=entrega):
            if f.estado != 'falha' and not any(m.get('estado') != 'concluida' or m.get('aviso') for m in f.resultado.get('arquivos', [])):
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
        from .faixas_eventos import sandbox_avaliacao_atualizada
        sandbox_avaliacao_atualizada(a)
