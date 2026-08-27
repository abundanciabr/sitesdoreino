"""O sino ao lado do nome — Fase 5 de `docs/notificacoes/PLANO-MESTRE.md`.

A regra que manda em tudo, ao pé da letra: *"notificações fora do ar ⇒ o site
mostra o nome sem sino e a página abre normal"* — falha ABERTA, sem exceção.
Este arquivo mede exatamente essa regra, com **um teste por modo de falha**
(nunca um teste genérico "a caixa caiu"), mais as duas regras de produto da
Escolha 1 de `docs/decisoes/DECISAO-fase-4-do-sininho.md`: número EXATO, teto
de EXIBIÇÃO "99+" só acima de 99 — o dado nunca tem teto, só a tela.

`tests/test_sessao_no_site.py` já cobre `request.ator` (identidade) em
profundidade; este arquivo importa dela o que precisa (`logado`, `NOME`,
`COOKIE`, `_chamadas_de_sessao`) em vez de reconstruir um mundo próprio —
mesma convenção de `test_i18n_juridico.py` importando de `test_i18n_catalogo`
(import pelo nome do módulo, sem `tests.`: a pasta não é pacote).

**Por que NOTIFICACOES_API_URL/TOKEN não são setadas por padrão em
`tests/conftest.py`:** é o estado REAL de hoje — a VPS ainda não foi
provisionada para este par (fora do escopo deste despacho, comigo/o
mantenedor depois do merge). Deixar a suíte inteira rodar sem elas por padrão
faz TODO teste desta célula, mesmo os que nem sabem que o sino existe,
exercitar o fail-open por omissão — sem precisar de um teste dedicado por
página. Só os testes que precisam do caminho "configurado e respondendo"
pedem o fixture `notificacoes_configurada` abaixo.
"""

import httpx
import pytest

from apps.core.clients import IdentidadeClient, NotificacoesClient
from apps.core.middleware import AtorDaRequisicao, _consultar_avisos
from test_sessao_no_site import COOKIE, NOME, _chamadas_de_sessao, logado
from tests.conftest import HOST_MESH, NOTIFICACOES, SITE_MESH, caminho_mesh

RESUMO = f"{NOTIFICACOES}/resumo"


@pytest.fixture
def notificacoes_configurada(monkeypatch):
    """As duas variáveis que a Fase 5 lê — mesma convenção de
    `IDENTIDADE_API_URL`/`TOKEN` em `tests/conftest.py::ambiente`, só que POR
    TESTE (ver o porquê no docstring do módulo)."""
    monkeypatch.setenv("NOTIFICACOES_API_URL", NOTIFICACOES)
    monkeypatch.setenv("NOTIFICACOES_API_TOKEN", "token-do-par-funil-notificacoes")


def _chamadas_de_resumo(rede):
    return [c for c in rede.calls if "/resumo" in str(c.request.url)]


# ---------------------------------------------------------------------------
# 1. request.ator.id — o passo 1 do despacho (contracts/identidade.openapi.yaml,
#    schema Session, campo `id`: sempre esteve lá, o funil só nunca tinha lido)
# ---------------------------------------------------------------------------
def test_ator_expoe_o_id_da_plataforma(monkeypatch):
    monkeypatch.setattr(
        IdentidadeClient,
        "obter_sessao",
        lambda self, cookie: {
            "autenticado": True,
            "id": "idt-123",
            "nome_exibido": "Fulano",
            "papel": "",
        },
    )

    ator = AtorDaRequisicao("cookie-qualquer", "site-qualquer")

    assert ator.id == "idt-123"


def test_ator_sem_cookie_tem_id_none_e_nao_toca_a_rede(rede):
    ator = AtorDaRequisicao("", "site-qualquer")  # sem cookie: nem tenta a rede

    assert ator.id is None
    assert _chamadas_de_sessao(rede) == []


# ---------------------------------------------------------------------------
# 2. O sino aparece ao lado do nome quando a notificacoes responde
# ---------------------------------------------------------------------------
def test_sino_aparece_com_a_contagem_quando_configurado(
    client, logado, notificacoes_configurada
):
    logado.get(RESUMO).mock(return_value=httpx.Response(200, json={"nao_lidas": 3}))

    conteudo = client.get(
        caminho_mesh("pt-br"), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE
    ).content.decode()

    assert 'class="sino"' in conteudo
    assert '<span class="contagem">3</span>' in conteudo
    assert NOME in conteudo  # o nome continua aparecendo, do lado do sino


def test_sino_aponta_para_a_tela_de_avisos_da_caixa(
    client, logado, notificacoes_configurada
):
    """A URL REAL (`services/sugestoes/config/urls.py`, rota `avisos`, sob o
    prefixo público `/forms/sugestoes/`) — não `request.url_da_caixa` (a raiz
    da Caixa, o quadro, outra página)."""
    logado.get(RESUMO).mock(return_value=httpx.Response(200, json={"nao_lidas": 1}))

    conteudo = client.get(
        caminho_mesh("pt-br"), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE
    ).content.decode()

    assert 'href="/forms/sugestoes/avisos"' in conteudo


def test_o_endereco_dos_avisos_vem_do_ambiente(
    client, logado, notificacoes_configurada, monkeypatch
):
    """A mudança de casa da identidade (25/08) e da Caixa (`URL_DA_CAIXA`)
    foram variável de ambiente — o mesmo padrão vale para o novo endereço."""
    logado.get(RESUMO).mock(return_value=httpx.Response(200, json={"nao_lidas": 1}))
    monkeypatch.setenv("URL_DOS_AVISOS", "/outra/rota/avisos")

    conteudo = client.get(
        caminho_mesh("pt-br"), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE
    ).content.decode()

    assert 'href="/outra/rota/avisos"' in conteudo


def test_o_pedido_de_resumo_carrega_destinatario_site_e_o_bearer_do_par(
    client, logado, notificacoes_configurada
):
    logado.get(RESUMO).mock(return_value=httpx.Response(200, json={"nao_lidas": 1}))

    client.get(caminho_mesh("pt-br"), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE)

    chamada = _chamadas_de_resumo(logado)[0].request
    assert chamada.url.params["destinatario_id"] == "idt-de-teste"
    assert chamada.url.params["site_id"] == SITE_MESH["id"]
    assert chamada.headers["authorization"] == "Bearer token-do-par-funil-notificacoes"


@pytest.mark.parametrize(
    "idioma,esperado",
    [("en", "Notifications"), ("pt-br", "Avisos"), ("es", "Avisos")],
)
def test_aria_label_do_sino_e_traduzida(
    client, logado, notificacoes_configurada, idioma, esperado
):
    logado.get(RESUMO).mock(return_value=httpx.Response(200, json={"nao_lidas": 1}))

    conteudo = client.get(
        caminho_mesh(idioma), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE
    ).content.decode()

    assert f'aria-label="{esperado}"' in conteudo


# ---------------------------------------------------------------------------
# 3. Config ausente — nem tenta a rede (mesmo padrão de IdentidadeClient)
# ---------------------------------------------------------------------------
def test_sino_some_por_padrao_sem_nenhuma_variavel(client, logado):
    """O estado REAL de hoje, sem nenhum fixture de configuração envolvido."""
    resp = client.get(caminho_mesh("pt-br"), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE)

    assert resp.status_code == 200
    conteudo = resp.content.decode()
    assert NOME in conteudo
    assert 'class="sino"' not in conteudo


def test_sino_por_padrao_nao_toca_a_rede(client, logado):
    client.get(caminho_mesh("pt-br"), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE)

    assert _chamadas_de_resumo(logado) == []


@pytest.mark.parametrize(
    "ausente",
    ["NOTIFICACOES_API_URL", "NOTIFICACOES_API_TOKEN"],
    ids=["sem-url", "sem-token"],
)
def test_sino_some_com_configuracao_parcial(
    client, logado, notificacoes_configurada, monkeypatch, ausente
):
    monkeypatch.delenv(ausente, raising=False)

    resp = client.get(caminho_mesh("pt-br"), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE)

    assert resp.status_code == 200
    conteudo = resp.content.decode()
    assert NOME in conteudo
    assert 'class="sino"' not in conteudo


@pytest.mark.parametrize(
    "ausente",
    ["NOTIFICACOES_API_URL", "NOTIFICACOES_API_TOKEN"],
    ids=["sem-url", "sem-token"],
)
def test_sino_com_configuracao_parcial_nao_toca_a_rede(
    client, logado, notificacoes_configurada, monkeypatch, ausente
):
    monkeypatch.delenv(ausente, raising=False)

    client.get(caminho_mesh("pt-br"), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE)

    assert _chamadas_de_resumo(logado) == []


# ---------------------------------------------------------------------------
# 4. Fail-open por MODO de falha — um teste por modo, nunca um genérico
# ---------------------------------------------------------------------------
def test_sino_some_quando_a_rede_recusa_a_conexao(
    client, logado, notificacoes_configurada
):
    logado.get(RESUMO).mock(side_effect=httpx.ConnectError("connection refused"))

    resp = client.get(caminho_mesh("pt-br"), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE)

    assert resp.status_code == 200
    conteudo = resp.content.decode()
    assert NOME in conteudo
    assert 'class="sino"' not in conteudo


def test_sino_some_quando_a_rede_estoura_timeout(
    client, logado, notificacoes_configurada
):
    logado.get(RESUMO).mock(side_effect=httpx.TimeoutException("demorou demais"))

    resp = client.get(caminho_mesh("pt-br"), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE)

    assert resp.status_code == 200
    assert 'class="sino"' not in resp.content.decode()


def test_sino_some_quando_a_notificacoes_responde_500(
    client, logado, notificacoes_configurada
):
    logado.get(RESUMO).mock(return_value=httpx.Response(500))

    resp = client.get(caminho_mesh("pt-br"), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE)

    assert resp.status_code == 200
    assert 'class="sino"' not in resp.content.decode()


def test_sino_some_quando_o_corpo_nao_e_json(client, logado, notificacoes_configurada):
    """`json.JSONDecodeError` é `ValueError`, não `httpx.HTTPError` — a mesma
    distinção que furou o fail-open na Fase D (RETROSPECTIVA-FASE-D §4) se
    ficasse fora do `try` certo em `NotificacoesClient.obter_resumo`."""
    logado.get(RESUMO).mock(
        return_value=httpx.Response(200, text="<html>erro de proxy</html>")
    )

    resp = client.get(caminho_mesh("pt-br"), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE)

    assert resp.status_code == 200
    assert 'class="sino"' not in resp.content.decode()


def test_sino_some_quando_o_corpo_foge_do_contrato(
    client, logado, notificacoes_configurada
):
    """200 com JSON válido, mas sem o campo que o contrato promete — 2xx não é
    sucesso (RETROSPECTIVA-FASE-D §4): o corpo tem de descrever o que foi
    pedido, senão é "não sei", nunca um número adivinhado."""
    logado.get(RESUMO).mock(
        return_value=httpx.Response(200, json={"isto": "não é o contrato"})
    )

    resp = client.get(caminho_mesh("pt-br"), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE)

    assert resp.status_code == 200
    assert 'class="sino"' not in resp.content.decode()


def test_sino_some_quando_nao_lidas_tem_tipo_errado(
    client, logado, notificacoes_configurada
):
    """`nao_lidas` presente, mas não é inteiro — modo de falha distinto do
    anterior (campo ausente): um proxy/serializer com bug pode mandar string
    onde o contrato promete `integer`."""
    logado.get(RESUMO).mock(return_value=httpx.Response(200, json={"nao_lidas": "3"}))

    resp = client.get(caminho_mesh("pt-br"), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE)

    assert resp.status_code == 200
    assert 'class="sino"' not in resp.content.decode()


# ---------------------------------------------------------------------------
# 5. Sessão sem id de plataforma — `Session.id` é opcional no contrato
#    (`anyOf: [string, null]`); sem ele não há `destinatario_id` a perguntar.
# ---------------------------------------------------------------------------
def test_sino_some_quando_a_sessao_nao_tem_id_da_plataforma(
    client, rede, notificacoes_configurada
):
    rede["get_session"].mock(
        return_value=httpx.Response(
            200,
            json={"autenticado": True, "id": None, "nome_exibido": NOME, "papel": ""},
        )
    )

    conteudo = client.get(
        caminho_mesh("pt-br"), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE
    ).content.decode()

    assert NOME in conteudo
    assert 'class="sino"' not in conteudo


def test_sino_sem_id_da_plataforma_nao_chama_notificacoes(
    client, rede, notificacoes_configurada
):
    rede.get(RESUMO).mock(return_value=httpx.Response(200, json={"nao_lidas": 9}))
    rede["get_session"].mock(
        return_value=httpx.Response(
            200,
            json={"autenticado": True, "id": None, "nome_exibido": NOME, "papel": ""},
        )
    )

    client.get(caminho_mesh("pt-br"), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE)

    assert _chamadas_de_resumo(rede) == []


# ---------------------------------------------------------------------------
# 6. Visitante anônimo NUNCA chama a notificacoes
# ---------------------------------------------------------------------------
def test_visitante_anonimo_nunca_ve_o_sino(client, rede, notificacoes_configurada):
    conteudo = client.get(caminho_mesh("pt-br"), HTTP_HOST=HOST_MESH).content.decode()

    assert 'class="sino"' not in conteudo


def test_visitante_anonimo_nunca_chama_notificacoes(
    client, rede, notificacoes_configurada
):
    # Configurada e PRONTA para responder — se algo chamar, o mock devolveria
    # uma contagem de verdade. A prova é que ninguém chama.
    rede.get(RESUMO).mock(return_value=httpx.Response(200, json={"nao_lidas": 7}))

    client.get(caminho_mesh("pt-br"), HTTP_HOST=HOST_MESH)

    assert _chamadas_de_resumo(rede) == []


# ---------------------------------------------------------------------------
# 7. Número EXATO, teto de EXIBIÇÃO "99+" só acima de 99 (Escolha 1 da
#    DECISAO-fase-4-do-sininho.md) — os dois lados da fronteira, e o zero.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("quantidade", [1, 2, 42, 99])
def test_sino_mostra_o_numero_exato_ate_99(
    client, logado, notificacoes_configurada, quantidade
):
    logado.get(RESUMO).mock(
        return_value=httpx.Response(200, json={"nao_lidas": quantidade})
    )

    conteudo = client.get(
        caminho_mesh("pt-br"), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE
    ).content.decode()

    assert f'<span class="contagem">{quantidade}</span>' in conteudo
    assert "99+" not in conteudo


@pytest.mark.parametrize("quantidade", [100, 101, 12345])
def test_sino_mostra_99_mais_a_partir_de_100(
    client, logado, notificacoes_configurada, quantidade
):
    logado.get(RESUMO).mock(
        return_value=httpx.Response(200, json={"nao_lidas": quantidade})
    )

    conteudo = client.get(
        caminho_mesh("pt-br"), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE
    ).content.decode()

    assert '<span class="contagem">99+</span>' in conteudo
    assert f">{quantidade}<" not in conteudo  # o número CRU não vaza pra tela


def test_sino_sem_badge_quando_zero(client, logado, notificacoes_configurada):
    """Escolha da TELA: `0` é um valor CONHECIDO (diferente de `None`) — o
    sino aparece porque a pergunta foi respondida, só sem número, porque zero
    não lido não é novidade para chamar atenção. `None` (não sei) é o único
    caso em que o sino inteiro some (testes da seção 3 e 4)."""
    logado.get(RESUMO).mock(return_value=httpx.Response(200, json={"nao_lidas": 0}))

    conteudo = client.get(
        caminho_mesh("pt-br"), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE
    ).content.decode()

    assert 'class="sino"' in conteudo  # o sino existe: a caixa respondeu...
    assert 'class="contagem"' not in conteudo  # ...sem badge de número


# ---------------------------------------------------------------------------
# 8. Cache: um sino em TODA página não pode custar uma chamada por página
# ---------------------------------------------------------------------------
def test_a_contagem_e_reaproveitada_entre_paginas(
    client, logado, notificacoes_configurada
):
    """Uma rajada de páginas da MESMA pessoa, na MESMA janela de cache, custa
    UMA pergunta à notificacoes — não uma por página vista. Mesma medição que
    `test_sessao_no_site.py::test_a_resposta_e_reaproveitada_entre_paginas`
    já faz para a sessão."""
    logado.get(RESUMO).mock(return_value=httpx.Response(200, json={"nao_lidas": 4}))

    for caminho in ("/pt-br/", "/pt-br/cadastro", "/pt-br/login"):
        client.get(caminho, HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE)

    assert len(_chamadas_de_resumo(logado)) == 1


def test_cache_e_isolado_por_pessoa_e_por_site(monkeypatch):
    """Unitário e direto na função de cache (`_consultar_avisos`), para provar
    a CHAVE sem precisar simular duas identidades inteiras por HTTP: a mesma
    pessoa repetida é cache-hit (uma chamada), pessoa OU site diferente é
    cache-miss (chamada nova) — a chave é a dupla (destinatario_id, site_id).
    `tests/conftest.py::ambiente` já limpa o cache antes e depois de cada
    teste (autouse), então não é preciso fazer isso aqui."""
    chamadas = []

    def resumo_falso(self, destinatario_id, site_id):
        chamadas.append((destinatario_id, site_id))
        return 1

    monkeypatch.setattr(NotificacoesClient, "obter_resumo", resumo_falso)

    _consultar_avisos("pessoa-a", "site-1")
    _consultar_avisos("pessoa-a", "site-1")  # repetida: cache hit
    _consultar_avisos("pessoa-b", "site-1")  # pessoa diferente: chamada nova
    _consultar_avisos("pessoa-a", "site-2")  # mesma pessoa, site diferente: nova

    assert chamadas == [
        ("pessoa-a", "site-1"),
        ("pessoa-b", "site-1"),
        ("pessoa-a", "site-2"),
    ]


def test_none_tambem_e_cacheado_numa_rajada(monkeypatch):
    """Mesmo modo de falha ao longo de uma rajada: a primeira chamada tenta e
    descobre `None`; as seguintes, na mesma janela, reaproveitam o `None` —
    uma `notificacoes` fora do ar não pode virar uma tentativa de rede por
    página vista (é o efeito mais importante do cache: proteger justamente o
    serviço que já está com problema)."""
    chamadas = []

    def resumo_falso(self, destinatario_id, site_id):
        chamadas.append(1)
        return None

    monkeypatch.setattr(NotificacoesClient, "obter_resumo", resumo_falso)

    assert _consultar_avisos("pessoa-c", "site-1") is None
    assert _consultar_avisos("pessoa-c", "site-1") is None
    assert _consultar_avisos("pessoa-c", "site-1") is None

    assert len(chamadas) == 1
