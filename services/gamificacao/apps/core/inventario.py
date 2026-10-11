"""Inventário privado: arquivos e gestos da jornada pertencem à sessão."""
import hashlib
import uuid
import io
from pathlib import PurePosixPath
from urllib.parse import urlencode

from django.db import transaction
from django.http import FileResponse, JsonResponse, HttpResponse
from django.middleware.csrf import get_token
from django.urls import reverse
from ninja.errors import HttpError

from apps.gamificacao.jornada import situacao, salvar
from apps.gamificacao.models import AnexoDaJornada, JornadaPessoal, AvaliacaoDaJornada, RegistroDaJornada
from .sessao import _sessao, site_atual, ConfiguracaoAusente, IdentidadeIndisponivel
from .trilha_pessoal import _privada

MAX_ARQUIVO = 20 * 1024 * 1024
EXTENSOES = {'.blend', '.glb', '.gltf', '.obj', '.stl', '.fbx', '.zip', '.png', '.jpg', '.jpeg', '.webp'}

def _dono(request):
    site = site_atual()
    if not site:
        raise HttpError(503, 'Não foi possível consultar seu inventário agora.')
    cookie = request.META.get('HTTP_COOKIE', '')
    if not cookie:
        raise HttpError(403, 'Entre na sua conta para abrir seu inventário.')
    try:
        sessao = _sessao(cookie)
    except (ConfiguracaoAusente, IdentidadeIndisponivel):
        raise HttpError(503, 'Não foi possível confirmar sua sessão agora.') from None
    if sessao.get('autenticado') is not True or not isinstance(sessao.get('id'), str) or not sessao['id'].strip():
        raise HttpError(403, 'Sua sessão expirou. Entre novamente.')
    return sessao['id'], site

def _arquivo(arquivo):
    nome = PurePosixPath(arquivo.name.replace('\\', '/')).name[:180]
    if PurePosixPath(nome).suffix.lower() not in EXTENSOES:
        raise ValueError('Envie um modelo 3D, ZIP ou imagem nos formatos indicados.')
    if arquivo.size > MAX_ARQUIVO:
        raise ValueError('O arquivo deve ter até 20 MB.')
    corpo = arquivo.read(MAX_ARQUIVO + 1)
    if not corpo or len(corpo) > MAX_ARQUIVO:
        raise ValueError('Envie um arquivo não vazio de até 20 MB.')
    return nome, corpo, hashlib.sha256(corpo).hexdigest()

def _dados(request, pessoa, site):
    jornada = situacao(pessoa, site)
    from apps.gamificacao.inicio import para_tela
    return {
        'pessoa_id': pessoa, 'site_id': site, 'csrf': get_token(request),
        'revisao': jornada['revisao'], 'atual_ordem': jornada['atual']['ordem'],
        'meta_cents': jornada['meta_cents'], 'proposito': jornada['proposito'],
        'chave': jornada['chave'], 'total': jornada['total'],
        'inicio': para_tela(JornadaPessoal.objects.filter(pessoa_id=pessoa, site_id=site).first()),
        'etapas': [{k: p[k] for k in ('ordem', 'nome', 'conquista', 'alcancada')} for p in jornada['lista']],
        'anexos': [{'id': a.id, 'passo': a.passo, 'nome': a.nome, 'tamanho': a.tamanho,
                    'aprendi': a.aprendi, 'duvida': a.duvida,
                    'previa': f'/trilha/inventario/arquivos/{a.id}/?previa=1' if PurePosixPath(a.nome).suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp'} else None,
                    'criado_em': a.criado_em.isoformat(),
                    'url': f'/trilha/inventario/arquivos/{a.id}/'}
                   for a in AnexoDaJornada.objects.filter(pessoa_id=pessoa, site_id=site).defer('conteudo').order_by('-id')],
        'caminho': jornada.get('caminho'), 'graus_historicos': jornada.get('graus_historicos', []), 'faixa_nome': jornada['atual']['nome'],
        'avaliacoes': [{'ordem': a.ordem, 'resultado': a.resultado, 'feedback': a.feedback, 'criada_em': a.criada_em.isoformat()} for a in AvaliacaoDaJornada.objects.filter(pessoa_id=pessoa, site_id=site).order_by('-id')[:20]],
        'analises_pendentes': (JornadaPessoal.objects.filter(pessoa_id=pessoa, site_id=site).first().inicio or {}).get('analises_pendentes', {}) if JornadaPessoal.objects.filter(pessoa_id=pessoa, site_id=site).exists() else {},
        'historico': [{'texto': r.dados.get('texto', ''), 'criado_em': r.criado_em.isoformat()} for r in jornada['historico']],
        'recebimentos': [{'valor': r.valor, 'estado': r.estado, 'data': r.recebido_em.isoformat()} for r in jornada['recebimentos']],
    }

def inventario(request):
    if request.method not in ('GET', 'POST'):
        resposta = JsonResponse({'detail': 'Método não permitido.'}, status=405)
        resposta['Allow'] = 'GET, POST'
        return _privada(resposta)
    premio, analise, token, ordem, anexos = None, None, None, None, []
    ganho_tarefa = ganho_faixa = bonus_avaliacao = 0
    avaliacao_atual = None
    try:
        pessoa, site = _dono(request)
        if request.method == 'POST':
            if request.POST.get('contexto_pessoa', pessoa) != pessoa or request.POST.get('contexto_site', site) != site:
                raise HttpError(403, 'Sua sessão mudou. Reabra o inventário antes de continuar.')
            acao = request.POST.get('acao')
            permitidas = ('anexo', 'meta', 'recebimento', 'correcao', 'inicio-motivo', 'inicio-plano', 'inicio-compromisso', 'inicio-item', 'inicio-envio', 'ciclo-avaliar')
            if acao not in permitidas:
                raise ValueError('A conquista exige a avaliação desta etapa. Abra a atividade para continuar.')
            preparados = []
            if acao in ('anexo', 'inicio-envio', 'inicio-item', 'ciclo-avaliar'):
                for campo in ('arquivo_anterior', 'arquivo'):
                    if request.FILES.get(campo):
                        preparados.append((campo, _arquivo(request.FILES[campo])))
            tarefa = {'inicio-motivo': 1, 'inicio-compromisso': 2, 'inicio-plano': 2, 'inicio-item': 3, 'inicio-envio': 4}.get(acao)
            from apps.gamificacao.bonus_inicio import conceder, recebido, recebido_faixa, comprovante
            with transaction.atomic():
                from apps.core.perfil import perfil_de
                perfil_de(pessoa, site)
                JornadaPessoal.objects.get_or_create(pessoa_id=pessoa, site_id=site)
                j = JornadaPessoal.objects.select_for_update().get(pessoa_id=pessoa, site_id=site)
                if str(j.revisao) != request.POST.get('revisao'):
                    raise ValueError('Seu registro mudou em outra aba. Confira a versão salva antes de tentar novamente.')
                from apps.gamificacao.inicio import salvar_inicio, etapas_inicio, texto
                from apps.gamificacao.jornada import recuperar_avaliacoes_anteriores
                recuperar_avaliacoes_anteriores(pessoa, site)
                j.refresh_from_db()
                antes = situacao(pessoa, site)
                faixa_antes = recebido_faixa(pessoa, site, tarefa) if tarefa in (2, 3, 4) else 0
                if acao in ('inicio-motivo', 'inicio-plano', 'inicio-compromisso', 'inicio-item'):
                    salvar_inicio(j, request.POST)
                    if tarefa == 2:
                        ganho_faixa = max(0, recebido_faixa(pessoa, site, 2) - faixa_antes)
                        if acao == 'inicio-compromisso' and request.POST.get('assumir') == 'sim':
                            avaliacao = AvaliacaoDaJornada.objects.filter(pessoa_id=pessoa, site_id=site, ordem=2).order_by('-id').first()
                            if avaliacao:
                                avaliacao_atual = {'ordem': 2, 'resultado': avaliacao.resultado, 'feedback': avaliacao.feedback,
                                    'conquistada': avaliacao.resultado == 'reconhecida' and situacao(pessoa, site)['atual']['ordem'] >= 2,
                                    'bonus_xp': ganho_faixa}
                if acao == 'inicio-envio' and not etapas_inicio(pessoa, site, j)[3]['liberada']:
                    raise ValueError('Conclua a avaliação do relato do seu item antes de apresentar o material.')
                if acao == 'ciclo-avaliar':
                    try:
                        ordem = int(request.POST.get('ordem', '0'))
                    except ValueError:
                        raise ValueError('Escolha a etapa da sua criação.') from None
                    if (j.inicio or {}).get('motivo') not in ('ugc', 'jogo', 'aprender') or ordem not in (5, 6, 7):
                        raise ValueError('Abra a atividade do caminho que escolheu.')
                    if antes['atual']['ordem'] < ordem - 1:
                        raise ValueError('Conclua a faixa anterior antes de avaliar esta etapa.')
                passo = ordem if acao == 'ciclo-avaliar' else 2
                if acao == 'anexo' and not preparados:
                    raise ValueError('Escolha um arquivo para guardar.')
                for campo, (nome, corpo, sha) in preparados:
                    anexo, criado = AnexoDaJornada.objects.get_or_create(
                        pessoa_id=pessoa, site_id=site, passo=passo, sha256=sha,
                        defaults={'nome': nome, 'conteudo': corpo, 'tamanho': len(corpo),
                                  'aprendi': texto(request.POST, 'aprendi', 500), 'duvida': texto(request.POST, 'duvida', 500)})
                    if not criado:
                        for nota in ('aprendi', 'duvida'):
                            valor = texto(request.POST, nota, 500)
                            if valor:
                                setattr(anexo, nota, valor)
                        anexo.save(update_fields=['aprendi', 'duvida'])
                    anexos.append(anexo)
                if acao == 'inicio-item':
                    ordem = 3
                elif acao == 'inicio-envio':
                    ordem = 4
                    if not anexos:
                        anterior = AnexoDaJornada.objects.filter(pessoa_id=pessoa, site_id=site, passo=2).order_by('-id').first()
                        if anterior:
                            anexos = [anterior]
                    if not anexos:
                        raise ValueError('Apresente uma imagem ou um modelo compatível do seu item.')
                if acao == 'ciclo-avaliar':
                    if not anexos:
                        raise ValueError('Apresente a versão da sua criação para análise.')
                    if ordem in (5, 6) and len(anexos) != 2:
                        raise ValueError('Apresente a versão anterior e a atual do mesmo item para a comparação.')
                if ordem is not None:
                    token = str(uuid.uuid4())
                    analise = {k: texto(request.POST, k, limite) for k, limite in (
                        ('item_nome', 180), ('item_acao', 1000), ('explicacao', 1000), ('parte', 180))}
                    analise.update(item_nome=analise['item_nome'] or j.inicio.get('item_nome', ''),
                        item_acao=analise['item_acao'] or j.inicio.get('item_acao', ''),
                        caminho=j.inicio.get('motivo'), ordem=ordem, chave=token)
                    if ordem >= 5 and j.inicio.get('item_nome') and analise['item_nome'] != j.inicio['item_nome']:
                        raise ValueError('Continue o mesmo item que apresentou no começo. Use o nome já registrado.')
                    if ordem == 7 and analise['caminho'] == 'aprender':
                        anterior = AnexoDaJornada.objects.filter(pessoa_id=pessoa, site_id=site, passo=6).order_by('-id').first()
                        if anterior is None:
                            anterior = AnexoDaJornada.objects.filter(pessoa_id=pessoa, site_id=site, passo=2).order_by('-id').first()
                        if anterior and anterior.id != anexos[-1].id:
                            anexos.insert(0, anterior)
                            analise['anexo_anterior_id'] = anterior.id
                            analise['anexo_final_id'] = anexos[-1].id
                    pendentes = dict(j.inicio.get('analises_pendentes', {}))
                    pendentes[str(ordem)] = {'chave': token, 'dados': analise, 'anexos': [a.id for a in anexos], 'estado': 'pendente'}
                    j.inicio = {**j.inicio, 'analises_pendentes': pendentes}
                elif acao in ('meta', 'recebimento', 'correcao'):
                    salvar(pessoa, site, request.POST, arquivo=request.FILES.get('print'))
                    j.refresh_from_db()
                j.revisao += 1
                j.save(update_fields=['inicio', 'revisao', 'atualizada_em'])
                if tarefa == 1 and request.POST.get('concluir') == 'sim':
                    ganho_tarefa += conceder(pessoa, site, 1)
                elif tarefa == 2 and request.POST.get('assumir') == 'sim':
                    ganho_tarefa += conceder(pessoa, site, 2)
                elif tarefa == 4:
                    ganho_tarefa += conceder(pessoa, site, 4)
                RegistroDaJornada.objects.create(pessoa_id=pessoa, site_id=site, acao='atividade',
                    dados={'texto': 'Atividade guardada para avaliação.' if ordem else 'Escolha guardada na sua conta.',
                           'acao': acao, 'ordem': ordem, 'anexos': [a.id for a in anexos]})
            # O provedor é chamado após persistir a submissão; nenhuma rede dentro do lock.
            if analise is not None:
                from apps.gamificacao.avaliacao_inicio import avaliar
                resultado = avaliar(pessoa, site, ordem, analise, anexos=anexos)
                with transaction.atomic():
                    j = JornadaPessoal.objects.select_for_update().get(pessoa_id=pessoa, site_id=site)
                    pendentes = dict(j.inicio.get('analises_pendentes', {}))
                    atual = pendentes.get(str(ordem), {})
                    if atual.get('chave') == token and j.inicio.get('motivo') == analise['caminho']:
                        from apps.gamificacao.jornada import registrar_avaliacao
                        evidencia = {**resultado.get('evidencia', {}), 'chave': token,
                            'anexos': [a.id for a in anexos], 'atividade': analise}
                        faixa_antes = recebido_faixa(pessoa, site, tarefa) if tarefa in (2, 3, 4) else 0
                        depois = registrar_avaliacao(pessoa, site, ordem, resultado['resultado'], resultado['feedback'], evidencia)
                        bonus_avaliacao = int(depois.get('bonus_xp') or 0)
                        ganho_faixa += max(0, recebido_faixa(pessoa, site, tarefa) - faixa_antes) if tarefa in (2, 3, 4) else bonus_avaliacao
                        avaliacao_atual = {'ordem': ordem, 'resultado': resultado['resultado'], 'feedback': resultado['feedback'],
                            'conquistada': resultado['resultado'] == 'reconhecida' and depois['atual']['ordem'] >= ordem,
                            'bonus_xp': bonus_avaliacao}

                        j.refresh_from_db()
                        pendentes = dict(j.inicio.get('analises_pendentes', {}))
                        pendentes.pop(str(ordem), None)
                        j.inicio = {**j.inicio, 'analises_pendentes': pendentes}
                        j.save(update_fields=['inicio', 'atualizada_em'])
                        if tarefa == 3 and resultado['resultado'] == 'reconhecida':
                            ganho_tarefa += conceder(pessoa, site, 3)
                    else:
                        avaliacao_atual = {'ordem': ordem, 'resultado': 'falha', 'feedback': 'Seu caminho ou a versão mudou durante a análise. Confira a etapa atual e tente novamente.', 'conquistada': False, 'bonus_xp': 0}
                        # Um retorno obsoleto fica registrado, sem reconhecer outra versão/caminho.
                        RegistroDaJornada.objects.create(pessoa_id=pessoa, site_id=site, acao='analise-obsoleta',
                            dados={'texto': 'A análise de uma versão anterior terminou. Avalie a versão atual.',
                                   'ordem': ordem, 'chave': token, 'resultado': resultado['resultado'], 'feedback': resultado['feedback']})
            ganho = ganho_tarefa + ganho_faixa
            concluindo = (tarefa == 1 and request.POST.get('concluir') == 'sim' or tarefa == 2 and request.POST.get('assumir') == 'sim' or tarefa in (3, 4))
            if tarefa and concluindo:
                premio = {'conquista_xp': ganho, 'conquista_xp_tarefa': ganho_tarefa,
                    'conquista_xp_faixa': ganho_faixa, 'conquista_ja_recebida': ganho == 0}
                # A tela de conquista só abre depois do reconhecimento real (motivo registra microbônus).
                reconhecida = tarefa == 1 or bool(avaliacao_atual and avaliacao_atual['conquistada'])
                if reconhecida:
                    url = reverse('inicio-conquista', args=[tarefa])
                    if ganho_tarefa or ganho_faixa:
                        url += '?' + urlencode({'comprovante': comprovante(pessoa, site, tarefa, ganho_tarefa, ganho_faixa)})
                    premio['conquista_url'] = url
        dados_resposta = _dados(request, pessoa, site)
        if premio:
            dados_resposta.update(premio)
        if avaliacao_atual:
            dados_resposta['avaliacao_atual'] = avaliacao_atual
        resposta = JsonResponse(dados_resposta)
    except HttpError as erro:
        resposta = JsonResponse({'detail': erro.message}, status=erro.status_code)
    except (ValueError, TypeError) as erro:
        resposta = JsonResponse({'detail': str(erro) if isinstance(erro, ValueError) else 'Confira os dados enviados.'}, status=400)
    return _privada(resposta)

def arquivo_do_inventario(request, anexo_id):
    if request.method not in ('GET', 'HEAD'):
        return _privada(JsonResponse({'detail': 'Método não permitido.'}, status=405))
    try:
        pessoa, site = _dono(request)
    except HttpError as erro:
        return _privada(JsonResponse({'detail': erro.message}, status=erro.status_code))
    anexo = AnexoDaJornada.objects.filter(id=anexo_id, pessoa_id=pessoa, site_id=site).first()
    if anexo is None:
        return _privada(JsonResponse({'detail': 'Arquivo não encontrado.'}, status=404))
    if request.GET.get('previa') == '1':
        from PIL import Image, UnidentifiedImageError
        try:
            with Image.open(io.BytesIO(bytes(anexo.conteudo))) as imagem:
                if imagem.format not in ('PNG', 'JPEG', 'WEBP') or imagem.width * imagem.height > 20_000_000:
                    raise ValueError
                imagem.thumbnail((1000, 1000))
                destino = io.BytesIO()
                imagem.convert('RGB').save(destino, format='PNG')
            resposta = HttpResponse(destino.getvalue(), content_type='image/png')
            resposta['X-Content-Type-Options'] = 'nosniff'
            return _privada(resposta)
        except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            return _privada(JsonResponse({'detail': 'Prévia indisponível; seu arquivo continua guardado.'}, status=404))
    resposta = FileResponse(io.BytesIO(bytes(anexo.conteudo)), as_attachment=True,
                            filename=anexo.nome, content_type='application/octet-stream')
    resposta['X-Content-Type-Options'] = 'nosniff'
    return _privada(resposta)
