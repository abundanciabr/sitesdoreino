# tests/test_volume_dos_avisos.py
"""O leque de avisos custa o mesmo com 2 e com 20 interessados.
Compara dois números medidos em vez de cravar um: o custo não depende da plateia."""

import pytest
from django.db import transaction
from django.test.utils import CaptureQueriesContext
from django.db import connection

from apps.core.avisos import avisar_os_interessados
from apps.sugestoes.models import Aviso, Sugestao

pytestmark = pytest.mark.django_db

PEQUENA = 2
GRANDE = 20


def _contar(fazer) -> tuple[int, list[str]]:
    with CaptureQueriesContext(connection) as consultas:
        fazer()
    return len(consultas), [c["sql"] for c in consultas]


def _sem_savepoint(sql: list[str]) -> list[str]:
    """Só as idas ao banco: tira `SAVEPOINT`, `RELEASE` e `ROLLBACK TO` do atomic
    aninhado."""
    return [
        linha
        for linha in sql
        if not linha.startswith(("SAVEPOINT", "RELEASE SAVEPOINT", "ROLLBACK TO"))
    ]


def _uma_sugestao(quadro, categoria, autor, titulo):
    return Sugestao.objects.create(
        quadro=quadro,
        categoria=categoria,
        autor=autor,
        titulo=titulo,
        problema="Assisto no ônibus e não dá para ouvir.",
    )


def test_o_fan_out_custa_o_mesmo_com_2_e_com_20_interessados(
    quadro, categoria, aluno, plateia
):
    """Degrau 1: a função isolada faz as mesmas três consultas com plateia pequena ou
    grande."""
    pequena = _uma_sugestao(quadro, categoria, aluno, "Plateia pequena")
    grande = _uma_sugestao(quadro, categoria, aluno, "Plateia grande")
    plateia(pequena, votantes=PEQUENA, comentaristas=PEQUENA, marca="peq")
    plateia(grande, votantes=GRANDE, comentaristas=GRANDE, marca="gra")

    def _avisar(sugestao):
        def _fazer():
            with transaction.atomic():
                avisar_os_interessados(
                    sugestao=sugestao,
                    status_anterior=Sugestao.Status.EM_ANALISE,
                    status_novo=Sugestao.Status.PLANEJADO,
                    nota="anda",
                )

        return _fazer

    poucas, sql_poucas = _contar(_avisar(pequena))
    muitas, _ = _contar(_avisar(grande))

    # A prova de que a medição mediu alguma coisa: as plateias são MESMO
    # diferentes. Sem isto, um fan-out quebrado que não escrevesse nada passaria.
    assert Aviso.objects.filter(sugestao=pequena).count() == 2 * PEQUENA + 1
    assert Aviso.objects.filter(sugestao=grande).count() == 2 * GRANDE + 1

    assert poucas == muitas, (
        f"o número de consultas cresceu com a plateia: {poucas} para "
        f"{2 * PEQUENA + 1} interessados, {muitas} para {2 * GRANDE + 1}. "
        "O leque é UMA escrita em lote, não um create() por pessoa.\n"
        + "\n".join(sql_poucas)
    )
    # O custo é pequeno além de constante: três idas ao banco (quem comentou, quem
    # votou, o lote).
    idas = _sem_savepoint(sql_poucas)
    assert len(idas) == 3, idas


def test_a_jornada_inteira_de_mudar_status_nao_cresce_com_a_plateia(
    equipe, quadro, categoria, aluno, plateia
):
    """Degrau 2: o POST de mudar o status também não cresce com a plateia."""
    pequena = _uma_sugestao(quadro, categoria, aluno, "Jornada com poucos")
    grande = _uma_sugestao(quadro, categoria, aluno, "Jornada com muitos")
    plateia(pequena, votantes=PEQUENA, comentaristas=PEQUENA, marca="jpeq")
    plateia(grande, votantes=GRANDE, comentaristas=GRANDE, marca="jgra")

    def _post(sugestao):
        def _fazer():
            resposta = equipe.gestao.mudar_status(
                equipe, sugestao, Sugestao.Status.PLANEJADO, nota="vai sair"
            )
            assert resposta.status_code == 200, resposta.content

        return _fazer

    poucas, _ = _contar(_post(pequena))
    muitas, sql_muitas = _contar(_post(grande))

    assert poucas == muitas, (
        f"mudar o status custou {poucas} consultas com {2 * PEQUENA + 1} "
        f"interessados e {muitas} com {2 * GRANDE + 1} — o custo da moderação não "
        "pode depender de quanta gente votou na ideia.\n" + "\n".join(sql_muitas)
    )
