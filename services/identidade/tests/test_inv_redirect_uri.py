"""[INVARIANTE] O `redirect_uri` que vai ao Google, em TRÊS partes separadas.

Guardas repatriados da `sugestoes` (`test_entrada_script_name.py` na versão
anterior à mudança de casa do login, 25/08/2026). Eles não vieram junto com o
código na primeira entrega, e a auditoria provou o preço disso por mutação:
**remover `SECURE_PROXY_SSL_HEADER` deixava os 55 testes verdes** — e derrubaria
o login do site inteiro em produção, com CI verde, deploy verde e `/healthz`
respondendo 200.

O Google compara o `redirect_uri` **caractere a caractere** com o endereço
cadastrado no console. A string tem três partes, com três donos diferentes, e
cada uma quebra por um motivo diferente — por isso três asserções separadas, e
não uma só (uma asserção única mandaria a próxima pessoa procurar no lugar
errado):

| parte | quem produz | o que quebra se der errado |
|---|---|---|
| `https` | `SECURE_PROXY_SSL_HEADER` lendo o `X-Forwarded-Proto` do Traefik | `redirect_uri_mismatch` — ninguém entra |
| `meshcraft.top` | o cabeçalho `Host` da requisição — a célula NÃO crava domínio | login vazando para o domínio errado |
| `/entrar/google/retorno` | `reverse()` — o endereço neutro cadastrado em 24/08 | `redirect_uri_mismatch` |

O cliente de teste síncrono basta aqui (ao contrário do guarda-irmão da
Caixa, que precisava de `AsyncClient` por causa do `FORCE_SCRIPT_NAME`): esta
célula não tem prefixo de caminho, então o que importa é só o Host e o
`X-Forwarded-Proto`. O TLS termina no Traefik, e a requisição chega ao uvicorn
em `http` — é o cabeçalho encaminhado que carrega a verdade.
"""

from urllib.parse import parse_qs, urlparse

from django.test import Client

# Escrito à mão, e não derivado do código: é a string que o mantenedor cadastrou
# no console do Google (DECISAO-onde-mora-a-sessao §5.2). Um teste que a
# montasse com os mesmos `reverse()` do código passaria mesmo com tudo errado.
CADASTRADO_NO_GOOGLE = "https://meshcraft.top/entrar/google/retorno"


def _pela_borda_publica(*, https: bool = True, host: str = "meshcraft.top"):
    """Uma requisição como o Traefik a entrega: o esquema original só no
    cabeçalho encaminhado, o host escolhido por quem chama."""
    extra = {"HTTP_HOST": host}
    if https:
        extra["HTTP_X_FORWARDED_PROTO"] = "https"
    return Client().get("/entrar/google", **extra)


def _redirect_uri(resposta) -> str:
    destino = urlparse(resposta["Location"])
    assert destino.netloc == "accounts.google.com", resposta["Location"]
    return parse_qs(destino.query)["redirect_uri"][0]


def test_o_redirect_uri_sai_em_https_atras_do_traefik(db):
    """A metade que morre em produção — e SÓ em produção, porque em dev não há
    proxy nenhum para encaminhar esquema."""
    recebido = urlparse(_redirect_uri(_pela_borda_publica()))

    assert recebido.scheme == urlparse(CADASTRADO_NO_GOOGLE).scheme == "https", (
        "o redirect_uri saiu em http — SECURE_PROXY_SSL_HEADER foi removido do "
        "settings? O Google recusa com redirect_uri_mismatch e NINGUÉM entra"
    )


def test_sem_o_x_forwarded_proto_o_esquema_seria_http(db):
    """Fixa o PORQUÊ do `https`, não só o resultado.

    Se este teste um dia falhar dizendo que o esquema é `https` mesmo sem o
    cabeçalho, é sinal de que alguém cravou o esquema no código — e aí o
    guarda de cima passou a medir uma constante, não o comportamento.
    """
    recebido = urlparse(_redirect_uri(_pela_borda_publica(https=False)))

    assert recebido.scheme == "http"


def test_o_dominio_vem_da_requisicao_e_nunca_e_cravado_no_codigo(db):
    """Multissítio (Lei 9): a célula não conhece domínio nenhum.

    Um domínio cravado aqui faria o login de um site vazar para o endereço de
    outro. Note que o Google só aceita o endereço cadastrado — este guarda
    protege a origem do valor, não a lista do console.
    """
    recebido = urlparse(_redirect_uri(_pela_borda_publica(host="outro-dominio.test")))

    assert recebido.netloc == "outro-dominio.test", (
        "o domínio do redirect_uri não veio do Host da requisição — alguém "
        "cravou um domínio no código"
    )


def test_o_caminho_e_o_endereco_neutro_cadastrado_no_google(db):
    """A terceira parte: sem prefixo de célula (DECISAO-onde-mora-a-sessao §5.2
    — o endereço neutro foi cadastrado em 24/08 exatamente para este dia)."""
    recebido = urlparse(_redirect_uri(_pela_borda_publica()))

    assert recebido.path == urlparse(CADASTRADO_NO_GOOGLE).path


def test_as_tres_partes_juntas_batem_com_o_console(db):
    """A prova de ponta: a string inteira, como o Google a compara."""
    assert _redirect_uri(_pela_borda_publica()) == CADASTRADO_NO_GOOGLE
