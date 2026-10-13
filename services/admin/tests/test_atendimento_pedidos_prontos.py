import pytest
from django.http import Http404
from django.test import RequestFactory
from django.urls import resolve

from apps.atendimento import pedidos_prontos


@pytest.mark.parametrize('texto,tipo', [
    ('Não consigo entrar na minha conta.', 2),
    ('Paguei o curso e meu acesso não foi liberado.', 8),
    ('Preciso de ajuda no Blender ou no Roblox.', 10),
    ('Preciso de ajuda com a análise do meu trabalho no Sandbox.', 9),
    ('O site apresentou um erro.', 12),
    ('Preciso de ajuda com uma aula.', 0),
])
def test_pedidos_entram_na_triagem_atual_sem_inventar_resposta(texto, tipo):
    from types import SimpleNamespace
    from apps.atendimento import escala
    conversa = SimpleNamespace(interesse={}, site_id='teste-pedidos', rodada=1)
    escala.classificar(conversa, texto)
    assert conversa.tipo == tipo


@pytest.mark.parametrize('identidade', [None, {'id': 'aluno', 'equipe_apenas': True}])
def test_previa_e_assets_recusam_quem_nao_e_admin(identidade):
    request = RequestFactory().get('/atendimento/pedidos-prontos/')
    request.admin = identidade
    with pytest.raises(Http404):
        pedidos_prontos.previa(request)
    for nome in ('suporte.js', 'suporte.css'):
        with pytest.raises(Http404):
            pedidos_prontos.arquivo(request, nome)


def test_admin_recebe_previa_sem_cache_e_sem_criar_conversa():
    from apps.atendimento.models import Conversa, Mensagem
    request = RequestFactory().get('/atendimento/pedidos-prontos/')
    request.admin = {'id': 'admin-teste'}
    contagem = (Conversa.objects.count(), Mensagem.objects.count())
    resposta = pedidos_prontos.previa(request)
    assert resposta.status_code == 200
    assert 'no-store' in resposta['Cache-Control']
    assert b'Pr\xc3\xa9via exclusiva' in resposta.content
    assert (Conversa.objects.count(), Mensagem.objects.count()) == contagem
    assert resolve('/atendimento/pedidos-prontos/').func == pedidos_prontos.previa
    assert resolve('/atendimento/pedidos-prontos/arquivo/suporte.js').func == pedidos_prontos.arquivo


def test_assets_da_previa_sao_privados_e_sem_travessia_de_pasta():
    request = RequestFactory().get('/atendimento/pedidos-prontos/arquivo/suporte.js')
    request.admin = {'id': 'admin-teste'}
    for nome, tipo in [('suporte.js', 'text/javascript'), ('suporte.css', 'text/css')]:
        resposta = pedidos_prontos.arquivo(request, nome)
        assert resposta.status_code == 200
        assert resposta['Content-Type'].startswith(tipo)
        assert 'no-store' in resposta['Cache-Control']
        assert resposta['X-Content-Type-Options'] == 'nosniff'
        assert b''.join(resposta.streaming_content)
    for nome in ('../views.py', 'views.py'):
        with pytest.raises(Http404):
            pedidos_prontos.arquivo(request, nome)
