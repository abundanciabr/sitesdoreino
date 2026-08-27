"""`/healthz` responde 200 — e é a ÚNICA rota que esta célula publica.

A segunda metade não é zelo: a célula nasce sem tela e sem superfície de máquina
por lei (`DECISAO-notificacoes` §1.1 — `freeze: not-applicable`, contrato só
quando alguém for consumir). Uma rota que aparecesse aqui antes da Fase 4 seria
fronteira fabricada dentro de um despacho, e o congelamento de contrato deixaria
de significar alguma coisa.
"""

import pytest
from django.urls import get_resolver


def test_healthz_responde_ok(client):
    resposta = client.get("/healthz")

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}


def test_a_celula_nao_publica_nenhuma_outra_rota():
    rotas = sorted(str(p.pattern) for p in get_resolver().url_patterns)

    assert rotas == ["healthz"], (
        f"apareceu rota nova nesta célula: {rotas}. Superfície pública aqui é "
        "Fase 4 do PLANO-MESTRE, e Fase 4 é Rito de Contrato (RITOS §3)."
    )
