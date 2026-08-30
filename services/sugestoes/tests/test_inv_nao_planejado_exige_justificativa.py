# tests/test_inv_nao_planejado_exige_justificativa.py  # [RECEITA:R5 v1]
"""INV-SUG08 — `nao_planejado` sem justificativa é recusado.

`ESPECIFICACAO-CELULA.md` §10 é explícita: *"'não planejado' com justificativa
obrigatória"*. É o único status com essa exigência, e o motivo é o mesmo que
fez a `DECISAO-EVO-01` §5 proibir o "acesso negado" seco na porta: um "não
vamos fazer" sem uma linha de explicação é a forma mais rápida de a Caixa
ensinar aos alunos que sugerir não adianta. A pessoa escreveu o problema dela;
o mínimo é ela ler por que a resposta foi não.

A recusa acontece **antes** de qualquer escrita — nem o status muda, nem o
histórico ganha linha. E o texto exigido é o texto que vai para o histórico:
uma justificativa que a equipe escreve e o banco não guarda seria teatro.
"""

import pytest

from apps.sugestoes.models import HistoricoStatus, Sugestao

pytestmark = pytest.mark.django_db


def _recusar(equipe, sugestao, nota=""):
    """Pelo contrato — a tela de `/moderacao` foi aposentada em 30/08/2026."""
    return equipe.gestao.mudar_status(
        equipe, sugestao, Sugestao.Status.NAO_PLANEJADO, nota=nota
    )


def test_sem_justificativa_a_mudanca_e_recusada_e_nada_e_escrito(equipe, sugestao):
    resposta = _recusar(equipe, sugestao)

    assert resposta.status_code == 422, resposta.content
    sugestao.refresh_from_db()
    assert sugestao.status == Sugestao.Status.EM_ANALISE
    assert HistoricoStatus.objects.count() == 0


def test_justificativa_so_de_espaco_nao_conta(equipe, sugestao):
    """Senão o portão vira peneira: um espaço passaria por "texto"."""
    resposta = _recusar(equipe, sugestao, "   \n\t  ")

    assert resposta.status_code == 422, resposta.content
    sugestao.refresh_from_db()
    assert sugestao.status == Sugestao.Status.EM_ANALISE
    assert HistoricoStatus.objects.count() == 0


def test_a_recusa_diz_o_que_falta_em_portugues(equipe, sugestao):
    """A MESMA frase que a tela dizia — ela mudou de casa, não de redação."""
    erro = _recusar(equipe, sugestao).json()["erro"]

    assert "escreva o porquê" in erro
    assert "quem sugeriu vai ler" in erro


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
