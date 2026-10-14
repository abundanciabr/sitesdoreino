"""A fila é do site; a Caixa apenas encaminha, sem registrar pedidos."""
import pytest
from django.urls import reverse
from apps.sugestoes.models import Identidade, Sugestao, Voto, Comentario
from tests.conftest import sessao_do_site

@pytest.mark.parametrize('categoria', ['cadastrado','na_fila','aluno','ex_aluno','pausado','reembolsado'])
@pytest.mark.parametrize('pedido', [
    {'nome_completo':'Pessoa de Teste','whatsapp':'11999990000'},
    {'nome_completo':'Pessoa de Teste','whatsapp':'11999990000','comprou_em':'2026-09-15','turma':'Teste'},
    {'nome_completo':'','whatsapp':'12'},
    {'email':'outra@example.test','site_id':'outro'},
])
def test_pedido_antigo_encaminha_sem_alterar_a_fila(rede, db, categoria, pedido):
    email='pessoa@example.test'
    rede.alunos_situacao(email,categoria)
    rede.alunos_aceita_o_pedido()
    pessoa=sessao_do_site(rede,email=email)
    antes=(Identidade.objects.count(),Sugestao.objects.count(),Voto.objects.count(),Comentario.objects.count())
    for _ in range(2):
        resposta=pessoa.client.post(reverse('pedir_entrada'),pedido)
        assert resposta.status_code == 302
        assert resposta['Location'] == '/login?next=%2F'
        assert not resposta.cookies
    assert rede.pedidos == []
    assert antes == (Identidade.objects.count(),Sugestao.objects.count(),Voto.objects.count(),Comentario.objects.count())

def test_pedido_antigo_nao_aceita_get(client):
    assert client.get(reverse('pedir_entrada')).status_code == 405

def test_anonimo_nao_registra_pedido_nem_cria_identidade(client,rede,db):
    resposta=client.post(reverse('pedir_entrada'),{'email':'intruso@example.test'})
    assert resposta['Location'] == '/login?next=%2F'
    assert rede.pedidos == []
    assert Identidade.objects.count() == 0
