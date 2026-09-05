"""A fila de revisão é uma CONSULTA, e o relógio do prazo registra o estouro
uma vez só.

Lei: `PLANO-CELULA-CURSOS.md` §4 ("a fila de revisão não é tabela: é a
consulta dos envios em `recebido` ou `em_revisao`, ordenados por `prazo_em`,
os vencidos primeiro") e §5 (`revisao.prazo-estourado.v1`).

O que este arquivo protege:

1. **A fila** devolve só `recebido` e `em_revisao`, por prazo, os vencidos
   primeiro; e é por site.
2. **`registrar_estouros`** grava `estourado_em = agora` em todo envio da fila
   cujo prazo passou e emite o evento com as horas completas de atraso, no
   mínimo 1; a segunda passada não registra nem emite de novo (idempotente
   pelo filtro); envio já aberto não estoura; o estourado continua na fila, e
   na frente.
3. **O tique** (`tasks.bater_o_tique`) lê o relógio e chama o registro; o
   relay e o tique são os dois batimentos do worker, e não há timer agendado
   por envio.

Os envios aqui nascem com `enviado_em` no PASSADO relativo ao relógio real
(`timezone.now() - horas`), nunca num instante fixo: `estourado_em` é comparado
com `prazo_em` no banco, e instante fixo contra relógio real é bomba-relógio
(`armadilhas/323`).
"""

from __future__ import annotations

import re
from datetime import timedelta
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.cursos import envio as checkpoint
from apps.cursos import tasks
from apps.cursos.models import Curso, Envio, OutboxEvent, Pessoa
from tests.conftest import publicar

pytestmark = pytest.mark.django_db

H = timedelta(hours=1)
CELULA = Path(__file__).resolve().parent.parent / "apps" / "cursos"


def envio_de(pessoa, aula, *, ha: timedelta, estado=Envio.Estado.RECEBIDO) -> Envio:
    """Um envio feito há `ha`, pelo relógio real."""
    return Envio.objects.create(
        pessoa=pessoa,
        aula=aula,
        numero=1,
        enviado_em=timezone.now() - ha,
        estado=estado,
        links=[{"rotulo": "Arquivo", "url": "https://arquivos.exemplo.test/a"}],
        readme="x",
        laudo_do_aluno={"texto": "x"},
    )


@pytest.fixture
def fila(aula_publicada):
    """Quatro envios na E00, de quatro pessoas: dois vencidos (um `recebido`, um
    `em_revisao`), um no prazo, e um já aberto pelo laudo."""
    pessoas = {
        nome: Pessoa.objects.create(id_da_plataforma=f"p_{nome}", nome_exibido=nome)
        for nome in ("ana", "beto", "carla", "dudu")
    }
    return {
        "ana_30h": envio_de(pessoas["ana"], aula_publicada, ha=30 * H),
        "beto_2h": envio_de(pessoas["beto"], aula_publicada, ha=2 * H),
        "carla_26h_em_revisao": envio_de(
            pessoas["carla"], aula_publicada, ha=26 * H, estado=Envio.Estado.EM_REVISAO
        ),
        "dudu_50h_aberto": envio_de(
            pessoas["dudu"], aula_publicada, ha=50 * H, estado=Envio.Estado.ABERTO
        ),
    }


# ------------------------------------------------ 1. a fila
def test_a_fila_devolve_recebidos_e_em_revisao_por_prazo_vencidos_primeiro(fila):
    assert list(checkpoint.fila_de_revisao("escola-a")) == [
        fila["ana_30h"],
        fila["carla_26h_em_revisao"],
        fila["beto_2h"],
    ]


def test_a_fila_e_por_site(fila):
    call_command("semear_esqueleto", site="escola-b", stdout=StringIO())
    aula_b = publicar(Curso.objects.get(site_id="escola-b").aulas.get(numero="E00"))
    de_b = envio_de(Pessoa.objects.get(pk="p_ana"), aula_b, ha=40 * H)
    assert list(checkpoint.fila_de_revisao("escola-b")) == [de_b]
    assert de_b not in checkpoint.fila_de_revisao("escola-a")
    assert checkpoint.fila_de_revisao("escola-a").count() == 3


# ------------------------------------------------ 2. o estouro
def test_registrar_estouros_registra_estourado_em_e_emite_uma_vez(fila):
    agora = timezone.now()
    assert checkpoint.registrar_estouros(agora) == (
        fila["ana_30h"].pk,
        fila["carla_26h_em_revisao"].pk,
    )
    for chave in ("ana_30h", "carla_26h_em_revisao"):
        assert Envio.objects.get(pk=fila[chave].pk).estourado_em == agora
    for chave in ("beto_2h", "dudu_50h_aberto"):
        assert Envio.objects.get(pk=fila[chave].pk).estourado_em is None

    eventos = list(
        OutboxEvent.objects.filter(event="revisao.prazo-estourado").order_by("id")
    )
    assert [(e.payload["envio_id"], e.payload["horas_de_atraso"]) for e in eventos] == [
        (str(fila["ana_30h"].pk), 6),
        (str(fila["carla_26h_em_revisao"].pk), 2),
    ]
    assert all(e.payload["site_id"] == "escola-a" for e in eventos)
    assert all(e.envelope_extra == {"ator_id": None} for e in eventos)

    # A segunda passada, uma hora depois: nada a registrar, nada a emitir, e o
    # estouro registrado fica com a hora da primeira.
    assert checkpoint.registrar_estouros(agora + H) == ()
    assert OutboxEvent.objects.filter(event="revisao.prazo-estourado").count() == 2
    assert Envio.objects.get(pk=fila["ana_30h"].pk).estourado_em == agora


def test_um_estouro_de_minutos_conta_como_uma_hora(aula_publicada):
    ana = Pessoa.objects.create(id_da_plataforma="p_ana")
    envio = envio_de(ana, aula_publicada, ha=24 * H + timedelta(minutes=10))
    assert checkpoint.registrar_estouros(timezone.now()) == (envio.pk,)
    assert OutboxEvent.objects.get().payload["horas_de_atraso"] == 1


def test_no_instante_exato_do_prazo_ainda_nao_estourou(aula_publicada):
    ana = Pessoa.objects.create(id_da_plataforma="p_ana")
    envio = envio_de(ana, aula_publicada, ha=2 * H)
    assert checkpoint.registrar_estouros(envio.prazo_em) == ()
    assert checkpoint.registrar_estouros(envio.prazo_em + timedelta(seconds=1)) == (
        envio.pk,
    )


def test_o_estourado_continua_na_fila_e_na_frente(fila):
    checkpoint.registrar_estouros(timezone.now())
    assert [e.vencido for e in checkpoint.fila_de_revisao("escola-a")] == [
        True,
        True,
        False,
    ]


# ------------------------------------------------ 3. o tique
def test_o_tique_le_o_relogio_e_registra(fila):
    assert tasks.bater_o_tique() == (
        fila["ana_30h"].pk,
        fila["carla_26h_em_revisao"].pk,
    )
    assert tasks.bater_o_tique() == ()


def test_o_tique_e_o_relay_sao_os_dois_batimentos_e_nao_ha_timer_por_envio():
    from config.huey import huey

    periodicas = sorted(
        nome.rsplit(".", 1)[-1]
        for nome in huey._registry._registry
        if nome.startswith("apps.cursos.tasks.")
    )
    assert periodicas == ["relay_outbox_periodico", "tique_periodico"]

    agendamento = re.compile(r"\.(schedule|delay)\(|\beta=")
    for nome in ("envio.py", "tasks.py", "eventos.py"):
        assert not agendamento.search(
            (CELULA / nome).read_text(encoding="utf-8")
        ), f"{nome} agenda algo por envio: o relógio é reavaliação periódica"
