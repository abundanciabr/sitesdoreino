"""Dois calendários comerciais por produto, com metas e vendas confirmadas.

Os planos aprovados em 05/10/2026 ficam em ciclo_produtos. As funções
de contagem históricas continuam disponíveis aos outros consumidores.
"""

from __future__ import annotations

import datetime as dt

from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from .clients import AlunosClient, CatalogoClient, LeadsClient
from .placar import (
    CARTAO_DA_META,
    CAMPO_DA_DATA,
    diretorio_dos_cartoes,
    dia_em_sao_paulo,
    ler_cartao,
    semanas_do_ciclo,
    vendeu_pelo_site,
)


def contar_por_semana(alunos: "list[dict] | None", faixas: list[dict]) -> "list | None":
    """Quantas pessoas compraram pelo nosso site dentro de cada faixa de datas.

    `None` (a lista inteira) quando não deu para perguntar. Nunca uma lista de
    zeros: zero é uma afirmação, e afirmar sem ter perguntado é o falso-verde.
    """
    if alunos is None:
        return None
    contas = [0] * len(faixas)
    for a in alunos:
        if not vendeu_pelo_site(a):
            continue
        dia = dia_em_sao_paulo(a.get(CAMPO_DA_DATA))
        if dia is None:
            continue
        for i, faixa in enumerate(faixas):
            if faixa["de"] <= dia <= faixa["ate"]:
                contas[i] += 1
                break
    return contas


def montar_as_semanas(faixas: list[dict], reais: "list | None", hoje: dt.date) -> list:
    """Uma linha por semana: a meta, o acumulado, o que houve e o estado.

    O `estado` responde de relance a única pergunta que se faz olhando um
    calendário: *onde eu estou?* Três valores, e a semana de hoje é a única
    que não recebe veredito — julgar uma semana pela metade é o "ontem versus
    hoje engana" dos documentos.
    """
    linhas, acumulado_real = [], 0
    for i, faixa in enumerate(faixas):
        real = None if reais is None else reais[i]
        if real is not None:
            acumulado_real += real
        if hoje > faixa["ate"]:
            estado = "fechada"
        elif hoje < faixa["de"]:
            estado = "futura"
        else:
            estado = "andando"
        # Veredito SÓ de semana fechada e contada. A que está andando não tem
        # veredito, e a futura muito menos: um "não cumpriu" numa semana que
        # ainda nem começou treinaria o mantenedor a ignorar a coluna inteira.
        cumpriu = None
        if estado == "fechada" and real is not None:
            cumpriu = real >= faixa["alvo"]
        linhas.append(
            {
                **faixa,
                "real": real,
                "acumulado_real": None if reais is None else acumulado_real,
                "estado": estado,
                "cumpriu": cumpriu,
            }
        )
    return linhas


@require_GET
def ciclo(request):
    """Dois planos comerciais na mesma página, com vendas por produto."""
    from .ciclo_produtos import PAINEIS, INICIO, FIM, montar_painel
    from .vendas_do_crm import para_o_placar
    chave = request.GET.get("produto", "curso")
    if chave not in PAINEIS:
        chave = "curso"
    perfil = PAINEIS[chave]
    catalogo = CatalogoClient()
    site = catalogo.site_por_host(request.get_host().split(":")[0])
    produto = None
    if site:
        estado_oferta, oferta = catalogo.oferta_do_site(str(site["id"]), perfil["oferta"])
        if estado_oferta == catalogo.OK and isinstance(oferta, dict):
            produto = oferta.get("product")
    alunos = None
    if site and produto:
        fichas = AlunosClient().alunos()
        if fichas is not None:
            # Filtrar ANTES da deduplicação: comprar o desafio não apaga a compra do curso.
            alunos = para_o_placar([
                a for a in fichas if str(a.get("product_id")) == str(produto["id"])
                and str(a.get("site_id")) == str(site["id"])
            ])
    hoje = timezone.localdate()
    painel = montar_painel(chave, alunos, hoje)
    receita = None
    if chave == "desafio" and site and produto:
        cliente = LeadsClient()
        estado, fatos = cliente._pedir("/receita/fatos", {
            "site_id": str(site["id"]), "desde": INICIO.isoformat(), "ate": FIM.isoformat(),
        })
        if estado == cliente.OK and isinstance(fatos, dict) and isinstance(fatos.get("por_oferta"), list):
            itens = [i for i in fatos["por_oferta"] if i.get("oferta") in
                     (perfil["oferta"], perfil["slug"], str(produto["id"]))]
            if all(type(i.get("aprovado_centavos")) is int for i in itens):
                centavos = sum(i["aprovado_centavos"] for i in itens)
                receita = "R$ " + f"{centavos / 100:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return render(
        request,
        "admin/ciclo.html",
        {
            "admin": request.admin,
            "painel": painel,
            "botoes": [{"chave": k, "nome": p["botao"]} for k, p in PAINEIS.items()],
            "receita": receita,
            "hoje": hoje,
        },
    )
