"""[INVARIANTE 4] A mesma pessoa entrando dez vezes tem UMA `Identidade`.

`DECISAO-EVO-01-identidade.md` §3. Não é economia de linhas: `Identidade.id` é o
"autor" de toda sugestão, todo voto e todo comentário (`models.py`). Uma segunda
linha para a mesma pessoa partiria o histórico dela ao meio — e, pior, o
`UniqueConstraint` de `Voto` passaria a deixá-la votar duas vezes na mesma
sugestão, uma por identidade.

A idempotência é do BANCO (`Identidade.email` é `unique`), não desta camada: é o
que faz dois logins simultâneos virarem uma recuperação em vez de uma corrida.
"""

import pytest

from apps.sugestoes.models import Identidade

pytestmark = pytest.mark.django_db

PESSOA = "reincidente@exemplo.test"


def test_dez_entradas_uma_identidade(porta, perfil, rede, matricula):
    rede.alunos_diz(PESSOA, [matricula])

    for _ in range(10):
        resposta = porta.bater(perfil(PESSOA))
        assert resposta.status_code == 200, resposta.content

    assert Identidade.objects.filter(email=PESSOA).count() == 1


def test_a_segunda_entrada_recupera_o_mesmo_id(porta, perfil, rede, matricula):
    """O `id` é o que as sugestões apontam — ele não pode mudar entre logins."""
    rede.alunos_diz(PESSOA, [matricula])

    porta.bater(perfil(PESSOA))
    primeiro = Identidade.objects.get(email=PESSOA).id

    porta.bater(perfil(PESSOA))

    assert Identidade.objects.get(email=PESSOA).id == primeiro


def test_o_google_nao_sobrescreve_o_nome_escolhido(porta, perfil, rede, matricula):
    """`nome_exibido` é da pessoa depois da cunhagem, não do provedor.

    É o nome que aparece nas sugestões dela. Deixar o Google reescrevê-lo a cada
    login apagaria a escolha sem aviso — e a §3 chama esse campo de *default* do
    primeiro nome, não de espelho do Google.
    """
    rede.alunos_diz(PESSOA, [matricula])
    porta.bater(perfil(PESSOA, nome="João"))

    Identidade.objects.filter(email=PESSOA).update(nome_exibido="Jô da Marcenaria")
    porta.bater(perfil(PESSOA, nome="João"))

    assert Identidade.objects.get(email=PESSOA).nome_exibido == "Jô da Marcenaria"


def test_maiusculas_no_email_do_google_nao_criam_uma_segunda_pessoa(
    porta, perfil, rede, matricula
):
    """`Joao@…` e `joao@…` são a mesma caixa postal — e agora a mesma linha.

    Só a rota em minúsculas é dublada: se a normalização não acontecesse ANTES
    do salto de rede, o `respx` estouraria com `AllMockedAssertionError` em vez
    de deixar o teste chegar à contagem (armadilhas/054). O dublê prova as duas
    metades de uma vez.
    """
    rede.alunos_diz(PESSOA, [matricula])

    porta.bater(perfil(PESSOA))
    porta.bater(perfil(PESSOA.upper()))

    assert Identidade.objects.count() == 1
