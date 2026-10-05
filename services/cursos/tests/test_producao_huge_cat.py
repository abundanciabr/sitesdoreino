import json
from pathlib import Path
from types import SimpleNamespace

from django.conf import settings
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.test import RequestFactory
from django.urls import reverse

from apps.core import views
from apps.core.praticas import PRATICAS


def test_producao_libera_visitante_pelo_link_direto(monkeypatch):
    def restricao_inesperada(request):
        raise AssertionError('A aula pública não exige identidade de professor')
    monkeypatch.setattr(views, '_professor', restricao_inesperada)
    monkeypatch.setattr(views, 'quem_e', restricao_inesperada)
    response = views.producao_huge_cat(RequestFactory().get(reverse('producao-huge-cat-dia1')))
    assert response.status_code == 200
    assert b'demonstracao-1920x1200.mp4' in response.content


def test_producao_nativa_entrega_roteiro_sem_criar_progresso(monkeypatch):
    monkeypatch.setattr(views, '_professor', lambda request: (object(), None))
    captured = {}
    def render(request, template, context):
        captured.update(context)
        return HttpResponse(render_to_string(template, context))
    monkeypatch.setattr(views, 'render', render)
    response = views.producao_huge_cat(RequestFactory().get(reverse('producao-huge-cat-dia1')))
    html = response.content.decode()
    assert response.status_code == 200
    assert '<iframe' not in html and 'srcdoc=' not in html
    assert 'id="pratica-interativa"' in html
    assert 'demonstracao-1920x1200.mp4' in html and 'montagem-base-1920x1200.mp4' in html
    assert len(captured['roteiro']['blocos']) == 6
    assert 'aguarda os seis takes reais' in html
    assert 'concluir' not in captured and 'conclusao' not in captured


def test_alvos_do_huge_cat_usam_capturas_reais_e_cinco_etapas():
    video = views._video_por_url('https://meshcraft.top/cursos/static/huge-cat-dia1/demonstracao-1366x768.mp4')
    assert video['interativa']
    practice = video['pratica']
    assert {s['stage'] for s in practice['steps']} == {1,2,3,4,5}
    for step in practice['steps']:
        assert step['text'].startswith('Clique') and 'imagem' in step['text']
        assert (Path(settings.BASE_DIR) / 'static/huge-cat-dia1' / step['image']).is_file()
        assert 0 <= step['point'][0] <= practice['width'] and 0 <= step['point'][1] <= practice['height']
    assert practice['final']['image'] == practice['steps'][-1]['image']
    assert not views._video_por_url('https://outro.example/cursos/static/huge-cat-dia1/demonstracao-1366x768.mp4')['interativa']
