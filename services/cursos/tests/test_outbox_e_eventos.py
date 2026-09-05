"""O envelope que sai no fio casa com o CONTRATO CONGELADO, e a outbox não perde
nem duplica.

Os dois `contracts/eventos/{envio.recebido,revisao.prazo-estourado}.v1.json`
foram escritos em papel em 04/09/2026, antes de a célula emiti-los. Um contrato
que ninguém executa é documento: envelhece em silêncio, e a divergência só
aparece na `mensageria` ou na `metricas`, semanas depois, como um `KeyError`.

**O schema é LIDO do arquivo, nunca copiado para dentro deste teste.** Uma
cópia aqui seria uma segunda verdade sobre o contrato.

**E o guarda MORDE**: os contratos são `additionalProperties: false`, então um
`link` que alguém acrescente ao `data` "para o consumidor não precisar
perguntar" reprova o CI. Só ids opacos viajam.

Molde: `services/sugestoes/tests/test_inv_envelope_casa_com_contrato.py`.
"""

from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from django.urls import reverse
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from apps.cursos import envio as checkpoint
from apps.cursos import eventos
from apps.cursos.models import OutboxEvent
from apps.cursos.tasks import relay_outbox
from tests.conftest import ARQUIVO, AUTOAVALIACAO, COOKIE, README, entrega

pytestmark = pytest.mark.django_db

CONTRATOS = Path(__file__).resolve().parents[3] / "contracts" / "eventos"
FORMULARIO = {"arquivo": ARQUIVO, "readme": README, "autoavaliacao": AUTOAVALIACAO}


def _validador(evento: str, versao: int) -> Draft202012Validator:
    """O contrato do PAR evento+versão: a versão sai do envelope, nunca daqui."""
    schema = json.loads(
        (CONTRATOS / f"{evento}.v{versao}.json").read_text(encoding="utf-8")
    )
    # `FormatChecker` é o que faz `format: uuid` deixar de ser anotação e passar
    # a recusar valor.
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _conferir(envelope: dict) -> None:
    _validador(envelope["event"], envelope["version"]).validate(envelope)
    # `date-time` não está entre os checkers que o jsonschema traz sem
    # dependência extra; o guarda o confere aqui.
    datetime.fromisoformat(envelope["occurred_at"])


@pytest.fixture
def no_fio(ana_pronta, fio):
    """Os dois fatos provocados de verdade (a entrega e o estouro), e o que o
    relay REALMENTE publicou."""
    envio = checkpoint.entregar(ana_pronta, **entrega())
    checkpoint.registrar_estouros(envio.prazo_em + timedelta(hours=1, minutes=30))
    assert relay_outbox() == 2
    fio.envio = envio
    return fio


# ------------------------------------------------ o guarda não passa no vazio
def test_os_dois_contratos_existem():
    assert (CONTRATOS / "envio.recebido.v1.json").is_file()
    assert (CONTRATOS / "revisao.prazo-estourado.v1.json").is_file()


# ------------------------------------------------ os dois envelopes
def test_os_dois_envelopes_validam_contra_o_contrato_congelado(no_fio):
    assert len(no_fio.mensagens) == 2
    for _, envelope in no_fio.mensagens:
        _conferir(envelope)


def test_o_nome_do_stream_e_eventos_ponto_evento_e_a_versao_vai_no_envelope(no_fio):
    assert no_fio.streams == [
        "eventos.envio.recebido",
        "eventos.revisao.prazo-estourado",
    ]
    assert {(e["event"], e["version"]) for _, e in no_fio.mensagens} == {
        ("envio.recebido", 1),
        ("revisao.prazo-estourado", 1),
    }


def test_o_envio_recebido_leva_o_aluno_no_envelope_e_so_ids_no_data(no_fio):
    envelope = no_fio.um_envelope("envio.recebido")
    envio = no_fio.envio
    assert envelope["ator_id"] == "p_ana"
    assert envelope["data"] == {
        "site_id": "escola-a",
        "curso_id": str(envio.aula.curso_id),
        "aula_id": str(envio.aula_id),
        "envio_id": str(envio.pk),
        "numero": 1,
    }


def test_o_prazo_estourado_leva_ator_nulo_presente_e_as_horas_de_atraso(no_fio):
    envelope = no_fio.um_envelope("revisao.prazo-estourado")
    assert "ator_id" in envelope and envelope["ator_id"] is None
    assert envelope["data"] == {
        "site_id": "escola-a",
        "envio_id": str(no_fio.envio.pk),
        "horas_de_atraso": 1,
    }


# ------------------------------------------------ a privacidade, e o guarda morde
def test_nenhum_envelope_carrega_link_texto_nem_nome(no_fio):
    for _, envelope in no_fio.mensagens:
        cru = json.dumps(envelope, ensure_ascii=False)
        for vazamento in (ARQUIVO, "https://", README, AUTOAVALIACAO, "Ana", "@"):
            assert vazamento not in cru, f"{vazamento!r} vazou em {envelope['event']}"


@pytest.mark.parametrize("evento", ["envio.recebido", "revisao.prazo-estourado"])
def test_um_campo_a_mais_no_data_e_recusado(no_fio, evento):
    envelope = copy.deepcopy(no_fio.um_envelope(evento))
    _conferir(envelope)  # o de verdade passa...
    envelope["data"]["link"] = ARQUIVO
    with pytest.raises(ValidationError) as recusa:
        _conferir(envelope)  # ...e o com um campo a mais, não
    assert "link" in str(recusa.value)


def test_o_envio_recebido_sem_ator_ou_com_ator_nulo_e_recusado(no_fio):
    """O contrato exige o aluno no envelope: é o único lugar em que ele viaja."""
    sem = copy.deepcopy(no_fio.um_envelope("envio.recebido"))
    del sem["ator_id"]
    with pytest.raises(ValidationError):
        _conferir(sem)
    nulo = copy.deepcopy(no_fio.um_envelope("envio.recebido"))
    nulo["ator_id"] = None
    with pytest.raises(ValidationError):
        _conferir(nulo)


def test_o_prazo_estourado_sem_a_chave_ator_id_e_recusado(no_fio):
    """Nulo é informação; ausente é outra coisa, e o contrato não a aceita."""
    envelope = copy.deepcopy(no_fio.um_envelope("revisao.prazo-estourado"))
    del envelope["ator_id"]
    with pytest.raises(ValidationError):
        _conferir(envelope)


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
