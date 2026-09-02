"""A célula ganha voz: a carta do passo sai pela outbox e chega ao stream.

Degrau 5 da escada do `PLANO-SEQUENCIAS-DE-MENSAGENS.md` §7. O que se prova
aqui: a carta tem a FORMA do contrato, ela não carrega PII, ela nasce na mesma
transação da linha que diz que saiu, e o relay a publica sem perder nem duplicar.
"""

import json
import os
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
import redis
from django.db import transaction
from django.utils import timezone

from apps.jornadas import despacho, eventos, motor, regua, tasks
from apps.jornadas.models import (
    Entrega,
    Inscricao,
    Jornada,
    JornadaVersao,
    OutboxEvent,
    Passo,
)

pytestmark = pytest.mark.django_db(transaction=True)

SITE = "site-abc"
PESSOA = "pessoa-opaca-1"
EVENTO_DE_ORIGEM = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

CONTRATO = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "eventos"
    / "notificacao.devida.v1.json"
)


def quando(dia=15, hora=10):
    return timezone.make_aware(
        timezone.datetime(2026, 9, dia, hora, 0), timezone.get_current_timezone()
    )


def uma_jornada_pronta(slug="boas-vindas", canais=("sino",)):
    jornada = Jornada.objects.create(
        site_id=SITE, slug=slug, gatilho="identidade.pessoa-cadastrada.v1", ativa=True
    )
    versao = JornadaVersao.objects.create(jornada=jornada, numero=1)
    Passo.objects.create(
        jornada_versao=versao,
        ordem=1,
        atraso=timedelta(0),
        classe="relacional",
        canais=list(canais),
    )
    JornadaVersao.objects.filter(pk=versao.pk).update(publicada_em=quando(15, 9))
    return jornada


def inscrita(jornada, origem=EVENTO_DE_ORIGEM):
    return motor.inscrever(
        jornada,
        destinatario_id=PESSOA,
        site_id=SITE,
        origem_event_id=origem,
        momento=quando(15),
    )


# ---------------------------------------------------------------------------
# A OUTBOX RECUSA NASCER FORA DA TRANSAÇÃO
# ---------------------------------------------------------------------------


def test_emitir_fora_de_transacao_levanta_e_nao_grava_nada():
    """Em vez de confiar que todo ponto de emissão futuro lembre do `atomic`, a
    própria função recusa. Evento em autocommit sobrevive ao rollback do fato que
    o justifica, e a plataforma passa a acreditar em algo que não aconteceu."""
    with pytest.raises(eventos.EventoForaDaTransacao):
        eventos.passo_de_jornada_devido(
            site_id=SITE,
            destinatario_id=PESSOA,
            jornada_slug="boas-vindas",
            passo_id="00000000-0000-0000-0000-000000000000",
            ordem=1,
            origem_event_id=EVENTO_DE_ORIGEM,
        )
    assert not OutboxEvent.objects.exists()


# ---------------------------------------------------------------------------
# A CARTA TEM A FORMA DO CONTRATO, E NÃO CARREGA PII
# ---------------------------------------------------------------------------


def test_a_carta_tem_exatamente_os_campos_que_o_contrato_exige():
    """Conferido contra o CONTRATO no disco, e não contra uma lista aqui.

    `additionalProperties: false` no contrato significa que campo a mais reprova
    tanto quanto campo a menos — então o teste mede os dois lados.
    """
    contrato = json.loads(CONTRATO.read_text(encoding="utf-8"))
    forma = contrato["properties"]["data"]
    exigidos = set(forma["required"])
    permitidos = set(forma["properties"])

    with transaction.atomic():
        carta = eventos.passo_de_jornada_devido(
            site_id=SITE,
            destinatario_id=PESSOA,
            jornada_slug="boas-vindas",
            passo_id="11111111-1111-1111-1111-111111111111",
            ordem=1,
            origem_event_id=EVENTO_DE_ORIGEM,
        )

    dados = set(carta.payload)
    assert exigidos <= dados, f"faltando no data: {exigidos - dados}"
    assert (
        dados <= permitidos
    ), f"campo que o contrato nao conhece: {dados - permitidos}"

    assert carta.payload["assunto"] in forma["properties"]["assunto"]["enum"]
    assert carta.payload["assunto"] == "jornada.passo"

    parametros = set(carta.payload["parametros"])
    ramo = None
    for bloco in contrato["allOf"]:
        if "jornada.passo" in json.dumps(bloco, ensure_ascii=False):
            ramo = bloco["then"]["properties"]["data"]["properties"]["parametros"]
    assert ramo is not None, "o ramo de jornada.passo sumiu do contrato"
    assert set(ramo["required"]) <= parametros
    assert parametros <= set(ramo["properties"])


def test_a_carta_nao_carrega_e_mail_nome_nem_telefone():
    """Lei 2 do §3: evento nunca carrega PII, só id opaco de plataforma.

    Quem precisa falar com a pessoa PERGUNTA à `identidade` na hora do envio — e
    é isso que permite este fato circular pela plataforma inteira sem espalhar o
    e-mail de ninguém.
    """
    with transaction.atomic():
        carta = eventos.passo_de_jornada_devido(
            site_id=SITE,
            destinatario_id=PESSOA,
            jornada_slug="boas-vindas",
            passo_id="22222222-2222-2222-2222-222222222222",
            ordem=1,
            origem_event_id=EVENTO_DE_ORIGEM,
        )

    cru = json.dumps(carta.payload, ensure_ascii=False).lower()
    for proibido in ("@", "email", "e-mail", "telefone", "whatsapp", "nome"):
        assert proibido not in cru, f"a carta carrega {proibido!r}: {cru}"


def test_o_texto_da_mensagem_NAO_viaja_na_carta():
    """O modelo híbrido do §8.7.1: o sino BUSCA o texto pelo `passo_id`.

    Um passo reescrito deixaria avisos antigos mostrando a frase velha para
    sempre — e o mantenedor VAI reescrever, porque a tela dele existe para isso.
    """
    with transaction.atomic():
        carta = eventos.passo_de_jornada_devido(
            site_id=SITE,
            destinatario_id=PESSOA,
            jornada_slug="boas-vindas",
            passo_id="33333333-3333-3333-3333-333333333333",
            ordem=1,
            origem_event_id=EVENTO_DE_ORIGEM,
        )

    assert set(carta.payload["parametros"]) == {"jornada_slug", "passo_id", "ordem"}


# ---------------------------------------------------------------------------
# O DESPACHANTE
# ---------------------------------------------------------------------------


def test_o_despachante_recusa_os_canais_que_ainda_nao_sabe_entregar():
    """A recusa continua sendo recusa — mudou COMO ela é dita, e por quê.

    Até 02/09/2026 este teste afirmava `is False`. `False` quer dizer *"falhei
    AGORA"*, e o motor o trata como transitório: o passo continua devendo e a
    passada seguinte tenta de novo. Só que *"esta versão da plataforma não
    entrega por aqui"* nunca deixa de ser verdade sozinha — dizê-lo com `False`
    prendia a inscrição no passo para sempre (`armadilhas/283`).

    O que este teste continua garantindo, e é o essencial: **nenhuma carta sai**
    por um canal que a plataforma não entrega.
    """
    jornada = uma_jornada_pronta(canais=("sino", "email", "whatsapp"))
    inscricao = inscrita(jornada)
    passo = inscricao.jornada_versao.passos.get()

    with transaction.atomic():
        for canal in ("email", "whatsapp"):
            with pytest.raises(motor.CanalNaoSuportado, match=canal):
                despacho.despachar(inscricao, passo, canal)
    assert not OutboxEvent.objects.exists()


def test_sem_origem_conhecida_a_carta_nao_sai():
    """Fail-closed. `origem_event_id` é o que torna o aviso RASTREÁVEL: de
    qualquer aviso na tela se chega ao acontecimento que o causou. Inventar um
    valor deixaria uma pista que não leva a lugar nenhum."""
    jornada = uma_jornada_pronta()
    inscricao = inscrita(jornada, origem=None)
    passo = inscricao.jornada_versao.passos.get()

    with transaction.atomic():
        assert despacho.despachar(inscricao, passo, "sino") is False
    assert not OutboxEvent.objects.exists()


# ---------------------------------------------------------------------------
# A CARTA E A LINHA DE "SAIU" VIVEM OU MORREM JUNTAS
# ---------------------------------------------------------------------------


def test_o_motor_publica_a_carta_e_registra_a_entrega():
    jornada = uma_jornada_pronta()
    inscricao = inscrita(jornada)

    passada = motor.varrer(momento=quando(15), despachar=despacho.despachar)

    assert passada.entregues == 1
    assert passada.sem_despacho == 0

    carta = OutboxEvent.objects.get()
    assert carta.event == "notificacao.devida"
    assert carta.payload["destinatario_id"] == PESSOA
    assert carta.payload["parametros"]["jornada_slug"] == "boas-vindas"
    assert carta.envelope_extra == {"ator_id": None}

    entrega = Entrega.objects.get()
    assert entrega.resultado == "enviada"
    assert entrega.enviado_em is not None

    inscricao.refresh_from_db()
    assert inscricao.estado == "concluida"


def test_se_a_entrega_nao_puder_ser_gravada_a_carta_tambem_nao_sai():
    """A transação comum, medida.

    Sem ela, o aviso chega ao sininho e o motor acha que não entregou — e a
    passada seguinte manda de novo, com um `event_id` NOVO que a dedup do
    sininho não tem como pegar. Duas cartas iguais na caixa da mesma pessoa.
    """
    jornada = uma_jornada_pronta()
    inscrita(jornada)

    with patch.object(regua, "registrar", side_effect=RuntimeError("banco caiu")):
        with pytest.raises(RuntimeError):
            motor.varrer(momento=quando(15), despachar=despacho.despachar)

    assert not OutboxEvent.objects.exists(), "a carta sobreviveu ao rollback"
    assert not Entrega.objects.exists()


# ---------------------------------------------------------------------------
# O RELAY
# ---------------------------------------------------------------------------


def test_a_carta_chega_ao_stream_logo_depois_do_commit():
    """O `on_commit` é o que dá latência sub-segundo sem furar a outbox.

    Este teste começou errado: ele chamava `relay_outbox()` esperando publicar, e
    recebia zero. Não era defeito — a carta JÁ tinha sido publicada pelo
    `on_commit`, que é exatamente o comportamento desejado. O teste passou a
    medir o que acontece de verdade.
    """
    cliente = redis.from_url(os.environ["REDIS_STREAMS_URL"])
    stream = "eventos.notificacao.devida"
    antes = cliente.xlen(stream)

    jornada = uma_jornada_pronta()
    inscrita(jornada)
    motor.varrer(momento=quando(15), despachar=despacho.despachar)

    assert cliente.xlen(stream) == antes + 1
    assert OutboxEvent.objects.get().published_at is not None

    # E o relay é seguro de chamar a qualquer momento: linha já publicada não
    # volta ao fio.
    assert tasks.relay_outbox() == 0
    assert cliente.xlen(stream) == antes + 1


def test_o_relay_leva_a_carta_que_ficou_pendente():
    """A rede de segurança: Redis fora do ar na hora do commit não perde carta.

    Aqui a carta nasce SEM o `on_commit` (é o que acontece quando aquele publish
    falha e o `except` largo o engole): ela fica com `published_at=None`, e a
    passada periódica do worker a leva.
    """
    cliente = redis.from_url(os.environ["REDIS_STREAMS_URL"])
    stream = "eventos.notificacao.devida"
    antes = cliente.xlen(stream)

    with transaction.atomic():
        eventos.passo_de_jornada_devido(
            site_id=SITE,
            destinatario_id=PESSOA,
            jornada_slug="boas-vindas",
            passo_id="44444444-4444-4444-4444-444444444444",
            ordem=1,
            origem_event_id=EVENTO_DE_ORIGEM,
        )

    assert OutboxEvent.objects.get().published_at is None
    assert tasks.relay_outbox() == 1
    assert cliente.xlen(stream) == antes + 1
    assert OutboxEvent.objects.get().published_at is not None
    assert tasks.relay_outbox() == 0


def test_o_envelope_no_fio_tem_a_identidade_da_carta():
    jornada = uma_jornada_pronta()
    inscrita(jornada)
    motor.varrer(momento=quando(15), despachar=despacho.despachar)

    cliente = redis.from_url(os.environ["REDIS_STREAMS_URL"])
    stream = "eventos.notificacao.devida"

    ultima = cliente.xrevrange(stream, count=1)[0][1]
    envelope = json.loads(ultima[b"json"])

    assert envelope["event"] == "notificacao.devida"
    assert envelope["version"] == 1
    assert envelope["ator_id"] is None
    assert envelope["data"]["assunto"] == "jornada.passo"
    assert "occurred_at" in envelope and "event_id" in envelope


def test_envelope_extra_nao_pode_trocar_a_identidade_da_carta():
    """Um `**extra` solto sobrescreveria o que veio antes, e a carta chegaria ao
    consumidor errado — em silêncio. Aqui isso é erro e para a publicação."""
    with transaction.atomic():
        eventos.emitir(
            "notificacao.devida",
            {"qualquer": "coisa"},
            envelope_extra={"event": "outro.evento.qualquer"},
        )

    with pytest.raises(ValueError, match="sobrescrever"):
        tasks.relay_outbox()
