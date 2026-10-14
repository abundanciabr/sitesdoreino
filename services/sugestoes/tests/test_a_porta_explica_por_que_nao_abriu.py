"""Os estados continuam distintos na autorização; a tela agora é o login."""
import pytest
from django.test import RequestFactory
from django.urls import reverse
from apps.core import sessao as ses
from tests.conftest import sessao_do_site

@pytest.mark.parametrize('categoria,estado', [
    ('cadastrado',ses.SEM_MATRICULA),('na_fila',ses.NA_FILA),
    ('ex_aluno',ses.EX_ALUNO),('pausado',ses.PAUSADO),
    ('reembolsado',ses.REEMBOLSADO),('desconhecida',ses.INDISPONIVEL),
])
def test_estado_preservado_e_tela_encaminhada_ao_site(rede,db,quadro,categoria,estado):
    email='pessoa@example.test'
    rede.alunos_situacao(email,categoria)
    pessoa=sessao_do_site(rede,email=email)
    cookie=pessoa.client.cookies.output(header='',sep=';').strip()
    resolucao=ses.resolver(RequestFactory().get('/',HTTP_COOKIE=cookie))
    assert resolucao.estado == estado
    assert resolucao.ator is None
    resposta=pessoa.abrir()
    assert resposta.status_code == 302
    assert resposta['Location'] == '/login?next=%2F'
    assert pessoa.client.get(reverse('quadro')).status_code == 302

def test_alunos_fora_do_ar_nao_autoriza_participacao(rede,db,quadro):
    email='pessoa@example.test'
    rede.alunos_fora_do_ar(email)
    pessoa=sessao_do_site(rede,email=email)
    assert not pessoa.esta_dentro
    assert pessoa.abrir()['Location'] == '/login?next=%2F'
