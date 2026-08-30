"""[INVARIANTE] Staff entra pela mesma sessão do site, e SEM precisar de matrícula.

A checagem de staff vem ANTES da de matrícula (herança da porta antiga, EVO-01
§4): quem modera a Caixa não pode ser obrigado a comprar o próprio curso, e não
pode ficar de fora quando a `alunos` estiver fora do ar.

**O mecanismo da prova é o `respx` do conftest** (armadilhas/054): a fixture de
staff NÃO dubla a `alunos` — se a ordem dos portões inverter um dia, estes
guardas caem com `AllMockedAssertionError`, não com um verde de mentira.

E o crachá vem da lista DESTA célula (`SUGESTOES_STAFF_EMAILS`), nunca do
`papel` que a `identidade` responde no contrato — aquele é de exibição, e o
invariante da DECISAO-onde-mora-a-sessao §4 proíbe usá-lo para autorizar.
"""

from django.urls import reverse


def test_staff_entra_sem_a_alunos_ser_consultada(equipe):
    """A fixture `equipe` é a prova inteira: nenhum endpoint de `alunos` foi
    dublado, e ela está dentro."""
    resposta = equipe.abrir()
    assert "equipe" in resposta.content.decode(), "o crachá aparece na porta"


def test_staff_alcanca_a_moderacao(equipe, sugestao):
    """301 (e não 200) desde 30/08/2026: a tela mudou de casa, o crachá não.

    O que este guarda mede é que quem tem crachá ATRAVESSA a porta — quem não
    tem leva 403 e nem descobre para onde a gestão foi.
    """
    assert equipe.client.get(reverse("fila")).status_code == 301


def test_papel_do_contrato_nao_da_cracha(entrar_como, rede, db):
    """Se a `identidade` dissesse `papel: staff` (de exibição), a Caixa NÃO
    obedece: a lista dela continua vazia, então aqui a pessoa é aluno.

    É o invariante "reconhecer não é autorizar" medido do lado que autoriza.
    """
    pessoa = entrar_como(email="pessoa@exemplo.test")
    # força o dublê a afirmar staff na resposta do contrato
    valor = pessoa.client.cookies["meshcraft_sessao"].value
    rede.sessoes[valor]["papel"] = "staff"

    from apps.core import sessao as ses

    ses.limpar_caches()  # a resposta mudou; o cache guardava a anterior

    resposta = pessoa.client.get(reverse("fila"))
    assert resposta.status_code == 403, (
        "a moderação obedeceu o papel do contrato — autorização vazou para "
        "fora da célula dona do recurso"
    )
