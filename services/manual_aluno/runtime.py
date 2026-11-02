"""Reuse the installed course clients and journey, without migrations or workers."""
import os
import sys

sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from config.runtime import load_original_settings, install_contextual_settings, serving
load_original_settings()
install_contextual_settings()
from internal import instalar
instalar()

from app import Application, Unavailable
from django.db import connections, transaction, close_old_connections


class Production:
    def access(self, cookie):
        close_old_connections()
        if not cookie:
            return {'autenticado': False}, [], {}
        with serving('cursos'):
            from modules.cursos.apps.core.clients import IdentidadeClient, AlunosClient
            from modules.cursos.apps.core.sessao import site_atual
            from modules.cursos.apps.cursos.models import Curso
            identity = IdentidadeClient().sessao_completa(cookie)
            if identity.get('autenticado') is not True:
                return identity, [], {}
            if not identity.get('id') or not identity.get('email'):
                raise Unavailable()
            course = Curso.objects.filter(site_id=site_atual(), slug='primeiros-dolares').values('site_id', 'produto_id').first()
            if not course or not course.get('produto_id'):
                raise Unavailable()
            enrollments = AlunosClient().matriculas_de(identity['email'].strip().lower())
            return identity, enrollments, course

    def progress(self, person, site):
        with serving('cursos'):
            from modules.cursos.apps.cursos.models import Aula
            lesson_states = {a['titulo_exibido']: 'Disponível conforme sua progressão' if a['estado'] == 'publicada' else 'Em preparo'
                             for a in Aula.objects.filter(curso__site_id=site, curso__slug='primeiros-dolares').values('titulo_exibido', 'estado')}
        with serving('gamificacao'), transaction.atomic(using='gamificacao'):
            with connections['gamificacao'].cursor() as cursor:
                cursor.execute('SET TRANSACTION READ ONLY')
            from modules.gamificacao.apps.gamificacao.jornada import situacao, reais
            from modules.gamificacao.apps.gamificacao.models import JornadaPessoal
            data = situacao(person, site)
            journey = JornadaPessoal.objects.filter(pessoa_id=person, site_id=site).first()
            data['pending'] = ((journey.inicio or {}).get('analises_pendentes', {}) if journey else {})
            data['receipt_states'] = [r.estado for r in data.get('recebimentos', [])]
            data['recognized_total'] = reais(data.get('total_conferido_cents', 0))
            # Force all querysets inside the read-only transaction. Render only the summary.
            return {key: data.get(key) for key in ('atual', 'proxima', 'caminho', 'pending', 'receipt_states',
                    'recognized_total', 'percentual', 'meta', 'meta_escolhida', 'sandbox_avaliacoes')} | {'lesson_states': lesson_states}


application = Application(Production())
