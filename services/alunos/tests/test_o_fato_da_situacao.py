"""O FATO `matricula.situacao-alterada`, que nasceu no degrau 8 do painel.

A pergunta que este arquivo existe para responder, e que a suíte da CARTA
(`test_a_carta_da_liberacao.py`) não responde: **toda mudança de situação de
uma matrícula deixa rastro?**

Por que as duas suítes são separadas, e não uma:

- a **carta** avisa UMA pessoa, e só nasce quando ela GANHA acesso e tem
  identidade da plataforma;
- o **fato** conta o que aconteceu com a matrícula, e nasce SEMPRE.

Recusa, suspensão, encerramento e reembolso não produzem carta nenhuma. São
justamente as mudanças de que o livro de fatos precisa, e um livro append-only
não se preenche para trás: o que não for anotado na hora está perdido. É por
isso que o guarda mais importante daqui é o §1 (os cinco caminhos), e não o
formato do envelope.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apps.matriculas.eventos import SITUACAO_ALTERADA, fato_de_situacao
from apps.matriculas.models import Matricula, OutboxEvent
from apps.matriculas.services import (
    atualizar_matricula,
    decidir_na_fila,
    entrar_na_fila,
    matricular,
)

pytestmark = pytest.mark.django_db

# [INV-ALU-C1] Desde 06/09/2026 liberar exige dizer o curso
# (`docs/decisoes/DECISAO-cursos-matriculas-e-alunos.md`). Aqui vale qualquer
# texto opaco: o valor de verdade e um id de produto do `catalogo`, e quem prova
# a exigencia e `tests/test_inv_alu_c1_a_matricula_diz_o_curso.py`.
CURSO = "produto-do-curso-1"

CONTRATO = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "eventos"
    / "matricula.situacao-alterada.v1.json"
)


def _fatos():
    """So os FATOS — a mesma outbox carrega tambem as cartas."""
    return list(OutboxEvent.objects.filter(event=SITUACAO_ALTERADA).order_by("id"))


def _envelope(evento: OutboxEvent) -> dict:
    """O envelope como o relay o montaria: a forma que vai para o fio."""
    envelope = {
        "event": evento.event,
        "version": evento.version,
        "event_id": str(evento.event_id),
        "occurred_at": evento.occurred_at.isoformat(),
        "data": evento.payload,
    }
    envelope.update(evento.envelope_extra)
    return envelope


def _na_fila(email="quem.espera@exemplo.test"):
    linha, _ = entrar_na_fila(
        site_id="escola-a",
        email=email,
        nome_completo="Quem Espera",
        whatsapp="(96) 99999-0000",
    )
    return linha


def _comprou(order_id="pedido-1", email="quem.comprou@exemplo.test"):
    linha, _ = matricular(
        site_id="escola-a",
        order_id=order_id,
        product_id="curso-1",
        email=email,
        name="Quem Comprou",
    )
    return linha


# --------------------------------------------------------------------------
# §1 OS CINCO CAMINHOS. Se um deles parar de anotar, o livro fica com um
#    buraco que ninguem descobre olhando a tela — so meses depois, quando a
#    historia for pedida e nao existir.
# --------------------------------------------------------------------------


def test_a_compra_que_cria_a_matricula_anota_o_fato():
    _comprou()
    (fato,) = _fatos()
    assert fato.payload["situacao_nova"] == Matricula.STATUS_ATIVA
    assert fato.payload["origem"] == "comprou"
    # Nasceu: nao havia estado anterior, e ausencia diz isso melhor que "".
    assert "situacao_anterior" not in fato.payload


def test_quem_pede_entrada_anota_o_fato():
    _na_fila()
    (fato,) = _fatos()
    assert fato.payload["situacao_nova"] == Matricula.STATUS_AGUARDANDO
    assert fato.payload["origem"] == "liberado"
    assert "situacao_anterior" not in fato.payload


def test_liberar_anota_o_fato():
    linha = _na_fila()
    decidir_na_fila(
        id_da_linha=str(linha.pk),
        decisao="liberar",
        decidido_por="idt-do-mantenedor",
        product_id=CURSO,
    )
    _, fato = _fatos()
    assert fato.payload["situacao_anterior"] == Matricula.STATUS_AGUARDANDO
    assert fato.payload["situacao_nova"] == Matricula.STATUS_ATIVA


def test_recusar_anota_o_fato_mesmo_sem_carta_nenhuma():
    """O caso que justifica o contrato: recusa NUNCA gera carta."""
    linha = _na_fila()
    decidir_na_fila(
        id_da_linha=str(linha.pk),
        decisao="recusar",
        decidido_por="idt-do-mantenedor",
        motivo="nao achei sua compra",
    )
    _, fato = _fatos()
    assert fato.payload["situacao_nova"] == Matricula.STATUS_RECUSADA
    assert not OutboxEvent.objects.filter(event="notificacao.devida").exists()


def test_quem_foi_recusado_e_reenvia_anota_a_volta_para_a_fila():
    linha = _na_fila()
    decidir_na_fila(
        id_da_linha=str(linha.pk),
        decisao="recusar",
        decidido_por="idt-do-mantenedor",
        motivo="x",
    )
    _na_fila()  # a mesma pessoa reenvia
    fato = _fatos()[-1]
    assert fato.payload["situacao_anterior"] == Matricula.STATUS_RECUSADA
    assert fato.payload["situacao_nova"] == Matricula.STATUS_AGUARDANDO


@pytest.mark.parametrize(
    "novo",
    [
        Matricula.STATUS_SUSPENSA,
        Matricula.STATUS_ENCERRADA,
        Matricula.STATUS_REEMBOLSADA,
    ],
)
def test_perder_acesso_anota_o_fato_e_e_o_que_a_carta_nunca_conta(novo):
    """Suspender, encerrar e reembolsar: sem carta, e o livro precisa dos tres."""
    linha = _comprou()
    atualizar_matricula(
        id_da_linha=str(linha.pk),
        mudancas={"status": novo},
        decidido_por="idt-do-mantenedor",
    )
    fato = _fatos()[-1]
    assert fato.payload["situacao_anterior"] == Matricula.STATUS_ATIVA
    assert fato.payload["situacao_nova"] == novo
    assert not OutboxEvent.objects.filter(event="notificacao.devida").exists()


def test_corrigir_um_dado_sem_mexer_no_status_NAO_anota_fato():
    """O fato e sobre SITUACAO. Trocar o nome da pessoa nao e mudanca de estado."""
    linha = _comprou()
    antes = len(_fatos())
    atualizar_matricula(
        id_da_linha=str(linha.pk),
        mudancas={"nome_completo": "Nome Corrigido"},
        decidido_por="idt-do-mantenedor",
    )
    assert len(_fatos()) == antes


def test_a_funcao_recusa_anotar_quando_nada_mudou():
    """A decisao mora num lugar so: quem chama sempre chama, e ela decide."""
    linha = _comprou()
    assert fato_de_situacao(linha, anterior=linha.status) is None


# --------------------------------------------------------------------------
# §2 O QUE VAI DENTRO
# --------------------------------------------------------------------------


def test_o_envelope_casa_com_o_contrato_congelado():
    import jsonschema

    linha = _na_fila()
    decidir_na_fila(
        id_da_linha=str(linha.pk),
        decisao="liberar",
        decidido_por="idt-do-mantenedor",
        product_id=CURSO,
    )
    schema = json.loads(CONTRATO.read_text(encoding="utf-8"))
    fatos = _fatos()
    # Sem esta linha o teste passaria por verdade VAZIA: uma lista sem fato
    # nenhum satisfaz "todos casam com o contrato" (armadilhas/266).
    assert len(fatos) == 2, "esperava o nascimento na fila e a liberacao"
    for fato in fatos:
        jsonschema.validate(_envelope(fato), schema)


def test_o_fato_nao_leva_nome_email_nem_telefone():
    """Nenhum dado pessoal viaja em evento — lei da casa, e o contrato fecha a porta."""
    _na_fila(email="pessoa@exemplo.test")
    fatos = _fatos()
    assert fatos, "sem fato nenhum este teste passaria por vazio"
    cru = json.dumps([f.payload for f in fatos], ensure_ascii=False)
    assert "pessoa@exemplo.test" not in cru
    assert "Quem Espera" not in cru
    assert "99999-0000" not in cru


def test_virou_aluno_em_e_nulo_enquanto_ninguem_decidiu_e_preenche_ao_liberar():
    linha = _na_fila()
    (nascimento,) = _fatos()
    assert nascimento.payload["virou_aluno_em"] is None

    decidir_na_fila(
        id_da_linha=str(linha.pk),
        decisao="liberar",
        decidido_por="idt-do-mantenedor",
        product_id=CURSO,
    )
    _, liberacao = _fatos()
    assert liberacao.payload["virou_aluno_em"] is not None


def test_o_ator_vai_no_envelope_e_e_nulo_quando_ninguem_apertou_botao():
    """A compra nao tem gente: o provedor aprovou o pagamento."""
    _comprou()
    (fato,) = _fatos()
    assert fato.envelope_extra["ator_id"] is None

    linha = _na_fila()
    decidir_na_fila(
        id_da_linha=str(linha.pk),
        decisao="liberar",
        decidido_por="idt-do-mantenedor",
        product_id=CURSO,
    )
    assert _fatos()[-1].envelope_extra["ator_id"] == "idt-do-mantenedor"
