"""`/admin/placar/funil/` — quantas pessoas passam de cada degrau da venda.

Frente F7 do sistema de experimentos (26/09/2026). O placar tinha o caminho da
venda desenhado e apagado; esta tela é o caminho aceso: das pessoas que abriram
a página de venda, quantas chegaram à oferta, clicaram para pagar, deixaram o
contato, fizeram o pedido e pagaram.

## De onde sai cada número

De `countFunnel` da `metricas`, uma chamada por abertura, sempre pela memória e
nunca pelo banco de ninguém (célula não lê banco de outra). Cada degrau conta VISITANTES DISTINTOS na
janela: a mesma pessoa que abriu a página três vezes é uma pessoa. E cada
degrau é contado sozinho, não "quem passou pelo anterior e também por este";
por isso uma taxa acima de 100% pode acontecer, e a tela diz isso em vez de a
esconder.

## Três respostas que só a primeira vista confunde

- **A memória não respondeu:** a tela diz o que houve e o que fazer, e nenhum
  número aparece. Uma escada de zeros ali diria que ninguém visitou a página.
- **Sem coleta:** a memória respondeu e nenhum evento do funil chegou na
  janela. Não é "zero pessoas"; é "ninguém está sendo medido ainda".
- **Zero verdadeiro:** houve coleta, e num degrau ninguém chegou. Esse zero é
  informação, e aparece como número.

## Por dia, sem inventar o passado

A tabela por dia começa no primeiro dia com evento, como as coortes começam no
primeiro mês com conquista: antes dele não se sabe se ninguém veio ou se a
medição não escutava. Depois dele, dia sem linha é zero honesto.
"""

from __future__ import annotations

import datetime as dt

from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from .clients import MedicaoClient
from .placar import site_de

#: As janelas que a pessoa escolhe, em dias corridos terminando hoje.
JANELAS = (7, 30, 90)

#: Trinta, e não sete: com o tráfego do começo, uma semana mostra gente de
#: menos para uma taxa querer dizer alguma coisa.
JANELA_PADRAO = 30

#: Os degraus, na ordem de `countFunnel`, com o nome que aparece na tela.
PASSOS = (
    ("pagina_vista", "Abriram a página de venda"),
    ("secao_vista", "Chegaram à oferta"),
    ("cta_checkout", "Clicaram para pagar"),
    ("checkout_iniciado", "Abriram uma sessão no checkout"),
    ("lead_capturado", "Deixaram o contato"),
    ("pedido_atribuido", "Fizeram o pedido"),
    ("pedido_pago", "Pagaram"),
)


def escolher_janela(pedida: str | None) -> tuple[int, bool]:
    """`(dias, pedida_invalida)`. Pedido fora da lista cai na padrão e a tela
    avisa, em vez de perguntar uma janela que ninguém escolheu."""
    if pedida is None:
        return JANELA_PADRAO, False
    if pedida in {str(dias) for dias in JANELAS}:
        return int(pedida), False
    return JANELA_PADRAO, True


def _taxa(visitantes: int, anteriores: int | None) -> str | None:
    """A passagem do degrau anterior para este, em texto: "37,5%".

    Degrau anterior vazio devolve `None`, e a tela diz "sem base": dividir por
    zero não é "ninguém passou", é "não havia de onde passar".
    """
    if not anteriores:
        return None
    return f"{100 * visitantes / anteriores:.1f}".replace(".", ",") + "%"


def _momento(texto: object) -> dt.datetime | None:
    try:
        return dt.datetime.fromisoformat(str(texto))
    except ValueError:
        return None


def _dias(por_dia: list[dict], ate: dt.date) -> list[dict]:
    """Do dia mais novo ao primeiro dia com evento, sem buraco."""
    if not por_dia:
        return []
    medidos = {linha["dia"]: linha["passos"] for linha in por_dia}
    dia = max(ate, max(medidos))
    primeiro = min(medidos)
    linhas = []
    while dia >= primeiro:
        passos = medidos.get(dia)
        linhas.append(
            {
                "dia": dia,
                "visitantes": [passos.get(p) if passos else (None if p == "checkout_iniciado" else 0) for p, _ in PASSOS],
            }
        )
        dia -= dt.timedelta(days=1)
    return linhas


def montar(desfecho: str, resposta: dict | None, ate: dt.date) -> dict:
    """A tela inteira, calculada. `veredito` antes de qualquer número:
    `sem-configuracao`, `nao-respondeu`, `sem-coleta` ou `medindo`."""
    if desfecho != MedicaoClient.OK or resposta is None:
        return {"veredito": desfecho, "escada": [], "dias": []}
    coleta = resposta["coleta"]
    if coleta["primeiro"] is None:
        return {"veredito": "sem-coleta", "escada": [], "dias": []}
    escada = []
    anteriores = None
    for passo, nome in PASSOS:
        visitantes = resposta["passos"].get(passo)
        escada.append(
            {
                "passo": passo,
                "nome": nome,
                "visitantes": visitantes,
                "taxa": _taxa(visitantes, anteriores) if visitantes is not None else None,
            }
        )
        anteriores = visitantes
    return {
        "veredito": "medindo",
        "escada": escada,
        "dias": _dias(resposta["por_dia"], ate),
        "nomes": [nome for _, nome in PASSOS],
        "ultimo_evento": _momento(coleta["ultimo"]),
    }


@require_GET
def funil(request):
    """A tela. Fail-OPEN, como as irmãs do placar: ela abre e DIZ o que faltou."""
    hoje = timezone.localdate()
    dias, janela_invalida = escolher_janela(request.GET.get("janela"))
    desde = hoje - dt.timedelta(days=dias - 1)
    site_id = site_de(request)
    desfecho, resposta = MedicaoClient().funil(desde, hoje, site_id)
    return render(
        request,
        "admin/funil.html",
        {
            "admin": request.admin,
            "tela": montar(desfecho, resposta, hoje),
            "janelas": JANELAS,
            "dias": dias,
            "janela_invalida": janela_invalida,
            "desde": desde,
            "ate": hoje,
            "site_id": site_id,
        },
    )
