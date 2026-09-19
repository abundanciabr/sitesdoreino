"""[INVARIANTE] O TLS termina no Traefik, e todo cookie desta célula sabe disso.

A vitrine foi a última célula Django da casa a declarar
`SECURE_PROXY_SSL_HEADER` (`config/settings.py`). Enquanto ela não declarava,
`request.is_secure()` respondia `False` em PRODUÇÃO: o Traefik encerra o TLS e
entrega a requisição ao uvicorn em `http://funil:8000`. O cookie da prévia da
equipe saía do site ao vivo sem a marca `Secure` — ele não autoriza nada, mas
era um cookie nosso trafegando em claro, e toda gravação de cookie futura desta
célula herdaria o mesmo engano.

O defeito era INVISÍVEL para as 603 provas da célula: nenhuma delas mandava o
`X-Forwarded-Proto`, então nenhuma media a diferença entre "chegou por HTTPS" e
"o Django acha que não". É a mesma armadilha que a `identidade` trava no
`test_inv_redirect_uri.py`, e pelo mesmo motivo: configuração que só tem efeito
em produção precisa de um guarda que a exercite, senão apagar a linha deixa a
suíte inteira verde e quebra o site.

Quatro provas para os DOIS `set_cookie` da célula, porque cada uma morre de um
jeito diferente e uma asserção só mandaria a próxima pessoa procurar no lugar
errado:

| prova | o que ela pega |
|---|---|
| a prévia sai com `Secure` | alguém apagou `SECURE_PROXY_SSL_HEADER` |
| sem o cabeçalho, a prévia sai sem `Secure` | alguém cravou `secure=True` e o guarda virou constante |
| o número do visitante sai com `Secure` | o mesmo, no outro `set_cookie` da célula |
| sem o cabeçalho, o número sai sem `Secure` | o número voltou a decidir por `DEBUG` em vez de pelo transporte |

As duas linhas "sem o cabeçalho" são o que impede este arquivo de medir uma
constante. Sem elas, um `secure=True` escrito à mão deixaria as outras duas
verdes sem que a célula soubesse nada sobre o transporte.
"""

from test_categorias_na_home import com_email  # noqa: F401  (fixture do da_equipe)
from test_sessao_no_site import COOKIE as COOKIE_DE_SESSAO
from test_ver_como import TELA, da_equipe  # noqa: F401  (fixture)
from tests.conftest import HOST_MESH

from apps.core import ver_como, visitante

HOME = "/pt-br/"

#: Como o Traefik entrega: o esquema original só no cabeçalho encaminhado,
#: porque para o uvicorn a requisição chega em `http`. Escrito assim, e não com
#: o atalho `secure=True` do cliente de teste do Django: aquele mexe direto no
#: `wsgi.url_scheme` e provaria um caminho que produção não usa.
COMO_O_TRAEFIK_ENTREGA = {"HTTP_X_FORWARDED_PROTO": "https"}


def _gravar_a_previa(client, **extra):
    """O POST do `ver-como`, do jeito que o `test_ver_como.py` já o faz."""
    return client.post(
        TELA,
        {"como": "aluno"},
        HTTP_HOST=HOST_MESH,
        HTTP_COOKIE=COOKIE_DE_SESSAO,
        **extra,
    )


def test_a_previa_da_equipe_sai_com_secure_atras_do_traefik(client, da_equipe):
    """O defeito que esta tarefa fecha, medido no cookie que o site grava."""
    resposta = _gravar_a_previa(client, **COMO_O_TRAEFIK_ENTREGA)

    assert resposta.status_code == 302
    assert resposta.cookies[ver_como.COOKIE]["secure"], (
        "a prévia saiu sem Secure numa requisição que chegou por HTTPS: "
        "SECURE_PROXY_SSL_HEADER sumiu do config/settings.py e o Django voltou "
        "a achar que o site inteiro é http"
    )


def test_sem_o_x_forwarded_proto_a_previa_sai_sem_secure(client, da_equipe):
    """Fixa o PORQUÊ do `Secure`, e não só o resultado.

    Se esta prova um dia falhar dizendo que saiu `Secure` mesmo sem o
    cabeçalho, é sinal de que alguém cravou o valor no código — e aí a prova de
    cima passou a medir uma constante, não o comportamento.
    """
    assert not _gravar_a_previa(client).cookies[ver_como.COOKIE]["secure"]


def test_o_numero_do_visitante_sai_com_secure_atras_do_traefik(client, rede):
    """O outro `set_cookie` da célula, pela mesma régua.

    Ele nasceu em 19/09/2026 decidindo por `not DEBUG`, justamente porque
    `is_secure()` mentia aqui. Consertada a causa, o contorno saiu e esta é a
    prova de que ele não precisa voltar.
    """
    morsel = client.get(HOME, HTTP_HOST=HOST_MESH, **COMO_O_TRAEFIK_ENTREGA).cookies[
        visitante.COOKIE
    ]

    assert morsel["secure"], (
        "o número do visitante saiu sem Secure numa requisição que chegou por "
        "HTTPS: SECURE_PROXY_SSL_HEADER sumiu do config/settings.py"
    )


def test_sem_o_x_forwarded_proto_o_numero_do_visitante_sai_sem_secure(client, rede):
    """O par da prova acima, e o que prende o número ao TRANSPORTE.

    Esta é a linha que fica vermelha se alguém devolver o `not settings.DEBUG`
    ao `visitante.py`: com ele, o cookie sai com `Secure` mesmo quando a
    requisição não chegou por HTTPS, e a célula volta a ter duas respostas
    diferentes para a mesma pergunta.
    """
    morsel = client.get(HOME, HTTP_HOST=HOST_MESH).cookies[visitante.COOKIE]

    assert not morsel["secure"]
