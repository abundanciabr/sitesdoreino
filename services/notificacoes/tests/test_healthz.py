"""`/healthz` responde 200 — e a célula só publica o que o Rito autorizou.

Até a Fase 4 do sininho, a superfície pública inteira desta célula era
`/healthz`: a gênese nasceu sem tela e sem contrato por lei
(`DECISAO-notificacoes` §1.1 — `freeze: not-applicable`, contrato só quando
alguém fosse consumir), e este arquivo reprovava qualquer rota nova como
fronteira fabricada dentro de um despacho.

A Fase 4 (`contracts/notificacoes.openapi.yaml`, Rito de Contrato de
27/08/2026, PR #274) MUDOU essa fronteira — e o guarda muda JUNTO, para
continuar medindo alguma coisa: agora ele prova que a célula publica
EXATAMENTE o que o Rito autorizou, nem uma rota a mais. Isto não é o guarda
enfraquecido, é o guarda reapontado (mesmo espírito da nota em
`DECISAO-notificacoes` §2 sobre o guarda do `Aviso` transacional): continuar
exigindo só `/healthz` estaria exigindo a arquitetura de ANTES do Rito, que o
mantenedor decidiu não ter mais.
"""

from django.urls import get_resolver


def test_healthz_responde_ok(client):
    resposta = client.get("/healthz")

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}


def test_a_celula_so_publica_o_que_o_rito_autorizou():
    rotas = sorted(str(p.pattern) for p in get_resolver().url_patterns)

    assert rotas == ["api/notificacoes/", "healthz"], (
        f"a superfície publicada é {rotas}. `healthz` é a sonda de sempre; "
        "`api/notificacoes/` é a porta de consulta da Fase 4 (`/resumo`, "
        "`/avisos`, `/marcar-lidas` — RITOS §3). Rota além dessas duas é "
        "fronteira fabricada dentro de um despacho."
    )
