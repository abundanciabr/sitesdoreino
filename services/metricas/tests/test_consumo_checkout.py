"""Teste-guarda: a metricas assina os dois eventos de compra do checkout.

O que estes guardas protegem (F10b, DESENHO-COMUM.md — sistema de
experimentos, sessão de 26/09/2026):

1. **Os dois assuntos estão em `STREAMS`**, e são exatamente
   `checkout.pedido-atribuido` e `checkout.pedido-pago` (contrato F4a).
2. **Um envelope bom de cada um vira fato**, guardado pelo mesmo caminho
   (`processar` -> `recepcao.receber`) que qualquer outro assunto da casa.
3. **Reentrega não duplica**: o mesmo `event_id` processado duas vezes conta
   uma fato só.
4. **Payload com dado pessoal nunca entra no livro.** DESENHO-COMUM.md é
   taxativo: os dois eventos de compra NUNCA levam `customer`, e-mail, nome,
   telefone ou documento. Se um deles aparecer em `data`, o envelope vira
   `EventoMorto` (a fila que o painel mostra), nunca um `Evento` (o livro é
   append-only e não se corrige depois — armadilhas/lei da imutabilidade).
5. **O guarda é do checkout, não da casa inteira**: os mesmos nomes de campo
   continuam livres em qualquer outro assunto, porque `recepcao.receber` não
   valida miolo por desenho (quem valida é quem publica) — só os dois
   eventos de compra do checkout têm essa exceção.
"""

from __future__ import annotations

import json
import uuid

import pytest

from apps.fatos.management.commands.consume_eventos import (
    EVENTOS_DE_COMPRA_DO_CHECKOUT,
    STREAMS,
    processar,
)
from apps.fatos.models import Evento, EventoMorto
from apps.fatos.recepcao import GUARDADO, JA_TINHA, MORTO

pytestmark = pytest.mark.django_db

CRIADO_EM = "2026-09-26T18:00:00+00:00"
PAGO_EM = "2026-09-26T18:05:00+00:00"


def envelope_pedido_atribuido(**sobre_dados) -> str:
    dados = {
        "site_id": "meshcraft",
        "order_id": "pedido-1",
        "checkout_session_id": "sessao-1",
        "visitor_id": "visitante-1",
        "produto": "curso-x",
        "valor_centavos": 19700,
        "moeda": "BRL",
        "criado_em": CRIADO_EM,
    }
    dados.update(sobre_dados)
    corpo = {
        "event": "checkout.pedido-atribuido",
        "version": 1,
        "event_id": str(uuid.uuid4()),
        "occurred_at": CRIADO_EM,
        "data": dados,
    }
    return json.dumps(corpo)


def envelope_pedido_pago(**sobre_dados) -> str:
    dados = {
        "site_id": "meshcraft",
        "order_id": "pedido-1",
        "visitor_id": "visitante-1",
        "valor_centavos": 19700,
        "moeda": "BRL",
        "pago_em": PAGO_EM,
    }
    dados.update(sobre_dados)
    corpo = {
        "event": "checkout.pedido-pago",
        "version": 1,
        "event_id": str(uuid.uuid4()),
        "occurred_at": PAGO_EM,
        "data": dados,
    }
    return json.dumps(corpo)


def test_os_dois_assuntos_de_compra_estao_assinados():
    assert "eventos.checkout.pedido-atribuido" in STREAMS
    assert "eventos.checkout.pedido-pago" in STREAMS
    assert EVENTOS_DE_COMPRA_DO_CHECKOUT == {
        "checkout.pedido-atribuido",
        "checkout.pedido-pago",
    }


@pytest.mark.parametrize(
    "fabricar, tipo",
    [
        (envelope_pedido_atribuido, "checkout.pedido-atribuido"),
        (envelope_pedido_pago, "checkout.pedido-pago"),
    ],
)
def test_envelope_bom_de_cada_evento_de_compra_vira_fato(fabricar, tipo):
    desfecho = processar(fabricar())
    assert desfecho == GUARDADO
    evento = Evento.objects.get(tipo=tipo)
    assert evento.site_id == "meshcraft"
    assert evento.dados["order_id"] == "pedido-1"
    assert EventoMorto.objects.count() == 0


@pytest.mark.parametrize("fabricar", [envelope_pedido_atribuido, envelope_pedido_pago])
def test_reentrega_do_mesmo_evento_de_compra_nao_duplica(fabricar):
    corpo = fabricar()
    assert processar(corpo) == GUARDADO
    assert processar(corpo) == JA_TINHA
    assert Evento.objects.count() == 1


@pytest.mark.parametrize("fabricar", [envelope_pedido_atribuido, envelope_pedido_pago])
@pytest.mark.parametrize(
    "chave, valor",
    [
        ("customer", {"nome": "Fulano"}),
        ("email", "fulano@exemplo.com"),
        ("nome", "Fulano de Tal"),
        ("telefone", "+55 11 90000-0000"),
        ("documento", "000.000.000-00"),
    ],
)
def test_payload_com_campo_pessoal_vira_evento_morto_nunca_livro(
    fabricar, chave, valor
):
    desfecho = processar(fabricar(**{chave: valor}))
    assert desfecho == MORTO
    assert Evento.objects.count() == 0, "dado pessoal nunca entra no livro"
    morto = EventoMorto.objects.get()
    assert chave in morto.motivo
    assert morto.estado == EventoMorto.Estado.NOVO


def test_o_guarda_de_dado_pessoal_e_so_do_checkout():
    """O mesmo campo continua livre em outro assunto: a exceção é do checkout."""
    corpo = json.dumps(
        {
            "event": "identidade.pessoa-cadastrada",
            "version": 1,
            "event_id": str(uuid.uuid4()),
            "occurred_at": CRIADO_EM,
            "data": {"site_id": "meshcraft", "email": "fulano@exemplo.com"},
        }
    )
    assert processar(corpo) == GUARDADO
    assert EventoMorto.objects.count() == 0
