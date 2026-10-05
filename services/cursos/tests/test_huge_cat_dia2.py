from pathlib import Path
from types import SimpleNamespace
from django.conf import settings
from django.template.loader import render_to_string
from apps.core.views import _video_por_url

def test_dia2_nativo_preserva_navegacao_e_conclusao():
    video=_video_por_url('https://meshcraft.top/cursos/static/huge-cat-dia2/demonstracao-1920x1200.mp4')
    assert video['interativa']
    aula=SimpleNamespace(titulo_na_ordem='Aula 2 — Dia 2: prepare e salve o corpo',numero='D02',curso=SimpleNamespace(slug='roblox'),bloco=SimpleNamespace(parte=1))
    html=render_to_string('cursos/aula.html',{'aula':aula,'video':video,'conclusao':{'feita':False},'navegacao':{'anterior':{'url':'/dia1','titulo':'Dia 1'},'proxima':{'url':'/seguinte','titulo':'Próxima'}}})
    assert '<iframe' not in html and 'srcdoc=' not in html and 'postMessage' not in html
    assert 'Concluir esta aula' in html and 'href="/dia1"' in html and 'href="/seguinte"' in html
    assert 'Dia 2 concluído' in html and 'huge-cat-dia2-inicio.blend' in html
    assert not _video_por_url('https://outro.example/cursos/static/huge-cat-dia2/demonstracao-1920x1200.mp4')['interativa']

def test_dia2_cinco_etapas_com_tamanhos_em_passos_separados():
    p=_video_por_url('https://meshcraft.top/cursos/static/huge-cat-dia2/demonstracao-1920x1200.mp4')['pratica']
    assert (p['width'],p['height'])==(1920,1200)
    assert {s['stage'] for s in p['steps']}=={1,2,3,4,5}
    assert sum(s['stage']==3 for s in p['steps'])==3
    assert p['final']['image']==p['steps'][-1]['image']
    for s in p['steps']:
        assert s['text'].startswith('Clique') and 'imagem' in s['text']
        assert (Path(settings.BASE_DIR)/'static/huge-cat-dia2'/s['image']).is_file()
