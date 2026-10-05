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
    assert 'id="preparacao-livia"' in html and 'Fala da Lívia — bloco 5' in html
    assert 'tela-05-amanha.png' in html and 'montagem-base-1920x1200.mp4' in html
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

def test_preparacao_dia2_reusa_falas_e_imagens_na_aula_sem_progresso():
    from django.test import RequestFactory
    from django.urls import reverse
    from apps.core.views import producao_huge_cat_dia2
    response=producao_huge_cat_dia2(RequestFactory().get(reverse('producao-huge-cat-dia2')))
    html=response.content.decode()
    assert response.status_code==200
    assert '<iframe' not in html and 'srcdoc=' not in html
    for n in range(1,6):
        assert f'id="livia-bloco-{n}"' in html and f'Fala da Lívia — bloco {n}' in html
    assert '8 minutos em 1920×1200' in html and 'aguarda os cinco takes reais' in html
    assert 'Concluir esta aula</button>' not in html
    assert 'D02#preparacao-livia' in html
    p=_video_por_url('https://meshcraft.top/cursos/static/huge-cat-dia2/demonstracao-1920x1200.mp4')['producao_livia']
    for b in p['blocos']:
        for file in [b['imagem_tela'],*[c['arquivo'] for c in b['capturas']]]:
            assert (Path(settings.BASE_DIR)/'static'/file).is_file()

def test_karaoke_preserva_verbatim_e_tempos_dos_cinco_blocos():
    import json
    pasta=Path(settings.BASE_DIR)/'static/huge-cat-dia2'
    script=json.loads((pasta/'roteiro-livia.json').read_text(encoding='utf-8'))
    cues=json.loads((pasta/'karaoke-livia.json').read_text(encoding='utf-8'))
    assert cues['duracao']==480 and cues['resolucao']==[1920,1200]
    assert ' '.join(f['texto'] for f in cues['frases'])==' '.join(' '.join(b['fala'].split()) for b in script['blocos'])
    last=0
    for f in cues['frases']:
        block=next(b for b in cues['blocos'] if b['numero']==f['bloco'])
        assert block['inicio'] <= f['inicio'] < f['fim'] <= block['fim']
        assert last<=f['inicio']
        last=f['fim']
        assert ' '.join(w['texto'] for w in f['palavras'])==f['texto']
        for w in f['palavras']:
            assert f['inicio']<=w['inicio']<w['fim']<=f['fim']
    assert len(cues['pausas'])==3
    html=render_to_string('cursos/_karaoke_livia_dia2.html')
    assert '<iframe' not in html and 'karaoke-livia.js' in html
    for name in ['ensaio-livia-1920x1200.mp4','ensaio-karaoke-1920x1200.mp4','legendas-livia.srt','kit-gravacao-karaoke.zip']:
        assert name in html and (pasta/name).is_file()
