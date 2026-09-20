"""Cartas de exemplo dos contratos de pagamento sem nome de fornecedor.

Uma carta VALIDA e uma carta INVALIDA para cada schema novo. A invalida nunca
erra por acaso: cada uma quebra exatamente a lei que o schema existe para fazer
valer, e o teste ao lado (`test_pagamento_sem_nome_de_fornecedor.py`) reprova se
o schema deixar qualquer uma delas passar.

POR QUE UM MODULO PYTHON E NAO ARQUIVOS .json SOLTOS: `ci/contrato_aditivo.py`
lê TODO arquivo `.json` ou `.yaml` dentro de `contracts/` como contrato, e
decide pelo caminho se é evento (JSON Schema, precisa da chave `properties`) ou
API (OpenAPI, precisa da chave `paths`). Uma carta de exemplo não tem nem uma
nem outra, então ela passaria despercebida enquanto fosse arquivo novo e viraria
ERROR do portão na primeira vez que alguém a editasse. Em Python as cartas ficam
legíveis, versionadas junto do schema e fora do alcance desse engano.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# pagamento.aprovado.v2
# ---------------------------------------------------------------------------

APROVADO_V2_VALIDA: dict = {
    "event": "pagamento.aprovado",
    "version": 2,
    "event_id": "7c9d2f3a-1b4e-4c8a-9f21-5d6e7a8b9c01",
    "occurred_at": "2026-09-20T18:42:11Z",
    "data": {
        "platform_site_id": "meshcraft",
        "payment_id": "pay_01H9Z3",
        "order_id": "ord_01H9Z2",
        "amount_cents": 19700,
        "method": "card",
        "provider": "appmax",
        "provider_reference_id": "4471230",
        "product_id": "curso-fundamentos",
        "customer": {
            "email": "aluno@example.com",
            "name": "Maria de Souza",
            "phone": "+5596981000000",
        },
    },
}

#: Quebra as duas leis centrais do v2 de uma vez: volta a carregar o nome do
#: fornecedor no campo (`mp_payment_id`) e não traz o par neutro que substitui
#: esse nome. `additionalProperties: false` recusa o campo velho e `required`
#: recusa a ausência do par.
APROVADO_V2_INVALIDA: dict = {
    "event": "pagamento.aprovado",
    "version": 2,
    "event_id": "7c9d2f3a-1b4e-4c8a-9f21-5d6e7a8b9c02",
    "occurred_at": "2026-09-20T18:42:11Z",
    "data": {
        "platform_site_id": "meshcraft",
        "payment_id": "pay_01H9Z3",
        "order_id": "ord_01H9Z2",
        "amount_cents": 19700,
        "method": "card",
        "mp_payment_id": "123456789",
        "customer": {"email": "aluno@example.com", "name": "Maria de Souza"},
    },
}

# ---------------------------------------------------------------------------
# pagamento.recusado.v2
# ---------------------------------------------------------------------------

RECUSADO_V2_VALIDA: dict = {
    "event": "pagamento.recusado",
    "version": 2,
    "event_id": "b1e5c7d9-2a3f-4b6c-8d90-1e2f3a4b5c06",
    "occurred_at": "2026-09-20T18:45:02Z",
    "data": {
        "platform_site_id": "meshcraft",
        "payment_id": "pay_01H9Z7",
        "order_id": "ord_01H9Z6",
        "amount_cents": 19700,
        "method": "card",
        "provider": "mercadopago",
        "provider_reference_id": "987654321",
        "reason_code": "cc_rejected_insufficient_amount",
        "customer": {"email": "aluno@example.com", "name": "Maria de Souza"},
    },
}

#: Um provedor que a plataforma não conhece. O enum fechado é o que impede um
#: quarto fornecedor de entrar no fio sem passar pelo Rito de Contrato, e sem
#: ele a chave de deduplicação dos consumidores deixaria de ser única.
RECUSADO_V2_INVALIDA: dict = {
    "event": "pagamento.recusado",
    "version": 2,
    "event_id": "b1e5c7d9-2a3f-4b6c-8d90-1e2f3a4b5c07",
    "occurred_at": "2026-09-20T18:45:02Z",
    "data": {
        "platform_site_id": "meshcraft",
        "payment_id": "pay_01H9Z7",
        "order_id": "ord_01H9Z6",
        "amount_cents": 19700,
        "method": "card",
        "provider": "stripe",
        "provider_reference_id": "987654321",
        "reason_code": "cc_rejected_insufficient_amount",
        "customer": {"email": "aluno@example.com", "name": "Maria de Souza"},
    },
}

# ---------------------------------------------------------------------------
# pagamento.estornado.v2
# ---------------------------------------------------------------------------

ESTORNADO_V2_VALIDA: dict = {
    "event": "pagamento.estornado",
    "version": 2,
    "event_id": "c2f6d8e0-3b4a-4c7d-9e01-2f3a4b5c6d08",
    "occurred_at": "2026-09-21T09:12:40Z",
    "data": {
        "platform_site_id": "meshcraft",
        "provider": "appmax",
        "provider_reference_id": "4471230",
        "motivo": "contestacao",
        "amount_cents": 19700,
    },
}

#: Dinheiro em reais fracionados e um motivo que não existe. As duas coisas são
#: o mesmo erro de fundo: tratar como texto livre o que decide se o acesso do
#: aluno cai. `amount_cents` é inteiro em centavos em todo contrato desta
#: plataforma (contracts/README.md, ponto 7).
ESTORNADO_V2_INVALIDA: dict = {
    "event": "pagamento.estornado",
    "version": 2,
    "event_id": "c2f6d8e0-3b4a-4c7d-9e01-2f3a4b5c6d09",
    "occurred_at": "2026-09-21T09:12:40Z",
    "data": {
        "platform_site_id": "meshcraft",
        "provider": "appmax",
        "provider_reference_id": "4471230",
        "motivo": "arrependimento",
        "amount_cents": 197.00,
    },
}

# ---------------------------------------------------------------------------
# Confirmação de cartão: a pública (checkout) e a interna (pagamentos)
# ---------------------------------------------------------------------------

CARTAO_VALIDA: dict = {
    "token": "tok_appmax_9f31c0a4",
    "ip": "191.53.14.202",
    "holder_name": "MARIA DE SOUZA",
    "holder_document_number": "39053344705",
    "installments": 3,
}

#: O navegador mandando dinheiro. É o erro que INV-P2 existe para impedir: total
#: e produto vêm do snapshot congelado no servidor, nunca da página. A carta
#: também omite o `ip`, que a Appmax exige para criar o cliente e que só o
#: Appmax JS consegue coletar.
CARTAO_INVALIDA: dict = {
    "token": "tok_appmax_9f31c0a4",
    "holder_name": "MARIA DE SOUZA",
    "holder_document_number": "39053344705",
    "installments": 3,
    "amount_cents": 100,
    "product_id": "curso-fundamentos",
}
