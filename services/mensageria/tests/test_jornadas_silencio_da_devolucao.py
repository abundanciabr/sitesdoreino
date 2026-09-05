"""A jornada do silêncio de 14 e 30 dias (degrau 2.4 da sala de aula).

`PLANO-CELULA-CURSOS.md` §3.6: o laudo devolvido dispara, o reenvio cancela, a
frase é fixa e nunca é cobrança. Os dois eventos entram pelo mesmo consumidor
idempotente das outras sequências; o que este arquivo prova é a parte que só
existe aqui: a correlação `envio_id -> aluno` (o devolvido não carrega o aluno),
o cancelamento POR EVENTO, o relógio que recomeça no último devolvido, e a
chave por AULA.

OS ENVELOPES SÃO OS DO CONTRATO, VALIDADOS EM DISCO
----------------------------------------------------
`armadilhas/255`: um teste com envelope de fantasia prova que o motor funciona
com dados que nunca vão chegar. Aqui cada envelope é conferido contra o schema
congelado antes de entrar no consumidor, e é por isso que o `ator_id` do aluno
está no NÍVEL DE CIMA, e não dentro de `data`: é assim que a `cursos` publica.

O tempo entra por parâmetro (`momento=`), como no motor e na régua: os cenários
são sobre DIAS diferentes, e um relógio real os tornaria intestáveis.
"""

import json
import logging
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from uuid import uuid4

import jsonschema
import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.eventos.handlers import (
    EVENTO_ENVIO_RECEBIDO,
    GATILHO_DEVOLUCAO,
    ao_checkpoint_devolvido,
    ao_envio_recebido,
)
from apps.eventos.management.commands.consume_eventos import (
    STREAMS,
    processar_envelope,
)
from apps.jornadas import despacho, motor
from apps.jornadas.management.commands.semear_silencio_da_devolucao import FRASE
from apps.jornadas.models import (
    EnvioDeCheckpoint,
    Inscricao,
    Jornada,
    OutboxEvent,
    TextoDoPasso,
)

pytestmark = pytest.mark.django_db

SITE = "site-abc"
ALUNO = "aluno-opaco-1"
PROFESSORA = "professora-opaca-1"
AULA = "aula-opaca-1"
OUTRA_AULA = "aula-opaca-2"
ENVIO = "envio-opaco-1"
CURSO = "curso-opaco-1"

CONTRATOS = Path(__file__).resolve().parents[3] / "contracts" / "eventos"
RISCAS_LONGAS = ("—", "–", "―")


def semear(ligar=True):
    saida = StringIO()
    call_command(
        "semear_silencio_da_devolucao", site_id=SITE, ligar=ligar, stdout=saida
    )
    return saida.getvalue()


def quando(dia, hora=10, minuto=0):
    return timezone.make_aware(
        datetime(2026, 9, dia, hora, minuto), timezone.get_current_timezone()
    )


def _validado(envelope):
    schema = json.loads(
        (CONTRATOS / f"{envelope['event']}.v1.json").read_text(encoding="utf-8")
    )
    jsonschema.validate(envelope, schema)
    return envelope


def envio_recebido(envio_id=ENVIO, aula_id=AULA, numero=1, aluno=ALUNO):
    return _validado(
        {
            "event": "envio.recebido",
            "version": 1,
            "event_id": str(uuid4()),
            "occurred_at": "2026-09-01T12:00:00Z",
            "ator_id": aluno,
            "data": {
                "site_id": SITE,
                "curso_id": CURSO,
                "aula_id": aula_id,
                "envio_id": envio_id,
                "numero": numero,
            },
        }
    )


def checkpoint_devolvido(envio_id=ENVIO, aula_id=AULA):
    return _validado(
        {
            "event": "checkpoint.devolvido",
            "version": 1,
            "event_id": str(uuid4()),
            "occurred_at": "2026-09-02T12:00:00Z",
            "ator_id": PROFESSORA,
            "data": {
                "site_id": SITE,
                "aula_id": aula_id,
                "envio_id": envio_id,
                "data_de_retorno": "2026-09-05",
            },
        }
    )


def consumir(envelope):
    """O caminho REAL: dedup por `event_id` e o handler do stream do evento."""
    return processar_envelope(envelope, STREAMS[f"eventos.{envelope['event']}"])


def andando():
    return Inscricao.objects.filter(estado="andando")


# ---------------------------------------------------------------------------
# O GATILHO CASA COM O STREAM — a falha que não dá erro nenhum
# ---------------------------------------------------------------------------


def test_os_dois_eventos_entram_pelo_consumidor_e_o_gatilho_casa_com_o_stream():
    """`checkpoint.devolvido.v1` cita o contrato; `checkpoint.devolvido` é o
    nome no fio. Errar isto faz a jornada nunca casar com evento nenhum, em
    silêncio. As duas pontas amarradas uma na outra."""
    semear()
    jornada = Jornada.objects.get(site_id=SITE, slug="silencio-da-devolucao")

    assert jornada.gatilho == GATILHO_DEVOLUCAO
    assert ".v1" not in jornada.gatilho
    assert STREAMS[f"eventos.{GATILHO_DEVOLUCAO}"] is ao_checkpoint_devolvido
    assert STREAMS[f"eventos.{EVENTO_ENVIO_RECEBIDO}"] is ao_envio_recebido


# ---------------------------------------------------------------------------
# A SEMEADURA: DESLIGADA, DOIS PASSOS, A FRASE FIXA, SEM RISCA LONGA
# ---------------------------------------------------------------------------


def test_a_jornada_nasce_desligada_e_desligada_nao_inscreve_ninguem():
    """Ligar é decisão do mantenedor, na tela dele. Um devolvido com a jornada
    desligada não inscreve, mesmo com a correlação no lugar."""
    semear(ligar=False)
    assert Jornada.objects.get(slug="silencio-da-devolucao").ativa is False

    consumir(envio_recebido())
    consumir(checkpoint_devolvido())

    assert not Inscricao.objects.exists()


def test_os_passos_sao_aos_14_e_aos_30_dias_sem_condicao_e_pela_regua():
    semear()
    passos = list(Jornada.objects.get().versoes.get().passos.order_by("ordem"))

    assert [p.atraso for p in passos] == [timedelta(days=14), timedelta(days=30)]
    assert {p.classe for p in passos} == {"engajamento"}
    assert {p.condicao_slug for p in passos} == {""}
    assert {p.assunto for p in passos} == {"jornada.passo"}
    assert [p.canais for p in passos] == [["sino"], ["sino"]]


def test_a_frase_e_exatamente_a_fixa_e_igual_nos_dois_passos():
    """A do playbook (P51), sem cobrança, sem "você sumiu", sem contagem."""
    semear()
    corpos = list(
        TextoDoPasso.objects.filter(idioma="pt-br")
        .order_by("passo__ordem")
        .values_list("corpo", flat=True)
    )

    assert corpos == [FRASE, FRASE]
    assert FRASE == (
        "Você sabe o que fazer amanhã de manhã? Se não, responda esta mensagem."
    )


def test_cada_passo_tem_texto_nos_tres_idiomas():
    semear()
    for passo in Jornada.objects.get().versoes.get().passos.all():
        assert set(passo.textos.values_list("idioma", flat=True)) == {
            "pt-br",
            "en",
            "es",
        }


def test_nenhuma_risca_longa_no_texto_semeado():
    """O portão do travessão vale para texto publicado, e o texto semeado É
    publicado: o sino o mostra ao aluno."""
    semear()
    for texto in TextoDoPasso.objects.all():
        for campo in (texto.assunto_visivel, texto.corpo):
            assert not any(risca in campo for risca in RISCAS_LONGAS), campo


def test_semear_duas_vezes_nao_duplica_nem_reescreve():
    semear()
    saida = semear()

    assert Jornada.objects.count() == 1
    assert TextoDoPasso.objects.count() == 6
    assert "ja existe" in saida


# ---------------------------------------------------------------------------
# A CORRELAÇÃO: O DEVOLVIDO INSCREVE O ALUNO DO ENVIO, NUNCA A PROFESSORA
# ---------------------------------------------------------------------------


def test_o_devolvido_inscreve_o_aluno_do_envio_recebido_e_nao_quem_assinou_o_laudo():
    """O `ator_id` do devolvido é a professora. O aluno vem da correlação que o
    `envio.recebido` do mesmo `envio_id` gravou antes."""
    semear()
    consumir(envio_recebido())
    devolvido = checkpoint_devolvido()
    consumir(devolvido)

    inscricao = Inscricao.objects.get()
    assert inscricao.destinatario_id == ALUNO
    assert inscricao.destinatario_id != PROFESSORA
    assert inscricao.site_id == SITE
    assert inscricao.contexto_id == AULA
    assert inscricao.estado == "andando"
    assert str(inscricao.origem_event_id) == devolvido["event_id"]


def test_o_ator_id_chega_ao_handler_pelo_envelope_e_nao_pelo_data():
    """A correlação lê o aluno do NÍVEL DE CIMA do envelope. Um handler que o
    procurasse dentro de `data` gravaria `None` em produção e nada erraria: o
    schema do contrato proíbe `ator_id` dentro de `data`
    (`additionalProperties: false`), então este envelope é o único possível."""
    envelope = envio_recebido()
    assert "ator_id" not in envelope["data"]

    consumir(envelope)

    correlacao = EnvioDeCheckpoint.objects.get()
    assert correlacao.aluno_id == ALUNO
    assert correlacao.aula_id == AULA
    assert correlacao.envio_id == ENVIO


def test_o_devolvido_sem_o_recebido_nao_inscreve_e_avisa_no_log(caplog):
    """Relay fora de ordem, ou envio anterior ao dia em que esta célula passou
    a escutar a sala de aula: ninguém é inscrito (chutar seria a pessoa
    fantasma da `armadilhas/255`), e o log diz por quê, com os ids."""
    semear()
    with caplog.at_level(logging.WARNING, logger="apps.eventos.handlers"):
        assert consumir(checkpoint_devolvido()) is True

    assert not Inscricao.objects.exists()
    aviso = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(aviso) == 1
    assert ENVIO in aviso[0].getMessage()
    assert "NAO inscrevo" in aviso[0].getMessage()


def test_o_mesmo_devolvido_reentregue_nao_inscreve_duas_vezes():
    """As duas camadas medidas: o dedup por `event_id` do consumidor e, por
    baixo dele, o `origem_event_id` do motor (o handler chamado direto)."""
    semear()
    consumir(envio_recebido())
    devolvido = checkpoint_devolvido()

    assert consumir(devolvido) is True
    assert consumir(devolvido) is False
    assert Inscricao.objects.count() == 1

    ao_checkpoint_devolvido(devolvido["data"], devolvido["event_id"], PROFESSORA)
    assert Inscricao.objects.count() == 1
    assert andando().count() == 1, "a reentrega nao pode cancelar o proprio episodio"


# ---------------------------------------------------------------------------
# O CANCELAMENTO POR EVENTO, E A CHAVE POR AULA
# ---------------------------------------------------------------------------


def test_o_reenvio_cancela_a_jornada_na_hora():
    """A capacidade que o §2 do plano chama de "desistir na hora certa", vinda
    de um EVENTO: o aluno que reenviou não recebe "você sabe o que fazer
    amanhã?" amanhã. Prova por mutação: sem o `motor.cancelar` do handler do
    envio, este teste fica vermelho na primeira asserção."""
    semear()
    consumir(envio_recebido())
    consumir(checkpoint_devolvido())
    assert andando().count() == 1

    consumir(envio_recebido(envio_id="envio-opaco-2", numero=2))

    assert andando().count() == 0
    inscricao = Inscricao.objects.get()
    assert inscricao.estado == "cancelada"
    assert inscricao.proximo_em is None
    assert inscricao.motivo_de_saida == "o aluno enviou o checkpoint de novo"


def test_cancelada_a_varredura_nao_manda_nada():
    """O que o cancelamento compra: aos 14 dias, ninguém é examinado."""
    semear()
    jornada = Jornada.objects.get()
    motor.inscrever(
        jornada,
        destinatario_id=ALUNO,
        site_id=SITE,
        contexto_id=AULA,
        origem_event_id=str(uuid4()),
        momento=quando(1),
    )
    motor.cancelar(
        jornada,
        destinatario_id=ALUNO,
        site_id=SITE,
        contexto_id=AULA,
        motivo="o aluno enviou o checkpoint de novo",
    )

    passada = motor.varrer(momento=quando(15), despachar=despacho.despachar)

    assert passada.examinadas == 0
    assert not OutboxEvent.objects.exists()


def test_o_reenvio_de_uma_aula_nao_cancela_o_silencio_da_outra():
    """A chave é (site, aluno, AULA): dois devolvidos em aulas diferentes são
    dois relógios, e o reenvio de uma não cala a outra."""
    semear()
    consumir(envio_recebido(envio_id="envio-a1", aula_id=AULA))
    consumir(envio_recebido(envio_id="envio-a2", aula_id=OUTRA_AULA))
    consumir(checkpoint_devolvido(envio_id="envio-a1", aula_id=AULA))
    consumir(checkpoint_devolvido(envio_id="envio-a2", aula_id=OUTRA_AULA))
    assert andando().count() == 2

    consumir(envio_recebido(envio_id="envio-a1-v2", aula_id=AULA, numero=2))

    assert andando().count() == 1
    assert andando().get().contexto_id == OUTRA_AULA


def test_um_devolvido_novo_para_a_mesma_aula_recomeca_a_contagem():
    """O relógio conta do ÚLTIMO devolvido: o episódio anterior é cancelado e
    o novo nasce ancorado no segundo devolvido."""
    semear()
    jornada = Jornada.objects.get()
    primeiro = motor.recomecar(
        jornada,
        destinatario_id=ALUNO,
        site_id=SITE,
        contexto_id=AULA,
        origem_event_id=str(uuid4()),
        motivo="um devolvido novo recomecou a contagem",
        momento=quando(1),
    )
    segundo = motor.recomecar(
        jornada,
        destinatario_id=ALUNO,
        site_id=SITE,
        contexto_id=AULA,
        origem_event_id=str(uuid4()),
        motivo="um devolvido novo recomecou a contagem",
        momento=quando(5),
    )

    primeiro.refresh_from_db()
    assert primeiro.estado == "cancelada"
    assert primeiro.motivo_de_saida == "um devolvido novo recomecou a contagem"
    assert segundo.pk != primeiro.pk
    assert segundo.estado == "andando"
    assert segundo.ancora_em == quando(5)
    assert segundo.proximo_em == quando(5) + timedelta(days=14)


# ---------------------------------------------------------------------------
# O RELÓGIO: 14 DIAS, DEPOIS 30, CONTADOS DA ÂNCORA
# ---------------------------------------------------------------------------


def test_o_passo_de_14_dias_so_sai_com_o_relogio_em_14_dias():
    """Aos 13 dias nada; aos 14, a carta. A janela da régua (8h-20h em São
    Paulo) vale aqui como em toda entrega da célula."""
    semear()
    jornada = Jornada.objects.get()
    inscricao = motor.inscrever(
        jornada,
        destinatario_id=ALUNO,
        site_id=SITE,
        contexto_id=AULA,
        origem_event_id=str(uuid4()),
        momento=quando(1),
    )
    assert inscricao.proximo_em == quando(15)

    cedo = motor.varrer(momento=quando(14), despachar=despacho.despachar)
    assert cedo.examinadas == 0
    assert not OutboxEvent.objects.exists()

    na_hora = motor.varrer(momento=quando(15), despachar=despacho.despachar)
    assert na_hora.entregues == 1

    carta = OutboxEvent.objects.get()
    assert carta.event == "notificacao.devida"
    assert carta.payload["destinatario_id"] == ALUNO
    assert carta.payload["assunto"] == "jornada.passo"
    assert carta.payload["parametros"]["jornada_slug"] == "silencio-da-devolucao"
    assert carta.payload["parametros"]["ordem"] == 1


def test_o_segundo_passo_sai_aos_30_dias_do_devolvido_e_depois_e_silencio():
    """30 dias da ÂNCORA, não 30 depois do primeiro passo. Depois, concluída:
    nunca uma terceira mensagem."""
    semear()
    jornada = Jornada.objects.get()
    inscricao = motor.inscrever(
        jornada,
        destinatario_id=ALUNO,
        site_id=SITE,
        contexto_id=AULA,
        origem_event_id=str(uuid4()),
        momento=quando(1),
    )
    motor.varrer(momento=quando(15), despachar=despacho.despachar)

    inscricao.refresh_from_db()
    assert inscricao.passo_atual == 1
    assert inscricao.proximo_em == quando(1) + timedelta(days=30)

    assert (
        motor.varrer(momento=quando(30), despachar=despacho.despachar).examinadas == 0
    )
    tarde = motor.varrer(
        momento=quando(1) + timedelta(days=30), despachar=despacho.despachar
    )
    assert tarde.entregues == 1

    inscricao.refresh_from_db()
    assert inscricao.estado == "concluida"
    assert inscricao.proximo_em is None
    assert OutboxEvent.objects.count() == 2
    assert {c.payload["parametros"]["ordem"] for c in OutboxEvent.objects.all()} == {
        1,
        2,
    }
