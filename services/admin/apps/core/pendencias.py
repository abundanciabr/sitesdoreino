# apps/core/pendencias.py — a Central de Pendências
"""`/admin/pendencias/` — a portaria: tudo que espera pelo mantenedor, numa tela.

Plano aprovado: `documentos/pendencias-e-conferencia-por-pares.md`, degrau 1.

## O problema, medido

Em 06/09/2026 o mantenedor abriu `/conquistas/interno` e disse *"que eu nem
sabia que isso existia"*. Não era memória fraca: era desenho. O trabalho que
espera por ele mora em SEIS endereços diferentes, nenhum deles avisa nada, e
uma fila que alguém precisa lembrar de abrir é uma fila que não existe.

Esta tela não resolve nada por dentro, e isso é a decisão central: cada fila
continua morando na própria casa, que é onde a regra dela é conferida. Aqui só
se pergunta *"quantos estão esperando aí, e o mais antigo é de quando?"*, e se
oferece a porta.

## Uma fonte, com cobertura declarada

Esta célula consulta quem quer entrar na escola. As filas que ela ainda não
enxerga entram na tela por escrito, em `FILAS_QUE_AINDA_NAO_VEJO`: sem isso,
"nada esperando você" seria uma frase que a tela não tem como sustentar.

Aqui `Fila.quantidade is None` significa *não consegui perguntar*, e o template
tem de distinguir os dois casos por listas separadas, nunca por um `{% if %}`
cru: zero é falso em template, e um zero legítimo cairia no ramo do "não sei".

## Fail-OPEN por linha, e não pela página

A fila que não responde perde a própria linha, e a tela abre do mesmo jeito.
Uma tela de operação que não abre é inútil justamente no dia em que alguém
precisa dela.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET

from .clients import AlunosClient

# As filas que este degrau ainda NÃO enxerga, com o endereço de cada uma. Elas
# entram na tela por escrito: sem isso, "nada esperando você" seria uma frase
# que a tela não tem como sustentar. Saem daqui uma a uma no degrau 3, e a
# lista vazia é o sinal de que a portaria ficou completa.
FILAS_QUE_AINDA_NAO_VEJO = (
    ("Portfólios pedindo conferência", "/pages/equipe"),
    ("Provas de marco enviadas pelos alunos", "/conquistas/interno"),
    ("Checkpoints de aula esperando laudo", "/cursos/plantao"),
)


@dataclass(frozen=True)
class Fila:
    """Uma linha da portaria.

    `quantidade is None` é *não consegui perguntar*, e nunca zero. `espera_ha`
    é em dias, e só existe quando há alguém esperando de verdade.
    `acesso_negado` marca a fila muda porque a `alunos` recusou a credencial
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
    """A portaria abre mesmo com a `alunos` fora do ar: fila muda é aviso, não zero."""
    filas = [quem_quer_entrar(AlunosClient())]
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
            "ainda_nao_vejo": FILAS_QUE_AINDA_NAO_VEJO,
        },
    )
