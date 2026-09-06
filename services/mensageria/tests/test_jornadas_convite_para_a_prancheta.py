"""O convite para a Prancheta (degrau 17 da escada do portfólio).

`CS-PAGES-0001` AC-19: a sequência dispara por um fato **declarado** e nunca por
inferência de progresso. Este arquivo prova as duas metades, e a segunda é a que
importa: a plataforma não serve aula e não sabe sozinha quando alguém terminou
(`PLANO-PORTFOLIO-DO-ALUNO.md` §3), então adivinhar produziria "monte o seu
portfólio" para quem está na terceira aula.

O FATO DECLARADO ESCOLHIDO, E POR QUE ELE
------------------------------------------
`aula.concluida` com `e_boss` verdadeiro: o Bloco fechado. São duas declarações
humanas encadeadas, e nenhuma contagem: a professora assinou o laudo que abriu a
porta da aula, e a escola declarou, na estrutura do curso, que aquela aula fecha
um Bloco. O mesmo evento com `e_boss` falso é progresso comum, e é exatamente o
palpite que este arquivo obriga o código a recusar.

OS ENVELOPES SÃO OS DO CONTRATO, VALIDADOS EM DISCO
----------------------------------------------------
`armadilhas/255`: envelope de fantasia prova que o motor funciona com dados que
nunca vão chegar. Cada envelope aqui passa pelo schema congelado antes de entrar
no consumidor, e é por isso que o aluno está no `ator_id` do NÍVEL DE CIMA.
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
from apps.jornadas.management.commands.semear_convite_para_a_prancheta import (
    PASSOS,
    SLUG,
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

# O que os degraus 08 a 14 ainda não entregaram. O texto do convite não pode
# prometer nada disto: quem chega e não encontra desliga a caixa de entrada, e
# essa confiança não volta.
AINDA_NAO_EXISTE = (
    "semáforo",
    "selo",
    "vitrine",
    "PDF",
    "pdf",
    "cole o link",
    "colar o link",
)


def semear(ligar=True):
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
    """`aula.concluida.v1` é o contrato; `aula.concluida` é o nome no fio.
    Errar isto faz a sequência nunca casar com evento nenhum, em silêncio."""
    semear()
    jornada = Jornada.objects.get(site_id=SITE, slug=SLUG)

    assert jornada.gatilho == GATILHO_BLOCO_FECHADO
    assert ".v1" not in jornada.gatilho
    assert STREAMS[f"eventos.{GATILHO_BLOCO_FECHADO}"] is ao_aula_concluida


# ---------------------------------------------------------------------------
# O FATO DECLARADO CONVIDA. O PALPITE, NUNCA.
# ---------------------------------------------------------------------------


def test_o_bloco_fechado_convida_o_aluno_que_o_fechou():
    """O `ator_id` do evento é o aluno cuja porta abriu, e é ele quem entra."""
    semear()
    marco = aula_concluida(e_boss=True)

    consumir(marco)

    inscricao = Inscricao.objects.get()
    assert inscricao.destinatario_id == ALUNO
    assert inscricao.site_id == SITE
    assert inscricao.contexto_id == "", "o convite é da pessoa, não de uma aula"
    assert inscricao.estado == "andando"
    assert str(inscricao.origem_event_id) == marco["event_id"]


def test_a_aula_comum_do_meio_do_curso_nao_convida_ninguem():
    """A PROVA DO AC-19, e a razão de este arquivo existir.

    Aula concluída sem `e_boss` é progresso, não marco. Quem está na terceira
    aula de um curso de trinta não recebe "monte o seu portfólio" nem uma vez.
    """
    semear()

    assert consumir(aula_concluida(e_boss=False)) is True

    assert not Inscricao.objects.exists()


def test_nenhuma_quantidade_de_aulas_comuns_vira_um_convite():
    """O palpite mais tentador: "ele já concluiu dez aulas, deve ter terminado".

    Dez fatos de progresso continuam sendo zero fatos declarados. Nada aqui
    conta aulas, e é de propósito: a plataforma não serve aula e não sabe
    quantas existem no curso.
    """
    semear()

    for numero in range(10):
        consumir(aula_concluida(e_boss=False, aula_id=f"aula-opaca-{numero}"))

    assert not Inscricao.objects.exists()


def test_o_bloco_de_um_aluno_nao_convida_o_outro():
    semear()

    consumir(aula_concluida(e_boss=True, aluno=ALUNO))

    assert list(Inscricao.objects.values_list("destinatario_id", flat=True)) == [ALUNO]
    assert not Inscricao.objects.filter(destinatario_id=OUTRO_ALUNO).exists()


def test_o_segundo_bloco_nao_convida_de_novo():
    """Convite é um só. Um curso com cinco Blocos não manda cinco convites para
    a mesma Prancheta: quem já foi chamado uma vez não é chamado a cada Bloco.
    """
    semear()
    consumir(aula_concluida(e_boss=True, aula_id="aula-do-bloco-1"))
    primeira = Inscricao.objects.get()
    Inscricao.objects.filter(pk=primeira.pk).update(estado="concluida")

    consumir(aula_concluida(e_boss=True, aula_id="aula-do-bloco-2"))

    assert Inscricao.objects.count() == 1


def test_o_mesmo_marco_reentregue_nao_convida_duas_vezes():
    """As duas camadas: o dedup por `event_id` do consumidor e, por baixo dele,
    o `origem_event_id` do motor (o handler chamado direto)."""
    semear()
    marco = aula_concluida(e_boss=True)

    assert consumir(marco) is True
    assert consumir(marco) is False
    ao_aula_concluida(marco["data"], marco["event_id"], ALUNO)

    assert Inscricao.objects.count() == 1


def test_marco_sem_aluno_no_ator_id_nao_convida_ninguem_e_avisa_no_log(caplog):
    """Fail-closed: inscrever com destinatário vazio abriria um episódio de
    ninguém, e a carta sairia endereçada ao nada (`armadilhas/255`)."""
    semear()
    marco = aula_concluida(e_boss=True)

    with caplog.at_level(logging.WARNING, logger="apps.eventos.handlers"):
        ao_aula_concluida(marco["data"], marco["event_id"], "")

    assert not Inscricao.objects.exists()
    avisos = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(avisos) == 1
    assert "NAO convido" in avisos[0].getMessage()


# ---------------------------------------------------------------------------
# A SEMEADURA: DESLIGADA, DOIS PASSOS, TEXTO HONESTO E SEM RISCA LONGA
# ---------------------------------------------------------------------------


def test_a_jornada_nasce_desligada_e_desligada_nao_convida_ninguem():
    """Ligar é decisão do mantenedor, na tela dele. E ela nasce desligada por
    um motivo a mais neste degrau: a Prancheta ainda está sendo construída."""
    semear(ligar=False)
    assert Jornada.objects.get(slug=SLUG).ativa is False

    consumir(aula_concluida(e_boss=True))

    assert not Inscricao.objects.exists()


def test_os_passos_sao_no_marco_e_uma_semana_depois():
    semear()
    passos = list(Jornada.objects.get().versoes.get().passos.order_by("ordem"))

    assert [p.atraso for p in passos] == [timedelta(0), timedelta(days=7)]
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
    """O portão do travessão vale para texto publicado, e o texto semeado É
    publicado: o sino o mostra ao aluno."""
    semear()
    for texto in TextoDoPasso.objects.all():
        for campo in (texto.assunto_visivel, texto.corpo):
            assert not any(risca in campo for risca in RISCAS_LONGAS), campo


def test_o_convite_nao_promete_o_que_os_degraus_seguintes_ainda_nao_entregaram():
    """Peças por link, semáforo, selo, vitrine e dossiê em PDF são degraus 08 a
    14. Convidar para eles hoje é mandar a pessoa a uma porta que não abre."""
    semear()
    for texto in TextoDoPasso.objects.all():
        for palavra in AINDA_NAO_EXISTE:
            assert palavra not in texto.corpo, f"{palavra} em {texto.corpo!r}"


def test_o_convite_manda_o_aluno_ao_guia_que_ja_esta_publicado():
    """O guia da escola existe desde o degrau 16, em `/docs/guia-do-portfolio`,
    com as quatro regras da professora. O convite aponta para lá, e não descreve
    as regras de novo: o mantenedor edita o guia sem abrir PR, e um resumo aqui
    seria o mesmo texto em dois lugares."""
    semear()
    corpos = " ".join(TextoDoPasso.objects.values_list("corpo", flat=True))

    assert "meshcraft.top/docs/guia-do-portfolio" in corpos


def test_semear_duas_vezes_nao_duplica_nem_reescreve():
    semear()
    saida = semear()

    assert Jornada.objects.count() == 1
    assert TextoDoPasso.objects.count() == sum(len(p["textos"]) for p in PASSOS)
    assert "ja existe" in saida
