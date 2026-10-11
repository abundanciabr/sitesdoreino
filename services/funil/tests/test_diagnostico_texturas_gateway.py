import httpx
import respx
from django.test import RequestFactory
from apps.core.diagnostico_texturas_gateway import diagnostico_texturas_gateway,UPSTREAM


@respx.mock
def test_endereco_publico_encaminha_ao_servico_e_conserva_sessao():
    route=respx.get(UPSTREAM).mock(return_value=httpx.Response(200,text='Ferramenta',headers={'content-type':'text/html'}))
    req=RequestFactory().get('/ferramentas/diagnostico-de-texturas/',HTTP_HOST='meshcraft.top',HTTP_COOKIE='sessao=opaca')
    response=diagnostico_texturas_gateway(req)
    assert response.status_code==200
    assert route.calls.last.request.headers['cookie']=='sessao=opaca'
    assert route.calls.last.request.headers['host']=='meshcraft.top'
    assert route.calls.last.request.headers['x-forwarded-proto']=='https'


@respx.mock
def test_upload_preserva_corpo_para_o_token_assinado():
    route=respx.post(UPSTREAM+'enviar/').mock(return_value=httpx.Response(201,json={'id':'a'*32}))
    req=RequestFactory().post('/ferramentas/diagnostico-de-texturas/enviar/',b'conteudo',content_type='application/octet-stream',HTTP_HOST='meshcraft.top')
    response=diagnostico_texturas_gateway(req,'enviar/')
    assert response.status_code==201
    assert route.calls.last.request.content==b'conteudo'


@respx.mock
def test_gateway_nao_encaminha_caminhos_fora_da_ferramenta():
    req=RequestFactory().get('/',HTTP_HOST='meshcraft.top')
    for path in ('../admin/','imagens/'+('a'*32)+'/../../meta.json','api/','%2e%2e/admin/'):
        assert diagnostico_texturas_gateway(req,path).status_code==404
    assert len(respx.calls)==0


@respx.mock
def test_servico_indisponivel_aparece_como_falha_tecnica():
    respx.get(UPSTREAM).mock(side_effect=httpx.ConnectError('indisponivel'))
    req=RequestFactory().get('/',HTTP_HOST='meshcraft.top')
    assert diagnostico_texturas_gateway(req).status_code==503
