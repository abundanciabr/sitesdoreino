# apps/core/clients.py  # [RECEITA:R2 v1]
"""O que esta célula fala com o mundo lá fora — e nada além disso.

Duas conversas, e a `DECISAO-EVO-01-identidade.md` §2 separa as duas com uma
frase que organiza este arquivo inteiro: **o Google prova QUEM É; a célula
`alunos` decide SE PODE.** São perguntas diferentes, feitas a serviços
diferentes, e nenhuma das duas autoriza sozinha.

**Lei 3:** a `sugestoes` NUNCA lê o banco de `alunos`. Pergunta por HTTP, pelo
contrato congelado (`contracts/alunos.openapi.yaml`, operação
`listEnrollments`), com Bearer do par e **timeout sempre explícito** — o mesmo
padrão que `checkout` já usa para falar com `catalogo` e `pagamentos`.

**Nada aqui é lido no import.** Toda variável de ambiente é buscada no ponto de
uso, via `exigir()`: o container web não pode morrer no boot porque uma
credencial do Google ainda não foi colada no servidor (convenção da casa —
`LICOES.md`, "Fail-hard: só as duas variáveis que o CI já fornece"). Faltando a
variável, quem falha é o CAMINHO que precisa dela, fechado e com o nome da
variável na mensagem.

Em dev e no CI **nada disto chega à rede**: `tests/conftest.py` dubla as três
URLs de fora com `respx`. O aplicativo OAuth de verdade só nasce no Lote 2.
"""

import os
from urllib.parse import quote, urlencode

import httpx

# Timeout SEMPRE explícito (R2). Curto de propósito: estes dois saltos estão no
# caminho de uma pessoa esperando uma página abrir, e a resposta certa para
# "demorou" é falhar fechado depressa, não pendurar a requisição dela.
TIMEOUT = 5.0

_cliente: httpx.Client | None = None


def http() -> httpx.Client:
    """Um `httpx.Client` por processo, em vez de `httpx.get()` a cada chamada.

    Não é micro-otimização: `httpx.get()` constrói um cliente novo por chamada, e
    com ele um `ssl.SSLContext` que carrega os certificados raiz do sistema.
    **Medido nesta máquina: 0,4 s por chamada, contra 0,0 s com o cliente
    reaproveitado.** São dois saltos por login (Google + `alunos`), então é
    quase um segundo de espera pura para quem está entrando — e a suíte desta
    célula caía de 85 s para segundos com a mesma troca.

    Vale também o que vem de brinde: conexão reaproveitada entre logins, em vez
    de handshake TLS novo a cada um.

    `httpx.Client` é seguro entre threads, que é o que o uvicorn precisa. E o
    dublê continua valendo: o `respx` troca o transporte na classe, então um
    cliente criado ANTES de o mock entrar em cena é interceptado do mesmo jeito
    (conferido; e fora do mock ele volta a falhar de verdade, que é o que torna
    "a suíte não usa a rede" uma afirmação verificável).
    """
    global _cliente
    if _cliente is None:
        _cliente = httpx.Client(timeout=TIMEOUT)
    return _cliente


class ConfiguracaoAusente(RuntimeError):
    """Falta uma variável de ambiente que ESTE caminho precisa.

    Não é levantada no import — só quando alguém tenta atravessar a porta. A
    mensagem nomeia a variável porque o leitor do log vai ser o mantenedor.
    """


class GoogleIndisponivel(RuntimeError):
    """O Google não respondeu, ou respondeu coisa que não dá para usar."""


class AlunosIndisponivel(RuntimeError):
    """A célula `alunos` não respondeu, ou respondeu fora do contrato.

    **Isto NUNCA pode virar "deixa entrar porque não deu para conferir".** Não
    conseguir perguntar não é sinônimo de resposta positiva; quem trata esta
    exceção fecha a porta (ver `apps/core/views.py`).
    """


def exigir(nome: str) -> str:
    """Lê uma variável de ambiente NO PONTO DE USO, ou falha fechado e alto."""
    valor = (os.environ.get(nome) or "").strip()
    if not valor:
        raise ConfiguracaoAusente(
            f"variável de ambiente ausente: {nome}. "
            "A entrada pela Caixa fica FECHADA até ela existir no env desta célula."
        )
    return valor


class GoogleOAuth:
    """Fluxo de código de autorização do Google — só o pedaço que interessa.

    Por que o perfil vem do endpoint `userinfo` e não da verificação local do
    `id_token`: verificar o JWT na mão exigiria buscar o JWKS do Google (mais
    uma ida à rede, mais um cache para envelhecer errado) e uma biblioteca de
    criptografia a mais no `requirements.txt`. O `access_token` que usamos aqui
    veio da PRÓPRIA troca servidor-a-servidor com o Google, sobre TLS — trocá-lo
    pelo perfil no `userinfo` é um salto a mais na mesma conversa, não um
    afrouxamento de confiança.
    """

    AUTORIZACAO = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN = "https://oauth2.googleapis.com/token"
    PERFIL = "https://openidconnect.googleapis.com/v1/userinfo"
    ESCOPO = "openid email profile"

    def url_de_autorizacao(self, *, redirect_uri: str, estado: str) -> str:
        """Para onde o botão "Entrar com Google" manda a pessoa.

        `prompt=select_account` não é enfeite: é o que torna acionável o
        conselho da §5 da decisão ("se você comprou com outro e-mail, entre com
        ele"). Sem ele, o Google reentra em silêncio com a mesma conta e a
        pessoa fica presa no mesmo "não encontramos matrícula" para sempre.
        """
        parametros = {
            "client_id": exigir("GOOGLE_CLIENT_ID"),
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": self.ESCOPO,
            "state": estado,
            "access_type": "online",
            "prompt": "select_account",
        }
        return f"{self.AUTORIZACAO}?{urlencode(parametros)}"

    def perfil_do_codigo(self, *, codigo: str, redirect_uri: str) -> dict:
        """Troca o código pelo perfil. `redirect_uri` tem de ser IDÊNTICO ao do
        pedido — o Google confere, e é por isso que ele nunca é montado à mão
        (ver `_url_de_retorno` em `views.py`)."""
        try:
            resposta = http().post(
                self.TOKEN,
                data={
                    "code": codigo,
                    "client_id": exigir("GOOGLE_CLIENT_ID"),
                    "client_secret": exigir("GOOGLE_CLIENT_SECRET"),
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
        except httpx.RequestError as erro:
            raise GoogleIndisponivel(
                f"não deu para falar com o Google: {erro}"
            ) from erro

        if resposta.status_code != 200:
            raise GoogleIndisponivel(
                f"o Google recusou a troca do código (HTTP {resposta.status_code})"
            )

        acesso = (resposta.json() or {}).get("access_token")
        if not acesso:
            raise GoogleIndisponivel("o Google não devolveu access_token na troca")

        try:
            perfil = http().get(
                self.PERFIL, headers={"Authorization": f"Bearer {acesso}"}
            )
        except httpx.RequestError as erro:
            raise GoogleIndisponivel(
                f"não deu para buscar o perfil no Google: {erro}"
            ) from erro

        if perfil.status_code != 200:
            raise GoogleIndisponivel(
                f"o Google recusou o perfil (HTTP {perfil.status_code})"
            )

        corpo = perfil.json()
        if not isinstance(corpo, dict):
            raise GoogleIndisponivel("o perfil do Google veio num formato inesperado")
        return corpo


class AlunosClient:
    """`contracts/alunos.openapi.yaml`, operação `listEnrollments` — leitura pura.

    `ALUNOS_API_URL` aponta para a rede interna do Docker
    (`http://alunos:8000/api/alunos`, o `servers` do contrato), nunca para a
    borda pública. O token é o do PAR `sugestoes→alunos`: do outro lado ele
    entra como mais uma variável `TOKENS_ACEITOS_*` no env da `alunos` (Lote 2),
    sem uma linha de código lá.
    """

    def matriculas_de(self, email: str) -> list[dict]:
        """As matrículas deste e-mail. Lista vazia = não tem. Erro = FECHA.

        O contrato responde **404** para "aluno inexistente" — este é o único
        não-200 que significa uma resposta, e por isso é o único traduzido para
        lista vazia. Qualquer outro (401 de token errado, 500, timeout, conexão
        recusada) sobe como `AlunosIndisponivel`, porque "não consegui
        perguntar" e "perguntei e não tem" são fatos diferentes e merecem telas
        diferentes.
        """
        base = exigir("ALUNOS_API_URL").rstrip("/")
        token = exigir("ALUNOS_API_TOKEN")
        try:
            resposta = http().get(
                f"{base}/alunos/{quote(email, safe='@')}/matriculas",
                headers={"Authorization": f"Bearer {token}"},
            )
        except httpx.RequestError as erro:
            raise AlunosIndisponivel(
                f"não deu para falar com a célula alunos: {erro}"
            ) from erro

        if resposta.status_code == 404:
            return []
        if resposta.status_code != 200:
            raise AlunosIndisponivel(
                f"a célula alunos respondeu HTTP {resposta.status_code}"
            )

        corpo = resposta.json()
        if not isinstance(corpo, list):
            raise AlunosIndisponivel(
                "a célula alunos respondeu fora do contrato (esperava uma lista)"
            )
        return corpo
