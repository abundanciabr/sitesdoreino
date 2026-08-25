"""Fixtures compartilhadas pelos testes-guarda da célula.

--------------------------------------------------------------------------
NADA AQUI TOCA A REDE — e é isto que torna a suíte executável sem internet
--------------------------------------------------------------------------
A porta fala com UM serviço de fora: o Google (quem é). Ele é dublado com
`respx`, que troca o transporte do `httpx` por um roteador em memória.

A prova disso é mecânica, não promessa: `respx.mock` sem `assert_all_called`
levanta `AllMockedAssertionError` para QUALQUER requisição que não tenha sido
registrada (armadilhas/054). Se alguém acrescentar amanhã um salto de rede
novo neste fluxo — uma consulta de matrícula, por exemplo, que a
DECISAO-celula-de-identidade proíbe NA PORTA — a suíte estoura em vez de sair
silenciosamente para a internet.
"""

from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx

from apps.core.clients import GoogleOAuth
from apps.identidade.models import Identidade

# ---------------------------------------------------------------------------
# A porta de entrada — o mundo lá fora, de mentira
# ---------------------------------------------------------------------------


def perfil_google(
    email: str = "joao.silva@exemplo.test",
    *,
    verificado: bool = True,
    nome: str = "João",
) -> dict:
    """O corpo que o `userinfo` do Google devolve — com os campos que a porta lê."""
    return {
        "sub": "1234567890",
        "email": email,
        "email_verified": verificado,
        "given_name": nome,
        "name": f"{nome} da Silva",
    }


@pytest.fixture
def perfil():
    """A fábrica de perfis do Google, como fixture — cada guarda monta o seu."""
    return perfil_google


@pytest.fixture(autouse=True)
def ambiente(monkeypatch):
    """O env da célula como ele será na VPS — menos os segredos, que são falsos.

    `autouse` porque a porta lê tudo NO PONTO DE USO: um teste que esqueça de
    montar o ambiente não veria um erro claro, veria uma recusa de configuração
    ausente e perderia tempo. A lista de staff começa VAZIA de propósito —
    ninguém é staff por acidente; o teste que precisa dela a declara.
    """
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "id-de-teste.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "segredo-de-teste-nunca-real")
    monkeypatch.delenv("IDENTIDADE_STAFF_EMAILS", raising=False)


class Rede:
    """A conversa com o Google, sob controle do teste.

    Cada método diz o que o mundo VAI responder; o teste declara só o que
    importa para o invariante que está provando. O que não for declarado
    estoura (armadilhas/054) — é assim que um salto de rede novo aparece.
    """

    def __init__(self, mock: respx.MockRouter) -> None:
        self.mock = mock
        # A troca do código pelo access_token é sempre a mesma e nunca é o
        # assunto de nenhum guarda: fica pronta desde o começo.
        self.token = mock.post(GoogleOAuth.TOKEN).mock(
            return_value=httpx.Response(200, json={"access_token": "acesso-de-teste"})
        )
        self.perfil = mock.get(GoogleOAuth.PERFIL)
        self.google_diz(perfil_google())

    def google_diz(self, perfil: dict) -> None:
        self.perfil.mock(return_value=httpx.Response(200, json=perfil))

    def google_fora_do_ar(self):
        return self.perfil.mock(side_effect=httpx.ConnectError("connection refused"))


@pytest.fixture
def rede():
    with respx.mock(assert_all_called=False) as mock:
        yield Rede(mock)


class Porta:
    """O fluxo inteiro do clique até a volta, com o Google dublado.

    Existe para que cada guarda mostre só o seu invariante em vez de repetir a
    dança do `state` cinco vezes. O `state` é lido do redirecionamento REAL que
    a célula produziu — não é inventado aqui, senão o guarda do antifalsificação
    passaria a testar a si mesmo.
    """

    def __init__(self, client, rede: Rede) -> None:
        self.client = client
        self.rede = rede

    def bater(self, perfil: dict | None = None, next: str | None = None, **extra):
        if perfil is not None:
            self.rede.google_diz(perfil)
        parametros_inicio = {"next": next} if next is not None else {}
        inicio = self.client.get("/entrar/google", parametros_inicio)
        assert inicio.status_code == 302, inicio.content
        estado = parse_qs(urlparse(inicio["Location"]).query)["state"][0]
        parametros = {"code": "codigo-de-teste", "state": estado, **extra}
        return self.client.get("/entrar/google/retorno", parametros)

    @property
    def esta_dentro(self) -> bool:
        """A prova de sessão aberta, lida do cookie de verdade do navegador."""
        from apps.core.sessao import CHAVE_IDENTIDADE

        # Nome escrito à mão, e não lido de settings: um teste que lê a mesma
        # variável que o código passaria mesmo com o valor errado. É o MESMO
        # nome que a Caixa usava — a sessão mudou de casa, não de nome
        # (DECISAO-celula-de-identidade).
        cookie = self.client.cookies.get("meshcraft_sessao")
        if cookie is None or not cookie.value:
            return False
        return CHAVE_IDENTIDADE in self.client.session

    @property
    def identidade(self) -> Identidade:
        """Quem a sessão diz que é — lido do cookie, não guardado à parte."""
        from apps.core.sessao import CHAVE_IDENTIDADE

        return Identidade.objects.get(pk=self.client.session[CHAVE_IDENTIDADE])


@pytest.fixture
def porta(client, rede, db):
    return Porta(client, rede)


@pytest.fixture
def entrar_como(rede, db):
    """Abre uma sessão pelo fluxo REAL da porta — quantas precisar.

    Poderia ser mais rápido assinar um cookie de sessão na mão. Seria também
    um guarda que continua verde no dia em que a porta parar de funcionar.
    Cada chamada usa um `Client` próprio — duas pessoas ao mesmo tempo é caso
    normal, e um cliente só teria um cookie só.
    """
    from django.test import Client

    def _entrar(email: str = "joao.silva@exemplo.test", nome: str = "João") -> Porta:
        pessoa = Porta(Client(), rede)
        resposta = pessoa.bater(perfil_google(email=email, nome=nome))
        assert pessoa.esta_dentro, resposta.content
        return pessoa

    return _entrar


@pytest.fixture
def dentro(entrar_como):
    """Alguém já dentro — o ponto de partida dos guardas da API interna."""
    return entrar_como()


@pytest.fixture
def lista_da_staff(monkeypatch):
    """Põe um e-mail em `IDENTIDADE_STAFF_EMAILS`, acumulando.

    Acumula porque a variável é UMA lista separada por vírgula: um `setenv`
    por pessoa faria a segunda apagar o crachá da primeira. Note que ela nasce
    ausente (fixture `ambiente`): **ninguém é staff por acidente**.
    """
    emails: list[str] = []

    def _incluir(email: str) -> None:
        emails.append(email.strip().lower())
        monkeypatch.setenv("IDENTIDADE_STAFF_EMAILS", ",".join(emails))

    return _incluir
