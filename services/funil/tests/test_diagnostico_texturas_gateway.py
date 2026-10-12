from django.test import RequestFactory
from apps.core.diagnostico_texturas_gateway import diagnostico_texturas_gateway,UPSTREAM


def test_endereco_publico_encaminha_apenas_ao_mesmo_site():
    req=RequestFactory().get('/ferramentas/diagnostico-de-texturas/?analise='+('a'*32),HTTP_HOST='meshcraft.top')
    result=diagnostico_texturas_gateway(req)
    assert result.status_code==307
    assert result['Location']==UPSTREAM+'?analise='+('a'*32)
    assert result['Cache-Control']=='private, no-store'


def test_upload_usa_redirect_que_preserva_metodo_e_arquivo():
    req=RequestFactory().post('/ferramentas/diagnostico-de-texturas/enviar/',b'conteudo',content_type='application/octet-stream',HTTP_HOST='meshcraft.top')
    result=diagnostico_texturas_gateway(req,'enviar/')
    assert result.status_code==307
    assert result['Location']==UPSTREAM+'enviar/'
    assert req.body==b'conteudo'


def test_gateway_nao_encaminha_caminhos_ou_hosts_fora_da_ferramenta():
    req=RequestFactory().get('/',HTTP_HOST='meshcraft.top')
    for path in ('../admin/','imagens/'+('a'*32)+'/../../meta.json','api/','%2e%2e/admin/'):
        assert diagnostico_texturas_gateway(req,path).status_code==404
    foreign=RequestFactory().get('/',HTTP_HOST='outro.top')
    assert diagnostico_texturas_gateway(foreign).status_code==404


def test_envio_grande_e_metodo_inesperado_nao_sao_encaminhados():
    req=RequestFactory().post('/',b'arquivo',content_type='application/octet-stream',HTTP_HOST='meshcraft.top',CONTENT_LENGTH=str(67*1024*1024))
    assert diagnostico_texturas_gateway(req,'enviar/').status_code==413
    req=RequestFactory().delete('/',HTTP_HOST='meshcraft.top')
    assert diagnostico_texturas_gateway(req).status_code==405
