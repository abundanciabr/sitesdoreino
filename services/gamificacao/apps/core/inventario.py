"""Inventário privado: arquivos e gestos da jornada pertencem à sessão."""
import hashlib
import io
from pathlib import PurePosixPath

from django.db import transaction
from django.http import FileResponse, JsonResponse
from django.middleware.csrf import get_token
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
    return {
        'pessoa_id': pessoa, 'site_id': site, 'csrf': get_token(request),
        'revisao': jornada['revisao'], 'atual_ordem': jornada['atual']['ordem'],
        'meta_cents': jornada['meta_cents'], 'proposito': jornada['proposito'],
        'chave': jornada['chave'], 'total': jornada['total'],
        'etapas': [{k: p[k] for k in ('ordem', 'nome', 'conquista', 'alcancada')} for p in jornada['lista']],
        'anexos': [{'id': a.id, 'passo': a.passo, 'nome': a.nome, 'tamanho': a.tamanho,
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
            if acao not in ('declaracao', 'anexo', 'meta', 'recebimento'):
                raise ValueError('Escolha um registro do inventário.')
            preparado = None
            if acao in ('anexo', 'declaracao'):
                try:
                    passo = int(request.POST.get('passo', '0'))
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
                if preparado:
                    nome, corpo, sha = preparado
                    AnexoDaJornada.objects.get_or_create(pessoa_id=pessoa, site_id=site, passo=passo, sha256=sha,
                        defaults={'nome': nome, 'conteudo': corpo, 'tamanho': len(corpo)})
                if acao == 'declaracao' and passo == 2 and not AnexoDaJornada.objects.filter(pessoa_id=pessoa, site_id=site, passo=2).exists():
                    raise ValueError('Anexe seu primeiro item 3D ou uma imagem dele antes de concluir.')
                # Repetir o clique não cria nova declaração nem novo bônus.
                repetida = acao == 'declaracao' and bool(jornada.declaracoes.get(str(passo)))
                if acao != 'anexo' and not repetida:
                    salvar(pessoa, site, request.POST, arquivo=request.FILES.get('print'))
        resposta = JsonResponse(_dados(request, pessoa, site))
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
    resposta = FileResponse(io.BytesIO(bytes(anexo.conteudo)), as_attachment=True,
                            filename=anexo.nome, content_type='application/octet-stream')
    resposta['X-Content-Type-Options'] = 'nosniff'
    return _privada(resposta)
