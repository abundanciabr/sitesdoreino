"""A superfície de máquina: "quem é o dono desta sessão?" (getSession).

Herdeiros diretos dos guardas homônimos da Caixa. O que eles travam é a parte
fácil de quebrar sem perceber: **as duas perguntas que se cruzam neste
endpoint têm códigos de resposta diferentes**.

| Pergunta | Prova | Falha |
|---|---|---|
| quem CHAMA? | Bearer do par | 401 |
| quem é a PESSOA? | cookie repassado | 200 com `autenticado: false` |

Toda sessão aqui é aberta pela PORTA de verdade (`entrar_como`), nunca por
cookie assinado à mão: uma sessão fabricada continuaria verde no dia em que o
login parar de funcionar, e aí o guarda mede outra coisa.
"""

import pytest

TOKEN = "token-do-par-funil-identidade"
CAMINHO = "/interno/sessao"


@pytest.fixture
def par_autorizado(settings):
    """O token do par consumidor→provedor, como o env real o forneceria.

    Vai por `settings` e não por `monkeypatch.setenv`: `TOKENS_ACEITOS` é
    derivado do ambiente **no import** de `config/settings.py`, que já
    aconteceu quando o teste roda — mexer no env agora não mudaria nada.
    """
    settings.TOKENS_ACEITOS = {TOKEN}
    return TOKEN


def _perguntar(client, token: "str | None" = TOKEN, caminho: str = CAMINHO):
    cabecalhos = {"authorization": f"Bearer {token}"} if token else {}
    return client.get(caminho, headers=cabecalhos)


# ---------------------------------------------------------------------------
# Quem CHAMA: sem o token do par, a porta de máquina não abre — 401.
# ---------------------------------------------------------------------------
def test_sem_token_do_par_e_401(client, db, par_autorizado):
    assert _perguntar(client, token=None).status_code == 401


def test_token_errado_e_401(client, db, par_autorizado):
    assert _perguntar(client, token="token-de-outro-alguem").status_code == 401


def test_sem_nenhum_token_configurado_tudo_e_401(client, db, settings):
    """Env ausente ⇒ conjunto vazio ⇒ ninguém entra. Fail-closed por construção."""
    settings.TOKENS_ACEITOS = set()
    assert _perguntar(client, token=TOKEN).status_code == 401


# ---------------------------------------------------------------------------
# Quem é a PESSOA: visitante é resposta de SUCESSO, não erro.
# ---------------------------------------------------------------------------
def test_visitante_sem_sessao_e_200_dizendo_que_nao_ha_ninguem(
    client, db, par_autorizado
):
    resposta = _perguntar(client)
    assert resposta.status_code == 200, resposta.content
    assert resposta.json() == {"autenticado": False}


def test_quem_entrou_pela_porta_e_reconhecido(dentro, par_autorizado):
    resposta = _perguntar(dentro.client)
    assert resposta.status_code == 200, resposta.content
    corpo = resposta.json()
    assert corpo["autenticado"] is True
    assert corpo["id"] == dentro.identidade.id
    assert corpo["nome_exibido"] == "João"
    assert corpo["papel"] == "aluno"


def test_depois_de_sair_a_resposta_volta_a_ser_ninguem(dentro, par_autorizado):
    saida = dentro.client.post("/entrar/sair", HTTP_ORIGIN="http://testserver")
    assert saida.status_code == 302, saida.content
    assert _perguntar(dentro.client).json() == {"autenticado": False}
