import json
import pytest
from django.test import RequestFactory
from apps.core import previa_aula3 as previa

@pytest.fixture
def media(tmp_path,monkeypatch):
    monkeypatch.setenv('AULA3_VIDEO_DIR',str(tmp_path))
    (tmp_path/'aula-3-previa-legendada.mp4').write_bytes(b'0123456789')
    return tmp_path

@pytest.mark.parametrize('range_header,body,content_range',[
    ('bytes=2-5',b'2345','bytes 2-5/10'),('bytes=7-',b'789','bytes 7-9/10'),
    ('bytes=-3',b'789','bytes 7-9/10'),('bytes=0-100',b'0123456789','bytes 0-9/10')])
def test_busca_no_video(media,range_header,body,content_range):
    response=previa.midia(RequestFactory().get('/',HTTP_RANGE=range_header),'aula-3-previa-legendada.mp4')
    assert response.status_code==206
    assert b''.join(response.streaming_content)==body
    assert response['Content-Range']==content_range

@pytest.mark.parametrize('range_header',['bytes=50-','bytes=4-2','bytes=-0','bytes=0-1,3-4','invalido'])
def test_intervalo_invalido(media,range_header):
    response=previa.midia(RequestFactory().get('/',HTTP_RANGE=range_header),'aula-3-previa-legendada.mp4')
    assert response.status_code==416 and response['Content-Range']=='bytes */10'

def test_head_download_e_metodo(media):
    response=previa.midia(RequestFactory().head('/?download=1'),'aula-3-previa-legendada.mp4')
    assert response.status_code==200 and response.content==b''
    assert response['Content-Length']=='10' and 'attachment' in response['Content-Disposition']
    assert previa.midia(RequestFactory().post('/'),'aula-3-previa-legendada.mp4').status_code==405

def test_so_arquivos_publicados(media):
    from django.http import Http404
    for name in ['direcao.json','recibos-voz.json','voz-000.ogg','../segredo.env']:
        with pytest.raises(Http404):previa.midia(RequestFactory().get('/'),name)

def test_pagina_usa_rota_cursos_e_roteiro(media,client):
    shots=[dict(id=i,titulo=f'Cena {i}',texto='A fala do roteiro.',modo='tela',acao='Ação visual.') for i in range(24)]
    (media/'direcao.json').write_text(json.dumps(dict(duracao=180,shots=shots)))
    (media/'capitulos.json').write_text(json.dumps([dict(titulo='Espelho',inicio=15.5)]))
    response=client.get('/desafio-como-ganhar-em-dolar-com-roblox/previa-aula-3')
    assert response.status_code==200
    html=response.content.decode()
    assert 'video-aula3' in html and 'Não é uma gravação nem clonagem da Lívia' in html
    assert 'data-video-inicio="15.50"' in html
    assert html.count('A fala do roteiro.')==24 and 'transcricao.txt?v=' in html
    import os,re
    original=re.search(r'aula-3-previa-legendada.mp4\?v=([0-9a-f]+)',html).group(1)
    arquivo=media/'aula-3-previa-legendada.mp4'
    os.utime(arquivo,ns=(arquivo.stat().st_atime_ns,arquivo.stat().st_mtime_ns+1_000_000_000))
    updated=client.get('/desafio-como-ganhar-em-dolar-com-roblox/previa-aula-3').content.decode()
    assert re.search(r'aula-3-previa-legendada.mp4\?v=([0-9a-f]+)',updated).group(1)!=original
