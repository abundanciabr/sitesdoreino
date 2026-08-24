# tests/test_inv_status_grava_historico.py  # [RECEITA:R5 v1]
"""INV-SUG07 — mudar status grava histórico, e as duas coisas são UMA transação.

Spec §10 (*"status com histórico append-only"*) e §8. O invariante tem duas
metades, e a segunda é a que costuma faltar:

1. **Toda mudança deixa rastro** — uma linha de `HistoricoStatus` por mudança,
   com de onde veio, para onde foi, a nota e quem mudou.
2. **Se o rastro não puder ser gravado, a mudança não acontece.** Um status
   alterado sem histórico é pior que uma mudança que não aconteceu: ninguém
   consegue nem descobrir que aconteceu, nem quando, nem por quem. Por isso as
   duas escritas vivem dentro do mesmo `transaction.atomic()` em
   `registrar_mudanca_de_status()` — e o guarda que falsifica isso derruba a
   gravação do histórico de propósito e confere que o status ficou onde estava.

O que este arquivo **não** precisa provar de novo: que a linha é imutável
depois de criada. Isso é o INV-SUG02, e mora em
`tests/test_inv_historico_append_only.py`, em três degraus, incluindo um
trigger no Postgres.
"""

import pytest
from django.urls import reverse

from apps.sugestoes.models import HistoricoStatus, Sugestao

pytestmark = pytest.mark.django_db


def _mudar(equipe, sugestao, status, nota=""):
    return equipe.client.post(
        reverse("mudar_status", args=[sugestao.id]), {"status": status, "nota": nota}
    )


def test_mudar_o_status_grava_exatamente_uma_linha(equipe, sugestao):
    resposta = _mudar(equipe, sugestao, Sugestao.Status.PLANEJADO, "entra na trilha 2")

    assert resposta.status_code == 302, resposta.content
    sugestao.refresh_from_db()
    assert sugestao.status == Sugestao.Status.PLANEJADO
    assert HistoricoStatus.objects.count() == 1


def test_a_linha_guarda_de_onde_veio_para_onde_foi_a_nota_e_quem_mudou(
    equipe, sugestao
):
    _mudar(equipe, sugestao, Sugestao.Status.EM_DESENVOLVIMENTO, "começou hoje")

    linha = HistoricoStatus.objects.get()
    assert linha.sugestao_id == sugestao.id
    assert linha.status_anterior == Sugestao.Status.EM_ANALISE
    assert linha.status_novo == Sugestao.Status.EM_DESENVOLVIMENTO
    assert linha.nota == "começou hoje"
    assert linha.alterado_por_id == equipe.identidade.id


def test_duas_mudancas_deixam_duas_linhas_encadeadas(equipe, sugestao):
    """A segunda linha começa onde a primeira terminou — é o que faz o
    histórico ser uma linha do tempo, e não um monte de fatos soltos."""
    _mudar(equipe, sugestao, Sugestao.Status.PLANEJADO)
    _mudar(equipe, sugestao, Sugestao.Status.IMPLEMENTADO, "saiu na v1.4")

    passos = list(HistoricoStatus.objects.values_list("status_anterior", "status_novo"))
    assert passos == [
        (Sugestao.Status.EM_ANALISE, Sugestao.Status.PLANEJADO),
        (Sugestao.Status.PLANEJADO, Sugestao.Status.IMPLEMENTADO),
    ]


def test_se_o_historico_NAO_PUDER_ser_gravado_o_status_nao_muda(
    equipe, sugestao, monkeypatch
):
    """O guarda da transação: derruba a gravação do rastro e mede o status.

    `HistoricoStatus.save` é o ponto exato onde `objects.create()` toca o
    banco. Com ele explodindo, a única coisa que separa "status alterado sem
    rastro" de "nada aconteceu" é o `atomic` — se as duas escritas estiverem
    soltas, o `UPDATE` do status já commitou quando o histórico falha, e este
    teste fica vermelho.
    """

    def explodir(self, *args, **kwargs):
        raise RuntimeError("o banco caiu no meio da gravação do histórico")

    monkeypatch.setattr(HistoricoStatus, "save", explodir)

    with pytest.raises(RuntimeError):
        _mudar(equipe, sugestao, Sugestao.Status.IMPLEMENTADO, "vai dar errado")

    sugestao.refresh_from_db()
    assert sugestao.status == Sugestao.Status.EM_ANALISE, (
        "o status mudou sem que o histórico fosse gravado — as duas escritas "
        "precisam estar na MESMA transação."
    )
    assert HistoricoStatus.objects.count() == 0


def test_status_fora_da_lista_e_recusado_e_nao_grava_nada(equipe, sugestao):
    resposta = _mudar(equipe, sugestao, "virou_unicornio")

    assert resposta.status_code == 400
    sugestao.refresh_from_db()
    assert sugestao.status == Sugestao.Status.EM_ANALISE
    assert HistoricoStatus.objects.count() == 0


def test_mesclado_nao_entra_pela_porta_do_status(equipe, sugestao):
    """`mesclado` é status legítimo do model e mesmo assim é recusado aqui.

    Mesclar é **V1.1** (spec §10) e é uma operação transacional inteira: mover
    votos sem duplicar ator, preservar comentários e histórico, manter a URL
    antiga resolvendo. Deixar o rótulo disponível daria à equipe um jeito de
    marcar "mesclado" sem que nada tivesse sido mesclado — e a lista de
    mescladas nasceria mentindo, com `sugestao_canonica` vazia.
    """
    resposta = _mudar(equipe, sugestao, Sugestao.Status.MESCLADO, "juntei com a outra")

    assert resposta.status_code == 400
    sugestao.refresh_from_db()
    assert sugestao.status == Sugestao.Status.EM_ANALISE
    assert HistoricoStatus.objects.count() == 0
