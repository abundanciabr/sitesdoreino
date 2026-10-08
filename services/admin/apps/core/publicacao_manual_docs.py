"""Ordem do mantenedor: /docs/ só recebe publicação manual pelo painel admin."""
import hashlib
import json
from contextlib import contextmanager
from functools import wraps

from django.conf import settings
from django.core import signing
from django.db import connection, transaction
from django.http import HttpResponseForbidden
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_protect

SALT = 'docs-publicacao-manual-v1'
INTENCAO = 'docs-intencao-no-painel-v1'


def impressao(documento):
    dados = [documento.nome, documento.titulo, documento.corpo, documento.formato]
    return hashlib.sha256(json.dumps(dados, ensure_ascii=False).encode()).hexdigest()


def admin_humano(request):
    from .porta import _emails_autorizados
    admin = getattr(request, 'admin', {}) or {}
    email = (admin.get('email') or '').strip().lower()
    return bool(email and email in _emails_autorizados() and not admin.get('robo')
                and not admin.get('equipe_apenas')
                and not request.META.get('HTTP_AUTHORIZATION'))


def somente_admin_manual(view):
    @wraps(view)
    def verificar(request, *args, **kwargs):
        if not admin_humano(request):
            return HttpResponseForbidden('Somente o admin pode fazer isso manualmente no painel.')
        return view(request, *args, **kwargs)
    return csrf_protect(verificar)


def _vinculo(request):
    cookies = [request.COOKIES.get(settings.ADMIN_LOCAL_COOKIE_NAME, ''),
               request.COOKIES.get('meshcraft_sessao', ''),
               request.META.get('CSRF_COOKIE', '')]
    return hashlib.sha256(json.dumps(cookies).encode()).hexdigest()


def intencao_no_painel(request, documento):
    if not admin_humano(request):
        return ''
    get_token(request)
    return signing.dumps({'impressao': impressao(documento),
                          'admin': request.admin['email'], 'sessao': _vinculo(request)},
                         salt=INTENCAO)


def conferir_intencao(request, documento):
    if not admin_humano(request):
        return False
    try:
        dados = signing.loads(request.POST.get('intencao_publicar', ''),
                              salt=INTENCAO, max_age=900)
    except (signing.BadSignature, ValueError, TypeError):
        return False
    return dados == {'impressao': impressao(documento),
                     'admin': request.admin['email'], 'sessao': _vinculo(request)}


def autorizado(documento):
    if not documento.publicacao_manual:
        return False
    try:
        dados = signing.loads(documento.publicacao_manual, salt=SALT)
    except (signing.BadSignature, ValueError, TypeError):
        return False
    return (isinstance(dados, dict) and bool(dados.get('admin'))
            and dados.get('impressao') == impressao(documento))


@contextmanager
def gravacao_manual(request, documento):
    if not admin_humano(request):
        raise PermissionError('Publicação exclusiva do admin no painel.')
    documento.publicacao_manual = signing.dumps(
        {'admin': request.admin['email'], 'impressao': impressao(documento)}, salt=SALT)
    with transaction.atomic():
        if connection.vendor == 'postgresql':
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('meshcraft.docs_manual', %s, true)",
                               [documento.publicacao_manual])
        try:
            yield
        finally:
            if connection.vendor == 'postgresql' and not connection.needs_rollback:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT set_config('meshcraft.docs_manual', '', true)")
