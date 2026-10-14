from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from django.test import Client

from conftest import ALUNOS, EMAIL_DE_QUEM_ENTROU, HOST_MESH
from test_categorias_na_home import com_email, _situacao

COOKIE = 'meshcraft_sessao=sessao-de-teste'
LOGIN = '/pt-br/login?next=%2Ftrilha%2F'
PEDIDO = {'nome_completo': 'Pessoa de Teste', 'whatsapp': '11999990000',
          'comprou_em': '2026-09-15', 'turma': 'Turma de teste'}


def abrir(client, metodo='get', dados=None):
    return getattr(client, metodo)(LOGIN, dados or {}, HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE)


def test_google_e_senha_retornam_ao_login_para_conferir_matricula(client, rede):
    resposta = client.get(LOGIN, HTTP_HOST=HOST_MESH)
    retorno = '/pt-br/login?next=%2Ftrilha%2F'
    assert resposta.context['destino'] == retorno
    assert parse_qs(urlsplit(resposta.context['url_de_entrada']).query)['next'] == [retorno]


def test_aluno_segue_para_o_destino_solicitado(client, com_email):
    _situacao(com_email, 'aluno')
    resposta = abrir(client)
    assert resposta.status_code == 302
    assert resposta['Location'] == '/trilha/'


def test_sem_matricula_pede_acesso_no_login_sem_caixa(client, com_email):
    _situacao(com_email, 'cadastrado')
    resposta = abrir(client)
    html = resposta.content.decode()
    assert resposta.status_code == 200
    assert 'Acesso do aluno' in html
    assert 'Pedir liberação' in html
    assert 'forms/sugestoes' not in html
    assert EMAIL_DE_QUEM_ENTROU in html
    assert 'csrfmiddlewaretoken' in html
    assert 'no-store' in resposta['Cache-Control']


def test_pedido_preserva_fila_e_identidade_da_sessao(client, com_email):
    import json
    _situacao(com_email, 'cadastrado')
    envio = com_email.post(f'{ALUNOS}/pre-matriculas').mock(return_value=httpx.Response(201))
    resposta = abrir(client, 'post', {**PEDIDO, 'email': 'intruso@example.test', 'site_id': 'outro'})
    assert resposta.status_code == 302
    assert resposta['Location'] == LOGIN
    corpo = json.loads(envio.calls[0].request.content)
    assert corpo == {**PEDIDO, 'email': EMAIL_DE_QUEM_ENTROU, 'site_id': 'site-mesh'}


def test_recibo_vem_da_fila_e_depois_encaminha_sem_reenvio(client, com_email):
    _situacao(com_email, 'na_fila', {'estado': 'aguardando', 'esperando_ha_dias': 0})
    resposta = abrir(client)
    assert 'Seu pedido já está com a gente' in resposta.content.decode()
    assert 'http-equiv="refresh"' in resposta.content.decode()
    assert 'Pedir liberação' not in resposta.content.decode()
    assert not any('/pre-matriculas' in str(c.request.url) for c in com_email.calls)
    _situacao(com_email, 'aluno')
    assert abrir(client)['Location'] == '/trilha/'


@pytest.mark.parametrize('dados', [{**PEDIDO, 'nome_completo': ''},
                                  {**PEDIDO, 'whatsapp': '12'},
                                  {**PEDIDO, 'comprou_em': 'ontem'}])
def test_formulario_invalido_preserva_dados_sem_envio(client, com_email, dados):
    _situacao(com_email, 'cadastrado')
    resposta = abrir(client, 'post', dados)
    assert resposta.status_code == 400
    assert 'Confira o nome' in resposta.content.decode()
    assert not any('/pre-matriculas' in str(c.request.url) for c in com_email.calls)


def test_falha_de_envio_nao_mostra_recibo(client, com_email):
    _situacao(com_email, 'cadastrado')
    com_email.post(f'{ALUNOS}/pre-matriculas').mock(return_value=httpx.Response(500))
    resposta = abrir(client, 'post', PEDIDO)
    assert resposta.status_code == 502
    html = resposta.content.decode()
    assert 'Não conseguimos confirmar' in html
    assert PEDIDO['nome_completo'] in html
    assert 'Seu pedido já está com a gente' not in html


@pytest.mark.parametrize('categoria', ['pausado', 'reembolsado', 'desconhecida'])
def test_estados_sem_pedido_nao_gravam(client, com_email, categoria):
    _situacao(com_email, categoria)
    html = abrir(client, 'post', PEDIDO).content.decode()
    assert 'Pedir liberação' not in html
    assert not any('/pre-matriculas' in str(c.request.url) for c in com_email.calls)


def test_ex_aluno_pode_pedir_para_voltar(client, com_email):
    _situacao(com_email, 'ex_aluno')
    assert 'Pedir para voltar' in abrir(client).content.decode()


def test_falha_na_conferencia_nao_promete_matricula_ausente(client, com_email):
    com_email.get(f'{ALUNOS}/alunos/{EMAIL_DE_QUEM_ENTROU}/situacao').mock(return_value=httpx.Response(503))
    resposta = abrir(client)
    assert resposta.status_code == 503
    assert 'Não conseguimos conferir' in resposta.content.decode()
    assert 'Pedir liberação' not in resposta.content.decode()


@pytest.mark.parametrize('codigo', [401, 403, 422, 500])
def test_resposta_recusada_no_envio_nao_vira_recibo(client, com_email, codigo):
    _situacao(com_email, 'cadastrado')
    com_email.post(f'{ALUNOS}/pre-matriculas').mock(return_value=httpx.Response(codigo))
    resposta = abrir(client, 'post', PEDIDO)
    assert resposta.status_code == 502
    assert 'Seu pedido já está com a gente' not in resposta.content.decode()


@pytest.mark.parametrize('categoria', ['aluno', 'na_fila', 'pausado', 'reembolsado'])
def test_post_de_pagina_antiga_nao_duplica_pedido_apos_mudanca_de_estado(client, com_email, categoria):
    _situacao(com_email, categoria, {'estado': 'aguardando'} if categoria == 'na_fila' else None)
    resposta = abrir(client, 'post', PEDIDO)
    assert resposta.status_code in (200, 302)
    assert not any('/pre-matriculas' in str(c.request.url) for c in com_email.calls)


def test_opcionais_em_branco_nao_sao_enviados(client, com_email):
    import json
    _situacao(com_email, 'cadastrado')
    envio = com_email.post(f'{ALUNOS}/pre-matriculas').mock(return_value=httpx.Response(201))
    resposta = abrir(client, 'post', {'nome_completo': 'Pessoa de Teste', 'whatsapp': '+55 (11) 99999-0000'})
    assert resposta.status_code == 302
    corpo = json.loads(envio.calls[0].request.content)
    assert 'comprou_em' not in corpo and 'turma' not in corpo


def test_recibo_so_aparece_se_a_fila_confirmar(client, com_email):
    _situacao(com_email, 'na_fila', {'estado': 'aguardando'})
    assert 'Seu pedido já está com a gente' in abrir(client).content.decode()
    _situacao(com_email, 'cadastrado')
    html = abrir(client).content.decode()
    assert 'Seu pedido já está com a gente' not in html
    assert 'Pedir liberação' in html


def test_pedido_recusado_mostra_motivo_sem_relogio(client, com_email):
    _situacao(com_email, 'na_fila', {'estado': 'recusada', 'motivo_recusa': 'Confira o e-mail da compra.'})
    html = abrir(client).content.decode()
    assert 'Seu pedido não foi aprovado' in html
    assert 'Confira o e-mail da compra.' in html
    assert 'http-equiv="refresh"' not in html


def test_reembolso_tem_explicacao_propria(client, com_email):
    _situacao(com_email, 'reembolsado')
    html = abrir(client).content.decode()
    assert 'Seu acesso terminou com o reembolso' in html
    assert 'Pedir para voltar' not in html
    assert EMAIL_DE_QUEM_ENTROU in html


@pytest.mark.parametrize('idioma', ['en', 'pt-br', 'es'])
def test_acesso_nos_idiomas_existentes(client, com_email, idioma):
    from conftest import caminho_mesh
    _situacao(com_email, 'cadastrado')
    resposta = client.get(caminho_mesh(idioma, '/login'), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE)
    assert resposta.status_code == 200
    assert 'name="nome_completo"' in resposta.content.decode()
    assert 'forms/sugestoes' not in resposta.content.decode()


def test_autorizacao_whatsapp_confere_numero_e_viaja_na_fila(client, com_email):
    import json
    _situacao(com_email, 'cadastrado')
    envio = com_email.post(f'{ALUNOS}/pre-matriculas').mock(return_value=httpx.Response(201))
    resposta = abrir(client, 'post', {**PEDIDO, 'whatsapp_avisos': 'sim',
                                    'whatsapp_confirmacao': '+55 (11) 99999-0000'})
    assert resposta.status_code == 302
    assert json.loads(envio.calls[0].request.content)['whatsapp_avisos'] is True


def test_numero_diferente_na_confirmacao_nao_registra_pedido(client, com_email):
    _situacao(com_email, 'cadastrado')
    resposta = abrir(client, 'post', {**PEDIDO, 'whatsapp_avisos': 'sim',
                                    'whatsapp_confirmacao': '21999990000'})
    assert resposta.status_code == 400
    assert 'Confirme o mesmo número' in resposta.content.decode()
    assert not any('/pre-matriculas' in str(c.request.url) for c in com_email.calls)


def test_sem_autorizacao_whatsapp_nao_envia_optin(client, com_email):
    import json
    _situacao(com_email, 'cadastrado')
    envio = com_email.post(f'{ALUNOS}/pre-matriculas').mock(return_value=httpx.Response(201))
    resposta = abrir(client, 'post', {**PEDIDO, 'whatsapp_avisos': 'nao',
                                    'whatsapp_confirmacao': '21999990000'})
    assert resposta.status_code == 302
    assert 'whatsapp_avisos' not in json.loads(envio.calls[0].request.content)


def test_troca_de_conta_abre_google_e_senha_no_login(client, com_email):
    _situacao(com_email, 'cadastrado')
    resposta = client.get(LOGIN + '&trocar=1', HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE)
    assert 'Continuar com o Google' in resposta.content.decode()
    assert 'name="senha"' in resposta.content.decode()


def test_post_exige_csrf(client, com_email):
    _situacao(com_email, 'cadastrado')
    seguro = Client(enforce_csrf_checks=True)
    resposta = abrir(seguro, 'post', PEDIDO)
    assert resposta.status_code == 403
    assert not any('/pre-matriculas' in str(c.request.url) for c in com_email.calls)
    pagina = abrir(seguro)
    token = pagina.cookies['csrftoken'].value
    com_email.post(f'{ALUNOS}/pre-matriculas').mock(return_value=httpx.Response(201))
    # Cookie da sessão e CSRF enviados pelo mesmo navegador.
    resposta = seguro.post(LOGIN, {**PEDIDO, 'csrfmiddlewaretoken': token},
                           HTTP_HOST=HOST_MESH,
                           HTTP_COOKIE=COOKIE + '; csrftoken=' + token)
    assert resposta.status_code == 302


@pytest.mark.parametrize('destino', ['//fora.test/', '/login?next=/', '/forms/sugestoes/entrar'])
def test_destinos_externos_ou_circulares_voltam_ao_site(client, com_email, destino):
    _situacao(com_email, 'aluno')
    resposta = client.get('/pt-br/login', {'next': destino}, HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE)
    assert resposta['Location'] == '/pt-br/'
