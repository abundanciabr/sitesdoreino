import uuid

import pytest
from django.test import Client

from apps.core import galeria_comunidade as galeria
from apps.core.galeria_models import ComentarioDaGaleria, VotoDaGaleria


@pytest.fixture
def participante(monkeypatch):
    pessoa = {'id': 'aluno-a', 'nome': 'Nome completo da escola', 'email': 'a@example.invalid'}
    monkeypatch.setattr(galeria, 'aluno', lambda request: pessoa)
    return pessoa


def test_galeria_abre_nove_modelos_e_nao_publica_comentarios(client, monkeypatch):
    monkeypatch.setattr(galeria, 'aluno', lambda request: None)
    ComentarioDaGaleria.objects.create(pessoa_id='a', nome='Nome sigiloso', email='a@example.invalid', imagem='apple', texto='Texto reservado da crítica', chave=uuid.uuid4())
    resposta = client.get('/galeria-publica')
    texto = resposta.content.decode()
    assert resposta.status_code == 200
    assert texto.count('class="modelo"') == 9
    assert 'Texto reservado' not in texto and 'Nome sigiloso' not in texto and 'a@example.invalid' not in texto
    assert 'visualizador' in texto and 'galeria.js' in texto


def test_votos_repetidos_nao_acumulam_e_retira_so_o_proprio(client, participante):
    VotoDaGaleria.objects.create(pessoa_id='outro', imagem='apple')
    for _ in range(4):
        resposta = client.post('/galeria-publica/voto', {'imagem': 'apple', 'acao': 'votar', 'pessoa_id': 'outro'})
        assert resposta.status_code == 200
    assert VotoDaGaleria.objects.filter(imagem='apple', ativo=True).count() == 2
    for _ in range(2):
        client.post('/galeria-publica/voto', {'imagem': 'apple', 'acao': 'retirar'})
    assert VotoDaGaleria.objects.filter(imagem='apple', ativo=True).count() == 1
    assert VotoDaGaleria.objects.get(pessoa_id='outro').ativo
    assert VotoDaGaleria.objects.filter(pessoa_id=participante['id'], imagem='apple').count() == 1


def test_aluno_vota_em_varios_modelos_e_classificacao_muda(client, participante):
    client.post('/galeria-publica/voto', {'imagem': 'minimalista', 'acao': 'votar'})
    resposta = client.post('/galeria-publica/voto', {'imagem': 'ultra-premium', 'acao': 'votar'})
    linhas = resposta.json()['imagens']
    assert [linha['slug'] for linha in linhas[:2]] == ['minimalista', 'ultra-premium']
    assert sum(linha['votado'] for linha in linhas) == 2
    assert all(set(linha) == {'slug','titulo','descricao','votos','votado','ordem','url'} for linha in linhas)


def test_sem_matricula_nao_vota_nem_comenta(client, monkeypatch):
    monkeypatch.setattr(galeria, 'aluno', lambda request: None)
    assert client.post('/galeria-publica/voto', {'imagem': 'apple', 'acao': 'votar'}).status_code == 403
    assert client.post('/galeria-publica/comentario', {'imagem': 'apple', 'texto': 'oi', 'chave': str(uuid.uuid4())}).status_code == 403
    assert not VotoDaGaleria.objects.exists() and not ComentarioDaGaleria.objects.exists()


def test_nome_do_comentario_vem_da_escola_e_reenvio_nao_duplica(client, participante):
    campos = {'imagem':'premium', 'texto':'Gostei <script>alert(1)</script>', 'chave':str(uuid.uuid4()), 'nome':'Nome adulterado', 'email':'falso@example.invalid', 'pessoa_id':'outra'}
    for _ in range(3):
        resposta = client.post('/galeria-publica/comentario', campos)
        assert resposta.status_code == 200
    comentario = ComentarioDaGaleria.objects.get()
    assert comentario.nome == participante['nome'] and comentario.email == participante['email']
    assert comentario.pessoa_id == participante['id']
    assert comentario.texto == campos['texto']
    assert set(resposta.json()) == {'mensagem','chave'}


def test_comentarios_so_admin_com_crm_e_texto_escapado(monkeypatch, settings):
    settings.ADMIN_EMAILS = 'admin@example.invalid'
    monkeypatch.setattr('apps.core.porta.IdentidadeClient.sessao_completa', lambda self, cookie: {'autenticado':True,'id':'admin','email':'admin@example.invalid','nome_exibido':'Admin'})
    comentario = ComentarioDaGaleria.objects.create(pessoa_id='a', nome='Nome completo aluno', email='a+curso@example.invalid', imagem='apple', texto='<script>roubar()</script>', chave=uuid.uuid4())
    cliente = Client(HTTP_COOKIE='meshcraft_sessao=teste')
    resposta = cliente.get('/comunidade/votacao/')
    assert resposta.status_code == 200
    texto = resposta.content.decode()
    assert '<h3>Nome</h3>' in texto and comentario.nome not in texto
    assert 'a%2Bcurso%40example.invalid' in texto
    assert '&lt;script&gt;' in texto and '<script>roubar' not in texto
    monkeypatch.setattr('apps.core.porta.IdentidadeClient.sessao_completa', lambda self, cookie: {'autenticado':True,'id':'a','email':'a@example.invalid','nome_exibido':'Aluno'})
    assert cliente.get('/comunidade/votacao/').status_code == 404
    assert cliente.get('/comunidade/').status_code == 404


def test_csrf_da_galeria_no_caminho_certo_e_post_protegido(participante):
    cliente = Client(enforce_csrf_checks=True)
    pagina = cliente.get('/galeria-publica')
    assert pagina.cookies['admin_csrf']['path'] == '/comunidade'
    assert cliente.post('/galeria-publica/voto', {'imagem':'apple','acao':'votar'}).status_code == 403
    token = pagina.cookies['admin_csrf'].value
    assert cliente.post('/galeria-publica/voto', {'imagem':'apple','acao':'votar'}, HTTP_X_CSRFTOKEN=token).status_code == 200


def test_identificacao_confere_matricula_e_nome_legitimo(monkeypatch):
    from django.test import RequestFactory
    monkeypatch.setattr(galeria.IdentidadeClient, 'sessao_completa', lambda self, cookie: {'autenticado':True,'id':'a','email':'A@example.invalid','nome_exibido':'Apelido'})
    ficha = {'categoria':'aluno','nome_completo':'Nome na matrícula'}
    monkeypatch.setattr(galeria.AlunosClient, 'prontuario', lambda self, email: ficha)
    request = RequestFactory().get('/galeria-publica', HTTP_COOKIE='meshcraft_sessao=teste')
    assert galeria.aluno(request)['nome'] == 'Nome na matrícula'
    ficha['categoria'] = 'cadastrado'
    assert galeria.aluno(request) is None


def test_imagem_nao_aceita_nome_ou_caminho_arbitrario(client, monkeypatch, tmp_path):
    monkeypatch.setenv('COMUNIDADE_GALERIA_DIR', str(tmp_path))
    (tmp_path/'apple.png').write_bytes(b'png-de-teste')
    resposta = client.get('/galeria-publica/imagens/apple')
    assert resposta.status_code == 200 and resposta['Content-Type'] == 'image/png'
    assert client.get('/galeria-publica/imagens/segredo').status_code == 404
    assert client.get('/galeria-publica/imagens/premium').status_code == 404
