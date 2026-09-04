"""`/admin/placar/ciclo/` — o calendário do ciclo, semana a semana.

Pedido do mantenedor em 04/09/2026, com o calendário dele nas mãos: *"quero
criar no painel os ciclos evolutivos onde a cada semana tenhamos a meta de ir
crescendo semana a semana até alcançar a escala"*, e a frase que define a
curva: *"nas primeiras semanas as vendas fiquem na faixa de 0 enquanto nós
vamos aprendendo e testando as campanhas, criativos, copys, landing pages,
funis"*.

## O que esta tela é, e o que ela NÃO é

Ela é a **leitura** da curva. A curva em si não mora aqui: mora em
`painel/cartoes/compras-no-ciclo.json`, no campo `semanas`, que é onde a régua
da meta já morava. Mudar a meta de uma semana é editar aquele arquivo, por PR,
e esta tela mostra o que ele disser no minuto seguinte.

Isso não é preciosismo de organização, é a única forma de a tela não mentir.
Se a curva vivesse aqui, o placar (`/admin/placar/`) continuaria julgando
ganhando/perdendo pela linha reta antiga enquanto esta tela mostrasse outra
coisa, e as duas teriam ar de certeza. Com a curva no cartão, **o placar
inteiro segue a mesma régua**: `placar.esperado_em` a lê, e com ela andam o
veredito do ciclo, a meta do mês e a meta da semana da tela de direção.

## De onde vêm os números REAIS

Da mesma lista que o placar usa (`alunos`, `GET /matriculas`, campo
`virou_aluno_em`), com os mesmos status que contam como compra. A contagem por
semana é feita aqui porque nenhuma outra tela pergunta isso, mas as REGRAS
(quais status contam, qual fuso decide o dia) são importadas de `placar.py` e
não reescritas: um segundo conjunto de regras de contagem seria a duplicação
que o `CLAUDE.md` proíbe.

**`None` é "não consegui perguntar", e nunca vira zero.** Uma semana sem
resposta da `alunos` mostrada como 0 diria "nesta semana ninguém comprou"
quando a verdade é que a pergunta não chegou (`RETROSPECTIVA-FASE-D` §1).
"""

from __future__ import annotations

import datetime as dt

from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from .clients import AlunosClient
from .placar import (
    CARTAO_DA_META,
    STATUS_QUE_COMPRARAM,
    CAMPO_DA_DATA,
    diretorio_dos_cartoes,
    dia_em_sao_paulo,
    ler_cartao,
    semanas_do_ciclo,
)


def contar_por_semana(alunos: "list[dict] | None", faixas: list[dict]) -> "list | None":
    """Quantas pessoas compraram dentro de cada faixa de datas.

    `None` (a lista inteira) quando não deu para perguntar. Nunca uma lista de
    zeros: zero é uma afirmação, e afirmar sem ter perguntado é o falso-verde.
    """
    if alunos is None:
        return None
    contas = [0] * len(faixas)
    for a in alunos:
        if a.get("status") not in STATUS_QUE_COMPRARAM:
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
    """A tela. Fail-OPEN na rede: sem a `alunos`, o calendário abre e as
    colunas do que houve dizem que não deu para perguntar."""
    meta, recusas = ler_cartao(CARTAO_DA_META, diretorio_dos_cartoes())
    faixas = semanas_do_ciclo(meta) if meta else []
    reais = contar_por_semana(AlunosClient().alunos(), faixas) if faixas else None
    hoje = timezone.localdate()
    return render(
        request,
        "admin/ciclo.html",
        {
            "admin": request.admin,
            "meta": meta,
            "recusas": recusas,
            "semanas": montar_as_semanas(faixas, reais, hoje),
            "nao_consigo_contar": faixas and reais is None,
            "hoje": hoje,
        },
    )
