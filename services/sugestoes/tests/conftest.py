"""Fixtures compartilhadas pelos testes-guarda da célula.

Duas metades: o quadro mínimo do modelo de dados (EVO-11) e o **dublê do mundo
lá fora** da porta de entrada (EVO-12a).

--------------------------------------------------------------------------
NADA AQUI TOCA A REDE — e é isto que torna a suíte executável sem internet
--------------------------------------------------------------------------
A porta fala com dois serviços de fora: o Google (quem é) e a célula `alunos`
(se pode). Os dois são dublados com `respx`, que troca o transporte do `httpx`
por um roteador em memória. Nenhuma das três URLs abaixo é resolvida, nenhum
socket é aberto, e o aplicativo OAuth de verdade — que o mantenedor só cria no
Lote 2 — não faz falta para nada aqui.

A prova disso é mecânica, não promessa: `respx.mock` sem `assert_all_called`
levanta `AllMockedAssertionError` para QUALQUER requisição que não tenha sido
registrada (armadilhas/054). Se alguém acrescentar amanhã um salto de rede novo
neste fluxo, a suíte estoura em vez de sair silenciosamente para a internet.

Os endereços de `alunos` são de mentira (`alunos.teste`), no mesmo espírito do
`conftest.py` do `checkout`: não existe host real por trás deles.
"""

from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx

from apps.core.clients import GoogleOAuth
from apps.sugestoes.models import Categoria, Identidade, Quadro, Sugestao

# ---------------------------------------------------------------------------
# O quadro mínimo do modelo de dados (EVO-11)
# ---------------------------------------------------------------------------


@pytest.fixture
def aluno(db):
    return Identidade.objects.create(
        email="aluno@exemplo.test", nome_exibido="Aluno de Teste"
    )


@pytest.fixture
def outro_aluno(db):
    return Identidade.objects.create(
        email="outro@exemplo.test", nome_exibido="Outro Aluno"
    )


@pytest.fixture
def quadro(db):
    return Quadro.objects.create(site_id="site-de-teste", nome="Quadro de teste")


@pytest.fixture
def categoria(quadro):
    return Categoria.objects.create(quadro=quadro, slug="curso", nome="Curso e aulas")


@pytest.fixture
def sugestao(quadro, categoria, aluno):
    return Sugestao.objects.create(
        quadro=quadro,
        categoria=categoria,
        autor=aluno,
        titulo="Legendas nas aulas",
        problema="Assisto no ônibus e não dá para ouvir.",
    )


# ---------------------------------------------------------------------------
# A porta de entrada (EVO-12a) — o mundo lá fora, de mentira
# ---------------------------------------------------------------------------

ALUNOS = "http://alunos.teste/api/alunos"

MATRICULA_ATIVA = {
    "site_id": "site-de-teste",
    "order_id": "pedido-1",
    "product_id": "curso-1",
    "status": "ativa",
    "enrolled_at": "2026-08-01T12:00:00+00:00",
}


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


@pytest.fixture
def matricula():
    """Uma matrícula ativa, na forma exata do `contracts/alunos.openapi.yaml`."""
    return dict(MATRICULA_ATIVA)


@pytest.fixture(autouse=True)
def ambiente(monkeypatch):
    """O env da célula como ele será na VPS — menos os segredos, que são falsos.

    `autouse` porque a porta lê tudo NO PONTO DE USO: um teste que esqueça de
    montar o ambiente não veria um erro claro, veria um 503 de configuração
    ausente e perderia tempo. A lista de staff começa VAZIA de propósito —
    ninguém é staff por acidente; o teste que precisa dela a declara.
    """
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "id-de-teste.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "segredo-de-teste-nunca-real")
    monkeypatch.setenv("ALUNOS_API_URL", ALUNOS)
    monkeypatch.setenv("ALUNOS_API_TOKEN", "token-do-par-sugestoes-alunos")
    monkeypatch.delenv("SUGESTOES_STAFF_EMAILS", raising=False)


class Rede:
    """As duas conversas de fora, sob controle do teste.

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

    def alunos_responde(self, email: str, resposta: httpx.Response):
        """A forma crua, para os guardas que varrem faixas de status."""
        return self.mock.get(self._url(email)).mock(return_value=resposta)

    def alunos_diz(self, email: str, matriculas: list[dict]):
        """200 com a lista — o caminho feliz do contrato."""
        return self.alunos_responde(email, httpx.Response(200, json=matriculas))

    def alunos_nao_conhece(self, email: str):
        """404 = "aluno inexistente", a resposta contratual para quem não comprou."""
        return self.alunos_responde(
            email, httpx.Response(404, json={"detail": "aluno inexistente"})
        )

    def alunos_fora_do_ar(self, email: str):
        """Conexão que não se estabelece — o mesmo que timeout, para esta porta."""
        return self.mock.get(self._url(email)).mock(
            side_effect=httpx.ConnectError("connection refused")
        )

    def alunos_demora_demais(self, email: str):
        return self.mock.get(self._url(email)).mock(
            side_effect=httpx.ReadTimeout("timed out")
        )

    @staticmethod
    def _url(email: str) -> str:
        return f"{ALUNOS}/alunos/{email}/matriculas"


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

    def bater(self, perfil: dict | None = None, **extra):
        if perfil is not None:
            self.rede.google_diz(perfil)
        inicio = self.client.get("/entrar/google")
        assert inicio.status_code == 302, inicio.content
        estado = parse_qs(urlparse(inicio["Location"]).query)["state"][0]
        parametros = {"code": "codigo-de-teste", "state": estado, **extra}
        return self.client.get("/entrar/google/retorno", parametros, follow=True)

    @property
    def esta_dentro(self) -> bool:
        """A prova de sessão aberta, lida do cookie de verdade do navegador."""
        from apps.core.sessao import CHAVE_IDENTIDADE

        cookie = self.client.cookies.get("sugestoes_sessao")
        if cookie is None or not cookie.value:
            return False
        return CHAVE_IDENTIDADE in self.client.session

    @property
    def identidade(self) -> Identidade:
        """Quem a sessão diz que é — lido do cookie, não guardado à parte.

        Um atributo gravado na entrada mentiria depois de um `/sair`, e é
        exatamente nos guardas de sessão que essa mentira apareceria tarde.
        """
        from apps.core.sessao import CHAVE_IDENTIDADE

        return Identidade.objects.get(pk=self.client.session[CHAVE_IDENTIDADE])


@pytest.fixture
def porta(client, rede, db):
    return Porta(client, rede)


# ---------------------------------------------------------------------------
# A participação do aluno (EVO-12b) — sessão aberta PELA PORTA, nunca à mão
# ---------------------------------------------------------------------------


@pytest.fixture
def entrar_como(rede, matricula, db):
    """Abre uma sessão de aluno pelo fluxo REAL do EVO-12a — quantas precisar.

    Poderia ser mais rápido assinar um cookie de sessão na mão. Seria também
    um guarda que continua verde no dia em que a porta parar de funcionar: a
    sessão de teste passaria a ser feita por um caminho que a produção não tem.
    Cada aluno destes entrou clicando no botão, com o Google e a `alunos`
    dublados como em qualquer outro guarda desta suíte.

    Cada chamada usa um `Client` próprio — dois alunos ao mesmo tempo é o caso
    normal de "votos de atores diferentes", e um cliente só teria um cookie só.
    """
    from django.test import Client

    def _entrar(email: str = "joao.silva@exemplo.test", nome: str = "João") -> Porta:
        rede.alunos_diz(email, [matricula])
        pessoa = Porta(Client(), rede)
        resposta = pessoa.bater(perfil_google(email=email, nome=nome))
        assert pessoa.esta_dentro, resposta.content
        return pessoa

    return _entrar


@pytest.fixture
def dentro(entrar_como):
    """Um aluno já dentro — o ponto de partida de todo guarda de participação."""
    return entrar_como()
