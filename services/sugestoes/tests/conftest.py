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

import json
from unittest import mock
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx
from django.urls import reverse

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


# ---------------------------------------------------------------------------
# A moderação (EVO-13) — o crachá também vem pela porta, e da variável de env
# ---------------------------------------------------------------------------


@pytest.fixture
def lista_da_staff(monkeypatch):
    """Põe um e-mail em `SUGESTOES_STAFF_EMAILS`, acumulando.

    Acumula porque a variável é UMA lista separada por vírgula: um
    `setenv` por pessoa faria a segunda apagar o crachá da primeira, e um
    guarda com duas pessoas da equipe falharia por um motivo que não é o dele.

    Note que ela nasce ausente (fixture `ambiente`): **ninguém é staff por
    acidente**, e o teste que precisa de crachá o pede explicitamente.
    """
    emails: list[str] = []

    def _incluir(email: str) -> None:
        emails.append(email.strip().lower())
        monkeypatch.setenv("SUGESTOES_STAFF_EMAILS", ",".join(emails))

    return _incluir


@pytest.fixture
def entrar_como_staff(rede, lista_da_staff, db):
    """Abre uma sessão de EQUIPE pelo mesmo fluxo real do aluno.

    Uma diferença que é prova por si: aqui **não se dubla a `alunos`**. A
    checagem de staff acontece antes da de matrícula (`DECISAO-EVO-01` §4), e o
    `respx` estoura em qualquer requisição não registrada (armadilhas/054) — se
    alguém inverter a ordem um dia, esta fixture cai com
    `AllMockedAssertionError`, não com um teste verde de mentira.
    """
    from django.test import Client

    def _entrar(email: str = "equipe@meshcraft.test", nome: str = "Equipe") -> Porta:
        lista_da_staff(email)
        pessoa = Porta(Client(), rede)
        resposta = pessoa.bater(perfil_google(email=email, nome=nome))
        assert pessoa.esta_dentro, resposta.content
        return pessoa

    return _entrar


@pytest.fixture
def equipe(entrar_como_staff):
    """Alguém da equipe já dentro — o ponto de partida de todo guarda do EVO-13."""
    return entrar_como_staff()


# ---------------------------------------------------------------------------
# Os eventos (EVO-20) — o fio e os quatro fatos, provocados pela jornada REAL
# ---------------------------------------------------------------------------


class Fio:
    """O transporte do relay sob controle do teste: o que saiu no `xadd`.

    O Redis é dublado no transporte (`redis.from_url`), e não com um servidor
    de verdade, pelo mesmo motivo que Google e `alunos` são dublados acima: uma
    suíte que precisa de container é uma suíte que fica vermelha por motivo
    alheio, e a máquina do mantenedor é Windows. O que se prova aqui é o
    comportamento do relay e a FORMA do que ele publica — a prova de que o fio
    de verdade funciona é o roteiro de Redis real do handoff (worker +
    `XRANGE`), que nenhum teste substitui.
    """

    def __init__(self) -> None:
        self.mensagens: list[tuple[str, dict]] = []
        self.cliente = mock.Mock()
        self.cliente.xadd.side_effect = self._xadd

    def _xadd(self, stream: str, campos: dict) -> None:
        # `json.loads` aqui de propósito: se o relay publicar algo que não é
        # JSON, o teste morre no ponto exato em vez de comparar strings.
        self.mensagens.append((stream, json.loads(campos["json"])))

    @property
    def streams(self) -> list[str]:
        return [stream for stream, _ in self.mensagens]

    def envelopes(self, event: str) -> list[dict]:
        return [
            envelope for _, envelope in self.mensagens if envelope["event"] == event
        ]

    def um_envelope(self, event: str) -> dict:
        achados = self.envelopes(event)
        assert len(achados) == 1, f"esperava 1 {event} no fio, vieram {len(achados)}"
        return achados[0]


@pytest.fixture
def fio(monkeypatch):
    """O relay publicando contra o dublê — e `REDIS_STREAMS_URL` presente.

    A variável é montada aqui e não na fixture `ambiente` de propósito: o relay
    a lê NO PONTO DE USO, e um teste que prove "Redis fora do ar" precisa poder
    tirá-la sem lutar com um `autouse`.
    """
    monkeypatch.setenv("REDIS_STREAMS_URL", "redis://redis.teste:6379/0")
    linha = Fio()
    monkeypatch.setattr("redis.from_url", lambda *a, **k: linha.cliente)
    return linha


class Caixa:
    """Os quatro fatos, provocados pelo clique de verdade — nunca pelo ORM.

    Um teste que criasse `Sugestao.objects.create(...)` à mão provaria que o
    construtor de evento funciona, e continuaria verde no dia em que a view
    parasse de chamá-lo. O que interessa aqui é o contrário: que a JORNADA
    emite. Por isso tudo passa pelo `client` da sessão aberta na porta.
    """

    def __init__(self, aluno, equipe) -> None:
        self.aluno = aluno
        self.equipe = equipe

    def publicar(self, titulo: str = "Legendas nas aulas", **extra) -> Sugestao:
        resposta = self.aluno.client.post(
            reverse("nova_sugestao"),
            {
                "titulo": titulo,
                "problema": "Assisto no ônibus e não dá para ouvir.",
                "categoria": "curso",
                "publicar": "1",
                **extra,
            },
        )
        assert resposta.status_code == 302, resposta.content
        return Sugestao.objects.get(titulo=titulo)

    def votar(self, sugestao: Sugestao, quem=None):
        return (quem or self.aluno).client.post(reverse("votar", args=[sugestao.id]))

    def desvotar(self, sugestao: Sugestao, quem=None):
        return (quem or self.aluno).client.post(reverse("desvotar", args=[sugestao.id]))

    def mudar_status(self, sugestao: Sugestao, status: str, nota: str = ""):
        return self.equipe.client.post(
            reverse("mudar_status", args=[sugestao.id]),
            {"status": status, "nota": nota},
        )

    def os_quatro_fatos(self) -> Sugestao:
        """Publicar, votar, desvotar e mudar o status — nesta ordem.

        A ordem não é decorativa: desvotar depois de votar é o único jeito de o
        `voto-removido` existir, e mudar o status por último deixa o
        `HistoricoStatus` contando a história inteira.
        """
        sugestao = self.publicar()
        assert self.votar(sugestao).status_code == 302
        assert self.desvotar(sugestao).status_code == 302
        assert (
            self.mudar_status(
                sugestao, Sugestao.Status.PLANEJADO, nota="Entra no próximo ciclo."
            ).status_code
            == 302
        )
        return sugestao


@pytest.fixture
def caixa(dentro, equipe, categoria):
    """Um aluno e alguém da equipe, os dois já dentro pela porta de verdade."""
    return Caixa(dentro, equipe)
