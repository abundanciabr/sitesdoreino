"""A mesma pessoa entrando dez vezes tem UMA linha (EVO-01 §3, mantido aqui)."""

from apps.identidade.models import Identidade
from tests.conftest import perfil_google


def test_reentrar_recupera_a_mesma_identidade(entrar_como):
    primeira = entrar_como().identidade
    segunda = entrar_como().identidade
    assert primeira.id == segunda.id
    assert Identidade.objects.count() == 1


def test_reentrar_nao_sobrescreve_o_nome(rede, db, entrar_como):
    """`nome_exibido` só é gravado na CUNHAGEM: o campo poderá ser editável
    pela pessoa, e o Google não pode apagar essa escolha a cada login."""
    pessoa = entrar_como(nome="João")
    Identidade.objects.filter(pk=pessoa.identidade.id).update(
        nome_exibido="Nome Escolhido"
    )
    de_novo = entrar_como(nome="João Do Google")
    assert de_novo.identidade.nome_exibido == "Nome Escolhido"


def test_email_e_normalizado_para_minusculas(rede, db, porta):
    porta.bater(perfil_google(email="Joao.Silva@Exemplo.TEST"))
    assert Identidade.objects.get().email == "joao.silva@exemplo.test"
