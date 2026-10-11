"""Prévia local isolada, com conta fictícia e banco exclusivo deste teste."""
import os
import sys
from pathlib import Path
from wsgiref.simple_server import make_server

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'output/previa-trilha'
OUT.mkdir(parents=True, exist_ok=True)
sys.path[:0] = [str(ROOT / 'services/gamificacao'), str(ROOT / 'packages/site_errors/src')]
os.environ.update(DJANGO_SETTINGS_MODULE='config.settings', DJANGO_SECRET_KEY='previa-local-sem-segredos',
                  DATABASE_URL='sqlite:///' + (OUT / 'previa.sqlite3').as_posix(),
                  SITE_ID='previa-motivos', DEBUG='1')
from django.conf import settings
settings.MIGRATION_MODULES = {'gamificacao': None, 'core': None, 'eventos': None, 'contenttypes': None}
settings.TEMPLATES[0]['DIRS'].append(ROOT / 'services/funil/templates')
import django
django.setup()
from django.core.management import call_command
call_command('migrate', run_syncdb=True, verbosity=0)
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.urls import path
from django.core.wsgi import get_wsgi_application
from apps.core import views, inventario, trilha_api
from config import urls

P, SITE = 'aluno-ficticio-local-2', 'previa-motivos'
views.quem_e = lambda request: P
inventario._sessao = lambda cookie: {'autenticado': True, 'id': P}
trilha_api._sessao = inventario._sessao

def trilha(request):
    response = render(request, 'funil/trilha_v4.html', {'trilha': {'aluno': {'nome': 'Teste local'}, 'pessoa_id': P, 'site_id': SITE}})
    response.set_cookie('previa_local', 'sim')
    return response

def asset(request, name):
    return HttpResponse((ROOT / 'services/funil/apps/core/trilha_v4_assets' / name).read_bytes(), content_type='text/css' if name.endswith('.css') else 'text/javascript')

urls.urlpatterns += [path('trilha/', trilha), path('trilha/style.css', asset, {'name': 'style.css'}, name='trilha_v4_css'),
                     path('trilha/app.js', asset, {'name': 'app.js'}, name='trilha_v4_js'),
                     path('encomendas/minha-trilha/', lambda request: JsonResponse({'pessoa_id': P, 'site_id': SITE, 'atividades': []}))]
application = get_wsgi_application()
def mounted(environ, start_response):
    if environ['PATH_INFO'].startswith('/conquistas/'):
        environ['SCRIPT_NAME'] = '/conquistas'
        environ['PATH_INFO'] = environ['PATH_INFO'][len('/conquistas'):]
    def protected(status, headers, exc_info=None):
        headers = [(k, v) for k, v in headers if k.lower() not in
                   ('x-frame-options', 'x-content-type-options', 'referrer-policy')]
        headers.extend([('X-Frame-Options', 'DENY'), ('X-Content-Type-Options', 'nosniff'),
                        ('Referrer-Policy', 'same-origin')])
        return start_response(status, headers, exc_info)
    return application(environ, protected)

if __name__ == '__main__':
    print('Prévia em http://127.0.0.1:8768/trilha/', flush=True)
    make_server('127.0.0.1', 8768, mounted).serve_forever()
