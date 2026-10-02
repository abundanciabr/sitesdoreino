# tests/test_inv_nao_planejado_exige_justificativa.py  # [RECEITA:R5 v1]
"""A nota da mudança de fase é opcional e, quando escrita, fica no histórico."""

import pytest

from apps.sugestoes.models import HistoricoStatus, Sugestao

pytestmark = pytest.mark.django_db


def _recusar(equipe, sugestao, nota=""):
    """Pelo contrato — a tela de `/moderacao` foi aposentada em 30/08/2026."""
    return equipe.gestao.mudar_status(
        equipe, sugestao, Sugestao.Status.NAO_PLANEJADO, nota=nota
    )


def test_sem_justificativa_a_mudanca_e_registrada(equipe, sugestao):
    resposta = _recusar(equipe, sugestao)

    assert resposta.status_code == 200, resposta.content
    sugestao.refresh_from_db()
    assert sugestao.status == Sugestao.Status.NAO_PLANEJADO
    assert HistoricoStatus.objects.get().nota == ""


def test_justificativa_so_de_espaco_vira_nota_vazia(equipe, sugestao):
    resposta = _recusar(equipe, sugestao, "   \n\t  ")

    assert resposta.status_code == 200, resposta.content
    sugestao.refresh_from_db()
    assert sugestao.status == Sugestao.Status.NAO_PLANEJADO
    assert HistoricoStatus.objects.get().nota == ""


def test_com_justificativa_passa_e_a_nota_fica_no_historico(equipe, sugestao):
    motivo = "Não cabe no escopo do curso: é assunto de outra formação."

    resposta = _recusar(equipe, sugestao, motivo)

    assert resposta.status_code == 200, resposta.content
    sugestao.refresh_from_db()
    assert sugestao.status == Sugestao.Status.NAO_PLANEJADO
    linha = HistoricoStatus.objects.get()
    assert linha.status_novo == Sugestao.Status.NAO_PLANEJADO
    assert linha.nota == motivo


def test_os_outros_status_nao_exigem_nota(equipe, sugestao, changespec):
    """A exigência é DESTE status, não do formulário — senão a equipe passaria
    a escrever "ok" em tudo, e o campo perderia o sentido justamente onde ele
    importa.

    **O `changespec` no argumento é do EVO-40, e é precondição, não
    afrouxamento.** A volta deste teste passa por `planejado →
    em_desenvolvimento`, que desde a trava do ChangeSpec (INV-SUG10) exige
    corredor registrado. Sem a fixture, este guarda passaria a medir a trava —
    e ficaria vermelho por um motivo que não é o dele. O que ele afirma
    continua idêntico: nenhum destes quatro status pede justificativa.
    """
    for status in (
        Sugestao.Status.PLANEJADO,
        Sugestao.Status.EM_DESENVOLVIMENTO,
        Sugestao.Status.IMPLEMENTADO,
        Sugestao.Status.EM_ANALISE,
    ):
        resposta = equipe.gestao.mudar_status(equipe, sugestao, status)
        assert resposta.status_code == 200, f"{status}: {resposta.content}"

    sugestao.refresh_from_db()
    assert sugestao.status == Sugestao.Status.EM_ANALISE
    assert HistoricoStatus.objects.count() == 4


# `test_depois_de_recusado_o_texto_digitado_volta_na_tela` saiu daqui em
# 30/08/2026 junto com a tela que ele media: ele exigia que o formulário fosse
# REDESENHADO com o rascunho dentro, e formulário é do consumidor — esta célula
# devolve `Recusa` em JSON e não desenha tela nenhuma. O cuidado que ele
# protegia (quem escreveu um parágrafo e errou o campo não pode perder o
# parágrafo) é hoje responsabilidade da tela do Admin, e está anotado no
# relatório da TAR-023 como diferença conhecida.
