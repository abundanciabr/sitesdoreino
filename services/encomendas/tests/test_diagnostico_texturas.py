import importlib.util
import json
from pathlib import Path
import sys
import pytest
from django.core import signing
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import Http404
from django.test import RequestFactory
from apps.core import diagnostico_texturas as tool

SOURCE=Path(__file__).resolve().parents[1]/'analise_texturas/geometria_uv.py'
spec=importlib.util.spec_from_file_location('texturas_geometria',SOURCE)
geometry=importlib.util.module_from_spec(spec)
spec.loader.exec_module(geometry)


def test_uv_bordas_adjacentes_nao_sao_erro():
    result=geometry.sobreposicoes([(0,[(0,0),(1,0),(1,1)]),(1,[(0,0),(1,1),(0,1)])])
    assert result['faces']==[]
    assert result['completa']


def test_uv_area_repetida_e_area_colapsada():
    tri=[(0,0),(1,0),(0,1)]
    result=geometry.sobreposicoes([(0,tri),(1,list(reversed(tri))),(2,[(0,0),(0,0),(0,0)])])
    assert result['faces']==[0,1]
    assert result['degeneradas']==[2]


def test_uv_leitura_parcial_e_explicita():
    tri=[(0,0),(1,0),(0,1)]
    result=geometry.sobreposicoes([(i,tri) for i in range(20)],max_candidates=2)
    assert result['completa'] is False


def test_duplicacao_exige_geometria_no_mesmo_lugar():
    tri=[[(0,0,0),(1,0,0),(0,1,0)]]
    assert geometry.assinatura_geometria(tri)==geometry.assinatura_geometria([list(reversed(tri[0]))])
    assert geometry.assinatura_geometria(tri)!=geometry.assinatura_geometria([[(x+2,y,z) for x,y,z in tri[0]]])


@pytest.fixture
def setup_tool(monkeypatch,tmp_path):
    monkeypatch.setattr(tool,'root',lambda:tmp_path)
    monkeypatch.setattr(tool,'identity',lambda r:('site-a','pessoa-a'))
    return RequestFactory(),tmp_path


def request(factory,person='pessoa-a',previous=''):
    return factory.post('/diagnostico-texturas/enviar/',{
        'token':signing.dumps({'site':'site-a','pessoa':person},salt=tool.SALT),
        'projeto':SimpleUploadedFile('teste.blend',b'BLENDER arquivo de teste'),
        'sintoma':'repetida','desejo':'pintura só de um lado','anterior':previous},
        HTTP_ORIGIN='https://meshcraft.top')


def test_envio_preserva_conteudo_e_enfileira_sem_criar_entrega(setup_tool):
    factory,root=setup_tool
    response=tool.enviar(request(factory))
    assert response.status_code==201
    ident=json.loads(response.content)['id']
    assert (root/ident/'entrada.blend').read_bytes()==b'BLENDER arquivo de teste'
    assert json.loads((root/ident/'estado.json').read_text())['estado']=='aguardando'
    assert json.loads((root/ident/'meta.json').read_text())['pessoa']=='pessoa-a'


def test_token_de_outra_pessoa_nao_envia(setup_tool):
    factory,root=setup_tool
    assert tool.enviar(request(factory,person='outra')).status_code==403
    assert not list(root.iterdir())


def test_resultado_e_imagens_nao_vazam_para_outro_dono(setup_tool,monkeypatch):
    factory,_=setup_tool
    ident=json.loads(tool.enviar(request(factory)).content)['id']
    monkeypatch.setattr(tool,'identity',lambda r:('site-a','outra'))
    with pytest.raises(Http404):tool.resultado(factory.get('/'),ident)
    with pytest.raises(Http404):tool.imagem(factory.get('/'),ident,'frontal.png')


def test_post_de_outro_site_nao_envia(setup_tool):
    factory,root=setup_tool
    req=request(factory)
    req.META['HTTP_ORIGIN']='https://outro.example'
    assert tool.enviar(req).status_code==403
    assert not list(root.iterdir())


def test_comparacao_examina_reenvio_sem_declarar_aprovacao(setup_tool):
    factory,root=setup_tool
    first=json.loads(tool.enviar(request(factory)).content)['id']
    second=json.loads(tool.enviar(request(factory,previous=first)).content)['id']
    for ident,codes in [(first,['uv_compartilhada']),(second,[])]:
        out=root/ident/'saida'
        out.mkdir()
        tool.salvar(out/'resultado.json',{'estado':'concluida','achados':[{'codigo':code} for code in codes],'limites':[]})
        tool.salvar(root/ident/'estado.json',{'estado':'concluida'})
    data=json.loads(tool.resultado(factory.get('/'),second).content)
    assert data['comparacao']['antes']['uv_compartilhada']==1
    assert data['comparacao']['agora']['uv_compartilhada']==0
    assert data['comparacao']['mesmo_conteudo'] is True
    assert 'aprovada' not in data
