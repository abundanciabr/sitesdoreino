"""O placar de doze e as estrelas-guia (degrau 4 do plano do painel de gestão).

O que estes guardas protegem:

1. **Os doze cartões existem, são válidos e cada um diz a verdade**: os que
   têm fonte medem; os que não têm dizem por quê (`sem_fonte_porque`).
2. **As duas estrelas-guia seguram uma à outra** (o par é mútuo).
3. **Crescimento mês a mês só existe com dois meses fechados** depois da
   partida; antes disso a tela diz "a partir de quando", nunca zero.
4. **Aprendizados validados contam o LABORATÓRIO**: experimento fechado com
   veredito de venceu ou perdeu, desde a partida. Zero contado é zero.
5. **"Não medi" nunca vira "sem fonte"**: fonte que existe e não respondeu é
   `nao-consigo-medir`.
"""

from __future__ import annotations

import datetime as dt

from apps.core import doze, placar

PARTIDA = dt.date(2026, 9, 3)


def _aluna(dia: str, status: str = "ativa") -> dict:
    return {
        "status": status,
        "origem": "liberado",
        "virou_aluno_em": f"{dia}T12:00:00-03:00",
    }


def test_os_doze_existem_sao_validos_e_estao_no_andar_zero():
    assert len(doze.DOZE) == 12 and len(set(doze.DOZE)) == 12
    for nome in doze.DOZE:
        cartao, problemas = placar.ler_cartao(nome)
        assert cartao is not None, (nome, problemas)
        assert cartao["andar"] == 0
        assert cartao["acao"], nome
        if cartao["fonte"] is None:
            assert cartao["sem_fonte_porque"], nome


def test_quatro_tem_fonte_e_oito_dizem_por_que_nao():
    com_fonte = [n for n in doze.DOZE if placar.ler_cartao(n)[0]["fonte"] is not None]
    assert sorted(com_fonte) == sorted(
        [
            "compras-no-mes",
            "crescimento-mes-a-mes",
            "pedidos-que-viraram-alunas",
            "aprendizados-validados-no-ciclo",
        ]
    )


def test_as_estrelas_guia_seguram_uma_a_outra():
    a, _ = placar.ler_cartao(doze.ESTRELAS[0])
    b, _ = placar.ler_cartao(doze.ESTRELAS[1])
    assert a["par"] == b["nome"] and b["par"] == a["nome"]
    assert a["fonte"] is None and b["fonte"] is None, "hoje nenhuma das duas tem fonte"


def test_compras_por_mes_so_depois_da_partida():
    alunos = [
        _aluna("2026-09-02"),
        _aluna("2026-09-10"),
        _aluna("2026-10-01"),
        _aluna("2026-10-02", status="reembolsada"),
    ]
    assert doze.compras_por_mes(alunos, PARTIDA) == {(2026, 9): 1, (2026, 10): 1}
    assert doze.compras_por_mes(None, PARTIDA) is None


def test_crescimento_espera_dois_meses_fechados():
    por_mes = {(2026, 9): 10, (2026, 10): 15, (2026, 11): 12}
    r = doze.crescimento_mes_a_mes(por_mes, PARTIDA, dt.date(2026, 10, 20))
    assert r["veredito"] == "sem-dados-ainda" and r["a_partir_de"] == dt.date(
        2026, 12, 1
    )
    r = doze.crescimento_mes_a_mes(por_mes, PARTIDA, dt.date(2026, 12, 5))
    assert r == {"veredito": "medido", "valor": -20, "m1": 12, "m2": 15}
    assert (
        doze.crescimento_mes_a_mes({}, PARTIDA, dt.date(2026, 12, 5))["veredito"]
        == "sem-base"
    )
    assert (
        doze.crescimento_mes_a_mes(None, PARTIDA, dt.date(2026, 12, 5))["veredito"]
        == "nao-consigo-medir"
    )


def test_aprendizados_validados_contam_experimentos_e_nao_qualquer_resposta():
    """O 12º conta o LABORATÓRIO, e a regra mora lá (05/09/2026, degrau 12).

    Até essa data a conta era "toda `medicao` com `responde_a` desde a
    partida", e no livro real ela dava 6: os seis eram vereditos de deploy
    respondendo a registros de entrega, num livro sem um único experimento. As
    duas primeiras linhas abaixo são exatamente esse caso, e hoje não contam.
    """
    veredito_de_deploy = [
        {"tipo": "entrega", "arquivo": "x", "quando": "2026-09-09"},
        {
            "tipo": "medicao",
            "arquivo": "x-deploy",
            "responde_a": "x",
            "quando": "2026-09-10",
        },
    ]
    assert doze.aprendizados_validados(veredito_de_deploy, PARTIDA) == 0

    experimento = [
        {
            "tipo": "medicao",
            "arquivo": "e1",
            "quando": "2026-09-05",
            "vence_em_dias": 7,
            "problema": "ninguém confirma no mesmo dia",
            "hipotese": "avisar por mensagem corta a espera pela metade",
            "metrica": "liberacoes-em-48h",
            "guarda": "se alguém esperar mais de 3 dias, paramos",
        },
        {
            "tipo": "medicao",
            "arquivo": "e1-fim",
            "responde_a": "e1",
            "quando": "2026-09-12",
            "veredito": "venceu",
        },
    ]
    assert doze.aprendizados_validados(experimento, PARTIDA) == 1
    assert doze.aprendizados_validados([], PARTIDA) == 0
    assert doze.aprendizados_validados(None, PARTIDA) is None


def test_medir_os_doze_distingue_medido_sem_fonte_e_nao_medi():
    itens = doze.medir_os_doze(
        barra={"x": 3, "mes": "09/2026"},
        por_mes={(2026, 9): 3},
        liberacao={"pedidos_28": 4, "liberados_28": 3},
        registros=[],
        partida_em=PARTIDA,
        hoje=dt.date(2026, 9, 20),
    )
    por_nome = {i["nome"]: i for i in itens}
    assert (
        por_nome["compras-no-mes"]["veredito"] == "medido"
        and por_nome["compras-no-mes"]["valor"] == 3
    )
    assert por_nome["pedidos-que-viraram-alunas"]["valor"] == 75
    assert por_nome["aprendizados-validados-no-ciclo"]["valor"] == 0
    assert por_nome["crescimento-mes-a-mes"]["veredito"] == "sem-dados-ainda"
    assert por_nome["margem-mensal"]["veredito"] == "sem-fonte"
    c = doze.confianca(itens)
    assert c == {"medidos": 3, "com_fonte": 4, "total": 12}


def test_fonte_que_nao_respondeu_e_nao_consigo_medir_e_nunca_sem_fonte():
    itens = doze.medir_os_doze(
        barra=None,
        por_mes=None,
        liberacao=None,
        registros=None,
        partida_em=PARTIDA,
        hoje=dt.date(2026, 9, 20),
    )
    por_nome = {i["nome"]: i["veredito"] for i in itens}
    assert por_nome["compras-no-mes"] == "nao-consigo-medir"
    assert por_nome["pedidos-que-viraram-alunas"] == "nao-consigo-medir"
    assert por_nome["aprendizados-validados-no-ciclo"] == "nao-consigo-medir"
    assert por_nome["custo-por-aluna"] == "sem-fonte"
