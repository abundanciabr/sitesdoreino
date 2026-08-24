"""Guarda de armadilhas/029, segunda temporada: o OAuth sob `SCRIPT_NAME`.

O `/healthz` desta célula já está travado (`test_healthz_script_name.py`). As
rotas da porta de entrada têm o MESMO problema, com um agravante: o `/healthz`
que some é uma sonda morta que alguém acaba percebendo, enquanto um
`redirect_uri` sem prefixo é o Google devolvendo `redirect_uri_mismatch` para
todo mundo — em produção, e **só** em produção, porque em dev não existe prefixo
nenhum para faltar.

A `DECISAO-EVO-01-identidade.md` §6 fixa o endereço que o mantenedor vai
cadastrar no console do Google:

    https://meshcraft.top/forms/sugestoes/entrar/google/retorno

O Google compara essa string **caractere a caractere** com o `redirect_uri` que
chega no pedido, e ela tem três partes com três donos diferentes:

| parte | quem produz | o que quebra se der errado |
|---|---|---|
| `https` | `SECURE_PROXY_SSL_HEADER` lendo o `X-Forwarded-Proto` do Traefik (o TLS termina lá; no uvicorn a requisição chega em `http`) | `redirect_uri_mismatch` |
| `meshcraft.top` | o cabeçalho `Host` da requisição — a célula NÃO crava domínio | login vazando para o domínio errado |
| `/forms/sugestoes/entrar/google/retorno` | `reverse()` + `FORCE_SCRIPT_NAME` | `redirect_uri_mismatch` |

Os três são conferidos separadamente abaixo, porque falham por motivos
diferentes e uma asserção única mandaria a próxima pessoa procurar no lugar
errado.

`AsyncClient` é obrigatório pelo mesmo motivo do guarda do `/healthz`: só ele
constrói o `ASGIRequest` que a célula usa em produção, cujo
`path_info = path.removeprefix(script_name)`. Pelo client síncrono a aritmética
é a inversa e o cenário medido seria outro (ver `LICOES.md`). Ele também é o
motivo de o host aqui ser `testserver`: a fábrica assíncrona do Django injeta
esse `Host` sozinha e não há como substituí-lo pela API pública — o que o guarda
prova é que o domínio vem da REQUISIÇÃO, seja ele qual for.
"""

from urllib.parse import parse_qs, urlparse

import pytest
from asgiref.sync import async_to_sync
from django.test import AsyncClient
from django.urls import clear_script_prefix, set_script_prefix

PREFIXO = "/forms/sugestoes"

# Escrito à mão, e não derivado do código: é a string que o mantenedor vai colar
# no console do Google (DECISAO-EVO-01 §6). Um teste que a montasse com os
# mesmos `reverse()` do código passaria mesmo com o endereço errado.
CADASTRADO_NO_GOOGLE = "https://meshcraft.top/forms/sugestoes/entrar/google/retorno"


@pytest.fixture
def env_de_producao(settings):
    """O env da VPS — MAIS o que o servidor de verdade faz e o client não faz.

    Armadilha que custa uma tarde se descoberta na hora errada: `reverse()` não
    lê `settings.FORCE_SCRIPT_NAME`, lê um prefixo guardado numa variável de
    thread. Quem a preenche é o servidor, na porta de entrada — o
    `ASGIHandler.__call__` real chama `set_script_prefix(get_script_prefix(scope))`
    antes de despachar. O `AsyncClientHandler` do Django **não chama**: ele
    monta o `ASGIRequest` e vai direto para o middleware.

    Resultado se esta linha não existisse: o roteamento acerta (o `ASGIRequest`
    calcula `path_info` sozinho a partir da setting), mas todo `reverse()` sai
    SEM o prefixo — e o guarda ficaria vermelho acusando um bug que só existe no
    teste, enquanto a produção estaria certa. Emular o servidor aqui é a mesma
    natureza de emular o Traefik não removendo o prefixo: cenário, não código
    sob teste.

    O prefixo é de thread e NÃO é limpo entre testes pelo Django — daí o
    `clear_script_prefix()` na saída, senão ele vaza para quem rodar depois.
    """
    settings.FORCE_SCRIPT_NAME = PREFIXO
    set_script_prefix(PREFIXO)
    yield
    clear_script_prefix()


def _pela_borda_publica(caminho, *, https=True):
    """Uma requisição como o Traefik entrega: prefixo na request line, e o
    esquema original só no cabeçalho encaminhado."""
    cabecalhos = {"x-forwarded-proto": "https"} if https else {}
    return async_to_sync(AsyncClient().get)(caminho, headers=cabecalhos)


def _redirect_uri(resposta) -> str:
    destino = urlparse(resposta["Location"])
    assert destino.netloc == "accounts.google.com", resposta["Location"]
    return parse_qs(destino.query)["redirect_uri"][0]


def test_o_redirect_uri_leva_o_prefixo_publico(env_de_producao):
    """A metade que morre em produção: sem o prefixo, o Google recusa."""
    resposta = _pela_borda_publica(f"{PREFIXO}/entrar/google")

    assert resposta.status_code == 302, resposta.content
    recebido = urlparse(_redirect_uri(resposta))
    assert recebido.path == urlparse(CADASTRADO_NO_GOOGLE).path


def test_o_redirect_uri_sai_em_https_atras_do_traefik(env_de_producao):
    """A outra metade: o TLS termina no proxy, e o Django precisa acreditar nele."""
    recebido = urlparse(_redirect_uri(_pela_borda_publica(f"{PREFIXO}/entrar/google")))

    assert recebido.scheme == urlparse(CADASTRADO_NO_GOOGLE).scheme == "https"


def test_sem_o_x_forwarded_proto_o_esquema_seria_http(env_de_producao):
    """Fixa o PORQUÊ do `https`, não só o resultado.

    Se alguém remover `SECURE_PROXY_SSL_HEADER` de `config/settings.py`, o teste
    de cima fica vermelho — mas este aqui explica que a diferença é o esquema, e
    não o prefixo, poupando a próxima pessoa de caçar no lugar errado.
    """
    recebido = urlparse(
        _redirect_uri(_pela_borda_publica(f"{PREFIXO}/entrar/google", https=False))
    )

    assert recebido.scheme == "http"
    assert recebido.path == urlparse(CADASTRADO_NO_GOOGLE).path


def test_o_dominio_vem_da_requisicao_e_nao_do_codigo(env_de_producao):
    """A Caixa é multi-domínio por natureza (Lei 9): o site é resolvido do Host.

    Um domínio cravado em `settings` ou no `views.py` funcionaria em
    `meshcraft.top` e mandaria os alunos dos outros sites para o lugar errado.
    """
    recebido = urlparse(_redirect_uri(_pela_borda_publica(f"{PREFIXO}/entrar/google")))

    assert recebido.netloc == "testserver"


def test_a_rota_de_retorno_existe_no_endereco_publico(env_de_producao):
    """O endereço cadastrado precisa RESOLVER quando o Google for usá-lo.

    Sem `code` nem `state` a porta recusa (400) — e é justamente esse 400, e não
    um 404, que prova que a rota existe sob o prefixo.
    """
    resposta = _pela_borda_publica(f"{PREFIXO}/entrar/google/retorno")

    assert resposta.asgi_request.path == f"{PREFIXO}/entrar/google/retorno"
    assert resposta.asgi_request.path_info == "/entrar/google/retorno"
    assert resposta.status_code == 400, resposta.status_code


def test_o_urlconf_continua_sem_conhecer_o_prefixo(client):
    """Sem `SCRIPT_NAME`, o caminho prefixado não existe — a Caixa é dona do
    próprio endereço por configuração, não por código."""
    assert client.get(f"{PREFIXO}/entrar/google").status_code == 404
    assert client.get(f"{PREFIXO}/entrar/google/retorno").status_code == 404
    assert client.get(f"{PREFIXO}/sair").status_code == 404
