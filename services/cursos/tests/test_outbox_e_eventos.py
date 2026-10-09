"""O envelope que sai no fio leva o que deve levar, e a outbox não perde nem
duplica. Curso e aula viajam pelos campos confirmados do modelo, sem dados do aluno.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest
from django.urls import reverse

from apps.cursos import envio as checkpoint
from apps.cursos import eventos
from apps.cursos import laudo as parecer
from apps.cursos.models import Laudo, OutboxEvent
from apps.cursos.tasks import relay_outbox
from tests.conftest import (
    ARQUIVO,
    AUTOAVALIACAO,
    COOKIE,
    README,
    entrega,
    forcas_validas,
    mudanca_valida,
    notas_validas,
)

pytestmark = pytest.mark.django_db

FORMULARIO = {"arquivo": ARQUIVO, "readme": README, "autoavaliacao": AUTOAVALIACAO}


@pytest.fixture
def no_fio(ana_pronta, fio):
    """Os dois fatos provocados de verdade (a entrega e o estouro), e o que o
    relay REALMENTE publicou."""
    envio = checkpoint.entregar(ana_pronta, **entrega())
    checkpoint.registrar_estouros(envio.prazo_em + timedelta(hours=1, minutes=30))
    assert relay_outbox() == 2
    fio.envio = envio
    return fio


# ------------------------------------------------ os dois envelopes
def test_o_nome_do_stream_e_eventos_ponto_evento_e_a_versao_vai_no_envelope(no_fio):
    assert no_fio.streams == [
        "eventos.envio.recebido",
        "eventos.revisao.prazo-estourado",
    ]
    assert {(e["event"], e["version"]) for _, e in no_fio.mensagens} == {
        ("envio.recebido", 1),
        ("revisao.prazo-estourado", 1),
    }


def test_o_envio_recebido_leva_aluno_e_contexto_real_do_curso(no_fio):
    envelope = no_fio.um_envelope("envio.recebido")
    envio = no_fio.envio
    assert envelope["ator_id"] == "p_ana"
    assert envelope["data"] == {
        "site_id": "escola-a",
        "curso_id": str(envio.aula.curso_id),
        "aula_id": str(envio.aula_id),
        "envio_id": str(envio.pk),
        "numero": 1,
        "produto_id": envio.aula.curso.produto_id,
        "curso_nome": envio.aula.curso.nome,
        "curso_slug": envio.aula.curso.slug,
        "aula_titulo": envio.aula.titulo_exibido,
        "aula_numero": envio.aula.numero,
    }
    assert envelope["data"]["produto_id"] != envelope["data"]["curso_id"]


def test_o_prazo_estourado_leva_ator_nulo_presente_e_as_horas_de_atraso(no_fio):
    envelope = no_fio.um_envelope("revisao.prazo-estourado")
    assert "ator_id" in envelope and envelope["ator_id"] is None
    assert envelope["data"] == {
        "site_id": "escola-a",
        "envio_id": str(no_fio.envio.pk),
        "horas_de_atraso": 1,
    }


# ------------------------------------------------ a privacidade
def test_nenhum_envelope_carrega_link_texto_nem_nome(no_fio):
    for _, envelope in no_fio.mensagens:
        cru = json.dumps(envelope, ensure_ascii=False)
        for vazamento in (ARQUIVO, "https://", README, AUTOAVALIACAO, "Ana", "@"):
            assert vazamento not in cru, f"{vazamento!r} vazou em {envelope['event']}"


# ------------------------------------------------ a outbox
def test_o_relay_marca_published_at_e_nao_republica(ana_pronta, fio):
    checkpoint.entregar(ana_pronta, **entrega())
    assert relay_outbox() == 1
    assert OutboxEvent.objects.get().published_at is not None
    assert relay_outbox() == 0
    assert len(fio.mensagens) == 1


@pytest.mark.django_db(transaction=True)
def test_depois_do_commit_o_relay_publica_sozinho(aluna, ana_pronta, client, fio):
    """O `on_commit` de `eventos.emitir` (`armadilhas/057`: só com
    `transaction=True` o commit acontece e o relay dispara)."""
    resposta = client.post(
        reverse("entregar-checkpoint", args=["E00"]), FORMULARIO, HTTP_COOKIE=COOKIE
    )
    assert resposta.status_code == 302
    assert fio.streams == ["eventos.envio.recebido"]
    assert OutboxEvent.objects.get().published_at is not None


@pytest.mark.django_db(transaction=True)
def test_sem_redis_o_evento_fica_pendente_e_a_entrega_nao_quebra(
    aluna, ana_pronta, client, monkeypatch
):
    monkeypatch.delenv("REDIS_STREAMS_URL", raising=False)
    resposta = client.post(
        reverse("entregar-checkpoint", args=["E00"]), FORMULARIO, HTTP_COOKIE=COOKIE
    )
    assert resposta.status_code == 302
    assert "recado=entregue" in resposta["Location"]
    evento = OutboxEvent.objects.get()
    assert evento.published_at is None, "o evento ficou pendente, não perdido"


@pytest.mark.django_db(transaction=True)
def test_emitir_fora_de_transacao_e_recusado():
    with pytest.raises(eventos.EventoForaDaTransacao):
        eventos.emitir("envio.recebido", {"site_id": "escola-a"})
    assert OutboxEvent.objects.count() == 0


# ---------------------------------------------------------------------------
# Os três eventos do laudo (degrau 2.2, TAR-156): esta célula é quem os emite.
# ---------------------------------------------------------------------------


def _emitir(envio, professora, **mudancas):
    base = dict(
        avaliador=professora,
        papel=Laudo.Papel.PROFESSOR,
        notas=notas_validas(),
        forcas=forcas_validas(),
        mudanca=mudanca_valida(envio.aula),
        decisao=Laudo.Decisao.ABERTO,
        sabe_o_que_fazer_amanha=True,
    )
    base.update(mudancas)
    return parecer.emitir(envio, **base)


@pytest.fixture
def no_fio_aberto(envio_na_fila, professora, fio):
    """`aberto`: publica `envio.recebido.v1` (de `envio_na_fila`),
    `laudo.emitido.v1` e `aula.concluida.v1` — os três pendentes na outbox."""
    _emitir(envio_na_fila, professora, decisao=Laudo.Decisao.ABERTO)
    assert relay_outbox() == 3
    return fio


@pytest.fixture
def no_fio_devolvido(envio_na_fila, professora, fio):
    """`devolvido`: publica `envio.recebido.v1`, `laudo.emitido.v1` e
    `checkpoint.devolvido.v1`."""
    amanha = datetime.now().date() + timedelta(days=1)
    _emitir(
        envio_na_fila,
        professora,
        decisao=Laudo.Decisao.DEVOLVIDO,
        data_de_retorno=amanha,
    )
    assert relay_outbox() == 3
    return fio


def test_aberto_publica_o_envio_o_laudo_e_a_aula_concluida(no_fio_aberto):
    assert set(no_fio_aberto.streams) == {
        "eventos.envio.recebido",
        "eventos.laudo.emitido",
        "eventos.aula.concluida",
    }


def test_devolvido_publica_o_envio_o_laudo_e_o_checkpoint_devolvido(no_fio_devolvido):
    assert set(no_fio_devolvido.streams) == {
        "eventos.envio.recebido",
        "eventos.laudo.emitido",
        "eventos.checkpoint.devolvido",
    }


def test_laudo_emitido_leva_o_avaliador_no_envelope_e_so_ids_no_data(
    no_fio_aberto, envio_na_fila, professora
):
    envelope = no_fio_aberto.um_envelope("laudo.emitido")
    assert envelope["ator_id"] == professora.id_da_plataforma
    assert envelope["data"] == {
        "site_id": "escola-a",
        "envio_id": str(envio_na_fila.pk),
        "laudo_id": str(Laudo.objects.get().pk),
        "decisao": "aberto",
        "avaliador_papel": "professor",
    }


def test_aula_concluida_leva_o_aluno_e_contexto_real_da_aula(no_fio_aberto, envio_na_fila):
    envelope = no_fio_aberto.um_envelope("aula.concluida")
    assert envelope["ator_id"] == envio_na_fila.pessoa_id
    assert envelope["data"] == {
        "site_id": "escola-a",
        "curso_id": str(envio_na_fila.aula.curso_id),
        "aula_id": str(envio_na_fila.aula_id),
        "e_boss": envio_na_fila.aula.e_boss,
        "produto_id": envio_na_fila.aula.curso.produto_id,
        "curso_nome": envio_na_fila.aula.curso.nome,
        "curso_slug": envio_na_fila.aula.curso.slug,
        "aula_titulo": envio_na_fila.aula.titulo_exibido,
        "aula_numero": envio_na_fila.aula.numero,
    }


def test_checkpoint_devolvido_leva_a_data_de_retorno(no_fio_devolvido, envio_na_fila):
    envelope = no_fio_devolvido.um_envelope("checkpoint.devolvido")
    laudo = Laudo.objects.get()
    assert envelope["data"] == {
        "site_id": "escola-a",
        "aula_id": str(envio_na_fila.aula_id),
        "envio_id": str(envio_na_fila.pk),
        "data_de_retorno": laudo.data_de_retorno.isoformat(),
    }


def test_aberto_nunca_leva_checkpoint_devolvido(no_fio_aberto):
    assert "eventos.checkpoint.devolvido" not in no_fio_aberto.streams


def test_devolvido_nunca_leva_aula_concluida(no_fio_devolvido):
    assert "eventos.aula.concluida" not in no_fio_devolvido.streams


def test_nenhum_envelope_do_laudo_carrega_nome_frase_ou_id_do_instrumento(
    no_fio_aberto,
):
    for _, envelope in no_fio_aberto.mensagens:
        cru = json.dumps(envelope, ensure_ascii=False)
        for vazamento in (
            "As bordas ficaram consistentes",
            "O bevel das arestas",
            "Praticar UV",
            "Dani",
        ):
            assert vazamento not in cru, f"{vazamento!r} vazou em {envelope['event']}"
