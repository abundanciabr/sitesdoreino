"""Sem matrícula, encaminha ao login e continua sem participar."""
import pytest
from django.urls import reverse
from apps.sugestoes.models import Identidade
from tests.conftest import sessao_do_site

@pytest.mark.parametrize('categoria',['cadastrado','na_fila','ex_aluno','pausado','reembolsado'])
def test_sem_matricula_encaminha_sem_cunhar_identidade(rede,db,quadro,categoria):
    email='sem-matricula@example.test'
    rede.alunos_situacao(email,categoria)
    pessoa=sessao_do_site(rede,email=email)
    assert pessoa.abrir()['Location'] == '/login?next=%2F'
    assert not pessoa.esta_dentro
    assert Identidade.objects.count() == 0

def test_lista_vazia_de_matriculas_tambem_e_recusa(rede,db,quadro):
    email='sem-matricula@example.test'
    rede.alunos_diz(email,[])
    pessoa=sessao_do_site(rede,email=email)
    assert not pessoa.esta_dentro

def test_visitante_encaminha_sem_criar_identidade(client,rede,db):
    resposta=client.get(reverse('entrar'))
    assert resposta.status_code == 302
    assert resposta['Location'] == '/login?next=%2F'
    assert not resposta.cookies
    assert Identidade.objects.count() == 0
