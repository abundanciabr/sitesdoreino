# tests/test_volume_da_api.py  # [RECEITA:R1 v1]
"""As três rotas da Fase 4 custam o MESMO com 2 e com 200 avisos.

**Por que este arquivo existe, e por que ele não é um `test_inv_`** (mesma
razão do `tests/test_volume_dos_avisos.py` da `sugestoes`, EVO-42, que este
arquivo imita de propósito — é o padrão que o despacho pediu para seguir). O
que ele prova não é uma regra de correção — um `/avisos` que fizesse um
`SELECT` por item da lista devolveria exatamente os mesmos avisos, na mesma
ordem, e passaria em cada guarda de `tests/test_api_avisos.py`. O que ele
prova é DESENHO: que o custo de responder "quantos" ou "quais" não cresce com
o tamanho da caixa. É a mesma exigência da `DECISAO-notificacoes` §5.2 — "o
sino aparece em TODA página" — agora medida do lado de fora, pela porta HTTP.

Comparar dois números MEDIDOS é melhor que cravar um: cravar `== 3` (por
exemplo) transformaria qualquer índice novo em vermelho falso, e a pergunta
aqui nunca foi "quantas consultas" — foi "o número depende de quantos avisos
a pessoa tem?".
"""

import json
import uuid

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.notificacoes.services import guardar
from tests.conftest import EQUIPE, SITE, cabecalho_bearer

pytestmark = pytest.mark.django_db

POUCOS = 2
MUITOS = 200


def _semear(destinatario_id: str, quantidade: int) -> None:
    for _ in range(quantidade):
        guardar(
            site_id=SITE,
            destinatario_id=destinatario_id,
            ator_id=EQUIPE,
            assunto="sugestao.status-alterado",
            parametros={"suggestion_id": "1"},
            origem_event_id=str(uuid.uuid4()),
        )


def _contar(fazer) -> tuple[int, list[str]]:
    with CaptureQueriesContext(connection) as consultas:
        fazer()
    return len(consultas), [c["sql"] for c in consultas]


def _sem_savepoint(sql: list[str]) -> list[str]:
    """Só o que consulta o banco de verdade — `SAVEPOINT`/`RELEASE` são o
    `atomic` que o `django_db` da suíte já abre, constantes nas duas medições
    e sem nada a dizer sobre o desenho (mesmo filtro de `test_volume_dos_avisos.py`
    da `sugestoes`)."""
    return [
        linha
        for linha in sql
        if not linha.startswith(("SAVEPOINT", "RELEASE SAVEPOINT", "ROLLBACK TO"))
    ]


def test_resumo_custa_o_mesmo_com_2_e_com_200_avisos(client, par_autorizado):
    _semear("pessoa-resumo-poucos", POUCOS)
    _semear("pessoa-resumo-muitos", MUITOS)

    def _pedir(destinatario_id):
        def _fazer():
            resposta = client.get(
                "/api/notificacoes/resumo",
                {"destinatario_id": destinatario_id},
                headers=cabecalho_bearer(),
            )
            assert resposta.status_code == 200, resposta.content

        return _fazer

    poucas, sql_poucas = _contar(_pedir("pessoa-resumo-poucos"))
    muitas, sql_muitas = _contar(_pedir("pessoa-resumo-muitos"))

    assert poucas == muitas, (
        f"/resumo custou {poucas} consulta(s) com {POUCOS} avisos e {muitas} "
        f"com {MUITOS} — deixou de ser O(1).\n" + "\n".join(sql_poucas)
    )


def test_avisos_custa_o_mesmo_com_2_e_com_200_avisos(client, par_autorizado):
    _semear("pessoa-avisos-poucos", POUCOS)
    _semear("pessoa-avisos-muitos", MUITOS)

    def _pedir(destinatario_id):
        def _fazer():
            resposta = client.get(
                "/api/notificacoes/avisos",
                # limite MÁXIMO de propósito: até pedindo a página mais cara
                # que o contrato permite, o custo não pode depender do total.
                {"destinatario_id": destinatario_id, "limite": 100},
                headers=cabecalho_bearer(),
            )
            assert resposta.status_code == 200, resposta.content

        return _fazer

    poucas, sql_poucas = _contar(_pedir("pessoa-avisos-poucos"))
    muitas, sql_muitas = _contar(_pedir("pessoa-avisos-muitos"))

    assert poucas == muitas, (
        f"/avisos custou {poucas} consulta(s) com {POUCOS} avisos e {muitas} "
        f"com {MUITOS} — deixou de ser O(1).\n" + "\n".join(sql_poucas)
    )
    # E ele não é só constante: é DUAS — uma por tabela (Notificacao +
    # NotificacaoArquivada), nunca uma por item da página.
    idas = _sem_savepoint(sql_poucas)
    assert len(idas) == 2, idas


def test_marcar_lidas_custa_o_mesmo_com_2_e_com_200_avisos(client, par_autorizado):
    _semear("pessoa-marcar-poucos", POUCOS)
    _semear("pessoa-marcar-muitos", MUITOS)

    def _marcar(destinatario_id):
        def _fazer():
            resposta = client.post(
                "/api/notificacoes/marcar-lidas",
                data=json.dumps({"destinatario_id": destinatario_id}),
                content_type="application/json",
                headers=cabecalho_bearer(),
            )
            assert resposta.status_code == 200, resposta.content

        return _fazer

    poucas, sql_poucas = _contar(_marcar("pessoa-marcar-poucos"))
    muitas, sql_muitas = _contar(_marcar("pessoa-marcar-muitos"))

    assert poucas == muitas, (
        f"/marcar-lidas custou {poucas} consulta(s) marcando {POUCOS} avisos "
        f"e {muitas} marcando {MUITOS} — deixou de ser O(1).\n" + "\n".join(sql_poucas)
    )
