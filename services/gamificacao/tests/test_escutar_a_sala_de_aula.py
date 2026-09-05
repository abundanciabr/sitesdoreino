"""A porta de uma aula abre na sala de aula, e o ponto cai aqui.

A célula `cursos` publica `aula.concluida.v1` toda vez que um laudo ABRE a porta
de uma aula (degrau 2.2 da escada dela); esta é a outra metade da ponte, o
degrau 2.5: a tomada que a lei desta célula previa desde o plano ("entregar dá
XP, aprovar dá porta"), ligada nas três pontas: o consumidor assina o assunto, o
handler credita, a regra está semeada.

O QUE ESTE ARQUIVO TRAVA:

1. **O envelope do teste é o que o contrato fixa.** Um envelope de fantasia
   provaria que o motor funciona com dados que nunca vão chegar
   (`armadilhas/255`): aqui ele é validado contra o ARQUIVO congelado.
2. **Regra desligada não paga, e ligar depois não paga o passado.** A data de
   vigência nasce no clique do mantenedor, e o motor recusa fato anterior a ela.
3. **O mesmo evento paga uma vez só**, nas duas camadas: a do consumidor
   (`EventoProcessado`) e a do ledger (`Unique(origem_event_id, regra_slug,
   pessoa)`). A segunda segura sozinha, e é ela que a prova por mutação derruba.
4. **Fechar um Bloco (`e_boss`) paga o mesmo XP e ainda NÃO concede medalha.**
   O vocabulário fechado de critérios não tem palavra para "fechou um Bloco", e
   acrescentá-la é decisão do mantenedor, não de um handler.
5. **Envelope torto não credita pela metade.** Sem `ator_id` não há de quem ser
   o ponto: nada é pago, nenhuma pessoa fantasma nasce. E campo NOVO no dado
   não derruba o crédito: é a via aditiva dos contratos (RITOS §3.3).
"""

from __future__ import annotations

import json
import uuid
from datetime import timedelta
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
from apps.gamificacao.handlers import HANDLERS, NAO_CREDITAM
from apps.gamificacao.interruptores import mudar
from apps.gamificacao.models import (
    Concessao,
    ConquistaDefinicao,
    LancamentoDeXP,
    PerfilJogador,
    Pessoa,
    RegraDePontuacao,
)

pytestmark = pytest.mark.django_db

SITE = "site-de-teste"
ALUNO = "pes-aluno"

CONTRATO = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "eventos"
    / "aula.concluida.v1.json"
)


def _regra(**campos) -> RegraDePontuacao:
    base = {
        "slug": "aula-concluida",
        "site_id": SITE,
        "evento_gatilho": "aula.concluida.v1",
        "beneficiario": RegraDePontuacao.Beneficiario.ATOR,
        "pontos": 50,
        "cristais": 0,
        "acoes_cheias_por_dia": 0,
        "quarentena_horas": 0,
        "ativa": True,
        "vigente_desde": timezone.now() - timedelta(days=365),
    }
    base.update(campos)
    return RegraDePontuacao.objects.create(**base)


def _aula_concluida(**campos) -> dict:
    """O envelope como `contracts/eventos/aula.concluida.v1.json` o fixa."""
    data = {"site_id": SITE, "curso_id": "c-1", "aula_id": "a-07", "e_boss": False}
    data.update(campos.pop("data", {}))
    base = {
        "event": "aula.concluida",
        "version": 1,
        "event_id": str(uuid.uuid4()),
        "occurred_at": timezone.now().isoformat(),
        "ator_id": ALUNO,
        "data": data,
    }
    base.update(campos)
    return base


def _entregar(envelope: dict) -> None:
    """O caminho real: o consumidor acha o handler pelo assunto e o chama."""
    HANDLERS[envelope["event"]](envelope)


# ------------------------------------------- 1. o envelope é o do contrato


def test_o_envelope_deste_arquivo_e_o_que_o_contrato_congelou():
    """Validado contra o ARQUIVO, nunca contra uma cópia do formato aqui dentro."""
    jsonschema.validate(_aula_concluida(), json.loads(CONTRATO.read_text("utf-8")))
    jsonschema.validate(
        _aula_concluida(data={"e_boss": True}),
        json.loads(CONTRATO.read_text("utf-8")),
    )


def test_a_tomada_esta_ligada_nas_tres_pontas_e_nasce_desligada():
    """Stream assinado, handler no mapa, regra semeada como DADO, e `ativa=False`.

    Quem liga é o mantenedor, em /admin/economia/: é ali que a data de vigência
    nasce, e é ela que faz o "nunca retroativo" ter mecanismo.
    """
    assert "eventos.aula.concluida" in STREAMS
    assert "aula.concluida" in HANDLERS
    assert "aula.concluida" not in NAO_CREDITAM

    call_command("semear_economia", "--site", SITE, stdout=StringIO())
    regra = RegraDePontuacao.objects.get(site_id=SITE, slug="aula-concluida")
    assert regra.evento_gatilho == "aula.concluida.v1"
    assert regra.beneficiario == RegraDePontuacao.Beneficiario.ATOR
    assert (regra.pontos, regra.cristais) == (50, 0)
    assert regra.acoes_cheias_por_dia == 0, "uma aula conclui uma vez: sem teto"
    assert regra.quarentena_horas == 0, "o laudo já validou: nada a esperar"
    assert regra.ativa is False
    assert regra.vigente_desde is None


# ------------------------------------------- 2. quem recebe, e quando


def test_a_porta_que_abre_paga_quem_entregou():
    _regra()

    _entregar(_aula_concluida())

    (lancamento,) = LancamentoDeXP.objects.all()
    assert lancamento.pessoa_id == ALUNO
    assert lancamento.pontos == 50
    assert lancamento.regra_slug == "aula-concluida"
    # Definitivo na hora: a validação humana aconteceu ANTES do fato existir.
    assert lancamento.status == LancamentoDeXP.Status.DEFINITIVO
    assert lancamento.liberado_em is None
    assert PerfilJogador.objects.get(pessoa_id=ALUNO).xp_total == 50


def test_regra_desligada_nao_paga_e_ligar_depois_nao_paga_o_passado():
    """A data de vigência nasce no clique de ligar, e o motor recusa fato
    anterior a ela (lei §10.5, "nunca retroativo"). Sem isto, a fila represada
    ou uma reentrega pagaria semanas de passado no segundo do clique."""
    _regra(ativa=False, vigente_desde=None)
    antes_de_ligar = _aula_concluida()
    instante_do_fato = timezone.now()

    _entregar(antes_de_ligar)
    assert LancamentoDeXP.objects.count() == 0, "regra desligada pagou"

    ligou_em = instante_do_fato + timedelta(minutes=1)
    mudar(site_id=SITE, slug="aula-concluida", ativa=True, agora=ligou_em)

    _entregar(antes_de_ligar)  # o MESMO fato, reentregue depois do clique
    assert LancamentoDeXP.objects.count() == 0, "ligar hoje pagou o que era de antes"

    depois = _aula_concluida(occurred_at=(ligou_em + timedelta(minutes=1)).isoformat())
    _entregar(depois)
    assert LancamentoDeXP.objects.count() == 1


# ------------------------------------------- 3. o mesmo evento, duas vezes


def test_o_mesmo_evento_reentregue_paga_uma_vez_so_nas_duas_camadas():
    """A do consumidor protege a ENTREGA; a do ledger protege o CRÉDITO.

    A segunda metade chama o handler DIRETO, sem passar pelo consumidor: é o
    caminho de um reprocesso manual ou de uma migração de dados, que a primeira
    camada não cobre. Prova por mutação: sem a chave única do ledger, esta
    asserção fica vermelha (`Unique(origem_event_id, regra_slug, pessoa)`).
    """
    _regra()
    envelope = _aula_concluida()

    processar_envelope(envelope, HANDLERS)
    processar_envelope(envelope, HANDLERS)
    assert EventoProcessado.objects.count() == 1
    assert LancamentoDeXP.objects.count() == 1

    _entregar(envelope)
    _entregar(envelope)
    assert LancamentoDeXP.objects.count() == 1, "o ledger deixou pagar duas vezes"
    assert PerfilJogador.objects.get(pessoa_id=ALUNO).xp_total == 50


# ------------------------------------------- 4. fechar um Bloco


def test_fechar_um_bloco_paga_o_mesmo_xp_e_ainda_nao_concede_medalha():
    """`e_boss` chega e HOJE não muda nada, e isso é deliberado.

    A medalha "Fechou um Bloco" pediria uma palavra nova no vocabulário fechado
    de critérios (`criterios.CONTAS`) e uma tabela-registro para contá-la, no
    molde de `AjudaAceita`. As duas coisas são decisão do mantenedor (critério
    de morte nº 1 da lei: nada de DSL). Quando ela existir, este teste quebra, e
    é para quebrar: quem a construir troca esta asserção pela concessão.

    Toda medalha semeada está LIGADA aqui, de propósito: a prova é que nenhuma
    delas cai por um Bloco fechado, e não que não havia medalha para cair.
    """
    call_command("semear_economia", "--site", SITE, stdout=StringIO())
    mudar(
        site_id=SITE,
        slug="aula-concluida",
        ativa=True,
        agora=timezone.now() - timedelta(days=1),
    )
    ConquistaDefinicao.objects.filter(
        site_id=SITE, classe=ConquistaDefinicao.Classe.MEDALHA
    ).update(ativa=True)

    _entregar(_aula_concluida(data={"e_boss": True}))

    (lancamento,) = LancamentoDeXP.objects.all()
    assert lancamento.pontos == 50
    assert Concessao.objects.count() == 0


# ------------------------------------------- 5. o envelope torto


@pytest.mark.parametrize("ator_id", [None, ""])
def test_sem_aluno_no_envelope_ninguem_e_pago_e_ninguem_nasce(ator_id):
    """Fail-closed: sem quem recebe, não se inventa um dono para o ponto.

    O contrato declara `ator_id` obrigatório e nunca nulo, mas quem consome fato
    de outra célula não confia na promessa. Pagar a um id inventado criaria uma
    pessoa fantasma que nenhuma sessão jamais resolve (`armadilhas/255`): o
    ledger enche e a tela de quem entregou continua em zero, sem erro nenhum.
    """
    _regra()

    processar_envelope(_aula_concluida(ator_id=ator_id), HANDLERS)
    sem_a_chave = _aula_concluida()
    del sem_a_chave["ator_id"]
    processar_envelope(sem_a_chave, HANDLERS)

    assert LancamentoDeXP.objects.count() == 0
    assert Pessoa.objects.count() == 0, "nem a pessoa espelho é inventada"
    assert PerfilJogador.objects.count() == 0
    # Registrado como visto, e não devolvido ao fio: reentregar para sempre um
    # envelope sem dono só encheria a fila morta com o mesmo nada.
    assert EventoProcessado.objects.count() == 2


def test_campo_novo_no_dado_nao_derruba_o_credito():
    """Um campo que o contrato ainda não conhece é a via ADITIVA do Rito de
    Contrato (RITOS §3.3): um consumidor que o recusasse transformaria toda
    emenda retrocompatível em quebra."""
    _regra()

    _entregar(_aula_concluida(data={"bloco": "A"}))

    assert LancamentoDeXP.objects.count() == 1
