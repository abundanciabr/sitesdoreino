# tests/test_estorno_suspende_a_matricula.py
"""O dinheiro voltou, o acesso fecha na hora.

`contracts/eventos/pagamento.estornado.v2.json`, congelado no Rito de Contrato
de 20/09/2026 com o mantenedor presente. A decisão dele naquele dia: **estorno e
contestação cortam o acesso do aluno na hora, sem distinção entre os dois**. O
que difere entre os dois motivos é o que a plataforma faz DEPOIS (contestação
tem prazo de defesa), e isso não é assunto desta célula.

**Por que `suspensa` e não `reembolsada`.** Os dois estados existem e os dois
tiram o acesso, então a escolha é real e precisa estar escrita. `reembolsada`
carrega uma segunda decisão junto: quem está nela não pede para voltar pela
fila (`STATUS_QUE_BARRAM_A_FILA`, `DECISAO-reembolso-tira-o-acesso.md`).
`suspensa` é exatamente o que o mantenedor pediu aqui: o acesso fecha, a ficha
fica inteira e **reabrir é decisão humana** — o painel religa a pessoa com um
clique. Quem quiser trocar isto por `reembolsada` está mudando a lei do que o
estorno significa, e isso é decisão dele, não de um despacho.

**O que este arquivo mede, e que nenhum outro mede sozinho:**

1. estorno suspende, e contestação suspende igual;
2. a reentrega do mesmo fato suspende UMA vez — pelo `event_id` repetido, pela
   identidade lógica do fato e pela chamada direta do serviço;
3. a suspensão não apaga nada da ficha, e o painel consegue reabrir;
4. uma aprovação que chegue DEPOIS do estorno não devolve o acesso sozinha;
5. estorno de um pagamento que não matriculou ninguém não derruba o consumidor.

O §6 fecha os dois modos de falha silenciosa do casamento entre o evento e a
matrícula: o escopo por site ([INV-P11]) e a referência vazia, que casaria com
toda matrícula nascida antes deste par existir.
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from pathlib import Path

import jsonschema
import pytest

from apps.eventos.management.commands.consume_eventos import (
    HANDLERS,
    processar_envelope,
)
from apps.eventos.models import EventoProcessado
from apps.matriculas.eventos import SITUACAO_ALTERADA
from apps.matriculas.models import Matricula, OutboxEvent
from apps.matriculas.services import (
    atualizar_matricula,
    matriculas_que_valem,
    suspender_por_estorno,
)

pytestmark = pytest.mark.django_db

CONTRATOS = Path(__file__).resolve().parents[3] / "contracts" / "eventos"

SITE = "escola-a"
PEDIDO = "pedido-553"
PROVEDOR = "appmax"
REFERENCIA_NO_PROVEDOR = "4471230"
PRODUTO = "curso-fundamentos"
COMPRADOR = {"email": "aluna@exemplo.com.br", "name": "Aluna Exemplo"}


def _aprovado(*, site=SITE, pedido=PEDIDO, referencia=REFERENCIA_NO_PROVEDOR) -> dict:
    """A compra que criou a matrícula, na versão 2."""
    return {
        "event": "pagamento.aprovado",
        "version": 2,
        "event_id": str(uuid.uuid4()),
        "occurred_at": "2026-09-21T12:00:00Z",
        "data": {
            "platform_site_id": site,
            "payment_id": f"pay-{pedido}",
            "order_id": pedido,
            "amount_cents": 19700,
            "method": "card",
            "provider": PROVEDOR,
            "provider_reference_id": referencia,
            "product_id": PRODUTO,
            "customer": dict(COMPRADOR),
        },
    }


def _estornado(
    *,
    site=SITE,
    referencia=REFERENCIA_NO_PROVEDOR,
    motivo="estorno",
    event_id=None,
) -> dict:
    """O dinheiro daquela mesma compra voltando. Validado contra o contrato em
    `test_os_envelopes_de_exemplo_batem_com_os_contratos` — sem isso o arquivo
    inteiro poderia estar medindo um evento que ninguém emite."""
    return {
        "event": "pagamento.estornado",
        "version": 2,
        "event_id": event_id or str(uuid.uuid4()),
        "occurred_at": "2026-09-21T13:00:00Z",
        "data": {
            "platform_site_id": site,
            "provider": PROVEDOR,
            "provider_reference_id": referencia,
            "motivo": motivo,
            "amount_cents": 19700,
        },
    }


def _matricula() -> Matricula:
    """A aluna que pagou e entrou, pelo caminho REAL do consumidor."""
    processar_envelope(_aprovado(), HANDLERS)
    return Matricula.objects.get(order_id=PEDIDO)


def _cortes() -> list[OutboxEvent]:
    """Os fatos de situação que dizem `suspensa` — um por corte de acesso."""
    return list(
        OutboxEvent.objects.filter(
            event=SITUACAO_ALTERADA, payload__situacao_nova=Matricula.STATUS_SUSPENSA
        ).order_by("id")
    )


# --------------------------------------------------------------------------
# §0 CONTROLE POSITIVO. Se os exemplos não forem eventos de verdade, todo o
#    resto deste arquivo mede uma fantasia.
# --------------------------------------------------------------------------


def test_os_envelopes_de_exemplo_batem_com_os_contratos():
    for envelope, arquivo in (
        (_aprovado(), "pagamento.aprovado.v2.json"),
        (_estornado(), "pagamento.estornado.v2.json"),
        (_estornado(motivo="contestacao"), "pagamento.estornado.v2.json"),
    ):
        schema = json.loads((CONTRATOS / arquivo).read_text(encoding="utf-8"))
        jsonschema.validate(envelope, schema)


# --------------------------------------------------------------------------
# §1 O CORTE. Os dois motivos cortam igual, e cortam na hora.
# --------------------------------------------------------------------------


def test_o_estorno_suspende_a_matricula_daquele_pagamento():
    # guarda: services/alunos/apps/matriculas/services.py:210
    matricula = _matricula()
    assert matricula.status == Matricula.STATUS_ATIVA

    processar_envelope(_estornado(), HANDLERS)

    matricula.refresh_from_db()
    assert matricula.status == Matricula.STATUS_SUSPENSA
    # O acesso fecha de verdade: a consulta que decide quem é aluno deixa de
    # enxergá-la. Sem isto, "suspensa" seria um rótulo na tela do painel.
    assert not matriculas_que_valem(COMPRADOR["email"]).exists()


def test_a_contestacao_suspende_igual_ao_estorno():
    """Decisão do mantenedor em 20/09/2026: os dois motivos cortam na hora, sem
    distinção. O contrato os separa porque o que vem DEPOIS difere (contestação
    tem prazo de defesa), e é fácil confundir essa separação com um tratamento
    diferente aqui dentro."""
    # guarda: services/alunos/apps/matriculas/services.py:210
    matricula = _matricula()

    processar_envelope(_estornado(motivo="contestacao"), HANDLERS)

    matricula.refresh_from_db()
    assert matricula.status == Matricula.STATUS_SUSPENSA


def test_o_fato_do_corte_vai_para_o_livro():
    """Perder acesso não gera carta para o aluno (ele não conseguiria abrir a
    página de avisos), mas gera FATO: sem ele o livro não sabe dizer por que
    aquela pessoa parou de entrar."""
    # guarda: services/alunos/apps/matriculas/services.py:212
    matricula = _matricula()

    processar_envelope(_estornado(), HANDLERS)

    (corte,) = _cortes()
    assert corte.payload["matricula_id"] == str(matricula.pk)
    assert corte.payload["situacao_anterior"] == Matricula.STATUS_ATIVA
    assert corte.payload["site_id"] == SITE
    # Ninguém DECIDIU isto: o fato do estorno é que cortou.
    assert corte.envelope_extra["ator_id"] is None


# --------------------------------------------------------------------------
# §2 A REENTREGA. O mesmo fato chega N vezes e suspende UMA.
# --------------------------------------------------------------------------


def test_o_mesmo_estorno_reentregue_suspende_uma_vez_so():
    matricula = _matricula()
    envelope = _estornado()

    for _ in range(3):
        processar_envelope(envelope, HANDLERS)

    matricula.refresh_from_db()
    assert matricula.status == Matricula.STATUS_SUSPENSA
    assert len(_cortes()) == 1
    assert EventoProcessado.objects.filter(event_id=envelope["event_id"]).count() == 1


def test_o_mesmo_estorno_com_outro_event_id_suspende_uma_vez_so():
    """A entrega at-least-once não é o único jeito de o mesmo fato voltar: o
    provedor pode reemitir o aviso com `event_id` novo. Quem barra isto é a
    identidade lógica do fato, e não o dedup por envelope."""
    _matricula()

    processar_envelope(_estornado(), HANDLERS)
    processar_envelope(_estornado(), HANDLERS)

    assert len(_cortes()) == 1


def test_suspender_o_ja_suspenso_nao_e_erro_nem_efeito_novo():
    """A terceira camada, e a única que sobrevive a um dedup furado: o próprio
    serviço, chamado duas vezes, corta uma só. Sem ela o livro ganharia um
    segundo fato de suspensão para uma matrícula que já estava suspensa, e a
    história daquele aluno passaria a mentir."""
    # guarda: services/alunos/apps/matriculas/services.py:210
    matricula = _matricula()
    chamada = {
        "site_id": SITE,
        "provider": PROVEDOR,
        "provider_reference_id": REFERENCIA_NO_PROVEDOR,
    }

    encontradas, suspensas = suspender_por_estorno(**chamada)
    assert [linha.pk for linha in encontradas] == [matricula.pk]
    assert [linha.pk for linha in suspensas] == [matricula.pk]

    encontradas, suspensas = suspender_por_estorno(**chamada)
    assert [linha.pk for linha in encontradas] == [matricula.pk]
    assert suspensas == []
    assert len(_cortes()) == 1


# --------------------------------------------------------------------------
# §3 A FICHA CONTINUA INTEIRA, e a decisão humana continua possível.
# --------------------------------------------------------------------------


def test_a_suspensao_nao_apaga_a_ficha_do_aluno():
    """*"Suspensão fecha o acesso, não apaga dado"* — e a ficha inteira é o que
    permite reabrir depois. Isto é a `DECISAO-a-ficha-nao-se-apaga.md` aplicada
    ao corte por estorno."""
    matricula = _matricula()
    antes = {
        "email": matricula.email,
        "name": matricula.name,
        "product_id": matricula.product_id,
        "order_id": matricula.order_id,
        "site_id": matricula.site_id,
        "enrolled_at": matricula.enrolled_at,
    }

    processar_envelope(_estornado(), HANDLERS)

    matricula.refresh_from_db()
    assert {campo: getattr(matricula, campo) for campo in antes} == antes


def test_o_painel_consegue_reabrir_o_acesso_suspenso():
    """Reabrir é DECISÃO OPERACIONAL, e por isso tem de continuar possível pela
    porta humana. Um corte que só uma migration desfizesse não seria suspensão,
    seria encerramento com outro nome."""
    matricula = _matricula()
    processar_envelope(_estornado(), HANDLERS)

    linha, resultado = atualizar_matricula(
        id_da_linha=str(matricula.pk),
        mudancas={"status": Matricula.STATUS_ATIVA},
        decidido_por="mantenedor@exemplo.test",
    )

    assert resultado == "ok"
    assert linha.status == Matricula.STATUS_ATIVA
    assert matriculas_que_valem(COMPRADOR["email"]).exists()

    _, suspensas = suspender_por_estorno(
        site_id=SITE,
        provider=PROVEDOR,
        provider_reference_id=REFERENCIA_NO_PROVEDOR,
    )
    linha.refresh_from_db()
    assert suspensas == []
    assert linha.status == Matricula.STATUS_ATIVA


# --------------------------------------------------------------------------
# §4 A TRANSIÇÃO É MONOTÔNICA: aprovação depois do estorno não reabre nada.
# --------------------------------------------------------------------------


def test_uma_aprovacao_depois_do_estorno_nao_reabre_o_acesso():
    """O modo de falha que este guarda fecha é silencioso e caro: o provedor
    reemite o aviso de aprovação daquela compra (reprocesso, conciliação, um
    webhook atrasado), e o aluno cujo dinheiro voltou entra de novo sem que
    ninguém tenha decidido nada. Reabrir é decisão operacional, e o consumidor
    não a toma sozinho."""
    matricula = _matricula()
    processar_envelope(_estornado(), HANDLERS)

    processar_envelope(_aprovado(), HANDLERS)

    matricula.refresh_from_db()
    assert matricula.status == Matricula.STATUS_SUSPENSA
    assert not matriculas_que_valem(COMPRADOR["email"]).exists()
    assert Matricula.objects.filter(order_id=PEDIDO).count() == 1


def test_estorno_antes_da_aprovacao_mantem_a_matricula_suspensa():
    """Aprovação e estorno correm em streams independentes, sem ordem garantida.

    O estorno órfão precisa deixar um estado persistente que a aprovação tardia
    consulte antes de abrir o acesso.
    """
    # guarda: services/alunos/apps/matriculas/services.py:190
    processar_envelope(_estornado(), HANDLERS)

    processar_envelope(_aprovado(), HANDLERS)

    matricula = Matricula.objects.get(order_id=PEDIDO)
    assert matricula.status == Matricula.STATUS_SUSPENSA
    assert not matriculas_que_valem(COMPRADOR["email"]).exists()
    assert len(_cortes()) == 1


def test_estorno_pendente_isola_site_e_reentregas():
    """A chave do estado pendente inclui o site e sobrevive a eventos repetidos."""
    estorno = _estornado()
    for _ in range(3):
        processar_envelope(estorno, HANDLERS)
    processar_envelope(_aprovado(site="escola-b", pedido="pedido-escola-b"), HANDLERS)
    processar_envelope(_aprovado(), HANDLERS)

    suspensa = Matricula.objects.get(order_id=PEDIDO)
    outra_escola = Matricula.objects.get(order_id="pedido-escola-b")
    assert suspensa.status == Matricula.STATUS_SUSPENSA
    assert outra_escola.status == Matricula.STATUS_ATIVA
    assert len(_cortes()) == 1


@pytest.mark.django_db(transaction=True)
def test_estorno_e_aprovacao_simultaneos_nao_abrem_acesso():
    """A gravação e a leitura do estado do pagamento usam o mesmo lock real."""
    from django.db import connection

    barreira = threading.Barrier(2, timeout=10)
    erros = []

    def processar(envelope):
        try:
            barreira.wait()
            processar_envelope(envelope, HANDLERS)
        except Exception as exc:  # pragma: no cover - preserva a falha da thread
            erros.append(exc)
        finally:
            connection.close()

    threads = [
        threading.Thread(target=processar, args=(envelope,))
        for envelope in (_estornado(), _aprovado())
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert not erros, erros
    assert not [thread for thread in threads if thread.is_alive()], "thread travada"
    matricula = Matricula.objects.get(order_id=PEDIDO)
    assert matricula.status == Matricula.STATUS_SUSPENSA
    assert not matriculas_que_valem(COMPRADOR["email"]).exists()


# --------------------------------------------------------------------------
# §5 O ESTORNO ÓRFÃO. Registra e segue — o consumidor não morre por isso.
# --------------------------------------------------------------------------


def test_estorno_de_pagamento_sem_matricula_nao_derruba_o_consumidor(caplog):
    """Vai acontecer: compra de outra célula, evento antigo, pagamento que nunca
    matriculou ninguém. Estourar aqui prenderia a mensagem no PEL e a mandaria
    para a fila morta, e o consumidor pararia de processar o resto da fila por
    um fato que não é dele."""
    envelope = _estornado(referencia="referencia-que-nao-matriculou-ninguem")

    with caplog.at_level(logging.WARNING):
        processar_envelope(envelope, HANDLERS)

    assert EventoProcessado.objects.filter(event_id=envelope["event_id"]).exists()
    assert not _cortes()
    assert "referencia-que-nao-matriculou-ninguem" in caplog.text


# --------------------------------------------------------------------------
# §6 QUEM O ESTORNO ALCANÇA. Os dois casamentos errados possíveis.
# --------------------------------------------------------------------------


def test_o_estorno_nao_alcanca_a_matricula_de_outra_escola():
    """[INV-P11] O `provider_reference_id` é o id da cobrança NA CONTA do
    fornecedor, e cada escola tem a sua: duas escolas podem receber a referência
    `4471230` no mesmo dia, de pagamentos que nada têm a ver um com o outro. Sem
    o site no casamento, o estorno de uma cortaria o acesso do aluno da outra."""
    _matricula()
    processar_envelope(_aprovado(site="escola-b", pedido="pedido-da-outra"), HANDLERS)
    da_outra = Matricula.objects.get(order_id="pedido-da-outra")

    processar_envelope(_estornado(site="escola-b"), HANDLERS)

    da_outra.refresh_from_db()
    assert da_outra.status == Matricula.STATUS_SUSPENSA
    assert Matricula.objects.get(order_id=PEDIDO).status == Matricula.STATUS_ATIVA


def test_estorno_sem_referencia_do_provedor_nao_suspende_ninguem():
    """A matrícula nascida antes deste par existir tem `provider` e
    `provider_reference_id` vazios, e é assim que ela fica para sempre: o evento
    de aprovação que a criou não carregava essa informação.

    Uma referência vazia casaria com TODAS elas de uma vez. O contrato pede
    `minLength: 1` nos dois campos, mas o consumidor lê o envelope do fio e não
    o valida contra o schema: um emissor com defeito suspenderia a escola
    inteira, em silêncio, num único evento."""
    antiga = Matricula.objects.create(
        site_id=SITE,
        order_id="pedido-de-antes-do-par",
        product_id=PRODUTO,
        email="antiga@exemplo.com.br",
        name="Matrícula Antiga",
    )

    encontradas, suspensas = suspender_por_estorno(
        site_id=SITE, provider="", provider_reference_id=""
    )

    assert (encontradas, suspensas) == ([], [])
    antiga.refresh_from_db()
    assert antiga.status == Matricula.STATUS_ATIVA
