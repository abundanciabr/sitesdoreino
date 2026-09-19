"""Teste-guarda [INV-P13]: a porta da área administrativa é fail-CLOSED.

Lei: `docs/decisoes/DECISAO-celula-admin.md` §2. Este arquivo trava a tabela
inteira — **uma linha de tabela, um teste** — mais a lista de caminhos isentos.

| Situação                            | Esperado aqui      | Site público (`funil`) |
|-------------------------------------|--------------------|------------------------|
| `identidade` fora do ar             | **503**            | abre, mostra "Entrar"  |
| sessão válida, e-mail fora da lista | **404** (não 403)  | —                      |
| sem sessão                          | 302 para o login   | —                      |

**Por que cada caso precisa de teste próprio, e não de um "testa a porta":** os
três se parecem de dentro (nenhum deles renderiza a página) e são
completamente diferentes de fora. Um bug que trocasse o 503 por 302 mandaria
o mantenedor para um login que também está fora do ar; um que trocasse o 404
por 200 abriria a operação da plataforma para qualquer conta Google. Nenhum
dos dois apareceria num teste que só perguntasse "a página abriu?".

A rede é dublada com `respx`: uma suíte que dependesse da `identidade` de
verdade ficaria vermelha por motivo alheio, e não poderia exercitar "o
provedor caiu" sem derrubar alguma coisa.
"""

import httpx
import pytest
import respx
from django.test import Client

BASE = "http://identidade:8000/interno"
SESSAO = f"{BASE}/sessao/completa"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"


@pytest.fixture(autouse=True)
def env_da_porta(settings, monkeypatch):
    """O env real da célula: endereço, token do par e a lista de quem entra."""
    monkeypatch.setenv("IDENTIDADE_API_URL", BASE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    settings.ADMIN_EMAILS = "dono@exemplo.com, OUTRO@Exemplo.com "
    settings.URL_DE_ENTRADA = "/entrar/google"


def _com_cookie() -> Client:
    c = Client()
    c.defaults["HTTP_COOKIE"] = COOKIE
    return c


def _pessoa(email: str, papel: str = "staff") -> dict:
    return {
        "autenticado": True,
        "id": "id-opaco-123",
        "nome_exibido": "Fulano",
        "papel": papel,
        "email": email,
    }


# --------------------------------------------------------------- linha 1 da tabela


@respx.mock
def test_identidade_fora_do_ar_nao_abre_e_nao_redireciona():
    """503 — e explicitamente NÃO 302.

    Mandar para o login seria mandar a pessoa para a porta que provavelmente
    também está fora do ar, e a área administrativa é justamente onde ela vai
    olhar quando algo está errado.
    """
    respx.get(SESSAO).mock(side_effect=httpx.ConnectError("recusou"))
    r = _com_cookie().get("/")
    assert r.status_code == 503, r.content
    assert "indisponível" in r.content.decode().lower()


@respx.mock
def test_identidade_respondendo_erro_tambem_fecha():
    """Um 5xx do provedor não é "visitante" — é "não consegui perguntar"."""
    respx.get(SESSAO).mock(return_value=httpx.Response(502))
    assert _com_cookie().get("/").status_code == 503


@respx.mock
def test_identidade_respondendo_403_fecha_e_nao_vira_visitante():
    """403 = o par não está em `TOKENS_COMPLETOS_ADMIN`.

    De dentro, isto é indistinguível de "você não está na lista" — e é por
    isso que o script de provisionamento confere os dois degraus do par. Aqui
    o que importa é que a resposta é 503 (problema de configuração), nunca
    302 nem 200.
    """
    respx.get(SESSAO).mock(return_value=httpx.Response(403))
    assert _com_cookie().get("/").status_code == 503


@respx.mock
def test_corpo_fora_do_contrato_fecha():
    """200 com corpo que não é JSON. *Status 2xx não é sucesso* (RETROSPECTIVA §4)."""
    respx.get(SESSAO).mock(return_value=httpx.Response(200, text="<html>proxy</html>"))
    assert _com_cookie().get("/").status_code == 503


def test_env_ausente_fecha_sem_derrubar_o_container(monkeypatch):
    """Sem endereço/token, a área fecha — mas o processo continua de pé.

    `armadilhas/097`: ler env no `__init__` de um cliente transforma variável
    ausente em HTTP 500 em toda página, com o deploy verde. Aqui tem de ser
    503 nomeado, e o `/healthz` (abaixo) tem de continuar 200.
    """
    monkeypatch.delenv("IDENTIDADE_API_URL", raising=False)
    monkeypatch.delenv("IDENTIDADE_API_TOKEN", raising=False)
    assert _com_cookie().get("/").status_code == 503
    assert Client().get("/healthz").status_code == 200


# --------------------------------------------------------------- linha 2 da tabela


@respx.mock
def test_sessao_valida_fora_da_lista_recebe_404_e_nao_403():
    """Para quem não é da casa, `/admin` não existe."""
    respx.get(SESSAO).mock(
        return_value=httpx.Response(200, json=_pessoa("estranho@exemplo.com"))
    )
    r = _com_cookie().get("/")
    assert r.status_code == 404, r.content


@respx.mock
def test_papel_staff_nao_autoriza_nada():
    """A resposta da identidade NUNCA autoriza — quem decide é `ADMIN_EMAILS`.

    Este é o guarda do invariante *reconhecer não é autorizar*
    (`DECISAO-onde-mora-a-sessao.md` §4) nesta célula: uma pessoa com papel
    `staff` — que dá moderação na Caixa — continua fora daqui se o e-mail dela
    não estiver na lista DESTA célula.
    """
    respx.get(SESSAO).mock(
        return_value=httpx.Response(200, json=_pessoa("staff@exemplo.com", "staff"))
    )
    assert _com_cookie().get("/").status_code == 404


@respx.mock
def test_lista_vazia_fecha_para_todo_mundo(settings):
    """Fail-closed por construção: sem lista, ninguém entra."""
    settings.ADMIN_EMAILS = ""
    respx.get(SESSAO).mock(
        return_value=httpx.Response(200, json=_pessoa("dono@exemplo.com"))
    )
    assert _com_cookie().get("/").status_code == 404


# --------------------------------------------------------------- linha 3 da tabela


def test_sem_cookie_vai_para_o_login_com_o_destino():
    """302 para o login, levando aonde a pessoa queria ir."""
    r = Client().get("/")
    assert r.status_code == 302
    assert r["Location"].startswith("/entrar/google?next=")


@respx.mock
def test_com_cookie_mas_sem_sessao_vai_para_o_login():
    """Cookie de outra coisa (idioma, analytics) é visitante, não erro."""
    respx.get(SESSAO).mock(
        return_value=httpx.Response(200, json={"autenticado": False})
    )
    r = _com_cookie().get("/")
    assert r.status_code == 302
    assert r["Location"].startswith("/entrar/google?next=")


# --------------------------------------------------------------- quem ENTRA


@respx.mock
def test_email_na_lista_entra():
    """O caso feliz — sem ele, os testes acima passariam com a porta soldada."""
    respx.get(SESSAO).mock(
        return_value=httpx.Response(200, json=_pessoa("dono@exemplo.com"))
    )
    r = _com_cookie().get("/")
    assert r.status_code == 200, r.content
    assert "Visão geral" in r.content.decode()


@respx.mock
def test_a_comparacao_de_email_normaliza_caixa_e_espaco():
    """`OUTRO@Exemplo.com ` no env casa com `outro@exemplo.com` na sessão.

    Sem isto, um espaço a mais na variável do servidor tranca o mantenedor
    para fora — e o que ele vê é um 404 indistinguível de erro de rota.
    """
    respx.get(SESSAO).mock(
        return_value=httpx.Response(200, json=_pessoa("Outro@Exemplo.COM"))
    )
    assert _com_cookie().get("/").status_code == 200


# --------------------------------------------------------------- os isentos


def test_os_caminhos_isentos_sao_exatamente_estes_e_so_estes():
    """Inventário por igualdade EXATA: rota nova não escapa em silêncio.

    Este conjunto é o que separa "a porta protege tudo" de "a porta protege o
    que alguém lembrou de proteger". Acrescentar caminho aqui é decisão
    visível no diff — que é o ponto. [INV-P14] fez a lista crescer de 1 para
    10 em 28/08/2026: `/healthz` (máquina) mais os 9 arquivos exatos de
    `/mapa-ia/` (o mapa técnico do projeto, pedido público pelo mantenedor).

    **O que NUNCA fazer:** trocar por `<=`, ou pôr um prefixo (`/mapa-ia/…`
    sem listar cada arquivo) — um prefixo isentaria qualquer coisa que algum
    dia nascer sob esse caminho, não só o que existe hoje. A `sugestoes` tem
    uma rota pública de estático declarada; esta célula não tem estático
    servido — o CSS é embutido no template, justamente para não abrir essa
    porta agora.
    """
    from apps.core.porta import CAMINHOS_ISENTOS

    assert CAMINHOS_ISENTOS == {
        "/healthz",
        "/mapa-ia/",
        "/mapa-ia/INDICE.md",
        "/mapa-ia/01-leis-ritos-e-invariantes.md",
        "/mapa-ia/02-armadilhas-e-padroes-recorrentes.md",
        "/mapa-ia/03-sistema-do-painel-e-livro.md",
        "/mapa-ia/04-arquitetura-de-celulas-e-contratos.md",
        "/mapa-ia/05-infraestrutura-ci-e-deploy.md",
        "/mapa-ia/06-produto-decisoes-e-roadmap.md",
        "/mapa-ia/07-oportunidades-e-fronteiras.md",
    }


def test_healthz_responde_sem_cookie_nenhum():
    """O healthcheck do compose não tem cookie para apresentar."""
    r = Client().get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@respx.mock
def test_healthz_nao_pergunta_a_identidade():
    """A sonda não pode depender de outra célula estar de pé.

    Se o `/healthz` perguntasse, a `identidade` caindo deixaria o container da
    `admin` `unhealthy` — e o `deploy-infra`, que exige todos os serviços
    `running`, reprovaria a plataforma inteira por causa de outra célula.
    `respx.mock` sem rota registrada estoura se alguém tentar sair para a rede.
    """
    assert Client().get("/healthz").status_code == 200


# --------------------------------------------------------------- a CSP


@respx.mock
def test_csp_permite_iframe_de_mesma_origem_e_nao_none():
    """`frame-ancestors 'self'` — NUNCA `'none'`.

    `'none'` proíbe enquadramento inclusive de mesma origem, e a galeria de
    painéis (fase 3) serve painel em iframe a partir da própria área. O erro
    já foi cometido uma vez, no papel, e pego na revisão (`armadilhas/109`) —
    este guarda existe para que a próxima vez seja vermelha em vez de
    descoberta em produção.
    """
    respx.get(SESSAO).mock(
        return_value=httpx.Response(200, json=_pessoa("dono@exemplo.com"))
    )
    csp = _com_cookie().get("/")["Content-Security-Policy"]
    assert "frame-ancestors 'self'" in csp
    assert "frame-ancestors 'none'" not in csp


def test_csp_vale_tambem_nas_respostas_de_recusa():
    """Página de recusa também é página: sem CSP ela seria a brecha."""
    assert "Content-Security-Policy" in Client().get("/")


# --------------------------------------------------------------------------
# NENHUMA TELA DESTA ÁREA PODE FICAR GUARDADA NO NAVEGADOR (06/09/2026)
#
# Toda tela daqui é CALCULADA do estado de agora — quem pediu acesso, quanto
# entrou, o que os robôs fizeram, que endereços o site tem. Uma cópia velha
# não é uma tela desatualizada: é uma tela que mente, e mente exatamente como
# uma tela certa. O dono não tem como perceber a diferença.
# --------------------------------------------------------------------------


@respx.mock
def test_nenhuma_tela_do_admin_pode_ficar_guardada_no_navegador():
    """A resposta saía SEM instrução de cache nenhuma, e o navegador decidia.

    Medido em 06/09/2026 contra o site no ar:

        $ curl -s -D - -o /dev/null https://meshcraft.top/docs/
        HTTP/1.1 200 OK
        Strict-Transport-Security: max-age=31536000; includeSubDomains

    Nem `Cache-Control`, nem `ETag`, nem `Last-Modified`: nada dizendo ao
    navegador o que fazer com aquilo.
    """
    respx.get(SESSAO).mock(
        return_value=httpx.Response(200, json=_pessoa("dono@exemplo.com"))
    )
    resposta = _com_cookie().get("/")
    assert resposta.status_code == 200
    assert resposta["Cache-Control"] == "no-store", (
        "a tela pode ser guardada pelo navegador e reexibida velha — e uma "
        "tela velha desta área é indistinguível de uma tela certa"
    )


def test_a_recusa_tambem_nao_fica_guardada():
    """Recusa guardada é pior que tela guardada.

    O 302 para o login e o 404 de quem não está na lista sobrevivendo no cache
    trancariam o dono para fora depois que o acesso dele fosse consertado.
    """
    assert Client().get("/")["Cache-Control"] == "no-store"


@respx.mock
def test_quem_manda_o_proprio_cache_continua_mandando():
    """`setdefault`, e não atribuição — senão a correção atropelaria o mapa-ia.

    `/mapa-ia/` e `/mapa-ia/planos/` mandam `public, max-age=300` de propósito:
    são texto público que uma IA de fora lê, e reler o mesmo texto a cada
    pedido é gasto sem ganho. Sem este guarda, um `resposta["Cache-Control"]`
    no lugar do `setdefault` apagaria essa decisão sem nada ficar vermelho.
    """
    resposta = Client().get("/mapa-ia/")
    assert resposta.status_code == 200, resposta.content
    assert resposta["Cache-Control"] == "public, max-age=300"
