"""[INVARIANTE] A porta do site fala com o GOOGLE, e com mais ninguém.

A DECISAO-celula-de-identidade tirou a consulta de matrícula da porta: quem
decide SE PODE é a célula dona do recurso, na hora do recurso (a Caixa confere
matrícula na participação; reconhecer não é autorizar —
DECISAO-onde-mora-a-sessao §4).

O mecanismo da prova é o `respx` do conftest (armadilhas/054): QUALQUER
requisição fora das duas URLs do Google registradas estoura
`AllMockedAssertionError`. Se um dia alguém reintroduzir uma consulta —
`alunos`, uma lista externa, o que for — este arquivo fica vermelho sem
precisar saber o nome do que foi consultado.
"""

from tests.conftest import perfil_google


def test_pessoa_sem_matricula_nenhuma_entra_no_site(porta):
    """O caso de produto: site padrão — qualquer conta Google verificada entra.

    Se a porta consultasse matrícula, este teste estouraria em
    `AllMockedAssertionError` (nenhum endpoint de `alunos` está dublado) —
    e é exatamente essa a dupla função dele.
    """
    resposta = porta.bater(perfil_google(email="visitante@exemplo.test"))
    assert resposta.status_code == 302
    assert porta.esta_dentro


def test_o_fluxo_inteiro_so_tocou_o_google(porta, rede):
    porta.bater()
    chamadas = [str(chamada.request.url) for chamada in rede.mock.calls]
    assert chamadas, "o fluxo deveria ter falado com o Google dublado"
    assert all("google" in url for url in chamadas), chamadas
