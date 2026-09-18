# tests/test_eventos_mortos_recuperaveis.py (TAR-456)
#
# A fila morta desta célula existe desde a reentrega da PEL, e até aqui era um
# beco sem saída: o log ERROR dizia "intervencao manual necessaria" e nenhuma
# mão tinha o que fazer. Estes guardas medem o caminho inteiro do operador:
# envenenar, morrer na fila depois do limite, corrigir a causa, reprocessar, e
# provar que o efeito aconteceu UMA vez.
#
# Contra Redis REAL, pelo mesmo motivo de `test_reentrega_pel.py`: a fila morta
# é um stream, e um dublê de Redis provaria o dublê.
import json
import logging
import os
from io import StringIO
from unittest.mock import patch
from uuid import uuid4

import pytest
import redis
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.eventos.handlers import ao_pagamento_aprovado
from apps.eventos.management.commands import consume_eventos, eventos_mortos
from apps.eventos.management.commands.consume_eventos import (
    GRUPO,
    MAX_ENTREGAS,
    _reivindicar_presas,
)
from apps.eventos.models import EnvioRegistrado, EventoProcessado

pytestmark = pytest.mark.django_db(transaction=True)

DATA = {
    "site_id": "site-abc",
    "payment_id": "pay-1",
    "order_id": "order-1",
    "amount_cents": 1000,
    "method": "pix",
    "mp_payment_id": "mp-1",
    "customer": {"email": "cliente@example.com", "name": "Cliente Um"},
}


def _envelope() -> dict:
    return {
        "event": "pagamento.aprovado",
        "version": 1,
        "event_id": str(uuid4()),
        "occurred_at": "2026-09-18T12:00:00Z",
        "data": DATA,
    }


@pytest.fixture()
def r():
    url = os.environ.get("REDIS_STREAMS_URL")
    if not url:
        # fail, não skip: pular aqui seria um verde falso (§5.6).
        pytest.fail(
            "REDIS_STREAMS_URL ausente, e estes testes exigem Redis real "
            "(lote 2 local: export REDIS_STREAMS_URL=redis://localhost:16383/0)"
        )
    cliente = redis.from_url(url)
    cliente.ping()
    yield cliente
    cliente.close()


@pytest.fixture()
def stream(r):
    nome = f"eventos.teste-mortos.{uuid4().hex}"
    yield nome
    r.delete(nome, f"{nome}.dlq")


@pytest.fixture()
def celula_de_um_stream(stream):
    """A célula vista pelo comando: um stream só, com o handler de verdade.

    O comando lê `consume_eventos.STREAMS` na hora de rodar justamente para que
    o teste possa apontá-lo para um stream descartável em vez de escrever nos
    sete streams reais.
    """
    with patch.object(consume_eventos, "STREAMS", {stream: ao_pagamento_aprovado}):
        yield stream


def _envenenar(r, stream: str, envelope: dict) -> None:
    """Deixa o evento na fila morta pelo CAMINHO DE PRODUÇÃO: ele é entregue,
    o handler estoura até esgotar MAX_ENTREGAS, e a reivindicação o move para
    `<stream>.dlq` sem rodar o handler de novo. Nada de xadd direto na fila
    morta: seria o teste escrevendo o estado que ele quer medir."""
    r.xadd(stream, {"json": json.dumps(envelope)})
    try:
        r.xgroup_create(stream, GRUPO, id="0")
    except redis.ResponseError:
        pass  # o grupo já existe: este envenenamento é o segundo do mesmo teste
    resposta = r.xreadgroup(GRUPO, "worker-que-morreu", {stream: ">"}, count=1)
    msg_id = resposta[0][1][0][0]
    r.xclaim(
        stream,
        GRUPO,
        "worker-que-morreu",
        min_idle_time=0,
        message_ids=[msg_id],
        retrycount=MAX_ENTREGAS,
    )

    def handler_envenenado(data, event_id=None, ator_id=None):
        raise AssertionError("evento esgotado não pode rodar o handler")

    with patch.object(consume_eventos, "IDLE_MS_REENTREGA", 0):
        _reivindicar_presas(r, stream, handler_envenenado)


def _rodar(*argumentos) -> str:
    saida = StringIO()
    call_command("eventos_mortos", *argumentos, stdout=saida)
    return saida.getvalue()


def test_a_lista_mostra_o_evento_morto_com_motivo_entregas_e_indicador(
    r, celula_de_um_stream
):
    """O operador abre a fila morta e vê o que precisa para decidir: qual
    evento, de qual stream, por que morreu, quantas entregas levou e desde
    quando. A última linha é o indicador, feito para ser lido por máquina."""
    envelope = _envelope()
    _envenenar(r, celula_de_um_stream, envelope)

    saida = _rodar()

    assert envelope["event_id"] in saida
    assert "pagamento.aprovado" in saida
    assert "max_entregas_esgotadas" in saida
    assert f"entregas={MAX_ENTREGAS}" in saida
    assert celula_de_um_stream in saida
    assert (
        saida.strip().splitlines()[-1]
        == "INDICADOR eventos_mortos=1 streams_afetados=1"
    )


def test_fila_morta_vazia_diz_que_esta_vazia_e_o_indicador_marca_zero(
    r, celula_de_um_stream
):
    """Primeiro uso, e o dia bom: nada morreu. A tela precisa dizer isso com
    todas as letras, porque silêncio aqui se confunde com comando quebrado."""
    saida = _rodar()

    assert "FILA MORTA VAZIA" in saida
    assert (
        saida.strip().splitlines()[-1]
        == "INDICADOR eventos_mortos=0 streams_afetados=0"
    )


def test_envenenado_morre_reprocessa_uma_vez_e_o_efeito_acontece(
    r, celula_de_um_stream
):
    """O aceite da TAR-456 inteiro: evento envenenado atinge o limite e cai na
    fila morta, a causa é corrigida, o operador reprocessa uma vez e o efeito
    final (o envio) acontece de verdade."""
    envelope = _envelope()
    _envenenar(r, celula_de_um_stream, envelope)
    assert EventoProcessado.objects.count() == 0  # morreu sem efeito nenhum

    with patch("apps.eventos.handlers.enviar_notificacao") as enviar:
        saida = _rodar("--reprocessar", envelope["event_id"])

    assert enviar.call_count == 1
    assert (
        EnvioRegistrado.objects.filter(order_id="order-1", tipo="boas_vindas").count()
        == 1
    )
    assert EventoProcessado.objects.filter(event_id=envelope["event_id"]).count() == 1
    assert "RECUPERADO" in saida
    assert envelope["event_id"] in saida
    # e a entrada saiu da fila morta: ela guarda o que AINDA está morto
    assert r.xlen(f"{celula_de_um_stream}.dlq") == 0


def test_reprocessar_duas_vezes_produz_um_unico_efeito(r, celula_de_um_stream):
    """Idempotência provada com o caso repetido, não afirmada: a mesma
    recuperação rodada duas vezes manda UM e-mail só. A segunda passagem
    encontra a fila vazia e diz que o efeito já está gravado, em vez de
    reenviar ou de estourar na cara do operador."""
    envelope = _envelope()
    _envenenar(r, celula_de_um_stream, envelope)

    with patch("apps.eventos.handlers.enviar_notificacao") as enviar:
        _rodar("--reprocessar", envelope["event_id"])
        segunda = _rodar("--reprocessar", envelope["event_id"])

    assert enviar.call_count == 1
    assert (
        EnvioRegistrado.objects.filter(order_id="order-1", tipo="boas_vindas").count()
        == 1
    )
    assert "JÁ RECUPERADO" in segunda


def test_entrada_repetida_na_fila_morta_tambem_produz_um_unico_efeito(
    r, celula_de_um_stream
):
    """O outro formato da mesma pergunta: o MESMO evento morreu duas vezes (o
    consumidor caiu, voltou, e a segunda cópia esgotou as entregas de novo).
    Reprocessar tudo limpa as duas entradas com um efeito só, pela dedup de
    `event_id` que já existia."""
    envelope = _envelope()
    _envenenar(r, celula_de_um_stream, envelope)
    _envenenar(r, celula_de_um_stream, envelope)
    assert r.xlen(f"{celula_de_um_stream}.dlq") == 2

    with patch("apps.eventos.handlers.enviar_notificacao") as enviar:
        saida = _rodar("--reprocessar-tudo")

    assert enviar.call_count == 1
    assert EventoProcessado.objects.filter(event_id=envelope["event_id"]).count() == 1
    assert r.xlen(f"{celula_de_um_stream}.dlq") == 0
    assert "eventos_mortos_recuperados=2" in saida


def test_causa_nao_corrigida_mantem_o_evento_na_fila_e_o_erro_diz_o_que_fazer(
    r, celula_de_um_stream
):
    """Reprocessar antes de corrigir a causa não pode limpar a fila morta: o
    evento continua morto, e a mensagem de erro nomeia o event_id, o erro real
    e o próximo passo. Fila morta esvaziada por engano é evento perdido."""
    envelope = _envelope()
    _envenenar(r, celula_de_um_stream, envelope)

    def ainda_quebrado(data, event_id=None, ator_id=None):
        raise ValueError("template boas_vindas ausente")

    with patch.object(
        consume_eventos, "STREAMS", {celula_de_um_stream: ainda_quebrado}
    ):
        with pytest.raises(CommandError) as erro:
            _rodar("--reprocessar", envelope["event_id"])

    mensagem = str(erro.value)
    assert envelope["event_id"] in mensagem
    assert "template boas_vindas ausente" in mensagem
    assert "continua na fila morta" in mensagem
    assert r.xlen(f"{celula_de_um_stream}.dlq") == 1  # nada foi perdido
    assert EventoProcessado.objects.count() == 0


def test_entrada_so_sai_da_fila_morta_com_o_efeito_conferido_no_banco(
    r, celula_de_um_stream
):
    """A prova do efeito final é lida do BANCO, não do fato de o handler ter
    voltado sem estourar. Com um processamento que diz ter funcionado e não
    grava nada, a entrada FICA na fila morta e o comando reprova."""
    envelope = _envelope()
    _envenenar(r, celula_de_um_stream, envelope)

    with patch.object(eventos_mortos, "processar_envelope", return_value=True):
        with pytest.raises(CommandError) as erro:
            _rodar("--reprocessar", envelope["event_id"])

    assert "sem deixar efeito no banco" in str(erro.value)
    assert r.xlen(f"{celula_de_um_stream}.dlq") == 1


def test_recuperacao_deixa_no_log_o_mesmo_event_id_do_alarme(
    r, celula_de_um_stream, caplog
):
    """O alarme da fila morta é um log ERROR com o event_id. A recuperação
    fecha o ciclo no MESMO lugar: quem achou o alarme grepando o event_id
    precisa achar a baixa dele sem abrir o Redis."""
    envelope = _envelope()
    _envenenar(r, celula_de_um_stream, envelope)

    with caplog.at_level(logging.INFO):
        with patch("apps.eventos.handlers.enviar_notificacao"):
            _rodar("--reprocessar", envelope["event_id"])

    recuperacoes = [
        registro
        for registro in caplog.records
        if "FILA MORTA RECUPERADA" in registro.getMessage()
    ]
    assert len(recuperacoes) == 1
    assert envelope["event_id"] in recuperacoes[0].getMessage()


def test_event_id_que_nunca_esteve_na_fila_morta_e_erro_nomeado(r, celula_de_um_stream):
    """Digitou o id errado: o comando não pode fingir sucesso nem sumir em
    silêncio. Recusa dizendo que o evento não está morto nem processado."""
    with pytest.raises(CommandError) as erro:
        _rodar("--reprocessar", str(uuid4()))

    assert "não está na fila morta" in str(erro.value)


def test_reprocessar_com_event_id_vazio_nao_vira_listagem_silenciosa(
    r, celula_de_um_stream
):
    """`--reprocessar ""` (a variável de shell que veio vazia) pedia
    recuperação e recebia a listagem, com saída zero: o operador ia embora
    achando que recuperou. Pedido vazio é erro nomeado, e o mesmo guarda pega
    qualquer texto que não seja UUID, que antes estourava um ValueError cru do
    ORM na cara de quem digitou errado."""
    with pytest.raises(CommandError) as erro:
        _rodar("--reprocessar", "")

    assert "não é um event_id" in str(erro.value)


def test_entrada_ilegivel_aparece_na_lista_e_nao_e_reprocessada_no_escuro(
    r, celula_de_um_stream
):
    """A fila morta copia o payload como veio, e um corpo que nem JSON é pode
    estar lá. Ele precisa APARECER na lista (sumir seria perder o evento) e o
    reprocesso precisa recusar, porque não há envelope para entregar a handler
    nenhum."""
    r.xadd(
        f"{celula_de_um_stream}.dlq",
        {b"json": b"isto nao e json", b"motivo": b"max_entregas_esgotadas"},
    )

    listagem = _rodar()
    assert "ilegível" in listagem
    assert "INDICADOR eventos_mortos=1" in listagem

    with pytest.raises(CommandError) as erro:
        _rodar("--reprocessar-tudo")
    mensagem = str(erro.value)
    assert "não há envelope para entregar a handler nenhum" in mensagem
    assert "XRANGE" in mensagem  # o operador precisa do comando para ler o corpo cru
    assert r.xlen(f"{celula_de_um_stream}.dlq") == 1
