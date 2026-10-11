"""Inventário privado: arquivos e gestos da jornada pertencem à sessão."""
import hashlib
import io
from pathlib import PurePosixPath
from urllib.parse import urlencode

from django.db import transaction
from django.http import FileResponse, JsonResponse, HttpResponse
from django.middleware.csrf import get_token
from django.urls import reverse
from ninja.errors import HttpError

from apps.gamificacao.jornada import situacao, salvar
from apps.gamificacao.models import AnexoDaJornada, JornadaPessoal
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
                    'previa': f'/conquistas/inventario/arquivos/{a.id}/?previa=1' if PurePosixPath(a.nome).suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp'} else None,
                    'criado_em': a.criado_em.isoformat(),
                    'url': f'/conquistas/inventario/arquivos/{a.id}/'}
                   for a in AnexoDaJornada.objects.filter(pessoa_id=pessoa, site_id=site).defer('conteudo').order_by('-id')],
        'historico': [{'texto': r.dados.get('texto', ''), 'criado_em': r.criado_em.isoformat()} for r in jornada['historico']],
        'recebimentos': [{'valor': r.valor, 'estado': r.estado, 'data': r.recebido_em.isoformat()} for r in jornada['recebimentos']],
    }

def inventario(request):
    if request.method not in ('GET', 'POST'):
        resposta = JsonResponse({'detail': 'Método não permitido.'}, status=405)
        resposta['Allow'] = 'GET, POST'
        return _privada(resposta)
    try:
        pessoa, site = _dono(request)
        if request.method == 'POST':
            if request.POST.get('contexto_pessoa', pessoa) != pessoa or request.POST.get('contexto_site', site) != site:
                raise HttpError(403, 'Sua sessão mudou. Reabra o inventário antes de continuar.')
            acao = request.POST.get('acao')
            if acao not in ('declaracao', 'anexo', 'meta', 'recebimento', 'inicio-motivo', 'inicio-plano', 'inicio-compromisso', 'inicio-item', 'inicio-envio'):
                raise ValueError('Escolha um registro do inventário.')
            preparado = None
            if acao in ('anexo', 'declaracao', 'inicio-envio'):
                try:
                    passo = 2 if acao == 'inicio-envio' else int(request.POST.get('passo', '0'))
                except ValueError:
                    raise ValueError('Escolha uma das entregas da jornada.') from None
                if passo not in (2, 3, 4):
                    raise ValueError('Escolha uma das entregas da jornada.')
                if acao == 'declaracao' and request.POST.get('estado') != 'feito':
                    raise ValueError('Use a declaração de conclusão desta etapa.')
                arquivo = request.FILES.get('arquivo')
                if arquivo:
                    preparado = _arquivo(arquivo)
                elif acao == 'anexo':
                    raise ValueError('Escolha um arquivo para guardar.')
            with transaction.atomic():
                # A mesma linha serializa os anexos e a declaração existentes.
                from apps.core.perfil import perfil_de
                perfil_de(pessoa, site)
                JornadaPessoal.objects.get_or_create(pessoa_id=pessoa, site_id=site)
                jornada = JornadaPessoal.objects.select_for_update().get(pessoa_id=pessoa, site_id=site)
                from apps.gamificacao.bonus_inicio import recebido, recebido_faixa_amarela, conceder, comprovante
                faixa_antes = recebido_faixa_amarela(pessoa, site) if acao in ('inicio-envio', 'declaracao') else 0
                tarefa_do_post = (1 if acao == 'inicio-motivo' else
                                  2 if acao in ('inicio-plano', 'inicio-compromisso') else
                                  3 if acao == 'inicio-item' else
                                  4 if acao == 'inicio-envio' or acao == 'declaracao' and passo == 2 else None)
                tarefa_antes = recebido(pessoa, site, tarefa_do_post) if tarefa_do_post else 0
                if acao in ('anexo', 'inicio-envio') and str(jornada.revisao) != request.POST.get('revisao'):
                    raise ValueError('Seu registro mudou em outra aba. Suas respostas continuam na tela; confira a versão salva antes de tentar novamente.')
                if acao in ('inicio-motivo', 'inicio-plano', 'inicio-compromisso', 'inicio-item'):
                    from apps.gamificacao.inicio import salvar_inicio
                    salvar_inicio(jornada, request.POST)
                if acao == 'inicio-envio' or acao == 'anexo' and passo == 2:
                    from apps.gamificacao.inicio import requisitos_branca, etapas_inicio
                    if not etapas_inicio(pessoa, site, jornada)[3]['liberada']:
                        raise ValueError('Conclua as três tarefas anteriores e receba seus XP antes de enviar.')
                if acao == 'inicio-envio':
                    requisitos = requisitos_branca(jornada, True)
                    if not all(requisitos.values()):
                        raise ValueError('Conclua seu motivo, compromisso e primeiro item antes de enviar.')
                    if not preparado and not AnexoDaJornada.objects.filter(pessoa_id=pessoa, site_id=site, passo=2).exists():
                        raise ValueError('Escolha um arquivo do seu item 3D ou uma imagem dele.')
                if preparado:
                    from apps.gamificacao.inicio import texto
                    nome, corpo, sha = preparado
                    notas = {campo: texto(request.POST, campo, 500) for campo in ('aprendi', 'duvida')}
                    anexo, criado = AnexoDaJornada.objects.get_or_create(pessoa_id=pessoa, site_id=site, passo=passo, sha256=sha,
                        defaults={'nome': nome, 'conteudo': corpo, 'tamanho': len(corpo),
                                  **notas})
                    atualizadas = []
                    if not criado:
                        atualizadas = [campo for campo, valor in notas.items() if valor and valor != getattr(anexo, campo)]
                        for campo in atualizadas:
                            setattr(anexo, campo, notas[campo])
                        if atualizadas:
                            anexo.save(update_fields=atualizadas)
                    if acao == 'anexo' and (criado or atualizadas):
                        jornada.revisao += 1
                        jornada.save(update_fields=['revisao', 'atualizada_em'])
                if acao == 'declaracao' and passo == 2 and not AnexoDaJornada.objects.filter(pessoa_id=pessoa, site_id=site, passo=2).exists():
                    raise ValueError('Anexe seu primeiro item 3D ou uma imagem dele antes de concluir.')
                if acao == 'inicio-envio':
                    revisao_antes = jornada.revisao
                    dados_conclusao = request.POST.copy()
                    dados_conclusao['acao'] = 'declaracao'
                    dados_conclusao['passo'] = '2'
                    dados_conclusao['estado'] = 'feito'
                    salvar(pessoa, site, dados_conclusao)
                    jornada.refresh_from_db(fields=['revisao'])
                    if preparado and (criado or atualizadas) and jornada.revisao == revisao_antes:
                        jornada.revisao += 1
                        jornada.save(update_fields=['revisao', 'atualizada_em'])
                # Repetir o clique não cria nova declaração nem novo bônus.
                repetida = acao == 'declaracao' and situacao(pessoa, site)['lista'][passo - 1]['alcancada']
                if acao not in ('anexo', 'inicio-motivo', 'inicio-plano', 'inicio-compromisso', 'inicio-item', 'inicio-envio') and not repetida:
                    salvar(pessoa, site, request.POST, arquivo=request.FILES.get('print'))
                etapa_concluida = (
                    1 if acao == 'inicio-motivo' and request.POST.get('concluir') == 'sim' and
                         jornada.inicio.get('motivo') and not jornada.inicio.get('motivo_rascunho') else
                    2 if acao == 'inicio-plano' and request.POST.get('assumir') == 'sim' and
                         jornada.inicio.get('confirmado_em') else
                    2 if acao == 'inicio-compromisso' and request.POST.get('assumir') == 'sim' and
                         jornada.inicio.get('compromisso_curso_em') else
                    3 if acao == 'inicio-item' and jornada.inicio.get('item_pronto_em') else
                    4 if (acao == 'inicio-envio' or
                          acao == 'declaracao' and passo == 2 and request.POST.get('estado') == 'feito') and
                         situacao(pessoa, site)['atual']['ordem'] >= 2 else None
                )
                premio = None
                if etapa_concluida:
                    if etapa_concluida != 4:
                        conceder(pessoa, site, etapa_concluida)
                    novo_tarefa = recebido(pessoa, site, etapa_concluida) - tarefa_antes
                    novo_faixa = (recebido_faixa_amarela(pessoa, site) - faixa_antes
                                  if etapa_concluida == 4 else 0)
                    url_conquista = reverse('inicio-conquista', args=[etapa_concluida])
                    if novo_tarefa or novo_faixa:
                        token = comprovante(pessoa, site, etapa_concluida, novo_tarefa, novo_faixa)
                        url_conquista += '?' + urlencode({'comprovante': token})
                    else:
                        url_conquista += '?repetida=1'
                    premio = {
                        'conquista_url': url_conquista,
                        'conquista_xp_tarefa': novo_tarefa,
                        'conquista_xp_faixa': novo_faixa,
                        'conquista_xp': novo_tarefa + novo_faixa,
                        'conquista_ja_recebida': not novo_tarefa and bool(recebido(pessoa, site, etapa_concluida)),
                    }
        dados_resposta = _dados(request, pessoa, site)
        if request.method == 'POST' and premio:
            dados_resposta.update(premio)
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
