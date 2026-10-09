import uuid

import pytest

from apps.cursos import faixas_carga
from apps.cursos.eventos import event_id_item_criado
from apps.cursos.models import Projeto3D, OutboxEvent
from tests.conftest import ANA
from tests.test_praticas_3d import enviar, pratica  # noqa: F401

pytestmark = pytest.mark.django_db
EV = "cursos.item-criado"


def test_criacao_emite_um_evento_e_atualizacao_nao(pratica, client):
    a, _ = pratica
    pid = uuid.uuid4()
    assert enviar(client, a, pid).status_code == 200
    ev = OutboxEvent.objects.filter(event=EV)
    assert ev.count() == 1
    e = ev.get()
    assert e.event_id == event_id_item_criado(pid)
    d = e.payload
    assert d["historico"] is False and d["item_id"] == str(pid)
    assert d["pessoa_id"] == ANA["id"] and d["site_id"] == a.aula.curso.site_id
    assert enviar(client, a, pid, 1, "#ff0000").status_code == 200
    assert OutboxEvent.objects.filter(event=EV).count() == 1


def test_carga_so_primeiro_item_e_nao_duplica(pratica, client):
    a, _ = pratica
    assert enviar(client, a).status_code == 200
    assert enviar(client, a).status_code == 200
    assert OutboxEvent.objects.filter(event=EV).count() == 2
    OutboxEvent.objects.all().delete()
    assert faixas_carga.carregar(Projeto3D, OutboxEvent) == 1
    assert faixas_carga.carregar(Projeto3D, OutboxEvent) == 0
    e = OutboxEvent.objects.get(event=EV)
    assert e.payload["historico"] is True
    assert e.event_id == event_id_item_criado(e.payload["item_id"])
