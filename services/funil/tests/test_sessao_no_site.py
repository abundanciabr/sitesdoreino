"""O site reconhece quem entrou — em toda página, nos três idiomas.

Entrega 3 da `docs/decisoes/DECISAO-onde-mora-a-sessao.md`. O `funil` não lê o
cookie de sessão (ele é assinado com a chave da outra célula e aponta para o
banco dela): ele **pergunta**, pelo contrato congelado
`contracts/identidade.openapi.yaml`, operação `getSession`.

Quatro coisas são guardadas aqui, e cada uma corresponde a uma forma diferente
de esta entrega dar errado:

1. **Reconhecer não é autorizar** — a Caixa fora do ar não pode derrubar a
   vitrine. Ela abre mostrando "Entrar" (§4 da decisão).
2. **Cache compartilhado** — página que mostrou o nome de alguém não pode ser
   guardada por proxy nenhum. Há Cloudflare na frente de domínio desta
   plataforma (`armadilhas/017`).
3. **Preguiça** — visitante anônimo em página de marketing não paga salto de
   rede nenhum. É a maioria absoluta do tráfego.
4. **O e-mail não atravessa** — o contrato não o traz, e o site não o mostra.
"""

import httpx
import pytest

from tests.conftest import HOST_A, HOST_MESH, SITE_MESH

IDIOMAS = ("en", "pt-br", "es")
NOME = "João"
COOKIE = "meshcraft_sessao=valor-opaco-que-o-funil-nao-interpreta"


def _chamadas_de_sessao(rede):
    return [c for c in rede.calls if "/sessao" in str(c.request.url)]


@pytest.fixture
def logado(rede):
    """Alguém entrou. A resposta é EXATAMENTE a do contrato — nada além."""
    rede["get_session"].mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "idt-de-teste",
                "nome_exibido": NOME,
                "papel": "aluno",
            },
        )
    )
    return rede


# ---------------------------------------------------------------------------
# 1. A porta aparece em toda página, nos três idiomas
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("caminho", ["/{}/", "/{}/cadastro", "/{}/login"])
@pytest.mark.parametrize("idioma", IDIOMAS)
def test_visitante_ve_entrar_em_toda_pagina(client, rede, idioma, caminho):
    resp = client.get(caminho.format(idioma), HTTP_HOST=HOST_MESH)

    assert resp.status_code == 200, resp.content
    conteudo = resp.content.decode()
    assert 'class="sessao"' in conteudo
    # O link aponta para a porta DESTE site, com o prefixo de idioma — nunca
    # para um caminho nu, que cairia no redirect da matriz do resolver.
    assert f'href="/{idioma}/login"' in conteudo


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_quem_entrou_ve_o_proprio_nome_em_toda_pagina(client, logado, idioma):
    resp = client.get(f"/{idioma}/", HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE)

    conteudo = resp.content.decode()
    assert NOME in conteudo
    assert f'href="/{idioma}/login"' not in conteudo  # já entrou: some o "Entrar"


def test_o_cookie_e_repassado_intacto_e_o_par_se_identifica(client, logado):
    client.get("/pt-br/", HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE)

    chamada = _chamadas_de_sessao(logado)[0].request
    # O cookie viaja OPACO: o funil carrega de um lado para o outro, não lê.
    assert chamada.headers["cookie"] == COOKIE
    # E o par se identifica — são credenciais diferentes provando coisas
    # diferentes (quem chama × quem é a pessoa).
    assert chamada.headers["authorization"] == "Bearer token-do-par-funil-identidade"


# ---------------------------------------------------------------------------
# 2. INVARIANTE: reconhecer não é autorizar — falhar não derruba a vitrine
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "resposta",
    [
        httpx.Response(500),
        httpx.Response(401),
        httpx.Response(200, json={"isto": "não é o contrato"}),
    ],
    ids=["caixa-com-erro", "token-recusado", "corpo-fora-do-contrato"],
)
def test_caixa_com_problema_a_pagina_abre_como_visitante(client, rede, resposta):
    rede["get_session"].mock(return_value=resposta)

    resp = client.get("/pt-br/", HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE)

    assert resp.status_code == 200, "a vitrine caiu porque a Caixa tropeçou"
    assert 'href="/pt-br/login"' in resp.content.decode()


def test_caixa_fora_do_ar_a_pagina_abre_como_visitante(client, rede):
    rede["get_session"].mock(side_effect=httpx.ConnectError("connection refused"))

    resp = client.get("/pt-br/", HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE)

    assert resp.status_code == 200
    assert 'href="/pt-br/login"' in resp.content.decode()


# ---------------------------------------------------------------------------
# 3. INVARIANTE: página com nome não é cacheável por ninguém
# ---------------------------------------------------------------------------
def test_pagina_de_quem_entrou_nao_pode_ser_guardada_por_proxy(client, logado):
    resp = client.get("/pt-br/", HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE)

    assert resp["Cache-Control"] == "private, no-store"
    assert "Cookie" in resp.get("Vary", "")


@pytest.mark.parametrize(
    "extra",
    [{}, {"HTTP_COOKIE": COOKIE}],
    ids=["sem-cookie", "com-cookie-de-visitante"],
)
def test_pagina_de_visitante_continua_cacheavel(client, rede, extra):
    """A outra metade, e ela é o motivo de o guarda acima existir em par.

    Este teste JÁ REPROVOU uma versão desta entrega: a primeira marcava a
    resposta sempre que o template *consultava* a sessão — e como toda página
    consulta (é o template perguntando "tem alguém?"), o efeito era tirar o
    cache da vitrine inteira do site. A marca certa é "alguém foi
    RECONHECIDO", não "alguém perguntou".

    Vale para o visitante COM cookie também: cookie de analytics não pode
    custar o cache da página.
    """
    resp = client.get("/pt-br/", HTTP_HOST=HOST_MESH, **extra)

    assert resp.status_code == 200
    assert "no-store" not in resp.get("Cache-Control", "")
    assert "Cookie" not in resp.get("Vary", "")


# ---------------------------------------------------------------------------
# 4. Preguiça: sem cookie, ninguém pergunta nada
# ---------------------------------------------------------------------------
def test_visitante_sem_cookie_nao_custa_salto_de_rede(client, rede):
    client.get("/pt-br/", HTTP_HOST=HOST_MESH)

    assert _chamadas_de_sessao(rede) == []


def test_a_resposta_e_reaproveitada_entre_paginas(client, logado):
    """Uma pergunta por janela de cache, não uma por página aberta."""
    for caminho in ("/pt-br/", "/pt-br/cadastro", "/pt-br/login"):
        client.get(caminho, HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE)

    assert len(_chamadas_de_sessao(logado)) == 1


# ---------------------------------------------------------------------------
# 5. O e-mail não atravessa a fronteira
# ---------------------------------------------------------------------------
def test_o_site_nunca_recebe_nem_mostra_email(client, rede):
    """Mesmo que a outra ponta um dia devolva e-mail, ele não vai para a tela.

    O contrato não traz o campo e a Caixa tem guarda própria — este é o cinto
    do lado de cá: o `funil` só sabe ler `nome_exibido` e `papel`.
    """
    rede["get_session"].mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "idt-de-teste",
                "nome_exibido": NOME,
                "papel": "aluno",
                "email": "joao.silva@exemplo.test",
            },
        )
    )

    conteudo = client.get(
        "/pt-br/", HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE
    ).content.decode()

    assert NOME in conteudo
    assert "joao.silva@exemplo.test" not in conteudo


# ---------------------------------------------------------------------------
# 6. A página de entrada
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("idioma", IDIOMAS)
def test_a_pagina_de_entrada_leva_ao_google(client, rede, idioma):
    """O botão vai à porta da `identidade`, dizendo aonde voltar (`next` =
    a home DO IDIOMA da página — quem entrou em espanhol volta ao espanhol)."""
    conteudo = client.get(f"/{idioma}/login", HTTP_HOST=HOST_MESH).content.decode()

    assert f'href="/entrar/google?next=%2F{idioma}%2F"' in conteudo


def test_o_endereco_de_entrada_vem_do_ambiente(client, rede, monkeypatch):
    """A mudança de casa da identidade FOI uma variável (25/08/2026) — e o
    guarda continua provando que a próxima também será."""
    monkeypatch.setenv("URL_DE_ENTRADA", "/outra/porta")

    conteudo = client.get("/pt-br/login", HTTP_HOST=HOST_MESH).content.decode()

    assert 'href="/outra/porta?next=%2Fpt-br%2F"' in conteudo


def test_caminho_nu_leva_ao_idioma_padrao(client, rede):
    resp = client.get("/login", HTTP_HOST=HOST_MESH)

    assert resp.status_code == 302
    assert resp["Location"] == f"/{SITE_MESH['default_language']}/login"


def test_site_monolingue_nao_tem_pagina_de_entrada(client, rede):
    """Os domínios antigos seguem exatamente como estavam — login é do site
    multilíngue, e a landing deles é comparada byte a byte noutro guarda."""
    assert client.get("/login", HTTP_HOST=HOST_A).status_code == 404
    assert client.get("/pt-br/login", HTTP_HOST=HOST_A).status_code == 404


def test_a_entrada_fica_fora_do_sitemap(client, rede):
    """Página de entrada não é conteúdo que alguém procure no Google."""
    corpo = client.get("/sitemap.xml", HTTP_HOST=HOST_MESH).content.decode()

    assert "/cadastro" in corpo  # sanidade: o sitemap está sendo gerado
    assert "/login" not in corpo


def test_recusa_da_identidade_e_explicada_no_idioma_da_pagina(client, rede):
    """O vocabulário de recusa (?erro=chave) vem da célula `identidade`, que
    não renderiza página — quem explica é esta tela, traduzida."""
    conteudo = client.get(
        "/pt-br/login", {"erro": "email-nao-verificado"}, HTTP_HOST=HOST_MESH
    ).content.decode()

    assert 'class="recusa"' in conteudo
    assert "não confirma esse e-mail como verificado" in conteudo


def test_erro_desconhecido_na_query_e_ignorado(client, rede):
    """Query string é entrada de rede: chave fora da lista não vira catálogo
    nem eco — a página abre limpa, como se o parâmetro não existisse."""
    conteudo = client.get(
        "/pt-br/login", {"erro": "<script>alert(1)</script>"}, HTTP_HOST=HOST_MESH
    ).content.decode()

    assert 'class="recusa"' not in conteudo
    assert "alert(1)" not in conteudo


# ---------------------------------------------------------------------------
# 7. A vitrine abre mesmo SEM CONFIGURAÇÃO — o buraco que a auditoria achou
# ---------------------------------------------------------------------------
# Os guardas acima cobrem a Caixa FORA DO AR (falha de rede). Nenhum cobria a
# falha mais provável de todas: a variável não colada no servidor. E era a
# única que derrubava o site — `KeyError` não é `httpx.HTTPError`, então
# atravessava o `try`, o middleware e o template, virando HTTP 500 para
# qualquer visitante com um cookie qualquer no navegador.
#
# Note o par: o de cima prova que a página ABRE, o de baixo prova que ela nem
# TENTA a rede (esperar 2s de timeout para descobrir que não há endereço
# atrasaria toda página do site).
@pytest.mark.parametrize(
    "ausente",
    ["IDENTIDADE_API_URL", "IDENTIDADE_API_TOKEN"],
    ids=["sem-url", "sem-token"],
)
def test_sem_configuracao_a_pagina_abre_como_visitante(
    client, rede, monkeypatch, ausente
):
    monkeypatch.delenv(ausente, raising=False)

    resp = client.get("/pt-br/", HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE)

    assert resp.status_code == 200, (
        "o site caiu porque uma variável de ambiente não estava no servidor — "
        "fail-open vale para configuração também, não só para rede"
    )
    assert 'href="/pt-br/login"' in resp.content.decode()


def test_sem_configuracao_nao_custa_salto_de_rede(client, rede, monkeypatch):
    monkeypatch.delenv("IDENTIDADE_API_URL", raising=False)

    client.get("/pt-br/", HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE)

    assert _chamadas_de_sessao(rede) == []


def test_resposta_200_que_nao_e_json_nao_derruba_a_vitrine(client, rede):
    """`json.JSONDecodeError` é `ValueError`, não `httpx.HTTPError`.

    Cenário real: um proxy interposto devolve a própria página de erro com
    status 200, ou a resposta chega truncada. Fora do `try`, isso furava o
    fail-open — é a família do bug mais caro da Fase D (*2xx não é sucesso*).
    """
    rede["get_session"].mock(
        return_value=httpx.Response(200, text="<html>erro do proxy</html>")
    )

    resp = client.get("/pt-br/", HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE)

    assert resp.status_code == 200
    assert 'href="/pt-br/login"' in resp.content.decode()
