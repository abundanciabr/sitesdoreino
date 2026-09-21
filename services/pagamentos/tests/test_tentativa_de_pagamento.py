# tests/test_tentativa_de_pagamento.py
# Guardas do modelo de tentativa de pagamento (core/models.PaymentAttempt e
# core/tentativas.py).
#
# Os dois comportamentos caros estão aqui e cada um tem nome de teste próprio:
# uma recusa NÃO pode prender o comprador (ele precisa poder pagar com outro
# cartão), e um resultado ambíguo NÃO pode virar segunda cobrança (é o caminho
# que tira dinheiro duas vezes da mesma pessoa).
#
# Os testes de corrida usam `django_db(transaction=True)` de propósito: o
# `django_db` padrão embrulha o teste numa transação que nunca faz COMMIT, e
# sem commit nenhuma outra conexão enxerga a linha, que é justamente o que
# estes guardas precisam medir (LICOES.md, Sessão B).
from __future__ import annotations

import threading
import uuid
from typing import Any, Callable, TypeVar

import pytest
from django.core.management import call_command
from django.db import connection, transaction

from pagamentos.core.models import Intent, PaymentAttempt
from pagamentos.core.tentativas import (
    EnvioNaoChegou,
    ResultadoAmbiguo,
    ResultadoDoProvedor,
    TentativaBloqueada,
    executar_tentativa,
    fechar_reconciliacao,
    tentativas_do_site,
)

pytestmark = pytest.mark.django_db(transaction=True)

_SITE = "meshcraft-top"
_OUTRO_SITE = "site-vizinho"
_TOKEN_DO_CARTAO = "tok_4111111111111111_abcdef"

T = TypeVar("T")


def _criar_intent(*, site_id: str = _SITE, amount_cents: int = 19900) -> Intent:
    return Intent.objects.create(
        idempotency_key=str(uuid.uuid4()),
        site_id=site_id,
        order_id="pedido-1",
        method="card",
        amount_cents=amount_cents,
        customer={"email": "cliente@exemplo.com"},
    )


def _corpo(token: str = _TOKEN_DO_CARTAO) -> dict[str, Any]:
    return {
        "order_id": "pedido-1",
        "payment_data": {
            "credit_card": {
                "token": token,
                "holder_name": "CLIENTE TESTE",
                "holder_document_number": "12345678909",
                "installments": 1,
            }
        },
    }


def _aprovar(
    motivo: str = "accredited",
) -> Callable[[PaymentAttempt], ResultadoDoProvedor]:
    def enviar(tentativa: PaymentAttempt) -> ResultadoDoProvedor:
        return ResultadoDoProvedor(
            aprovada=True, provider_reference_id="pay-1", motivo=motivo
        )

    return enviar


def _recusar(
    motivo: str = "insufficient_funds",
) -> Callable[[PaymentAttempt], ResultadoDoProvedor]:
    def enviar(tentativa: PaymentAttempt) -> ResultadoDoProvedor:
        return ResultadoDoProvedor(
            aprovada=False, provider_reference_id="pay-recusado", motivo=motivo
        )

    return enviar


def _em_outra_conexao(consulta: Callable[[], T]) -> T:
    """Roda a consulta numa thread, que ganha conexão própria: só enxerga o que
    já foi COMMITADO. É assim que se prova 'persistida ANTES do envio' sem
    acreditar na palavra do código."""
    colhido: list[T] = []
    erros: list[BaseException] = []

    def correr() -> None:
        try:
            colhido.append(consulta())
        except BaseException as exc:  # noqa: BLE001 - relançada abaixo
            erros.append(exc)
        finally:
            connection.close()

    thread = threading.Thread(target=correr)
    thread.start()
    thread.join(timeout=15)
    if erros:
        raise erros[0]
    assert colhido, "a consulta em outra conexão não terminou"
    return colhido[0]


# ---------------------------------------------------------------------------
# Regra 3: nenhuma chamada externa sem tentativa persistida antes do envio
# ---------------------------------------------------------------------------


@pytest.mark.smoke_card
def test_tentativa_existe_commitada_antes_da_chamada_externa() -> None:
    """O provedor pode cobrar e a nossa máquina pode morrer no mesmo segundo.
    Se a linha não estiver commitada ANTES do envio, essa cobrança fica órfã e
    ninguém no mundo sabe que ela existe."""
    intent = _criar_intent()
    visto: dict[str, Any] = {}

    def enviar(tentativa: PaymentAttempt) -> ResultadoDoProvedor:
        gravada = _em_outra_conexao(
            lambda: PaymentAttempt.objects.filter(
                operation_id=tentativa.operation_id
            ).first()
        )
        visto["gravada"] = gravada
        visto["state"] = None if gravada is None else gravada.state
        return ResultadoDoProvedor(aprovada=True, provider_reference_id="pay-1")

    tentativa = executar_tentativa(
        intent=intent, provider="appmax", corpo=_corpo(), enviar=enviar
    )

    assert (
        visto["gravada"] is not None
    ), "a chamada externa aconteceu sem tentativa commitada: cobrança órfã"
    assert visto["state"] == "sending"
    assert tentativa.operation_id is not None
    assert tentativa.request_hash != ""
    assert tentativa.state == "approved"


@pytest.mark.smoke_card
def test_envio_dentro_de_transacao_aberta_e_recusado_antes_de_chamar() -> None:
    """Dentro de um `atomic()` do chamador a linha ainda não está commitada, e
    um crash apagaria o rastro da cobrança. O `durable=True` recusa esse
    caminho antes de a rede ser tocada."""
    intent = _criar_intent()
    chamadas: list[str] = []

    def contar(tentativa: PaymentAttempt) -> ResultadoDoProvedor:
        chamadas.append("chamou")
        return ResultadoDoProvedor(aprovada=True, provider_reference_id="pay-1")

    with pytest.raises(RuntimeError):
        with transaction.atomic():
            executar_tentativa(
                intent=intent, provider="appmax", corpo=_corpo(), enviar=contar
            )

    assert chamadas == []
    assert PaymentAttempt.objects.filter(intent=intent).count() == 0


@pytest.mark.smoke_card
def test_operation_id_e_hash_nao_guardam_o_token_do_cartao() -> None:
    """[INV-P8] O corpo enviado carrega token e documento do portador. Do corpo
    fica só um hash; nenhum campo da tentativa pode conter o dado cru."""
    intent = _criar_intent()

    tentativa = executar_tentativa(
        intent=intent, provider="appmax", corpo=_corpo(), enviar=_aprovar()
    )

    valores = " ".join(
        str(getattr(tentativa, campo.attname)) for campo in PaymentAttempt._meta.fields
    )
    assert _TOKEN_DO_CARTAO not in valores
    assert "12345678909" not in valores
    assert len(tentativa.request_hash) == 64


@pytest.mark.smoke_card
def test_hash_muda_quando_o_token_muda() -> None:
    """Hash que ignora o token não serve de evidência: duas tentativas com
    cartões diferentes ficariam indistinguíveis no registro."""
    intent_a = _criar_intent()
    intent_b = _criar_intent()

    primeira = executar_tentativa(
        intent=intent_a, provider="appmax", corpo=_corpo(), enviar=_recusar()
    )
    segunda = executar_tentativa(
        intent=intent_b,
        provider="appmax",
        corpo=_corpo(token="tok_5555444433332222_zzz"),
        enviar=_recusar(),
    )

    assert primeira.request_hash != segunda.request_hash


# ---------------------------------------------------------------------------
# Regra 1: recusa é terminal para a tentativa, nunca para o comprador
# ---------------------------------------------------------------------------


@pytest.mark.smoke_card
def test_recusa_nao_trava_o_comprador_e_aceita_token_novo() -> None:
    """Hoje o comprador recusado fica sem caminho. A tentativa recusada é
    terminal; o Intent continua aceitando uma tentativa nova com token novo."""
    intent = _criar_intent()

    recusada = executar_tentativa(
        intent=intent, provider="appmax", corpo=_corpo(), enviar=_recusar()
    )
    assert recusada.state == "rejected"

    aprovada = executar_tentativa(
        intent=intent,
        provider="appmax",
        corpo=_corpo(token="tok_outro_cartao_do_cliente"),
        enviar=_aprovar(),
    )

    assert aprovada.state == "approved"
    assert aprovada.pk != recusada.pk
    assert PaymentAttempt.objects.filter(intent=intent).count() == 2
    assert aprovada.request_hash != recusada.request_hash


@pytest.mark.smoke_card
def test_falha_antes_do_envio_nao_trava_o_comprador() -> None:
    """Conexão recusada significa que nada saiu da nossa máquina: não há
    cobrança possível lá fora, então a tentativa seguinte é segura."""
    intent = _criar_intent()

    def nao_chegou(tentativa: PaymentAttempt) -> ResultadoDoProvedor:
        raise EnvioNaoChegou("conexao recusada")

    with pytest.raises(EnvioNaoChegou):
        executar_tentativa(
            intent=intent, provider="appmax", corpo=_corpo(), enviar=nao_chegou
        )

    falhada = PaymentAttempt.objects.get(intent=intent)
    assert falhada.state == "failed"

    aprovada = executar_tentativa(
        intent=intent, provider="appmax", corpo=_corpo(), enviar=_aprovar()
    )
    assert aprovada.state == "approved"


@pytest.mark.smoke_card
def test_tentativa_aprovada_bloqueia_nova_tentativa() -> None:
    """Terminal e bloqueante: cobrar de novo quem já pagou é o pior resultado
    possível desta célula."""
    intent = _criar_intent()
    executar_tentativa(
        intent=intent, provider="appmax", corpo=_corpo(), enviar=_aprovar()
    )
    chamadas: list[str] = []

    def contar(tentativa: PaymentAttempt) -> ResultadoDoProvedor:
        chamadas.append("chamou")
        return ResultadoDoProvedor(aprovada=True, provider_reference_id="pay-2")

    with pytest.raises(TentativaBloqueada) as bloqueio:
        executar_tentativa(
            intent=intent, provider="appmax", corpo=_corpo(), enviar=contar
        )

    assert bloqueio.value.estado == "approved"
    assert chamadas == []
    assert PaymentAttempt.objects.filter(intent=intent).count() == 1


# ---------------------------------------------------------------------------
# Regra 2: resultado ambíguo bloqueia até uma consulta confiável fechar
# ---------------------------------------------------------------------------


@pytest.mark.smoke_card
def test_resultado_ambiguo_bloqueia_novo_envio() -> None:
    """Timeout depois do envio: a cobrança pode existir lá fora. Reenviar por
    conta própria é exatamente como se cobra a mesma pessoa duas vezes."""
    intent = _criar_intent()

    def estourar_o_relogio(tentativa: PaymentAttempt) -> ResultadoDoProvedor:
        raise ResultadoAmbiguo("timeout depois de enviar")

    with pytest.raises(ResultadoAmbiguo):
        executar_tentativa(
            intent=intent, provider="appmax", corpo=_corpo(), enviar=estourar_o_relogio
        )

    ambigua = PaymentAttempt.objects.get(intent=intent)
    assert ambigua.state == "reconciliation_required"

    chamadas: list[str] = []

    def contar(tentativa: PaymentAttempt) -> ResultadoDoProvedor:
        chamadas.append("chamou")
        return ResultadoDoProvedor(aprovada=True, provider_reference_id="pay-2")

    with pytest.raises(TentativaBloqueada) as bloqueio:
        executar_tentativa(
            intent=intent, provider="appmax", corpo=_corpo(), enviar=contar
        )

    assert bloqueio.value.estado == "reconciliation_required"
    assert chamadas == [], "reenviou sozinho um resultado ambíguo: cobrança dupla"
    assert PaymentAttempt.objects.filter(intent=intent).count() == 1


@pytest.mark.smoke_card
def test_erro_inesperado_no_envio_tambem_exige_reconciliacao() -> None:
    """Não saber o que aconteceu é o mesmo risco de saber que houve timeout: o
    padrão seguro é bloquear, nunca presumir que nada foi enviado."""
    intent = _criar_intent()

    def explodir(tentativa: PaymentAttempt) -> ResultadoDoProvedor:
        raise RuntimeError("bug no cliente do provedor")

    with pytest.raises(RuntimeError):
        executar_tentativa(
            intent=intent, provider="appmax", corpo=_corpo(), enviar=explodir
        )

    assert PaymentAttempt.objects.get(intent=intent).state == "reconciliation_required"


@pytest.mark.smoke_card
def test_consulta_confiavel_fecha_a_reconciliacao_como_recusada_e_destrava() -> None:
    """A consulta ao provedor disse que não houve cobrança: a tentativa fecha
    como recusada e o comprador volta a poder tentar."""
    intent = _criar_intent()

    def estourar_o_relogio(tentativa: PaymentAttempt) -> ResultadoDoProvedor:
        raise ResultadoAmbiguo("timeout depois de enviar")

    with pytest.raises(ResultadoAmbiguo):
        executar_tentativa(
            intent=intent, provider="appmax", corpo=_corpo(), enviar=estourar_o_relogio
        )

    fechada = fechar_reconciliacao(
        PaymentAttempt.objects.get(intent=intent),
        resultado=ResultadoDoProvedor(
            aprovada=False, provider_reference_id="pay-9", motivo="not_found"
        ),
    )

    assert fechada.state == "rejected"
    assert fechada.provider_reference_id == "pay-9"
    nova = executar_tentativa(
        intent=intent, provider="appmax", corpo=_corpo(), enviar=_aprovar()
    )
    assert nova.state == "approved"


@pytest.mark.smoke_card
def test_consulta_confiavel_que_acha_a_cobranca_fecha_como_aprovada() -> None:
    """A cobrança tinha chegado: fechar como aprovada é o que impede a segunda
    cobrança de acontecer depois."""
    intent = _criar_intent()

    def estourar_o_relogio(tentativa: PaymentAttempt) -> ResultadoDoProvedor:
        raise ResultadoAmbiguo("timeout depois de enviar")

    with pytest.raises(ResultadoAmbiguo):
        executar_tentativa(
            intent=intent, provider="appmax", corpo=_corpo(), enviar=estourar_o_relogio
        )

    fechada = fechar_reconciliacao(
        PaymentAttempt.objects.get(intent=intent),
        resultado=ResultadoDoProvedor(
            aprovada=True, provider_reference_id="pay-9", motivo="accredited"
        ),
    )

    assert fechada.state == "approved"
    with pytest.raises(TentativaBloqueada):
        executar_tentativa(
            intent=intent, provider="appmax", corpo=_corpo(), enviar=_aprovar()
        )


# ---------------------------------------------------------------------------
# Regra 5: duplo clique simultâneo
# ---------------------------------------------------------------------------


@pytest.mark.smoke_card
def test_duplo_clique_simultaneo_gera_uma_tentativa_e_uma_chamada() -> None:
    """Os dois cliques entram no mesmo instante, antes de qualquer um gravar.
    Quem decide não é a checagem em Python, é o índice único parcial do
    Postgres: com ele, o segundo INSERT não existe."""
    intent = _criar_intent()
    largada = threading.Barrier(2)
    chamadas: list[str] = []
    contador = threading.Lock()
    erros: list[BaseException] = []

    def enviar(tentativa: PaymentAttempt) -> ResultadoDoProvedor:
        with contador:
            chamadas.append(str(tentativa.operation_id))
        return ResultadoDoProvedor(aprovada=True, provider_reference_id="pay-1")

    def clicar() -> None:
        try:
            largada.wait(timeout=15)
            executar_tentativa(
                intent=intent, provider="appmax", corpo=_corpo(), enviar=enviar
            )
        except BaseException as exc:  # noqa: BLE001 - conferido abaixo
            erros.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=clicar) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert len(chamadas) == 1, f"{len(chamadas)} chamadas externas num duplo clique"
    assert PaymentAttempt.objects.filter(intent=intent).count() == 1
    assert len(erros) == 1 and isinstance(erros[0], TentativaBloqueada)


# ---------------------------------------------------------------------------
# Regra 4: platform_site_id isola
# ---------------------------------------------------------------------------


@pytest.mark.smoke_card
def test_tentativa_de_um_site_nunca_e_lida_por_outro() -> None:
    """Lei 9: `site_id` acompanha toda entidade. Uma loja não enxerga a
    tentativa de pagamento da loja vizinha, nem pelo identificador interno,
    nem pela referência do provedor."""
    minha = executar_tentativa(
        intent=_criar_intent(site_id=_SITE),
        provider="appmax",
        corpo=_corpo(),
        enviar=_aprovar(),
    )
    vizinha = executar_tentativa(
        intent=_criar_intent(site_id=_OUTRO_SITE),
        provider="appmax",
        corpo=_corpo(),
        enviar=_recusar(),
    )

    assert minha.platform_site_id == _SITE
    assert list(tentativas_do_site(_SITE)) == [minha]
    assert (
        tentativas_do_site(_OUTRO_SITE).filter(operation_id=minha.operation_id).first()
        is None
    )
    assert (
        tentativas_do_site(_SITE)
        .filter(provider_reference_id=vizinha.provider_reference_id)
        .first()
        is None
    )


# ---------------------------------------------------------------------------
# Motivo sanitizado e completude das migrations
# ---------------------------------------------------------------------------


@pytest.mark.smoke_card
def test_motivo_do_provedor_e_sanitizado_antes_de_ir_para_o_banco() -> None:
    """O motivo vem de fora e vai para tela e log. Ele entra como código, nunca
    como texto livre: nada de dado do portador atravessando por descuido."""
    intent = _criar_intent()

    tentativa = executar_tentativa(
        intent=intent,
        provider="appmax",
        corpo=_corpo(),
        enviar=_recusar(motivo="Recusado: cartao 4111111111111111 do JOSE <b>!"),
    )

    assert tentativa.reason == "recusado_cartao_do_jose_b"
    assert len(tentativa.reason) <= 120


def test_nao_existe_migration_pendente() -> None:
    """Modelo mexido sem migration é um deploy que quebra na VPS, não no CI."""
    call_command("makemigrations", "core", "--check", "--dry-run", verbosity=0)
