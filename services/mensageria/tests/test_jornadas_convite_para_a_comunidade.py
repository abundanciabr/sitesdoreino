"""O convite para a Comunidade (rodada 2 da Comunidade Meshcraft, R2-8).

Molde exato de `test_jornadas_convite_para_a_prancheta.py`: mesmo gatilho
(`aula.concluida` com `e_boss` verdadeiro), mesma recusa do palpite de
progresso, mesmas três camadas de idempotência. Este arquivo prova o que muda:
o texto (aponta para a Comunidade, não para a Prancheta, e não promete renda,
prazo nem nome de membro) e o horário (o passo 1 não chega no mesmo instante
que o passo 1 da Prancheta).
"""

import json
import logging
from datetime import timedelta
from io import StringIO
from pathlib import Path
from uuid import uuid4

import jsonschema
import pytest
from django.core.management import call_command

from apps.eventos.handlers import GATILHO_BLOCO_FECHADO, ao_aula_concluida
from apps.eventos.management.commands.consume_eventos import (
    STREAMS,
    processar_envelope,
)
from apps.jornadas.management.commands.semear_convite_para_a_comunidade import (
    PASSOS,
    SLUG,
)
from apps.jornadas.management.commands.semear_convite_para_a_prancheta import (
    SLUG as SLUG_PRANCHETA,
)
from apps.jornadas.models import Inscricao, Jornada, TextoDoPasso

pytestmark = pytest.mark.django_db

SITE = "site-abc"
ALUNO = "aluno-opaco-1"
OUTRO_ALUNO = "aluno-opaco-2"
CURSO = "curso-opaco-1"
AULA = "aula-opaca-1"

CONTRATOS = Path(__file__).resolve().parents[3] / "contracts" / "eventos"
RISCAS_LONGAS = ("—", "–", "―")

# `docs/comunidade/DOSSIE-TECNICO-FUNCIONAL-COMUNIDADE.md` §16, §17: nenhuma
# destas três coisas pode aparecer no convite.
PALAVRAS_PROIBIDAS = (
    "renda",
    "ganhar dinheiro",
    "grátis",
    "gratis",
    "prazo",
    "só até",
    "so ate",
    "última chance",
    "ultima chance",
    "urgente",
)


def semear(ligar=True):
    saida = StringIO()
    call_command(
        "semear_convite_para_a_comunidade", site_id=SITE, ligar=ligar, stdout=saida
    )
    return saida.getvalue()


def semear_prancheta(ligar=True):
    saida = StringIO()
    call_command(
        "semear_convite_para_a_prancheta", site_id=SITE, ligar=ligar, stdout=saida
    )
    return saida.getvalue()


def _validado(envelope):
    schema = json.loads(
        (CONTRATOS / f"{envelope['event']}.v1.json").read_text(encoding="utf-8")
    )
    jsonschema.validate(envelope, schema)
    return envelope


def aula_concluida(*, e_boss, aluno=ALUNO, aula_id=AULA):
    return _validado(
        {
            "event": "aula.concluida",
            "version": 1,
            "event_id": str(uuid4()),
            "occurred_at": "2026-09-06T12:00:00Z",
            "ator_id": aluno,
            "data": {
                "site_id": SITE,
                "curso_id": CURSO,
                "aula_id": aula_id,
                "e_boss": e_boss,
            },
        }
    )


def consumir(envelope):
    """O caminho REAL: dedup por `event_id` e o handler do stream do evento."""
    return processar_envelope(envelope, STREAMS[f"eventos.{envelope['event']}"])


# ---------------------------------------------------------------------------
# O GATILHO CASA COM O STREAM — a falha que não dá erro nenhum
# ---------------------------------------------------------------------------


def test_o_gatilho_da_jornada_casa_com_o_stream():
    """A jornada da Comunidade reusa o MESMO gatilho da Prancheta, e por isso
    não muda uma linha em `apps/eventos/handlers.py`: o handler já itera toda
    jornada ativa com este gatilho."""
    semear()
    jornada = Jornada.objects.get(site_id=SITE, slug=SLUG)

    assert jornada.gatilho == GATILHO_BLOCO_FECHADO
    assert ".v1" not in jornada.gatilho
    assert STREAMS[f"eventos.{GATILHO_BLOCO_FECHADO}"] is ao_aula_concluida


# ---------------------------------------------------------------------------
# O FATO DECLARADO CONVIDA. O PALPITE, NUNCA.
# ---------------------------------------------------------------------------


def test_o_bloco_fechado_convida_o_aluno_que_o_fechou():
    semear()
    marco = aula_concluida(e_boss=True)

    consumir(marco)

    inscricao = Inscricao.objects.get()
    assert inscricao.destinatario_id == ALUNO
    assert inscricao.site_id == SITE
    assert inscricao.estado == "andando"
    assert str(inscricao.origem_event_id) == marco["event_id"]


def test_a_aula_comum_nao_convida_ninguem():
    semear()

    assert consumir(aula_concluida(e_boss=False)) is True

    assert not Inscricao.objects.exists()


def test_o_bloco_de_um_aluno_nao_convida_o_outro():
    semear()

    consumir(aula_concluida(e_boss=True, aluno=ALUNO))

    assert list(Inscricao.objects.values_list("destinatario_id", flat=True)) == [ALUNO]
    assert not Inscricao.objects.filter(destinatario_id=OUTRO_ALUNO).exists()


def test_o_segundo_bloco_nao_convida_de_novo():
    """Uma inscrição por pessoa: quem já foi convidado uma vez não é
    convidado a cada Bloco fechado."""
    semear()
    consumir(aula_concluida(e_boss=True, aula_id="aula-do-bloco-1"))
    primeira = Inscricao.objects.get()
    Inscricao.objects.filter(pk=primeira.pk).update(estado="concluida")

    consumir(aula_concluida(e_boss=True, aula_id="aula-do-bloco-2"))

    assert Inscricao.objects.count() == 1


def test_o_mesmo_marco_reentregue_nao_convida_duas_vezes():
    semear()
    marco = aula_concluida(e_boss=True)

    assert consumir(marco) is True
    assert consumir(marco) is False
    ao_aula_concluida(marco["data"], marco["event_id"], ALUNO)

    assert Inscricao.objects.count() == 1


def test_marco_sem_aluno_no_ator_id_nao_convida_ninguem(caplog):
    semear()
    marco = aula_concluida(e_boss=True)

    with caplog.at_level(logging.WARNING, logger="apps.eventos.handlers"):
        ao_aula_concluida(marco["data"], marco["event_id"], "")

    assert not Inscricao.objects.exists()


# ---------------------------------------------------------------------------
# A SEMEADURA: DESLIGADA, DOIS PASSOS, TEXTO HONESTO E SEM RISCA LONGA
# ---------------------------------------------------------------------------


def test_a_jornada_nasce_desligada_e_desligada_nao_convida_ninguem():
    semear(ligar=False)
    assert Jornada.objects.get(slug=SLUG).ativa is False

    consumir(aula_concluida(e_boss=True))

    assert not Inscricao.objects.exists()


def test_ligada_inscreve_uma_vez_por_pessoa():
    semear(ligar=True)

    consumir(aula_concluida(e_boss=True, aluno=ALUNO))
    consumir(aula_concluida(e_boss=True, aluno=OUTRO_ALUNO, aula_id="aula-opaca-2"))

    assert Inscricao.objects.filter(jornada__slug=SLUG).count() == 2
    assert set(
        Inscricao.objects.filter(jornada__slug=SLUG).values_list(
            "destinatario_id", flat=True
        )
    ) == {ALUNO, OUTRO_ALUNO}


def test_os_passos_sao_um_dia_depois_e_uma_semana_depois():
    semear()
    passos = list(Jornada.objects.get().versoes.get().passos.order_by("ordem"))

    assert [p.atraso for p in passos] == [timedelta(days=1), timedelta(days=8)]
    assert [p.classe for p in passos] == ["relacional", "engajamento"]
    assert {p.condicao_slug for p in passos} == {""}
    assert {p.assunto for p in passos} == {"jornada.passo"}
    assert [p.canais for p in passos] == [["sino"], ["sino"]]


def test_cada_passo_tem_texto_nos_tres_idiomas():
    semear()
    for passo in Jornada.objects.get().versoes.get().passos.all():
        assert set(passo.textos.values_list("idioma", flat=True)) == {
            "pt-br",
            "en",
            "es",
        }


def test_nenhuma_risca_longa_no_texto_semeado():
    semear()
    for texto in TextoDoPasso.objects.filter(passo__jornada_versao__jornada__slug=SLUG):
        for campo in (texto.assunto_visivel, texto.corpo):
            assert not any(risca in campo for risca in RISCAS_LONGAS), campo


def test_o_convite_nao_promete_renda_prazo_nem_nome_de_membro():
    """`DOSSIE-TECNICO-FUNCIONAL-COMUNIDADE.md` §16, §17: a mesma régua que
    trava o texto da própria página da Comunidade trava o convite."""
    semear()
    for texto in TextoDoPasso.objects.filter(passo__jornada_versao__jornada__slug=SLUG):
        corpo_minusculo = texto.corpo.lower()
        for palavra in PALAVRAS_PROIBIDAS:
            assert palavra not in corpo_minusculo, f"{palavra!r} em {texto.corpo!r}"


def test_o_convite_aponta_para_o_forum_e_para_a_pagina_publica():
    semear()
    corpos = " ".join(
        TextoDoPasso.objects.filter(
            passo__jornada_versao__jornada__slug=SLUG
        ).values_list("corpo", flat=True)
    )

    assert "meshcraft.top/forum/comunidade" in corpos
    assert "meshcraft.top/docs/comunidade" in corpos


def test_semear_duas_vezes_nao_duplica_nem_reescreve():
    semear()
    saida = semear()

    assert Jornada.objects.filter(slug=SLUG).count() == 1
    assert TextoDoPasso.objects.filter(
        passo__jornada_versao__jornada__slug=SLUG
    ).count() == sum(len(p["textos"]) for p in PASSOS)
    assert "ja existe" in saida


# ---------------------------------------------------------------------------
# NÃO CHEGA NO MESMO INSTANTE QUE O CONVITE PARA A PRANCHETA
# ---------------------------------------------------------------------------


def test_o_convite_nao_chega_no_mesmo_instante_que_o_da_prancheta():
    """As duas jornadas escutam o MESMO evento e são inscritas na MESMA
    chamada do handler (mesmo `ancora_em`). O cronograma é `ancora_em +
    atraso` (LICOES.md): se os dois passos 1 tivessem o mesmo atraso, as duas
    cartas ficariam elegíveis no mesmo instante e disputariam a mesma vaga do
    teto diário. O passo 1 da Prancheta tem atraso zero; o da Comunidade tem
    um dia — por isso `proximo_em` diverge."""
    semear()
    semear_prancheta()
    marco = aula_concluida(e_boss=True)

    consumir(marco)

    comunidade = Inscricao.objects.get(jornada__slug=SLUG)
    prancheta = Inscricao.objects.get(jornada__slug=SLUG_PRANCHETA)

    # Cada `ancora_em` é `timezone.now()` no instante do `inscrever()` daquela
    # jornada (microssegundos de diferença entre as duas chamadas do mesmo
    # handler); o que a régua do §5 fixa é `proximo_em - ancora_em == atraso`.
    assert comunidade.proximo_em - comunidade.ancora_em == timedelta(days=1)
    assert prancheta.proximo_em - prancheta.ancora_em == timedelta(0)

    # A prova do requisito: a carta da Comunidade não fica elegível no mesmo
    # instante que a da Prancheta — a diferença é de quase um dia, não de
    # microssegundos.
    assert comunidade.proximo_em - prancheta.proximo_em > timedelta(hours=23)
