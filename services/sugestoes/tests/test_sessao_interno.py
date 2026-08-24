"""A superfície de máquina da Caixa: "quem é o dono desta sessão?" (EVO/`funil`).

Lei do assunto: `docs/decisoes/DECISAO-onde-mora-a-sessao.md`. Estes guardas
travam a parte que é fácil de quebrar sem perceber: **as duas perguntas que se
cruzam neste endpoint têm códigos de resposta diferentes**.

| Pergunta | Prova | Falha |
|---|---|---|
| quem CHAMA? | Bearer do par | 401 |
| quem é a PESSOA? | cookie repassado | 200 com `autenticado: false` |

Toda sessão aqui é aberta pela PORTA de verdade (`entrar_como`), nunca por
cookie assinado à mão: uma sessão fabricada continuaria verde no dia em que o
login parar de funcionar, e aí o guarda mede outra coisa.
"""

import pytest

from tests.conftest import perfil_google

TOKEN = "token-do-par-funil-sugestoes"
STAFF = "moderacao@exemplo.test"
CAMINHO = "/interno/sessao"


@pytest.fixture
def par_autorizado(settings):
    """O token do par consumidor→provedor, como o env real o forneceria.

    Vai por `settings` e não por `monkeypatch.setenv`: `TOKENS_ACEITOS` é
    derivado do ambiente **no import** de `config/settings.py`, que já
    aconteceu quando o teste roda — mexer no env agora não mudaria nada, e o
    guarda passaria a medir o default em vez do que ele pensa que mede.
    """
    settings.TOKENS_ACEITOS = {TOKEN}
    return TOKEN


def _perguntar(client, token: "str | None" = TOKEN):
    cabecalhos = {"authorization": f"Bearer {token}"} if token else {}
    return client.get(CAMINHO, headers=cabecalhos)


# ---------------------------------------------------------------------------
# Quem CHAMA: sem o token do par, a porta de máquina não abre — 401.
# ---------------------------------------------------------------------------
def test_sem_token_do_par_e_401(client, db, par_autorizado):
    assert _perguntar(client, token=None).status_code == 401


def test_token_errado_e_401(client, db, par_autorizado):
    assert _perguntar(client, token="token-de-outro-alguem").status_code == 401


def test_sem_nenhum_token_configurado_tudo_e_401(client, db, settings):
    """Env ausente ⇒ conjunto vazio ⇒ ninguém entra. Fail-closed por construção.

    É o estado em que a célula sobe antes de o token existir no servidor: as
    páginas continuam servindo e só a API interna fica fechada. O oposto —
    conjunto vazio aceitando qualquer um — seria a falha silenciosa clássica.
    """
    settings.TOKENS_ACEITOS = set()
    assert _perguntar(client, token=TOKEN).status_code == 401


# ---------------------------------------------------------------------------
# Quem é a PESSOA: visitante é resposta de SUCESSO, não erro.
# ---------------------------------------------------------------------------
def test_visitante_sem_sessao_e_200_dizendo_que_nao_ha_ninguem(
    client, db, par_autorizado
):
    """200, e não 401/404.

    Se "ninguém entrou ainda" respondesse 401, o `funil` não teria como
    distinguir isso de "a Caixa recusou a minha credencial" — e a primeira
    coisa que alguém faria para "consertar" seria afrouxar o token.
    """
    resposta = _perguntar(client)
    assert resposta.status_code == 200, resposta.content
    assert resposta.json() == {"autenticado": False}


def test_pessoa_logada_volta_id_e_nome(entrar_como, par_autorizado):
    pessoa = entrar_como(email="joao.silva@exemplo.test", nome="João")

    corpo = _perguntar(pessoa.client).json()

    assert corpo["autenticado"] is True
    assert corpo["id"] == pessoa.identidade.id
    assert corpo["nome_exibido"] == "João"
    assert corpo["papel"] == "aluno"


def test_depois_de_sair_volta_a_ser_visitante(entrar_como, par_autorizado):
    """O outro lado do login, e o que prova que a resposta lê a sessão VIVA."""
    pessoa = entrar_como()
    assert _perguntar(pessoa.client).json()["autenticado"] is True

    pessoa.client.post("/sair")

    assert _perguntar(pessoa.client).json() == {"autenticado": False}


# ---------------------------------------------------------------------------
# O papel é DERIVADO a cada requisição (EVO-01 §4) — nunca gravado.
# ---------------------------------------------------------------------------
def test_staff_e_reconhecido_pelo_papel(entrar_como, par_autorizado, monkeypatch, rede):
    monkeypatch.setenv("SUGESTOES_STAFF_EMAILS", STAFF)
    rede.alunos_nao_conhece(STAFF)
    pessoa = entrar_como(email=STAFF, nome="Moderação")

    assert _perguntar(pessoa.client).json()["papel"] == "staff"


def test_tirar_da_lista_tira_o_cracha_sem_novo_login(
    entrar_como, par_autorizado, monkeypatch, rede
):
    """A promessa da EVO-01 §4, medida do lado de fora.

    "Trocar quem é staff = editar uma variável e reiniciar a célula." Se o
    papel fosse gravado no cookie ou na linha da `Identidade`, quem já estava
    dentro continuaria staff — e a promessa quebraria em silêncio, que é o
    pior jeito de uma promessa quebrar.
    """
    monkeypatch.setenv("SUGESTOES_STAFF_EMAILS", STAFF)
    rede.alunos_nao_conhece(STAFF)
    pessoa = entrar_como(email=STAFF, nome="Moderação")
    assert _perguntar(pessoa.client).json()["papel"] == "staff"

    monkeypatch.setenv("SUGESTOES_STAFF_EMAILS", "")

    # MESMA sessão, MESMO cookie — só a variável mudou.
    assert _perguntar(pessoa.client).json()["papel"] == "aluno"


# ---------------------------------------------------------------------------
# Identidade apagada ⇒ o cookie deixa de valer no mesmo instante.
# ---------------------------------------------------------------------------
def test_identidade_apagada_derruba_a_resposta(entrar_como, par_autorizado):
    """`ator_atual` reconfere no banco a cada requisição, de propósito.

    Um cookie assinado sobrevive à linha que ele aponta; sem a reconferência,
    apagar alguém não tiraria essa pessoa de dentro.
    """
    pessoa = entrar_como()
    pessoa.identidade.delete()

    assert _perguntar(pessoa.client).json() == {"autenticado": False}


# ---------------------------------------------------------------------------
# O cookie tem ALCANCE DE SITE — é o motivo de tudo isto existir.
# ---------------------------------------------------------------------------
def test_o_cookie_de_sessao_sai_com_o_nome_e_o_tratamento_certos(
    porta, perfil, rede, matricula
):
    """O que dá para medir do lado de fora, em dev: nome novo e tratamento.

    **O CAMINHO do cookie NÃO se prova aqui** — em dev não há `SCRIPT_NAME`, e
    a linha ANTIGA (`FORCE_SCRIPT_NAME or "/"`) também daria `/`. Um assert de
    `path == "/"` neste teste ficaria verde com e sem a correção, ou seja não
    provaria nada (RETROSPECTIVA §1: portão que nunca foi visto reprovando é
    portão que ninguém sabe se reprova). Quem mede o caminho é o teste abaixo,
    que carrega o settings COM o prefixo de produção.
    """
    email = "joao.silva@exemplo.test"
    rede.alunos_diz(email, [matricula])

    porta.bater(perfil(email))

    assert porta.client.cookies.get("sugestoes_sessao") is None  # o nome velho morreu
    cookie = porta.client.cookies["meshcraft_sessao"]
    assert cookie["httponly"]
    # `Lax` é o que faz a volta do Google funcionar — `Strict` mataria todo login.
    assert cookie["samesite"] == "Lax"


def _settings_como_na_vps(monkeypatch):
    """Carrega `config/settings.py` COMO A VPS o carrega: com `SCRIPT_NAME`.

    Módulo NOVO, com nome próprio, via `importlib.util` — nunca `reload` do
    `config.settings` de verdade: o `django.conf.settings` desta suíte aponta
    para aquele objeto, e recarregá-lo trocaria a configuração viva no meio dos
    outros testes (falha que só apareceria como teste vizinho quebrando por
    ordem de execução).
    """
    import importlib.util
    from pathlib import Path

    monkeypatch.setenv("SCRIPT_NAME", "/forms/sugestoes")
    caminho = Path(__file__).resolve().parent.parent / "config" / "settings.py"
    spec = importlib.util.spec_from_file_location("settings_sob_prefixo", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_em_producao_a_sessao_vale_no_site_e_o_csrf_so_na_caixa(monkeypatch):
    """O coração da DECISAO-onde-mora-a-sessao, medido no regime que importa.

    Com `SCRIPT_NAME=/forms/sugestoes` — o env REAL da VPS — a linha antiga
    (`SESSION_COOKIE_PATH = FORCE_SCRIPT_NAME or "/"`) devolvia
    `/forms/sugestoes`, e era por isso que o site não sabia quem a pessoa era:
    o navegador não mandava o cookie para `/pt-br/qualquer-coisa`.

    **Este teste reprova se alguém devolver aquela linha ao lugar** — que é a
    única coisa que um guarda de configuração precisa fazer.

    O CSRF fica de fora de propósito: a sessão precisa de alcance de site, o
    token de CSRF protege os `<form>` desta célula, que vivem sob o prefixo
    dela. As duas linhas andavam juntas por acidente de escrita até 24/08/2026;
    divergem por decisão, e este assert impede que alguém as reunifique "para
    ficar consistente".
    """
    producao = _settings_como_na_vps(monkeypatch)

    assert producao.FORCE_SCRIPT_NAME == "/forms/sugestoes"  # sanidade do cenário
    assert producao.SESSION_COOKIE_PATH == "/"
    assert producao.CSRF_COOKIE_PATH == "/forms/sugestoes"
    assert producao.SESSION_COOKIE_NAME == "meshcraft_sessao"
