# tests/test_inv_contador_bate_com_a_tabela.py  # [RECEITA:R5 v1]
"""O contador de não lidos é O(1) E diz a verdade — as duas coisas, juntas.

Lei: `docs/decisoes/DECISAO-notificacoes.md` §5.2. O sino aparece em TODA página
do site, então a pergunta "quantos avisos eu tenho" não pode custar uma varredura
numa tabela que cresce para sempre.

**Um contador é uma cópia, e toda cópia pode divergir.** Este arquivo existe
porque a otimização traz um modo de falha novo que a versão lenta não tinha: o
número na tela deixar de bater com a caixa. Um `COUNT(*)` está sempre certo e é
lento; um contador é rápido e pode mentir. Trocar um pelo outro sem este guarda
é trocar um problema visível por um invisível.
"""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.notificacoes.handlers import ao_notificacao_devida
from apps.notificacoes.models import ContadorDeNaoLidos, Notificacao
from tests.conftest import ALGUEM, OUTRA, SITE, envelope_de_carta

pytestmark = pytest.mark.django_db


def _guardar(**kwargs):
    envelope = envelope_de_carta(**kwargs)
    ao_notificacao_devida(envelope["data"], ator_id=envelope["ator_id"])


def _contador(destinatario_id=ALGUEM):
    return ContadorDeNaoLidos.objects.get(
        site_id=SITE, destinatario_id=destinatario_id
    ).nao_lidos


def test_o_contador_bate_com_a_contagem_de_verdade():
    """A igualdade que importa, medida contra o `COUNT(*)` que ele substitui."""
    for _ in range(5):
        _guardar()
    _guardar(destinatario_id=OUTRA)

    for pessoa in (ALGUEM, OUTRA):
        de_verdade = Notificacao.objects.filter(
            site_id=SITE, destinatario_id=pessoa, lido_em__isnull=True
        ).count()
        assert _contador(pessoa) == de_verdade, (
            f"o contador de {pessoa} diz {_contador(pessoa)} e a tabela tem "
            f"{de_verdade} não lidas — a cópia divergiu do original"
        )


def test_a_caixa_de_uma_pessoa_nao_conta_a_da_outra():
    """Sem isto, um contador global passaria em tudo acima."""
    _guardar()
    _guardar()
    _guardar(destinatario_id=OUTRA)

    assert _contador(ALGUEM) == 2
    assert _contador(OUTRA) == 1


def test_ler_o_contador_custa_o_mesmo_com_1_e_com_50_avisos():
    """O(1) medido, não prometido — e medido do jeito que o sino vai ler.

    Comparar dois números medidos, nunca cravar um: cravar transformaria
    qualquer `select_related` novo em vermelho falso, e a pergunta nunca foi
    "quantas consultas" — foi "o custo depende do tamanho da caixa?".
    """
    _guardar()
    with CaptureQueriesContext(connection) as com_uma:
        _contador()

    for _ in range(49):
        _guardar()
    with CaptureQueriesContext(connection) as com_cinquenta:
        _contador()

    assert _contador() == 50, "a cena não foi montada — não há o que medir"
    assert len(com_uma) == len(com_cinquenta), (
        f"ler o contador custou {len(com_uma)} consulta(s) com 1 aviso e "
        f"{len(com_cinquenta)} com 50 — deixou de ser O(1)"
    )


def test_a_carta_e_o_contador_nascem_na_mesma_transacao(monkeypatch):
    """Se o contador falhar, a notificação não fica — e vice-versa.

    O modo de falha que isto fecha é o silencioso: a linha entra, o contador
    estoura, ninguém percebe, e a pessoa passa a ver um número menor que a caixa
    para sempre. Sabotamos o contador e exigimos que NADA tenha sido escrito.
    """
    from apps.notificacoes import services

    def explodir(*args, **kwargs):
        raise RuntimeError("contador fora do ar")

    monkeypatch.setattr(services.ContadorDeNaoLidos.objects, "get_or_create", explodir)

    with pytest.raises(RuntimeError):
        _guardar()

    assert not Notificacao.objects.exists(), (
        "a notificação sobreviveu ao erro do contador — as duas escritas não "
        "estão na mesma transação, e a caixa vai divergir do número na tela"
    )
