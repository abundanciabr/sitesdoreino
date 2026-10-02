# apps/core/pendencias.py — a Central de Pendências
"""As quatro filas da escola em uma tela, sem duplicar a decisão de cada célula.

Cada célula conta seus próprios pedidos e informa a idade do mais antigo.
`quantidade=None` significa fonte indisponível; zero é uma fila consultada e
vazia. A tela continua aberta quando uma fonte falha e identifica qual falhou.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET

from .clients import AlunosClient, PendenciasClient
from .placar import site_de

# Nome, endereço da equipe e descrição de cada fonte consultada.
OUTRAS_FILAS = (
    ("portfolio", "Portfólios pedindo conferência", "/pages/equipe", "a fila de portfólios"),
    ("marcos", "Provas de marco enviadas pelos alunos", "/conquistas/interno", "a fila de marcos"),
    ("checkpoints", "Checkpoints de aula esperando laudo", "/cursos/plantao", "o plantão de aulas"),
)


@dataclass(frozen=True)
class Fila:
    """Uma linha da portaria.

    `quantidade is None` é *não consegui perguntar*, e nunca zero. `espera_ha`
    é em dias, e só existe quando há alguém esperando de verdade.
    `acesso_negado` marca a fila muda porque a fonte recusou a credencial
    (401/403): recarregar não conserta, e a tela diz a quem pedir.
    """

    titulo: str
    quantidade: "int | None"
    espera_ha: "int | None"
    href: str
    o_que_e: str
    onde_mora: str
    acesso_negado: bool = False


def quem_quer_entrar(cliente: AlunosClient) -> Fila:
    """Quem pediu para entrar na escola e ainda não teve resposta.

    A `alunos` já conta há quantos dias cada pessoa espera
    (`esperando_ha_dias`, do contrato), e este módulo não reconta: a idade é
    dela, que é quem tem a data de verdade.
    """
    leitura = cliente.fila_para_central("aguardando")
    fila = leitura.itens
    return Fila(
        titulo="Pessoas querendo entrar na escola",
        quantidade=None if fila is None else len(fila),
        espera_ha=(
            max((p.get("esperando_ha_dias") or 0) for p in fila) if fila else None
        ),
        href=reverse("escola_alunos"),
        o_que_e="Alguém pediu entrada e fica sem acesso a nada até você liberar.",
        onde_mora="a lista de alunos",
        acesso_negado=leitura.acesso_negado,
    )


@require_GET
def pendencias(request):
    """Cada fonte responde por sua fila; fonte muda nunca vira zero."""
    filas = [quem_quer_entrar(AlunosClient())]
    site_id = site_de(request)
    cliente = PendenciasClient()
    for chave, titulo, href, onde_mora in OUTRAS_FILAS:
        leitura = cliente.resumo(chave, site_id)
        filas.append(Fila(
            titulo=titulo,
            quantidade=leitura.quantidade,
            espera_ha=leitura.espera_ha_dias,
            href=href,
            o_que_e="Há pedidos aguardando a equipe nesta fila.",
            onde_mora=onde_mora,
            acesso_negado=leitura.acesso_negado,
        ))
    esperando = [f for f in filas if f.quantidade]
    return render(
        request,
        "admin/pendencias.html",
        {
            "admin": request.admin,
            "esperando": esperando,
            # Vazias e mudas viajam separadas porque são frases diferentes na
            # tela: "não há nada aqui" e "não deu para perguntar" só se parecem
            # de dentro do código.
            "vazias": [f for f in filas if f.quantidade == 0],
            "mudas": [f for f in filas if f.quantidade is None],
            "total": sum(f.quantidade for f in esperando),
        },
    )
