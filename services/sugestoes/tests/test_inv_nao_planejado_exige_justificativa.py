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
from django.urls import reverse

from apps.sugestoes.models import HistoricoStatus, Sugestao

pytestmark = pytest.mark.django_db


def _recusar(equipe, sugestao, nota=""):
    return equipe.client.post(
        reverse("mudar_status", args=[sugestao.id]),
        {"status": Sugestao.Status.NAO_PLANEJADO, "nota": nota},
    )


def test_sem_justificativa_a_mudanca_e_recusada_e_nada_e_escrito(equipe, sugestao):
    resposta = _recusar(equipe, sugestao)

    assert resposta.status_code == 400
    sugestao.refresh_from_db()
    assert sugestao.status == Sugestao.Status.EM_ANALISE
    assert HistoricoStatus.objects.count() == 0


def test_justificativa_so_de_espaco_nao_conta(equipe, sugestao):
    """Senão o portão vira peneira: um espaço passaria por "texto"."""
    resposta = _recusar(equipe, sugestao, "   \n\t  ")

    assert resposta.status_code == 400
    sugestao.refresh_from_db()
    assert sugestao.status == Sugestao.Status.EM_ANALISE
    assert HistoricoStatus.objects.count() == 0


def test_a_recusa_diz_o_que_falta_em_portugues(equipe, sugestao):
    corpo = _recusar(equipe, sugestao).content.decode()

    assert "Não planejado" in corpo
    assert "quem sugeriu vai ler" in corpo


def test_com_justificativa_passa_e_a_nota_fica_no_historico(equipe, sugestao):
    motivo = "Não cabe no escopo do curso: é assunto de outra formação."

    resposta = _recusar(equipe, sugestao, motivo)

    assert resposta.status_code == 302, resposta.content
    sugestao.refresh_from_db()
    assert sugestao.status == Sugestao.Status.NAO_PLANEJADO
    linha = HistoricoStatus.objects.get()
    assert linha.status_novo == Sugestao.Status.NAO_PLANEJADO
    assert linha.nota == motivo


def test_os_outros_status_nao_exigem_nota(equipe, sugestao):
    """A exigência é DESTE status, não do formulário — senão a equipe passaria
    a escrever "ok" em tudo, e o campo perderia o sentido justamente onde ele
    importa."""
    for status in (
        Sugestao.Status.PLANEJADO,
        Sugestao.Status.EM_DESENVOLVIMENTO,
        Sugestao.Status.IMPLEMENTADO,
        Sugestao.Status.EM_ANALISE,
    ):
        resposta = equipe.client.post(
            reverse("mudar_status", args=[sugestao.id]), {"status": status}
        )
        assert resposta.status_code == 302, f"{status}: {resposta.content}"

    sugestao.refresh_from_db()
    assert sugestao.status == Sugestao.Status.EM_ANALISE
    assert HistoricoStatus.objects.count() == 4


def test_depois_de_recusado_o_texto_digitado_volta_na_tela(equipe, sugestao):
    """Detalhe de gente: quem escreveu um parágrafo e errou o campo não pode
    perder o parágrafo. O rascunho da nota volta preenchido."""
    corpo = _recusar(equipe, sugestao, "  ").content.decode()
    assert "Não planejado" in corpo

    escrito = "Fora de escopo, e aqui está o porquê inteiro."
    corpo = equipe.client.post(
        reverse("mudar_status", args=[sugestao.id]),
        {"status": "virou_unicornio", "nota": escrito},
    ).content.decode()
    assert escrito in corpo
