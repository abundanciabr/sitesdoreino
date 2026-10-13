import httpx
import pytest
import respx
from django.test import Client


@respx.mock
@pytest.mark.parametrize('papel', ['aluno', 'professor'])
@pytest.mark.parametrize('caminho', [
    '/super-equipe/', '/super-equipe/98/', '/super-equipe/fila/',
    '/super-equipe/executor/', '/equipe/robo/execucoes/98',
    '/equipe/robo/entregas/33', '/equipe/robo/andamento?execucao=98',
    '/documentos/auditoria-super-equipe-cinco-especialistas-20261012',
])
def test_sessao_reconhecida_de_aluno_ou_professor_nao_abre_admin(settings, monkeypatch, papel, caminho):
    monkeypatch.setenv("IDENTIDADE_API_URL", "http://identidade:8000/interno")
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-isolado-sem-credencial-real")
    settings.ADMIN_EMAILS = 'admin-isolado@exemplo.invalid'
    respx.get('http://identidade:8000/interno/sessao/completa').mock(
        return_value=httpx.Response(200, json={
            'autenticado': True, 'id': 'conta-isolada-' + papel,
            'nome_exibido': 'Teste', 'papel': papel,
            'email': papel + '@exemplo.invalid',
        }))
    cliente = Client(HTTP_COOKIE='meshcraft_sessao=sessao-isolada-sem-credencial-real')
    resposta = cliente.get(caminho)
    assert resposta.status_code == 404
    assert 'Fontes compartilhadas' not in resposta.content.decode()
