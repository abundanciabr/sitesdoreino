import json

from apps.core import galeria_comunidade as galeria
from apps.core.galeria_aula1 import BASE


def preparar(tmp_path, monkeypatch):
    monkeypatch.setenv('AULA1_VIDEO_DIR', str(tmp_path))
    monkeypatch.setattr(galeria, 'aluno', lambda request: None)
    (tmp_path / 'aula-1-previa-legendada.mp4').write_bytes(b'0123456789')
    (tmp_path / 'direcao.json').write_text(json.dumps({'duracao':366, 'shots':[
        {'id':i, 'inicio':i*50.5, 'fim':i*50.5+20, 'titulo':f'Cena {i}', 'texto':'Fala de referência.', 'bloco':i+1, 'modo':'camera'} for i in range(6)
    ]}))


def test_player_publico_tem_capitulos_legendas_e_transcricao(client, monkeypatch, tmp_path):
    preparar(tmp_path, monkeypatch)
    response=client.get('/previa-aula-1')
    html=response.content.decode()
    assert response.status_code==200
    assert '<video id="video-aula1" controls playsinline' in html
    assert BASE+'/midia/aula-1-previa-legendada.mp4' in html
    assert 'kind="captions"' in html
    assert html.count('data-video-inicio=')==6
    assert 'data-video-inicio="50.50"' in html
    assert 'voz é sintética' in html
    assert html.count('class="modelo"')==6


def test_video_tem_busca_por_intervalo_e_head_sem_abrir_outros_arquivos(client, monkeypatch, tmp_path):
    preparar(tmp_path,monkeypatch)
    url='/previa-aula-1/midia/aula-1-previa-legendada.mp4'
    response=client.get(url, HTTP_RANGE='bytes=2-5')
    assert response.status_code==206
    assert response['Content-Range']=='bytes 2-5/10'
    assert response['Content-Length']=='4'
    assert b''.join(response.streaming_content)==b'2345'
    response=client.get(url,HTTP_RANGE='bytes=-3')
    assert response.status_code==206
    assert b''.join(response.streaming_content)==b'789'
    response=client.head(url)
    assert response.status_code==200 and response['Content-Length']=='10' and response.content==b''
    for interval in ['bytes=12-20','bytes=-0','bytes=2-1','bytes=0-1,3-4','garbage']:
        assert client.get(url,HTTP_RANGE=interval).status_code==416
    assert client.get('/previa-aula-1/midia/direcao.json').status_code==404
    assert client.get('/previa-aula-1/midia/segredo.env').status_code==404
    assert client.post(url).status_code==405
    response=client.get(url+'?download=1')
    assert 'attachment' in response['Content-Disposition']
    response.close()
