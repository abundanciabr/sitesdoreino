"""A superfície de máquina da Caixa — DEPRECADA E INERTE, e provada assim.

Desde a `DECISAO-celula-de-identidade` (25/08/2026) quem responde "quem é o
dono desta sessão?" ao site é a célula `identidade`. Esta operação congelada
(`getSession`) continua existindo porque contrato só muda pelo Rito §3 (a
remoção é dívida registrada) — e continua respondendo pelas DUAS metades que
sempre teve:

| Pergunta | Prova | Falha |
|---|---|---|
| quem CHAMA? | Bearer do par | 401 |
| quem é a PESSOA? | a sessão LEGADA desta célula | 200 `autenticado: false` |

A diferença é a segunda metade: nenhum cookie novo é assinado por esta célula
desde a virada, então a resposta real é sempre "ninguém" — inclusive para quem
está LOGADO NO SITE (o cookie central falha a assinatura legada aqui). É isso
que estes guardas provam agora: o endpoint não mente, não ricocheteia a
pergunta para a `identidade` e não deixa a porta de máquina destrancada.
"""

import pytest

from tests.conftest import sessao_do_site

TOKEN = "token-do-par-funil-sugestoes"
CAMINHO = "/interno/sessao"


@pytest.fixture
def par_autorizado(settings):
    """O token do par, como o env real o forneceria.

    Vai por `settings` e não por `monkeypatch.setenv`: `TOKENS_ACEITOS` é
    derivado do ambiente **no import** de `config/settings.py`, que já
    aconteceu quando o teste roda.
    """
    settings.TOKENS_ACEITOS = {TOKEN}
    return TOKEN


def _perguntar(client, token: "str | None" = TOKEN):
    cabecalhos = {"authorization": f"Bearer {token}"} if token else {}
    return client.get(CAMINHO, headers=cabecalhos)


# ---------------------------------------------------------------------------
# Quem CHAMA: a porta de máquina continua trancada — 401 sem o par.
# ---------------------------------------------------------------------------
def test_sem_token_do_par_e_401(client, db, par_autorizado):
    assert _perguntar(client, token=None).status_code == 401


def test_token_errado_e_401(client, db, par_autorizado):
    assert _perguntar(client, token="token-de-outro-alguem").status_code == 401


def test_sem_nenhum_token_configurado_tudo_e_401(client, db, settings):
    settings.TOKENS_ACEITOS = set()
    assert _perguntar(client, token=TOKEN).status_code == 401


# ---------------------------------------------------------------------------
# Quem é a PESSOA: a resposta legada é sempre "ninguém" — e isso é o correto.
# ---------------------------------------------------------------------------
def test_visitante_sem_sessao_e_200_dizendo_que_nao_ha_ninguem(
    client, db, par_autorizado
):
    resposta = _perguntar(client)
    assert resposta.status_code == 200, resposta.content
    assert resposta.json() == {"autenticado": False}


def test_a_sessao_do_site_nao_e_lida_aqui(rede, db, matricula, par_autorizado):
    """Quem está logado NO SITE é 'ninguém' para o endpoint legado.

    Duas coisas numa tacada: (1) o cookie central não valida na assinatura
    legada — inerte como a lei manda; (2) a pergunta NÃO é encaminhada à
    `identidade` — o respx estouraria numa chamada não registrada ao
    `/sessao/completa`? Não: ela ESTÁ registrada. A prova do não-ricochete é
    a resposta: quem ricocheteasse responderia `autenticado: true`.
    """
    rede.alunos_diz("joao.silva@exemplo.test", [matricula])
    pessoa = sessao_do_site(rede, email="joao.silva@exemplo.test")
    assert pessoa.esta_dentro  # a pessoa participa normalmente da Caixa…

    resposta = _perguntar(pessoa.client)

    # …e mesmo assim a operação legada diz "ninguém": ela responde pela
    # sessão que ESTA célula assinava, e essa não existe mais.
    assert resposta.json() == {"autenticado": False}
