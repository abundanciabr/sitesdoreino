"""O placar de doze e as estrelas-guia (degrau 4 do plano do painel de gestão).

Os documentos do Scale OS (1 §32; 2 Parte XVII; 3 §10) põem doze indicadores
na primeira tela do dono. Nove dependem de venda ou de anúncio (congelados
desde 22/08/2026) ou de células que ainda não existem (cursos, portfólio,
indicação). A régua de doze fica; **cada cartão diz a verdade**: quatro
medidos, oito com `sem_fonte_porque` dizendo o que precisa existir para
acender. É o plano §4.3, e a decisão do mantenedor de 03/09/2026 sobre as
duas estrelas-guia: entram desenhadas, sem dados, acima da meta.

Nada aqui é nota composta: doze números, cada um com o seu cartão, e a
confiança da tela é a fração dos doze que chegaram com fonte.
"""

from __future__ import annotations

import datetime as dt

from . import laboratorio as laboratorio_
from .placar import STATUS_QUE_COMPRARAM, dia_em_sao_paulo, ler_cartao

#: Os doze, na ordem dos documentos, com o nome do cartão da casa.
DOZE = (
    "compras-no-mes",
    "crescimento-mes-a-mes",
    "custo-por-aluna",
    "custo-do-proximo-aluna",
    "dias-para-recuperar-o-custo",
    "margem-mensal",
    "margem-por-real-de-aquisicao",
    "pedidos-que-viraram-alunas",
    "primeira-acao-em-7-dias",
    "alunos-com-resultado-profissional",
    "vindos-por-indicacao",
    "aprendizados-validados-no-ciclo",
)

#: As duas estrelas-guia: valor ao aluno e valor econômico. Uma segura a outra.
ESTRELAS = ("alunos-com-resultado-profissional", "margem-mensal")


def _mes_anterior(mes: dt.date) -> dt.date:
    return (mes.replace(day=1) - dt.timedelta(days=1)).replace(day=1)


def compras_por_mes(alunos: list[dict] | None, partida_em: dt.date) -> dict | None:
    """`{ (ano, mes): quantas viraram alunas }`, só depois da partida."""
    if alunos is None:
        return None
    por_mes: dict = {}
    for a in alunos:
        if a.get("status") not in STATUS_QUE_COMPRARAM:
            continue
        dia = dia_em_sao_paulo(a.get("virou_aluno_em"))
        if dia is None or dia < partida_em:
            continue
        chave = (dia.year, dia.month)
        por_mes[chave] = por_mes.get(chave, 0) + 1
    return por_mes


def crescimento_mes_a_mes(
    por_mes: dict | None, partida_em: dt.date, hoje: dt.date
) -> dict:
    """O último mês fechado contra o anterior, em por cento; ou por que ainda não."""
    if por_mes is None:
        return {"veredito": "nao-consigo-medir"}
    m1 = _mes_anterior(hoje)
    m2 = _mes_anterior(m1)
    primeiro_mes_cheio = partida_em.replace(day=1)
    if partida_em.day != 1:
        primeiro_mes_cheio = (primeiro_mes_cheio + dt.timedelta(days=32)).replace(day=1)
    if m2 < primeiro_mes_cheio:
        # Ainda não há dois meses inteiros fechados depois da partida.
        quando = (primeiro_mes_cheio + dt.timedelta(days=62)).replace(day=1)
        return {"veredito": "sem-dados-ainda", "a_partir_de": quando}
    a = por_mes.get((m1.year, m1.month), 0)
    b = por_mes.get((m2.year, m2.month), 0)
    if b == 0:
        return {"veredito": "sem-base", "m1": a, "m2": b}
    return {"veredito": "medido", "valor": round(100 * (a - b) / b), "m1": a, "m2": b}


#: O 12º dos doze é o laboratório, e a conta mora LÁ (05/09/2026, degrau 12).
#:
#: Até esta data a regra era "toda `medicao` com `responde_a` desde a partida",
#: escrita aqui. Medida no livro real no dia da troca, ela dava **6** — e os
#: seis eram vereditos de deploy respondendo a registros de entrega, num livro
#: sem um único experimento. A conta não tinha bug: media a coisa errada com
#: precisão, que é como um indicador morre (`armadilhas/303`).
#:
#: Uma regra só, dois leitores: a tela do laboratório e este número não
#: conseguem discordar, porque são a mesma função.
aprendizados_validados = laboratorio_.aprendizados_validados


def medir_os_doze(
    *,
    barra: dict | None,
    por_mes: dict | None,
    liberacao: dict | None,
    registros: list[dict] | None,
    partida_em: dt.date,
    hoje: dt.date,
    pasta=None,
) -> list[dict]:
    """Os doze, cada um com o cartão, o valor (ou o motivo de não ter) e o veredito.

    Vereditos: `medido` · `sem-fonte` (o cartão diz por quê) · `nao-consigo-medir`
    (a fonte existe e não respondeu) · `sem-dados-ainda` (a fonte existe, o
    tempo não passou) · `sem-cartao` (fail-closed: o cartão está torto).
    """
    saida = []
    for nome in DOZE:
        cartao, problemas = ler_cartao(nome, pasta)
        item = {
            "nome": nome,
            "cartao": cartao,
            "problemas": problemas,
            "valor": None,
            "texto": None,
        }
        if cartao is None:
            item["veredito"] = "sem-cartao"
        elif cartao.get("fonte") is None:
            item["veredito"] = "sem-fonte"
        elif nome == "compras-no-mes":
            if barra is None or barra.get("x") is None:
                item["veredito"] = "nao-consigo-medir"
            else:
                item.update(
                    veredito="medido",
                    valor=barra["x"],
                    texto=f"{barra['x']} em {barra['mes']}",
                )
        elif nome == "crescimento-mes-a-mes":
            r = crescimento_mes_a_mes(por_mes, partida_em, hoje)
            item["veredito"] = r["veredito"]
            if r["veredito"] == "medido":
                item.update(
                    valor=r["valor"], texto=f"{r['valor']:+d}% ({r['m2']} → {r['m1']})"
                )
            elif r["veredito"] == "sem-dados-ainda":
                item["texto"] = (
                    f"a partir de {r['a_partir_de'].strftime('%m/%Y')}, quando houver dois meses fechados"
                )
            elif r["veredito"] == "sem-base":
                item["texto"] = (
                    f"o mês anterior teve 0; não há base para comparar ({r['m2']} → {r['m1']})"
                )
        elif nome == "pedidos-que-viraram-alunas":
            if liberacao is None:
                item["veredito"] = "nao-consigo-medir"
            elif not liberacao.get("pedidos_28"):
                item.update(
                    veredito="sem-dados-ainda",
                    texto="nenhum pedido de entrada nos últimos 28 dias",
                )
            else:
                pct = round(100 * liberacao["liberados_28"] / liberacao["pedidos_28"])
                item.update(
                    veredito="medido",
                    valor=pct,
                    texto=f"{pct}% ({liberacao['liberados_28']} de {liberacao['pedidos_28']} em 28 dias)",
                )
        elif nome == "aprendizados-validados-no-ciclo":
            n = aprendizados_validados(registros, partida_em)
            if n is None:
                item["veredito"] = "nao-consigo-medir"
            else:
                item.update(
                    veredito="medido",
                    valor=n,
                    texto=f"{n} desde {partida_em.strftime('%d/%m')}",
                )
        else:
            item["veredito"] = "nao-consigo-medir"
        saida.append(item)
    return saida


def confianca(doze: list[dict]) -> dict:
    """Quantos dos doze chegaram com fonte e número: a confiança desta tela."""
    medidos = sum(1 for d in doze if d["veredito"] == "medido")
    com_fonte = sum(
        1
        for d in doze
        if d["veredito"]
        in ("medido", "nao-consigo-medir", "sem-dados-ainda", "sem-base")
    )
    return {"medidos": medidos, "com_fonte": com_fonte, "total": len(doze)}
