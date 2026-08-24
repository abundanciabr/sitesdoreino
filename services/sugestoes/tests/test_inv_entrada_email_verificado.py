"""[INVARIANTE 1] E-mail não verificado no Google é RECUSADO, sem exceção.

`DECISAO-EVO-01-identidade.md` §2, passo 2. O Google prova QUEM É — mas só prova
alguma coisa se ele mesmo confirmar que o endereço pertence à conta. Um
`email_verified: false` significa literalmente "esta conta digitou este e-mail e
nós nunca confirmamos": aceitá-lo permitiria a qualquer pessoa criar uma conta
Google declarando o e-mail da compra de OUTRA e entrar no lugar dela.

O que o guarda prova: nesse caso **nada é criado e nenhuma sessão é aberta** — e
a `alunos` nem chega a ser perguntada, porque não há identidade a conferir.
"""

import pytest

from apps.sugestoes.models import Identidade

pytestmark = pytest.mark.django_db


def test_email_nao_verificado_nao_cunha_identidade_nem_abre_sessao(porta, perfil):
    resposta = porta.bater(perfil("naoverificado@exemplo.test", verificado=False))

    assert resposta.status_code == 403, resposta.content
    assert Identidade.objects.count() == 0
    assert not porta.esta_dentro


def test_email_nao_verificado_nao_chega_a_perguntar_a_alunos(porta, perfil, rede):
    """A recusa acontece ANTES do salto de rede — e o dublê é quem prova.

    A rota da `alunos` é registrada mas nunca respondida: se a porta a chamasse,
    `call_count` passaria de zero.
    """
    consulta = rede.alunos_diz("naoverificado@exemplo.test", [])

    porta.bater(perfil("naoverificado@exemplo.test", verificado=False))

    assert consulta.call_count == 0


def test_verificado_como_texto_nao_vale_como_verdadeiro(porta, perfil):
    """`"false"` é uma string, e toda string não vazia é verdadeira em Python.

    Este é o jeito exato de o portão virar peneira sem ninguém notar: um
    `if not perfil.get("email_verified")` deixaria passar tanto `"false"` quanto
    `"true"`. Só o booleano `True` do Google entra.
    """
    p = perfil("texto@exemplo.test")
    p["email_verified"] = "false"

    resposta = porta.bater(p)

    assert resposta.status_code == 403, resposta.content
    assert Identidade.objects.count() == 0
    assert not porta.esta_dentro


def test_perfil_sem_o_campo_email_verified_e_recusado(porta, perfil):
    """Ausência não é permissão: campo que não veio conta como não verificado."""
    p = perfil("semcampo@exemplo.test")
    del p["email_verified"]

    resposta = porta.bater(p)

    assert resposta.status_code == 403, resposta.content
    assert Identidade.objects.count() == 0
    assert not porta.esta_dentro
