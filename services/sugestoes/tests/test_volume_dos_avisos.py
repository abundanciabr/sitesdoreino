# tests/test_volume_dos_avisos.py
"""O leque de avisos custa o MESMO com 2 e com 20 interessados (EVO-42).

**Por que este arquivo existe, e por que ele não é um `test_inv_`.** O que ele
prova não é uma regra de correção — um fan-out escrito com um `create()` por
pessoa dentro do laço entrega exatamente os mesmos avisos, para as mesmas
pessoas, na mesma transação, e passa em cada guarda de
`test_inv_aviso_nasce_com_o_status.py`. O que ele prova é **desenho**: que o
custo de mudar um status não cresce com o tamanho da plateia. É a única classe
de erro que só aparece medindo, e é a que o mantenedor pediu para não pagar:
*"já é o começo do que vamos enviar de notificações para o aluno e serão
muitas"*.

O modo de falha que ele fecha é o mais gentil de todos: o desenho errado é o que
sai naturalmente de quem está escrevendo o recurso pela primeira vez, funciona
em dev com três votantes, e só dói na ideia mais votada da Caixa — a que mais
importa, num `SELECT … FOR UPDATE` aberto na linha da sugestão.

**Dois degraus, falsificáveis separadamente** (a lição do elo EVO-40: escada
testada só por fora prova o andar de cima e mente sobre os de baixo):

1. o **fan-out** em si — `avisar_os_interessados()`, três consultas fixas;
2. a **jornada inteira** — o POST da moderação, que é onde alguém poderia
   reintroduzir um laço por fora da função (percorrendo votantes na view, por
   exemplo) sem o degrau 1 notar.

Comparar dois números medidos é melhor que cravar um: cravar `== 3` transforma
qualquer `select_related` novo em vermelho falso, e a pergunta aqui nunca foi
"quantas consultas" — foi "o número depende da plateia?".
"""

import pytest
from django.db import transaction
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.urls import reverse

from apps.core.avisos import avisar_os_interessados, limpar_cache_de_resumo
from apps.sugestoes.models import Aviso, Sugestao

pytestmark = pytest.mark.django_db

PEQUENA = 2
GRANDE = 20


def _contar(fazer) -> tuple[int, list[str]]:
    with CaptureQueriesContext(connection) as consultas:
        fazer()
    return len(consultas), [c["sql"] for c in consultas]


def _sem_savepoint(sql: list[str]) -> list[str]:
    """Só o que consulta o banco de verdade.

    `SAVEPOINT`/`RELEASE` aparecem porque o `django_db` da suíte já abre um
    `atomic`, e um `atomic` aninhado vira savepoint. Eles são constantes e não
    dizem nada sobre o desenho — entram na COMPARAÇÃO (que é entre dois números
    medidos do mesmo jeito) e saem do TETO, que fala de idas ao banco.
    """
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
    """Degrau 1 — a função, isolada de tudo o que a moderação faz em volta.

    Duas sugestões idênticas, plateias de tamanhos muito diferentes, e o mesmo
    número de consultas nas duas: uma para quem comentou, uma para quem votou, e
    um `INSERT` para o leque inteiro. Com um `create()` por pessoa este teste
    compara 2+3 com 20+3 e reprova com os dois números na mensagem.
    """
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
    # E ele não é só constante: é PEQUENO — três idas ao banco, que são as três
    # perguntas do desenho (quem comentou, quem votou, grave o leque). Um fan-out
    # que lesse a `Identidade` de cada pessoa também seria constante em número de
    # consultas por chamada e continuaria errado; este teto o impede de nascer.
    idas = _sem_savepoint(sql_poucas)
    assert len(idas) == 3, idas


def test_a_jornada_inteira_de_mudar_status_nao_cresce_com_a_plateia(
    equipe, quadro, categoria, aluno, plateia
):
    """Degrau 2 — o POST de verdade, com tudo o que ele faz em volta.

    O degrau 1 sozinho mentiria sobre este: um laço escrito na view, por fora da
    função, deixaria `avisar_os_interessados()` com as suas três consultas e faria
    a jornada crescer assim mesmo.
    """
    pequena = _uma_sugestao(quadro, categoria, aluno, "Jornada com poucos")
    grande = _uma_sugestao(quadro, categoria, aluno, "Jornada com muitos")
    plateia(pequena, votantes=PEQUENA, comentaristas=PEQUENA, marca="jpeq")
    plateia(grande, votantes=GRANDE, comentaristas=GRANDE, marca="jgra")

    def _post(sugestao):
        def _fazer():
            resposta = equipe.client.post(
                reverse("mudar_status", args=[sugestao.id]),
                {"status": Sugestao.Status.PLANEJADO, "nota": "vai sair"},
            )
            assert resposta.status_code == 302, resposta.content

        return _fazer

    poucas, _ = _contar(_post(pequena))
    muitas, sql_muitas = _contar(_post(grande))

    assert poucas == muitas, (
        f"mudar o status custou {poucas} consultas com {2 * PEQUENA + 1} "
        f"interessados e {muitas} com {2 * GRANDE + 1} — o custo da moderação não "
        "pode depender de quanta gente votou na ideia.\n" + "\n".join(sql_muitas)
    )


def test_ler_a_pagina_de_avisos_nao_paga_consulta_pelo_vinculo(
    equipe, dentro, quadro, categoria, aluno, plateia
):
    """A outra metade da decisão "coluna × derivar na leitura", medida.

    O vínculo derivado na leitura custaria, além de mudar de valor com o tempo
    (`test_o_vinculo_sobrevive_ao_desvoto`), uma pergunta às tabelas de voto e
    comentário POR AVISO listado — ou um `JOIN` a mais na consulta da página. A
    coluna custa zero: a página com dez avisos faz o mesmo número de consultas
    que a página com um.

    Este é o lado do custo que a decisão põe na mesa; o outro é o da verdade.
    """
    poucos = [
        _uma_sugestao(quadro, categoria, aluno, f"Ideia curta {n}") for n in range(1)
    ]
    muitos = [
        _uma_sugestao(quadro, categoria, aluno, f"Ideia longa {n}") for n in range(10)
    ]

    def _mexer(sugestoes):
        for sugestao in sugestoes:
            Aviso.objects.create(
                destinatario=dentro.identidade,
                sugestao=sugestao,
                status_anterior=Sugestao.Status.EM_ANALISE,
                status_novo=Sugestao.Status.PLANEJADO,
                vinculo=Aviso.Vinculo.VOTO,
            )

    _mexer(poucos)

    def _abrir():
        assert dentro.client.get(reverse("avisos")).status_code == 200

    # O sino no trilho (`apps/core/avisos.py::sino`) também aparece nesta
    # página e tem CACHE PRÓPRIO (`_CACHE_DE_RESUMO`, TTL de 30s) — de
    # propósito, para uma rajada de páginas da mesma pessoa não pagar uma
    # chamada por clique. Sem limpar entre as duas medições, a SEGUNDA
    # visita pegaria o resumo do cache e pagaria consultas A MENOS por
    # isso — um efeito real, só que de OUTRO invariante (o do sino, já
    # coberto em `tests/test_sino_le_a_notificacoes.py`). Limpando antes de
    # cada medição, as duas pagam o mesmo custo de sino, e o que sobra na
    # diferença é só o que este teste quer medir: o custo do `vinculo`.
    limpar_cache_de_resumo()
    com_um, _ = _contar(_abrir)
    _mexer(muitos)
    limpar_cache_de_resumo()
    com_onze, sql = _contar(_abrir)

    assert Aviso.objects.count() == 11
    assert com_um == com_onze, (
        f"a página de avisos passou de {com_um} para {com_onze} consultas ao "
        "crescer de 1 para 11 avisos — o vínculo é coluna justamente para não "
        "cobrar isso.\n" + "\n".join(sql)
    )
