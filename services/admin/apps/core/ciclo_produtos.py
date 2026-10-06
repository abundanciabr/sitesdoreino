"""Calendários comerciais de outubro a dezembro de 2026, por produto."""
import datetime as dt

from .placar import CAMPO_DA_DATA, dia_em_sao_paulo, vendeu_pelo_site

INICIO = dt.date(2026, 10, 5)
FIM = INICIO + dt.timedelta(days=83)
PAINEIS = {
    "curso": {
        "nome": "Curso Primeiros Dólares com Roblox", "botao": "Curso · 500 vendas",
        "slug": "primeiros-dolares", "oferta": "primeiros-dolares-com-roblox",
        "meta": 500, "preco": "R$ 600", "preco_rotulo": "preço de referência do plano",
        "metas": (0, 0, 2, 4, 6, 18, 40, 80, 140, 210),
    },
    "desafio": {
        "nome": "Desafio Como Ganhar em Dólar com Roblox", "botao": "Desafio · 10.000 vendas",
        "slug": "desafio-como-ganhar-em-dolar-com-roblox",
        "oferta": "desafio-como-ganhar-em-dolar-com-roblox",
        "meta": 10000, "preco": "R$ 27–47", "preco_rotulo": "faixa de referência do plano",
        "metas": (0, 5, 15, 15, 20, 145, 500, 1300, 2800, 5200),
    },
}
APRENDIZADOS = {
    2: ("Testar anúncios e quiz", "Quiz: mais de 70% chegam ao resultado"),
    3: ("Validar o low ticket", "Low ticket: conversão de 5% a 10%"),
    4: ("Ajustar a oferta do curso", "Curso: conversão de 1,5% a 3%"),
    5: ("Ativar o comercial", "Comercial: recuperar pelo menos 10%"),
}


def numero(valor):
    return f"{valor:,}".replace(",", ".")


def dividir(meta):
    base, extras = divmod(meta, 4)
    return [base + (i < extras) for i in range(4)]


def montar_visao_ciclo(painel, hoje):
    """Orientação da home usando o mesmo calendário e a mesma contagem."""
    semanas = [painel["preparacao"], *painel["semanas"]]
    atual = next((s for s in semanas if s["atual"]), None)
    proxima = next((s for s in painel["semanas"] if s["de"] > hoje), None)
    etapas = []
    for n, nome, primeira, ultima in (
        (1, "Preparar", semanas[0], semanas[0]),
        (2, "Validar", semanas[1], semanas[4]),
        (3, "Crescer", semanas[5], semanas[9]),
    ):
        etapas.append({
            "n": n, "nome": nome, "de": primeira["de"], "ate": ultima["ate"],
            "atual": primeira["de"] <= hoje <= ultima["ate"],
            "passou": hoje > ultima["ate"],
        })
    preparacao = painel["preparacao"]
    fim_planejado = semanas[-1]["ate"]
    if hoje < preparacao["de"]:
        estado, foco = "O ciclo ainda não começou", "Preparar o início do ciclo"
        acao = "Testar o caminho completo: anúncio → quiz → compra"
    elif atual and atual["n"] == 1:
        estado, foco = "Semana de preparação", "Deixar tudo pronto para começar a vender"
        acao = "Testar o caminho completo: anúncio → quiz → compra"
    elif atual:
        estado = "Semana de vendas"
        foco = atual["foco"]
        acao = atual["indicador"] or "Conferir as vendas e ajustar o que está impedindo o avanço"
    elif hoje <= painel["recuperacoes"][-1]["ate"]:
        estado, foco = "Semanas de recuperação", "Completar o que faltar para a meta"
        acao = "Conferir o saldo e o plano de recuperação do desafio"
    else:
        estado, foco = "Ciclo encerrado", "Conferir o resultado final do ciclo"
        acao = "Revisar os resultados e os aprendizados do desafio"
    return {
        "etapas": etapas, "atual": atual, "proxima": proxima,
        "estado": estado, "foco": foco, "acao": acao,
        "fim_planejado": fim_planejado,
        "em_preparacao": hoje <= preparacao["ate"],
        "prazo_compromissos": preparacao["ate"] if hoje <= preparacao["ate"] else (
            atual["ate"] if atual else None
        ),
        "compromissos": (
            "Preparar a página e os anúncios",
            "Conferir o quiz do início ao fim",
            "Testar a compra e a entrega do acesso",
        ) if hoje <= preparacao["ate"] else (
            "Conferir o caminho dos anúncios até a compra",
            "Revisar os resultados dos testes da semana",
            "Definir o próximo ajuste com base nos resultados",
        ),
    }


def montar_painel(chave, alunos, hoje):
    perfil = PAINEIS[chave]
    datas = [] if alunos is None else [
        dia_em_sao_paulo(a.get(CAMPO_DA_DATA)) for a in alunos if vendeu_pelo_site(a)
    ]
    desconhecidas = sum(d is None for d in datas)
    total = None if alunos is None or desconhecidas else sum(INICIO <= d <= FIM for d in datas)
    semanas, acumulado = [], 0
    for n, meta in enumerate(perfil["metas"], 1):
        de = INICIO + dt.timedelta(weeks=n - 1)
        ate = de + dt.timedelta(days=6)
        acumulado += meta
        real = None if total is None else sum(de <= d <= ate for d in datas)
        dias = dividir(meta)
        # As primeiras vendas do curso ficam nos primeiros dias da semana.
        if chave == "curso" and meta in (1, 2):
            dias = [int(i < meta) for i in range(4)]
        recuperacao = "Sexta a domingo: recuperar se faltar."
        if chave == "curso" and n == 3:
            recuperacao = "Quarta a domingo: recuperar se faltar."
        foco, indicador = APRENDIZADOS.get(n, ("Escalar as vendas", ""))
        semanas.append({
            "n": n, "de": de, "ate": ate, "meta": meta, "meta_texto": numero(meta),
            "acumulado": numero(acumulado), "real": real,
            "real_texto": numero(real) if real is not None else "—",
            "dias": [{"nome": nome, "data": de + dt.timedelta(days=i),
                      "meta": numero(dias[i]) if dias[i] else "—"}
                     for i, nome in enumerate(("Seg", "Ter", "Qua", "Qui"))],
            "atual": de <= hoje <= ate, "foco": foco, "indicador": indicador,
            "recuperacao": recuperacao,
            "faltam": numero(max(0, meta - real)) if real is not None else None,
        })
    recuperacoes = []
    # O saldo é fixado pelo que foi vendido antes de cada semana de recuperação.
    for n in (11, 12):
        de = INICIO + dt.timedelta(weeks=n - 1)
        ate = de + dt.timedelta(days=6)
        vendidas_antes = None if total is None else sum(INICIO <= d < de for d in datas)
        saldo = None if vendidas_antes is None else max(0, perfil["meta"] - vendidas_antes)
        parcela = None if saldo is None else (saldo + (13 - n) - 1) // (13 - n)
        aberta = hoje >= de
        recuperacoes.append({
            "n": n, "de": de, "ate": ate, "atual": de <= hoje <= ate,
            "meta": numero(parcela) if aberta and parcela is not None else None,
            "dias": [{"nome": nome, "meta": numero(valor)}
                     for nome, valor in zip(("Seg", "Ter", "Qua", "Qui"), dividir(parcela or 0))]
                    if aberta and parcela is not None else [],
        })
    return {**perfil, "chave": chave, "meta_texto": numero(perfil["meta"]),
            "total": total, "total_texto": numero(total) if total is not None else "—",
            "saldo": numero(max(0, perfil["meta"] - total)) if total is not None else None,
            "progresso": min(100, total * 100 / perfil["meta"]) if total is not None else 0,
            "semanas": semanas[1:], "preparacao": semanas[0], "recuperacoes": recuperacoes,
            "sem_contagem": total is None, "datas_ausentes": desconhecidas}
