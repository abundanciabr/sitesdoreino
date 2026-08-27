"""Fixtures da caixa central de avisos.

**Nada aqui toca a rede** — esta célula não fala com ninguém: ela ouve o fio e
escreve no próprio banco. O consumidor é exercitado com um Redis DUBLADO (um
objeto em memória com a superfície que a receita R4 usa), porque o que os
guardas medem é a decisão do consumidor, não o Redis.

Desde a Fase 4 do sininho (`contracts/notificacoes.openapi.yaml`) esta célula
também tem uma porta HTTP — as fixtures `TOKEN_DO_PAR`/`par_autorizado` e o
helper `schema_da_resposta` servem os testes dela (`tests/test_api_*.py`,
`tests/test_volume_da_api.py`).
"""

import uuid
from pathlib import Path

import pytest
import yaml

SITE = "site-de-teste"
ALGUEM = "idt-pessoa-1"
OUTRA = "idt-pessoa-2"
EQUIPE = "idt-alguem-da-equipe"

# Um token de par qualquer — a autenticação (`apps/core/auth.py`) não distingue
# QUAL par (`TOKENS_ACEITOS_FUNIL` vs `TOKENS_ACEITOS_SUGESTOES`), só se o
# valor está no conjunto. Testar os dois pares seria testar a mesma linha de
# código duas vezes.
TOKEN_DO_PAR = "token-do-par-de-teste"

CONTRATO_HTTP = (
    Path(__file__).resolve().parents[3] / "contracts" / "notificacoes.openapi.yaml"
)


@pytest.fixture
def par_autorizado(settings):
    """O token do par, como o env real o forneceria (`TOKENS_ACEITOS_<PAR>`).

    Vai por `settings` e não por `monkeypatch.setenv`: `TOKENS_ACEITOS` é
    derivado do ambiente NO IMPORT de `config/settings.py`, que já aconteceu
    quando o teste roda.
    """
    settings.TOKENS_ACEITOS = {TOKEN_DO_PAR}
    return TOKEN_DO_PAR


def cabecalho_bearer(token: "str | None" = TOKEN_DO_PAR) -> dict:
    return {"authorization": f"Bearer {token}"} if token else {}


def schema_da_resposta(caminho: str, metodo: str, status: str) -> dict:
    """O schema JSON de uma resposta, lido do contrato CONGELADO — nunca
    copiado para dentro do teste (mesma regra do guarda irmão de eventos,
    `test_inv_carta_casa_com_o_contrato.py`): uma cópia aqui seria uma segunda
    verdade sobre o contrato, envelhecendo no próprio ritmo.
    """
    assert CONTRATO_HTTP.exists(), (
        f"o contrato não está em {CONTRATO_HTTP} — sem ele este teste passaria "
        "no vazio, que é o modo de falha que [INV-CI01] existe para matar"
    )
    doc = yaml.safe_load(CONTRATO_HTTP.read_text(encoding="utf-8"))
    operacao = doc["paths"][caminho][metodo]["responses"][status]
    return operacao["content"]["application/json"]["schema"]


def envelope_de_carta(
    *, destinatario_id=ALGUEM, ator_id=EQUIPE, site_id=SITE, origem=None, **parametros
):
    """Um `notificacao.devida.v1` como o relay da Caixa o publica.

    Montado à mão de propósito: o guarda que confere que ele CASA com o contrato
    congelado é `test_inv_carta_casa_com_o_contrato.py`, que lê o schema do
    arquivo. Se esta fixture derivar do contrato, as duas coisas passam a ser a
    mesma e o guarda deixa de medir alguma coisa.
    """
    return {
        "event": "notificacao.devida",
        "version": 1,
        "event_id": str(uuid.uuid4()),
        "occurred_at": "2026-08-26T22:00:00+00:00",
        "ator_id": ator_id,
        "data": {
            "site_id": site_id,
            "destinatario_id": destinatario_id,
            "assunto": "sugestao.status-alterado",
            "parametros": parametros
            or {
                "suggestion_id": "731",
                "status_anterior": "em_analise",
                "status_novo": "planejado",
            },
            "origem_event_id": origem or str(uuid.uuid4()),
        },
    }


@pytest.fixture
def carta():
    return envelope_de_carta
