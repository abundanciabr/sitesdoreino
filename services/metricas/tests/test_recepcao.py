"""Teste-guarda da recepção: o que entra no livro, e o que não entra.

O que estes guardas protegem (degrau 7.3, `AGENTS.metricas.md`):

1. **Envelope bom vira fato**, com o dia de São Paulo e a célula derivada.
2. **`receber` nunca levanta.** Todo corpo possível termina em fato guardado
   ou em evento morto, e o evento morto guarda o corpo cru e o motivo.
3. **Reentrega não conta duas vezes**, e o desfecho diz isso sem mentir que
   guardou de novo.
4. **Assunto desconhecido é fato**, não erro: esta célula é um livro, não um
   contador de assuntos previstos.
5. **O consumidor assina só o que tem contrato congelado e alguém publica.**

A régua deste arquivo é a lista de modos de falha de um corpo que chega pela
rede: não é UTF-8, não é JSON, é JSON mas não é objeto, faltam chaves, o id não
é UUID, a versão é texto, a data é ilegível, a data não tem fuso, `data` não é
objeto, falta `site_id`. Cada um tem um caso, porque cada um deles já foi, em
alguma casa, a linha que derrubou um consumidor às três da manhã.
"""

from __future__ import annotations

import json
import uuid

import pytest

from apps.fatos.models import Evento, EventoMorto
from apps.fatos.recepcao import GUARDADO, JA_TINHA, MORTO, receber

pytestmark = pytest.mark.django_db

# 01h de UTC do dia 1º: ainda é dia 30 em São Paulo.
NA_VIRADA = "2026-10-01T01:00:00+00:00"


def envelope(**sobre) -> str:
    corpo = {
        "event": "identidade.pessoa-cadastrada",
        "version": 1,
        "event_id": str(uuid.uuid4()),
        "occurred_at": NA_VIRADA,
        "data": {"site_id": "meshcraft", "pessoa_id": "id-opaco-1"},
    }
    corpo.update(sobre)
    return json.dumps(corpo)


def test_envelope_bom_vira_fato():
    desfecho, evento = receber(envelope())
    assert desfecho == GUARDADO
    assert evento.tipo == "identidade.pessoa-cadastrada"
    assert evento.celula == "identidade"
    assert evento.site_id == "meshcraft"
    assert str(evento.dia) == "2026-09-30", "01h UTC ainda é o dia anterior aqui"
    assert evento.dados["pessoa_id"] == "id-opaco-1"
    assert EventoMorto.objects.count() == 0


def test_bytes_tambem_servem():
    """É assim que a mensagem chega do Redis: bytes no campo `json`."""
    desfecho, _ = receber(envelope().encode("utf-8"))
    assert desfecho == GUARDADO


def test_reentrega_nao_conta_duas_vezes():
    corpo = envelope()
    assert receber(corpo)[0] == GUARDADO
    desfecho, evento = receber(corpo)
    assert desfecho == JA_TINHA, "o desfecho não mente que guardou de novo"
    assert Evento.objects.count() == 1
    assert evento is not None, "e devolve o fato que já estava lá"


def test_assunto_desconhecido_e_fato():
    """Um livro guarda o que ainda não sabe usar; um contador, não."""
    desfecho, evento = receber(envelope(event="encomenda.aprovada"))
    assert desfecho == GUARDADO
    assert evento.celula == "encomendas" or evento.celula == "encomenda"
    assert Evento.objects.count() == 1


@pytest.mark.parametrize(
    "corpo, trecho_do_motivo",
    [
        (b"\xff\xfe isto nao e utf-8", "UTF-8"),
        ("isto não é json", "não é JSON válido"),
        ("[1, 2, 3]", "não é um objeto"),
        (json.dumps({"event": "x.y"}), "faltam chaves"),
        (envelope(event_id="nao-e-uuid"), "UUID"),
        (envelope(event="semponto"), "celula.assunto"),
        (envelope(version="um"), "inteiro"),
        (envelope(version=0), "inteiro"),
        (envelope(occurred_at="ontem"), "legível"),
        (envelope(occurred_at="2026-10-01T01:00:00"), "sem fuso"),
        (envelope(data="não é objeto"), "`data` não é um objeto"),
        (envelope(data={"pessoa_id": "x"}), "site_id"),
    ],
)
def test_todo_corpo_torto_vira_evento_morto_e_nunca_levanta(corpo, trecho_do_motivo):
    desfecho, morto = receber(corpo)
    assert desfecho == MORTO
    assert trecho_do_motivo in morto.motivo, morto.motivo
    assert morto.corpo, "o corpo cru é a prova do que chegou"
    assert Evento.objects.count() == 0, "meio fato nunca entra no livro"


def test_o_evento_morto_guarda_o_que_deu_para_ler_do_envelope():
    """Para quem for inspecionar: o tipo e o id, quando existirem."""
    id_ = str(uuid.uuid4())
    _, morto = receber(envelope(event_id=id_, occurred_at="ontem"))
    assert morto.tipo_declarado == "identidade.pessoa-cadastrada"
    assert morto.event_id_declarado == id_
    assert morto.estado == EventoMorto.Estado.NOVO


def test_corpo_sem_nada_legivel_ainda_vira_morto():
    """Nem tipo nem id: os campos ficam vazios, e não são chave de nada."""
    _, morto = receber("{")
    assert morto.tipo_declarado == "" and morto.event_id_declarado == ""


# ----------------------------------------------------- o consumidor de streams


def test_o_consumidor_assina_so_o_que_tem_contrato_e_alguem_publica():
    """Stream sem publicador vira grupo de consumo vazio e ilusão de pronto.

    E stream sem contrato congelado seria fato construído sobre areia: o
    formato pode mudar sem aviso. `matricula.situacao-alterada` era o assunto
    que esta célula mais queria e entrou em 05/09/2026 (degrau 8), quando as
    duas condicoes passaram a valer: contrato congelado no PR #1076 e a
    `alunos` publicando de verdade no PR #1080.
    """
    from pathlib import Path

    from apps.fatos.management.commands.consume_eventos import GRUPO, STREAMS

    assert GRUPO == "metricas"
    contratos = Path(__file__).resolve().parents[3] / "contracts" / "eventos"
    assert contratos.is_dir(), contratos
    for stream in STREAMS:
        assunto = stream.removeprefix("eventos.")
        assert list(
            contratos.glob(f"{assunto}.v*.json")
        ), f"{assunto} não tem contrato congelado em contracts/eventos/"
    # Estava FORA ate 05/09/2026, e a linha vivia aqui como marcador da
    # divida. Agora e o contrario, e continua sendo uma afirmacao: se alguem
    # remover o assunto da lista, o livro para de saber quem virou aluna e
    # ninguem descobre olhando a tela.
    assert "eventos.matricula.situacao-alterada" in STREAMS


def test_o_lote_de_reentrega_nao_diverge_das_outras_celulas():
    """Números iguais aos das outras consumidoras: divergir é impedir comparação."""
    from apps.fatos.management.commands import consume_eventos as c

    assert c.IDLE_MS_REENTREGA == 60_000
    assert c.MAX_ENTREGAS == 5
    assert c.LOTE_REENTREGA == 10
