"""O selo da escola acende o marco do portfólio, e ele vale ZERO XP.

A célula `pages` publica `pages.portfolio.conferido.v1` quando alguém da equipe
confere o portfólio de um aluno e o selo sai (degrau 12 da escada do portfólio).
Este é o degrau 15: a gamificação só ESCUTA. Ela acende o marco na trilha e não
credita ponto, não mexe em nível e não entra na economia.

O QUE ESTE ARQUIVO TRAVA:

1. **O envelope do teste é o que o contrato fixa.** Um envelope de fantasia
   provaria que o handler funciona com dados que nunca vão chegar
   (`armadilhas/255`): aqui ele é validado contra o ARQUIVO congelado.
2. **Marco real vale ZERO XP**, de propósito (plano §7, decisão 7 da Sessão A).
   Nenhum lançamento nasce, o perfil não sobe e nenhum Cristal se move.
3. **O mesmo selo reentregue acende o marco uma vez só**, nas duas camadas: a
   do consumidor (`EventoProcessado`) e a da concessão
   (`Unique(pessoa, conquista)`). A segunda segura sozinha, e é ela que a prova
   por mutação derruba.
4. **Nada além do selo acende um marco.** O motor de critérios só concede
   MEDALHA, e o marco desligado não acende nem com o selo na mão: ligar uma
   conquista é decisão do mantenedor, em `/admin/economia/`.
5. **Envelope torto não acende pela metade**, e não inventa pessoa nenhuma:
   sem site, sem aluno ou sem quem conferiu, nada acontece. E ninguém acende o
   próprio marco (a trava 2 de `validacao.py`, aqui na porta do evento).
"""

from __future__ import annotations

import json
import uuid
from io import StringIO
from pathlib import Path

import jsonschema
import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.eventos.management.commands.consume_eventos import (
    STREAMS,
    processar_envelope,
)
from apps.eventos.models import EventoProcessado
from apps.gamificacao.cartas import ASSUNTO_MARCO
from apps.gamificacao.handlers import HANDLERS, MARCO_DO_PORTFOLIO, NAO_CREDITAM
from apps.gamificacao.models import (
    Concessao,
    ConquistaDefinicao,
    LancamentoDeXP,
    MovimentoDeCristais,
    OutboxEvent,
    PerfilJogador,
    Pessoa,
)

pytestmark = pytest.mark.django_db

SITE = "site-de-teste"
ALUNO = "pes-aluno"
MONITORA = "pes-monitora"

CONTRATO = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "eventos"
    / "pages.portfolio.conferido.v1.json"
)


def _marco(**campos) -> ConquistaDefinicao:
    """O marco do portfólio como `semear_economia` o semeia, porém LIGADO."""
    base = {
        "slug": MARCO_DO_PORTFOLIO,
        "site_id": SITE,
        "nome": "Portfólio no ar",
        "classe": ConquistaDefinicao.Classe.MARCO,
        "familia": ConquistaDefinicao.Familia.CARREIRA,
        "criterio": {"tipo": "manual"},
        "pontos": 0,
        "cristais": 0,
        "ativa": True,
    }
    base.update(campos)
    return ConquistaDefinicao.objects.create(**base)


def _selo(**campos) -> dict:
    """O envelope como `pages.portfolio.conferido.v1.json` o congelou."""
    data = {"site_id": SITE, "aluno_id": ALUNO, "portfolio_id": "pf-1"}
    data.update(campos.pop("data", {}))
    base = {
        "event": "pages.portfolio.conferido",
        "version": 1,
        "event_id": str(uuid.uuid4()),
        "occurred_at": timezone.now().isoformat(),
        "ator_id": MONITORA,
        "data": data,
    }
    base.update(campos)
    return base


def _entregar(envelope: dict) -> None:
    """O caminho real: o consumidor acha o handler pelo assunto e o chama."""
    HANDLERS[envelope["event"]](envelope)


def _nada_foi_pago() -> None:
    """O zero do marco real, medido nas três moedas desta célula."""
    assert LancamentoDeXP.objects.count() == 0, "o marco real pagou XP"
    assert MovimentoDeCristais.objects.count() == 0, "o marco real pagou Cristal"
    assert all(p.xp_total == 0 for p in PerfilJogador.objects.all())


# ------------------------------------------- 1. o envelope é o do contrato


def test_o_envelope_deste_arquivo_e_o_que_o_contrato_congelou():
    """Validado contra o ARQUIVO, nunca contra uma cópia do formato aqui dentro."""
    jsonschema.validate(_selo(), json.loads(CONTRATO.read_text("utf-8")))


def test_a_tomada_esta_ligada_nas_duas_pontas_e_o_marco_nasce_desligado():
    """Stream assinado, handler no mapa, e o marco semeado como DADO, desligado.

    Quem liga é o mantenedor, em `/admin/economia/`. E o assunto é DECLARADO
    entre os que chegam e não viram ponto: sem essa linha, a tela dele poderia
    um dia oferecer uma regra de pontuação pendurada neste fato sem avisar que
    ela não pagaria nada.
    """
    assert "eventos.pages.portfolio.conferido" in STREAMS
    assert "pages.portfolio.conferido" in HANDLERS
    assert "pages.portfolio.conferido" in NAO_CREDITAM

    call_command("semear_economia", "--site", SITE, stdout=StringIO())
    marco = ConquistaDefinicao.objects.get(site_id=SITE, slug=MARCO_DO_PORTFOLIO)
    assert marco.classe == ConquistaDefinicao.Classe.MARCO
    assert (marco.pontos, marco.cristais) == (0, 0)
    assert marco.ativa is False


# ------------------------------------------- 2. o selo acende, e não paga nada


def test_o_selo_acende_o_marco_e_nao_paga_nada():
    marco = _marco()

    _entregar(_selo())

    concessao = Concessao.objects.get()
    assert concessao.conquista_id == marco.pk
    assert concessao.pessoa_id == ALUNO
    assert concessao.site_id == SITE
    # A auditoria: quem disse que sim, e por causa de qual fato.
    assert concessao.validador_id == MONITORA
    assert concessao.validador_papel == Concessao.PapelDoValidador.MONITOR
    assert concessao.origem_event_id
    _nada_foi_pago()


def test_o_aluno_recebe_a_carta_do_marco_uma_vez_so():
    """Boa notícia vira carta, e o slug viaja; a frase nasce na leitura."""
    _marco()

    _entregar(_selo())

    carta = OutboxEvent.objects.get()
    assert carta.payload["assunto"] == ASSUNTO_MARCO
    assert carta.payload["destinatario_id"] == ALUNO
    assert carta.payload["parametros"]["conquista_slug"] == MARCO_DO_PORTFOLIO


def test_campo_novo_no_dado_nao_derruba_o_marco():
    """Campo que o contrato ainda não conhece é a via ADITIVA (RITOS §3.3)."""
    _marco()

    _entregar(_selo(data={"conferido_por_equipe": True}))

    assert Concessao.objects.count() == 1


# ------------------------------------------- 3. o mesmo selo, duas vezes


def test_o_mesmo_selo_reentregue_acende_uma_vez_so_nas_duas_camadas():
    """A do consumidor protege a ENTREGA; a da concessão protege o MARCO.

    A segunda metade chama o handler DIRETO, sem passar pelo consumidor: é o
    caminho de um reprocesso manual ou de uma migração de dados, que a primeira
    camada não cobre. Prova por mutação: sem o `get_or_create` de
    `validacao.conceder`, esta asserção fica vermelha.
    """
    _marco()
    envelope = _selo()

    processar_envelope(envelope, HANDLERS)
    processar_envelope(envelope, HANDLERS)
    assert EventoProcessado.objects.count() == 1
    assert Concessao.objects.count() == 1

    _entregar(envelope)
    _entregar(envelope)
    assert Concessao.objects.count() == 1, "o marco acendeu duas vezes"
    assert OutboxEvent.objects.count() == 1, "o aluno foi parabenizado duas vezes"
    _nada_foi_pago()


def test_dois_selos_diferentes_do_mesmo_aluno_acendem_um_marco_so():
    """Um portfólio reconferido é o mesmo marco: ele não volta a acender."""
    _marco()

    _entregar(_selo())
    _entregar(_selo(data={"portfolio_id": "pf-2"}))

    assert Concessao.objects.count() == 1
    _nada_foi_pago()


# ------------------------------------------- 4. nada além do selo acende


def test_marco_desligado_nao_acende_e_nao_inventa_pessoa():
    """Ligar uma conquista é decisão do mantenedor, com data. Fail-closed."""
    _marco(ativa=False)

    _entregar(_selo())

    assert Concessao.objects.count() == 0, "um marco desligado acendeu"
    assert Pessoa.objects.count() == 0, "nem a pessoa espelho é inventada"


def test_sem_o_marco_semeado_o_selo_nao_cria_conquista_nenhuma():
    """A escola que nunca semeou não ganha uma conquista inventada pelo evento."""
    _entregar(_selo())

    assert ConquistaDefinicao.objects.count() == 0
    assert Concessao.objects.count() == 0
    assert Pessoa.objects.count() == 0


def test_se_o_slug_apontar_para_uma_medalha_nada_acende_e_ninguem_ganha_xp():
    """A trava do ZERO nesta porta: só MARCO acende aqui.

    Uma medalha paga XP e Cristal, e o banco não a impede de fazê-lo — a
    restrição `marco_real_rende_zero_xp` só vale para a classe `marco`. Se um
    dia o slug do marco passasse a nomear um andaime, este evento estaria
    creditando pontos por um selo. Fail-closed: não acende, e diz por quê.
    """
    _marco(
        classe=ConquistaDefinicao.Classe.MEDALHA,
        familia=ConquistaDefinicao.Familia.OFICIO,
        pontos=50,
        cristais=5,
    )

    _entregar(_selo())

    assert Concessao.objects.count() == 0
    _nada_foi_pago()


def test_o_motor_automatico_nunca_acende_um_marco_sozinho():
    """Sem o selo, o marco não cai — nem com a escola inteira ligada.

    A conta automática (`criterios.avaliar`) só concede MEDALHA, e é essa
    assimetria que impede a escola de afirmar que alguém foi conferido sem
    ninguém ter olhado. Aqui a economia inteira está ligada de propósito: a
    prova é que nenhum marco cai, e não que não havia marco para cair.
    """
    call_command("semear_economia", "--site", SITE, stdout=StringIO())
    ConquistaDefinicao.objects.filter(site_id=SITE).update(ativa=True)

    from apps.gamificacao.motor import recalcular

    recalcular(ALUNO, SITE)

    assert not Concessao.objects.filter(
        conquista__classe=ConquistaDefinicao.Classe.MARCO
    ).exists(), "um marco caiu sem selo nenhum"


# ------------------------------------------- 5. o envelope torto


@pytest.mark.parametrize("faltando", ["site_id", "aluno_id"])
def test_selo_sem_site_ou_sem_aluno_nao_acende_nada(faltando):
    """Fail-closed: sem escola ou sem dono, não se inventa de quem é o marco."""
    _marco()
    torto = _selo()
    del torto["data"][faltando]

    processar_envelope(torto, HANDLERS)

    assert Concessao.objects.count() == 0
    assert Pessoa.objects.count() == 0
    # Registrado como visto, e não devolvido ao fio: reentregar para sempre um
    # envelope sem dono só encheria a fila morta com o mesmo nada.
    assert EventoProcessado.objects.count() == 1


@pytest.mark.parametrize("ator_id", [None, ""])
def test_selo_sem_quem_conferiu_nao_acende_nada(ator_id):
    """Não existe selo que o relógio assine sozinho.

    O contrato declara `ator_id` obrigatório e nunca nulo, mas quem consome fato
    de outra célula não confia na promessa: um marco sem validador não teria
    resposta para "quem disse que sim?" meses depois.
    """
    _marco()

    processar_envelope(_selo(ator_id=ator_id), HANDLERS)
    sem_a_chave = _selo()
    del sem_a_chave["ator_id"]
    processar_envelope(sem_a_chave, HANDLERS)

    assert Concessao.objects.count() == 0
    assert Pessoa.objects.count() == 0
    assert EventoProcessado.objects.count() == 2


def test_ninguem_acende_o_proprio_marco():
    """A trava 2 de `validacao.py`, aqui na porta do evento.

    Um selo em que quem conferiu é o próprio aluno seria a escola reconhecendo
    alguém pela palavra dele mesmo. Nenhuma restrição de banco compara essas
    duas colunas, então a trava mora no código.
    """
    _marco()

    _entregar(_selo(ator_id=ALUNO))

    assert Concessao.objects.count() == 0
    assert Pessoa.objects.count() == 0
