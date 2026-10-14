import pytest
from django.test import Client
from apps.core import comunidade_entrada as comunidade
from apps.core.comunidade_modelos import PerfilDaComunidade
from apps.core.galeria_models import VotoDaGaleria, ComentarioDaGaleria
from test_comunidade_entrada import admin, cadastrar


def test_comunidade_admin_liga_percurso_sem_criar_grupos(admin):
    cadastrar(admin)
    corpo=admin.get('/galeria-publica').content.decode()
    assert '/admin/previas-operacionais/?previa=comunidade-alunos' in corpo
    assert '/cursos/comunidade/pratica' in corpo
    assert 'não há grupos' in corpo.lower()
    assert 'D02 não foi liberada' in corpo


def test_visual_aluno_atual_e_leitura_sem_alterar_votos(admin):
    VotoDaGaleria.objects.create(pessoa_id='aluno-real', imagem='apple')
    resposta=admin.get('/comunidade/alunos-atual/')
    assert resposta.status_code == 200
    corpo=resposta.content.decode()
    assert 'Visual atual dos alunos' in corpo
    assert 'data-pode-votar="nao"' in corpo
    assert corpo.count('class="modelo"') == 9
    assert 'disabled class="votar' in corpo
    assert VotoDaGaleria.objects.count() == 1
    assert not ComentarioDaGaleria.objects.exists()
    assert not PerfilDaComunidade.objects.exists()
    assert 'no-store' in resposta['Cache-Control']
    assert 'noindex' in resposta['X-Robots-Tag']


@pytest.mark.parametrize('email', ['aluno@example.test', 'professor@example.test', ''])
def test_aluno_professor_e_visitante_nao_abrem_visual_admin(monkeypatch,settings,email):
    settings.ADMIN_EMAILS='admin@example.test'
    monkeypatch.setattr('apps.core.clients.IdentidadeClient.sessao_completa',lambda self,cookie:{
        'autenticado':bool(email), 'id':'pessoa', 'email':email, 'nome_exibido':'Pessoa', 'papel':'admin'})
    resposta=Client(HTTP_COOKIE='meshcraft_sessao=teste').get('/comunidade/alunos-atual/')
    assert resposta.status_code in (302,403,404)
    assert 'Visual atual dos alunos' not in resposta.content.decode()
