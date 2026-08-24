# tests/test_relay_outbox.py  # [RECEITA:R5 v1]
"""O relay (R3): o evento tem de CHEGAR ao fio — e o fio de verdade.

Antes deste despacho a Caixa guardava os fatos e não contava a ninguém
(`LICOES.md`). O relay espelha o de `pagamentos`, provado em produção, e o que
este arquivo trava é o que já custou caro em outras células:

- **a ordem do publish** — `xadd` ANTES de marcar `published_at`. Invertida, o
  pior caso deixa de ser "republicar" e passa a ser "perder evento em silêncio"
  (§4.12);
- **o `on_commit`** — e a pegadinha do `django_db` (`armadilhas/057`, §6.5), que
  tem aqui um teste dedicado só para explicar por que o de cima precisa de
  `transaction=True`;
- **o fio do worker** — a task periódica registrada na MESMA instância de Huey
  que `settings.HUEY` entrega ao djhuey (`armadilhas/030`, §4.11). Sem isso o
  `run_huey` sobe de pé e inútil, sem reclamar de nada.
"""

import pytest
from django.conf import settings
from django.urls import reverse

from apps.sugestoes import eventos
from apps.sugestoes.models import OutboxEvent, Sugestao
from apps.sugestoes.tasks import relay_outbox, relay_outbox_periodico

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# A ordem do publish, e a idempotência do relay
# ---------------------------------------------------------------------------


def test_publica_no_stream_ANTES_de_marcar_published_at(caixa, fio):
    """A ordem é o invariante inteiro deste teste.

    Marcar primeiro e publicar depois trocaria o pior caso: em vez de uma
    republicação (que o consumidor deduplica por `event_id`), um processo morto
    entre as duas escritas perderia o evento para sempre, e nada indicaria a
    falta.
    """
    sugestao = caixa.publicar()
    evento = OutboxEvent.objects.get(event=eventos.CRIADA)
    marcado_no_xadd = []
    fio.cliente.xadd.side_effect = lambda stream, campos: marcado_no_xadd.append(
        OutboxEvent.objects.get(pk=evento.pk).published_at
    )

    assert relay_outbox() == 1

    assert marcado_no_xadd == [None]  # no instante do xadd, ainda pendente
    evento.refresh_from_db()
    assert evento.published_at is not None  # e marcado logo depois
    assert str(sugestao.pk) == evento.payload["suggestion_id"]


def test_a_segunda_passada_nao_republica_o_que_ja_foi(caixa, fio):
    """Idempotência do relay: `published_at` preenchido sai do filtro.

    É o que torna seguro chamar `relay_outbox()` de qualquer lugar — o
    `on_commit` de uma requisição, a task periódica do minuto seguinte e um
    `manage.py shell` de emergência podem correr juntos sem duplicar nada.
    """
    caixa.os_quatro_fatos()

    assert relay_outbox() == 4
    assert relay_outbox() == 0

    assert len(fio.mensagens) == 4
    assert not OutboxEvent.objects.filter(published_at__isnull=True).exists()


# ---------------------------------------------------------------------------
# O `on_commit` — e a pegadinha que o faz mentir
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_os_quatro_fatos_chegam_ao_fio_sozinhos_apos_o_commit(caixa, fio):
    """Sem worker, sem chamar o relay na mão: o commit publica.

    `transaction=True` é OBRIGATÓRIO aqui (`armadilhas/057`, §6.5). O
    `django_db` padrão embrulha o teste numa transação que sofre rollback no
    fim — nunca há COMMIT, os callbacks do `on_commit` são descartados e este
    teste passaria sem publicar absolutamente nada. O teste logo abaixo existe
    para provar que essa é a diferença.
    """
    caixa.os_quatro_fatos()

    assert sorted(envelope["event"] for _, envelope in fio.mensagens) == [
        eventos.CRIADA,
        eventos.STATUS_ALTERADO,
        eventos.VOTO_ADICIONADO,
        eventos.VOTO_REMOVIDO,
    ]
    assert not OutboxEvent.objects.filter(published_at__isnull=True).exists()


def test_sem_transaction_true_o_on_commit_nao_dispara_e_o_guarda_mentiria(caixa, fio):
    """Este teste existe para ninguém "simplificar" o de cima.

    Ele roda no `django_db` PADRÃO de propósito: o fato acontece, a outbox
    grava — e nada sai no fio, porque o commit nunca chega. Quem tirar o
    `transaction=True` do guarda acima o deixa verde e vazio; é este teste que
    documenta mecanicamente o porquê (`armadilhas/057`, §6.5).
    """
    caixa.publicar()

    assert OutboxEvent.objects.filter(event=eventos.CRIADA).count() == 1
    assert fio.mensagens == []


# ---------------------------------------------------------------------------
# Redis fora do ar: pendente, nunca perdido — e o aluno nem percebe
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_redis_fora_do_ar_nao_quebra_a_pagina_e_o_evento_fica_pendente(
    caixa, fio, monkeypatch
):
    """O pior caso é atraso, nunca erro na cara de quem escreveu a sugestão.

    O evento fica na outbox com `published_at=None` e é republicado pela rede
    de segurança — a MESMA função que a task periódica do worker roda.
    """
    monkeypatch.setattr(
        "redis.from_url", lambda *a, **k: (_ for _ in ()).throw(OSError("redis caiu"))
    )

    sugestao = caixa.publicar(titulo="Uma sugestão com o Redis no chão")

    assert Sugestao.objects.filter(pk=sugestao.pk).exists()  # a página funcionou
    evento = OutboxEvent.objects.get(event=eventos.CRIADA)
    assert evento.published_at is None  # pendente, NÃO marcado sem publicar

    monkeypatch.setattr("redis.from_url", lambda *a, **k: fio.cliente)
    assert relay_outbox_periodico.call_local() == 1

    evento.refresh_from_db()
    assert evento.published_at is not None
    assert len(fio.mensagens) == 1


@pytest.mark.django_db(transaction=True)
def test_sem_REDIS_STREAMS_URL_o_voto_acontece_e_o_evento_espera(
    caixa, fio, monkeypatch
):
    """[§5.3] Variável ausente derruba o relay, nunca a célula.

    É o motivo de `REDIS_STREAMS_URL` ser lida no ponto de uso e de
    `HUEY_REDIS_URL` ter default no `config/huey.py`: o container web importa
    os dois caminhos e não pode morrer no boot por causa da fila.
    """
    sugestao = caixa.publicar()
    monkeypatch.delenv("REDIS_STREAMS_URL")

    assert caixa.votar(sugestao).status_code == 302

    assert OutboxEvent.objects.get(event=eventos.VOTO_ADICIONADO).published_at is None


# ---------------------------------------------------------------------------
# O fio do worker: run_huey precisa ENCONTRAR a task
# ---------------------------------------------------------------------------


def test_a_task_periodica_esta_registrada_na_instancia_que_o_run_huey_consome():
    """[§4.11] `run_huey` consome `settings.HUEY`.

    Se a task se registrasse noutra instância, o worker subiria de pé, logaria
    a lista de comandos VAZIA e não executaria nada — sem erro, sem aviso. É o
    modo de falha que este guarda existe para tornar impossível.
    """
    from huey.api import PeriodicTask, TaskWrapper

    from config.huey import huey

    assert "huey.contrib.djhuey" in settings.INSTALLED_APPS
    assert settings.HUEY is huey
    assert isinstance(relay_outbox_periodico, TaskWrapper)
    assert issubclass(relay_outbox_periodico.task_class, PeriodicTask)
    assert relay_outbox_periodico.huey is huey


def test_huey_nao_e_fail_hard_no_import_sem_a_variavel_de_ambiente(monkeypatch):
    """O container web importa `config/huey.py` via INSTALLED_APPS.

    Fail-hard aqui tiraria a Caixa inteira do ar por falta de uma variável que
    só o worker precisa de verdade. O default é inofensivo porque a conexão do
    Huey é preguiçosa: ninguém abre socket no import.
    """
    import importlib

    import config.huey

    monkeypatch.delenv("HUEY_REDIS_URL", raising=False)

    recarregado = importlib.reload(config.huey)

    assert recarregado.huey.name == "sugestoes"
    importlib.reload(config.huey)  # devolve o módulo ao estado do processo


# ---------------------------------------------------------------------------
# A borda pública: a Caixa serve sob prefixo, e o evento não muda por isso
# ---------------------------------------------------------------------------


def test_o_evento_nasce_igual_com_a_celula_servida_sob_prefixo(caixa, fio, settings):
    """[armadilhas/029 e /081] A Caixa mora em `/forms/sugestoes/`.

    O `SCRIPT_NAME` muda os endereços, não os fatos: `site_id` vem do quadro e
    os ids vêm do banco. Este guarda existe para que ninguém um dia derive
    `site_id` do caminho da requisição — que funcionaria em dev e mentiria
    exatamente onde o prefixo existe.
    """
    settings.FORCE_SCRIPT_NAME = "/forms/sugestoes"
    sugestao = caixa.publicar(titulo="Sugestão nascida sob prefixo")
    relay_outbox()

    dados = fio.um_envelope(eventos.CRIADA)["data"]
    assert dados["site_id"] == "site-de-teste"
    assert dados["suggestion_id"] == str(sugestao.pk)
    assert reverse("quadro").startswith("/")  # o urlconf segue sem saber do prefixo
