# apps/core/clients.py  # [RECEITA:R2 v1]
"""O que esta célula fala com o mundo lá fora — o Google, e só ele.

**O Google prova QUEM É. Ninguém aqui decide SE PODE.** A porta do site não
confere matrícula nem lista nenhuma: reconhecer não é autorizar
(DECISAO-onde-mora-a-sessao §4), e quem decide acesso é a célula dona do
recurso, na hora do recurso. Há guarda mecânico para isso —
`tests/test_inv_porta_nao_consulta_ninguem.py` estoura se um salto de rede
novo aparecer neste fluxo.

**Nada aqui é lido no import.** Toda variável de ambiente é buscada no ponto
de uso, via `exigir()`: o container web não pode morrer no boot porque uma
credencial do Google ainda não foi colada no servidor. Faltando a variável,
quem falha é o CAMINHO que precisa dela, fechado e com o nome da variável na
mensagem.

Em dev e no CI **nada disto chega à rede**: `tests/conftest.py` dubla as URLs
do Google com `respx`.
"""

import os
from urllib.parse import urlencode

import httpx

# Timeout SEMPRE explícito (R2). Curto de propósito: estes saltos estão no
# caminho de uma pessoa esperando uma página abrir, e a resposta certa para
# "demorou" é falhar fechado depressa, não pendurar a requisição dela.
TIMEOUT = 5.0

_cliente: httpx.Client | None = None


def http() -> httpx.Client:
    """Um `httpx.Client` por processo, em vez de `httpx.get()` a cada chamada.

    Não é micro-otimização (`armadilhas/082`): `httpx.get()` constrói um
    cliente novo por chamada, e com ele um `ssl.SSLContext` que carrega os
    certificados raiz do sistema — 0,4 s por chamada, medido. São dois saltos
    por login, então seria quase um segundo de espera pura para quem entra.
    `httpx.Client` é seguro entre threads, que é o que o uvicorn precisa; o
    `respx` troca o transporte na classe, então o dublê continua valendo.
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


def exigir(nome: str) -> str:
    """Lê uma variável de ambiente NO PONTO DE USO, ou falha fechado e alto."""
    valor = (os.environ.get(nome) or "").strip()
    if not valor:
        raise ConfiguracaoAusente(
            f"variável de ambiente ausente: {nome}. "
            "A entrada no site fica FECHADA até ela existir no env desta célula."
        )
    return valor


class GoogleOAuth:
    """Fluxo de código de autorização do Google — só o pedaço que interessa.

    Cópia do padrão da Caixa (que o estreou no EVO-12a). Por que o perfil vem
    do endpoint `userinfo` e não da verificação local do `id_token`: verificar
    o JWT na mão exigiria buscar o JWKS do Google (mais uma ida à rede, mais um
    cache para envelhecer errado) e uma biblioteca de criptografia a mais. O
    `access_token` usado aqui veio da PRÓPRIA troca servidor-a-servidor com o
    Google, sobre TLS — trocá-lo pelo perfil no `userinfo` é um salto a mais na
    mesma conversa, não um afrouxamento de confiança.
    """

    AUTORIZACAO = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN = "https://oauth2.googleapis.com/token"
    PERFIL = "https://openidconnect.googleapis.com/v1/userinfo"
    ESCOPO = "openid email profile"

    def url_de_autorizacao(self, *, redirect_uri: str, estado: str) -> str:
        """Para onde o botão "Entrar com Google" manda a pessoa.

        `prompt=select_account` não é enfeite: sem ele, o Google reentra em
        silêncio com a mesma conta, e quem precisa trocar de e-mail (o conselho
        da EVO-01 §5, que a Caixa dá na recusa de matrícula) fica preso na
        mesma conta para sempre.
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
