import mimetypes
import os
import uuid
from pathlib import Path
from urllib.parse import quote

from django.conf import settings
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count
from django.http import FileResponse, Http404, JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from .clients import AlunosClient, IdentidadeClient, IdentidadeIndisponivel
from .galeria_models import ComentarioDaGaleria, VotoDaGaleria

IMAGENS = [
    ('apple', 'Apple', 'Clara, elegante e com espaço para respirar.'),
    ('premium', 'Premium', 'Tons escuros e detalhes dourados.'),
    ('estudio', 'Estúdio criativo', 'Pessoas, portfólios e cores vibrantes.'),
    ('gamificada', 'Gamificada', 'Avatares e conquistas com estética de jogo.'),
    ('galeria', 'Galeria de artistas', 'Uma apresentação editorial dos talentos.'),
    ('acolhedora', 'Acolhedora', 'Cores suaves e proximidade entre alunos.'),
    ('futurista', 'Futurista', 'Um campus criativo com vidro e violeta.'),
    ('minimalista', 'Minimalista', 'Poucos elementos, foco nas pessoas.'),
    ('ultra-premium', 'Ultra Premium', 'Marfim, bordô e acabamento sofisticado.'),
]
SLUGS = frozenset(i[0] for i in IMAGENS)


def caminho_publico(caminho):
    prefixo_aula = '/previa-aula-1'
    if caminho in {prefixo_aula, prefixo_aula + '/', prefixo_aula + '/voto', prefixo_aula + '/comentario', prefixo_aula + '/galeria.css', prefixo_aula + '/galeria.js'} or caminho.startswith(prefixo_aula + '/imagens/'):
        return True
    return caminho in {'/galeria-publica', '/galeria-publica/', '/galeria-publica/voto', '/galeria-publica/comentario'} or caminho.startswith('/galeria-publica/imagens/') or caminho in {'/galeria-publica/galeria.css', '/galeria-publica/galeria.js'}


class CookieDaGaleria:
    """Mantém o CSRF da votação no caminho da própria página pública."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if caminho_publico(request.path_info) and settings.CSRF_COOKIE_NAME in response.cookies:
            from .galeria_aula1 import BASE
            response.cookies[settings.CSRF_COOKIE_NAME]['path'] = BASE if request.path_info.startswith('/previa-aula-1') else '/comunidade'
        return response


def aluno(request):
    cookie = request.META.get('HTTP_COOKIE', '')
    if not cookie:
        return None
    try:
        sessao = IdentidadeClient().sessao_completa(cookie)
    except IdentidadeIndisponivel:
        return None
    email = (sessao.get('email') or '').strip().lower()
    if not (sessao.get('autenticado') and sessao.get('id') and email):
        return None
    ficha = AlunosClient().prontuario(email)
    if not ficha or ficha.get('categoria') != 'aluno':
        return None
    return {'id': str(sessao['id']), 'email': email, 'nome': (ficha.get('nome_completo') or sessao.get('nome_exibido') or email)[:250]}


def classificacao(pessoa=None, *, imagens=IMAGENS, base='/comunidade', ordem_fixa=False):
    slugs = {i[0] for i in imagens}
    totais = {r['imagem']: r['total'] for r in VotoDaGaleria.objects.filter(ativo=True, imagem__in=slugs).values('imagem').annotate(total=Count('id'))}
    meus = set(VotoDaGaleria.objects.filter(pessoa_id=pessoa['id'], ativo=True).values_list('imagem', flat=True)) if pessoa else set()
    linhas = [{'slug': slug, 'titulo': titulo, 'descricao': descricao, 'votos': totais.get(slug, 0), 'votado': slug in meus, 'ordem': ordem, 'url': base + '/imagens/' + slug} for ordem, (slug, titulo, descricao) in enumerate(imagens)]
    return linhas if ordem_fixa else sorted(linhas, key=lambda i: (-i['votos'], i['ordem']))


@require_GET
@never_cache
def galeria(request):
    pessoa = aluno(request)
    return render(request, 'admin/galeria_publica.html', {'imagens': classificacao(pessoa), 'aluno': pessoa, 'csrf': get_token(request)})


@require_POST
@never_cache
def votar(request, *, imagens=IMAGENS, base='/comunidade', ordem_fixa=False):
    pessoa = aluno(request)
    if not pessoa:
        return JsonResponse({'erro': 'Entre com sua conta de aluno com matrícula ativa para participar.'}, status=403)
    slug, acao = request.POST.get('imagem'), request.POST.get('acao')
    if slug not in {i[0] for i in imagens} or acao not in {'votar', 'retirar'}:
        return JsonResponse({'erro': 'Escolha uma imagem e uma ação válidas.'}, status=400)
    with transaction.atomic():
        voto, _ = VotoDaGaleria.objects.get_or_create(pessoa_id=pessoa['id'], imagem=slug, defaults={'ativo': acao == 'votar'})
        voto = VotoDaGaleria.objects.select_for_update().get(pk=voto.pk)
        voto.ativo = acao == 'votar'
        voto.save(update_fields=['ativo', 'atualizado_em'])
    return JsonResponse({'imagens': classificacao(pessoa, imagens=imagens, base=base, ordem_fixa=ordem_fixa)})


@require_POST
@never_cache
def comentar(request, *, imagens=IMAGENS):
    pessoa = aluno(request)
    if not pessoa:
        return JsonResponse({'erro': 'Entre com sua conta de aluno com matrícula ativa para participar.'}, status=403)
    slug, texto = request.POST.get('imagem'), (request.POST.get('texto') or '').strip()
    try:
        chave = uuid.UUID(request.POST.get('chave', ''))
    except (ValueError, TypeError, AttributeError):
        return JsonResponse({'erro': 'Reabra o comentário e tente novamente.'}, status=400)
    if slug not in {i[0] for i in imagens} or not texto or len(texto) > 4000:
        return JsonResponse({'erro': 'Escolha uma imagem e escreva seu comentário (até 4.000 caracteres).'}, status=400)
    ComentarioDaGaleria.objects.get_or_create(pessoa_id=pessoa['id'], chave=chave, defaults={'nome': pessoa['nome'], 'email': pessoa['email'], 'imagem': slug, 'texto': texto})
    return JsonResponse({'mensagem': 'Comentário enviado. Obrigado!', 'chave': str(uuid.uuid4())})


@require_GET
def imagem(request, slug, *, imagens=IMAGENS):
    if slug not in {i[0] for i in imagens}:
        raise Http404
    raiz = Path(os.environ.get('COMUNIDADE_GALERIA_DIR', '/opt/plataforma/admin-midia/comunidade-conceitos'))
    mini = request.GET.get('mini') == '1'
    arquivo = raiz / (slug + ('-mini.webp' if mini else '.png'))
    if not arquivo.is_file():
        raise Http404
    response = FileResponse(arquivo.open('rb'), content_type='image/webp' if mini else 'image/png')
    response['Cache-Control'] = 'public, max-age=86400'
    return response


@require_GET
def recurso(request, nome):
    if nome not in {'galeria.css', 'galeria.js'}:
        raise Http404
    arquivo = Path(settings.BASE_DIR) / 'static' / 'comunidade-galeria' / nome
    return FileResponse(arquivo.open('rb'), content_type=mimetypes.guess_type(nome)[0])


@require_GET
@never_cache
def comentarios_admin(request):
    from .galeria_aula1 import IMAGENS as CENAS
    todas = IMAGENS + CENAS
    filtro = request.GET.get('imagem', '')
    registros = ComentarioDaGaleria.objects.all()
    if filtro in {i[0] for i in todas}:
        registros = registros.filter(imagem=filtro)
    pagina = Paginator(registros, 50).get_page(request.GET.get('pagina'))
    nomes = dict((i[0], i[1]) for i in todas)
    for comentario in pagina:
        comentario.modelo = nomes.get(comentario.imagem, comentario.imagem)
        comentario.crm = '/admin/contatos/?q=' + quote(comentario.email, safe='')
    return render(request, 'admin/galeria_comentarios.html', {'admin': request.admin, 'pagina': pagina, 'imagens': todas, 'filtro': filtro, 'ranking': classificacao()})
