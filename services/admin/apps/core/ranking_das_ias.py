# apps/core/ranking_das_ias.py — o ranking da tríade
"""`/admin/ranking-ias/` — quanto cada IA publicou em `main`, e o que custou.

Pedido do mantenedor em 17/09/2026: uma tela que mostre qual das três IAs está
produzindo mais e desperdiçando menos, para que o plano de uso de cada uma seja
decidido por número e não por impressão.

## Esta tela não conta nada

Quem conta é `ci/ranking_das_ias.py`, contra `origin/main`, e o resultado mora
em `painel/ranking-ias.json`. Aqui só se ORDENA e se dá nome ao lugar de cada
uma. É a lei anti-duplicação de sempre: uma conta, um lugar. O Python desta
casa já divergiu do painel uma vez, dizendo 6 onde o painel dizia 7, e o
cabeçalho de `apps/core/pendencias.py` guarda o episódio.

A pasta é a mesma de `responsabilidades.json`, servida pelo mesmo publicador,
com o mesmo ponteiro validado. Nenhuma pasta nova nasce aqui.

## Sem retrato, a tela DIZ isso

Um ranking que abrisse zerado quando o arquivo falta afirmaria "nenhuma das três
entregou nada" — a mentira mais cara que esta tela pode contar, porque é
exatamente a frase que faria o mantenedor cortar o plano de alguém. Sem
arquivo, a página mostra o que houve e o comando que resolve.

## Por que o custo é em linha, e não em token

Foi pedida uma coluna de tokens. O repositório não registra token de ninguém:
nenhuma das três grava consumo em lugar nenhum, e não há de onde ler. Preencher
a coluna com autodeclaração premiaria quem declara melhor, e é justamente o que
o pedido queria impedir. Linhas somadas e apagadas em `main` é medida, está no
Git, e é o que os tokens compram.

O que esta tela NÃO enxerga vai escrito nela, em `O_QUE_NAO_ENXERGO`, pela
mesma razão que a Central de Pendências declara as filas que ainda não vê: um
ranking que mede metade e não avisa ensina a confiar no número errado.

## Autoria não única não é desempenho ruim

`sem_assinatura` é trabalho publicado em `main` sem uma única IA reconhecida
nos trailers `Co-authored-by`, por ausência ou múltipla autoria. Ele aparece fora do
pódio, como linha própria: distribuí-lo por palpite inventaria o ranking, e
escondê-lo faria as somas não fecharem com o repositório.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from django.shortcuts import render
from django.views.decorators.http import require_GET

from .painel import dados_do_painel, diretorio_do_painel

ARQUIVO = "ranking-ias.json"
IDENTIDADES_IAS = {
    "claude-code": ("Claude Code", "Maestro"),
    "codex": ("Codex", "Executor"),
    "antigravity": ("Antigravity", "Sentinela"),
}

# A regra de recompensa que o mantenedor escreveu em 17/09/2026. Mora aqui, e
# não no gerador, porque é decisão dele sobre os números — e muda sem que a
# medição mude.
PLANOS = (
    ("Plano Premium", "20x mais limites de uso"),
    ("Plano Médio", "5x mais limites de uso"),
    ("Zona de eliminação", "sai do projeto na próxima revisão"),
)

# O que o Git não sabe responder, dito por extenso na tela. Texto puro: ele vai
# direto para o HTML, e crase aqui apareceria como crase na tela.
O_QUE_NAO_ENXERGO = (
    "Tokens consumidos: nenhuma das três registra consumo no repositório.",
    "Trabalho que não chegou na main: rascunho, PR aberto e ramo abandonado.",
    "Auditoria e verificação da Sentinela, que por lei não viram commit.",
)


@dataclass(frozen=True)
class Participante:
    """Uma linha do ranking, já ordenada e já com o lugar dela.

    `custo_por_pagina` e `dias_por_pagina` são `None` — nunca zero — para quem
    não publicou página: zero diria "publicou de graça", que é o contrário.
    """

    nome: str
    papel: str
    paginas: int
    entregas: int
    linhas: int
    retrabalho: int
    dias_ativos: int
    ultima_entrega: "datetime | None"
    posicao: "int | None" = None
    plano: "str | None" = None
    consequencia: "str | None" = None

    @property
    def custo_por_pagina(self) -> "int | None":
        return round(self.linhas / self.paginas) if self.paginas else None

    @property
    def dias_por_pagina(self) -> "float | None":
        return round(self.dias_ativos / self.paginas, 1) if self.paginas else None

    @property
    def retrabalho_por_cento(self) -> "int | None":
        return round(100 * self.retrabalho / self.entregas) if self.entregas else None

    @property
    def sem_entrega(self) -> bool:
        return self.entregas == 0


def _data(texto: "str | None") -> "datetime | None":
    if not isinstance(texto, str) or not texto:
        return None
    try:
        return datetime.fromisoformat(texto)
    except ValueError:
        return None


def _participante(bruto: dict, nome: str, papel: str) -> "Participante | None":
    """Uma linha do retrato, ou `None` se ela não veio inteira.

    Campo faltando derruba a LINHA, e não a página: um ranking com duas das três
    IAs continua respondendo a pergunta que o mantenedor foi fazer ali.
    """
    numeros = ("paginas", "entregas", "linhas", "retrabalho", "dias_ativos")
    if not isinstance(bruto, dict) or any(
        type(bruto.get(campo)) is not int or bruto[campo] < 0 for campo in numeros
    ):
        return None
    ultima_entrega = _data(bruto.get("ultima_entrega"))
    if bruto.get("ultima_entrega") is not None and ultima_entrega is None:
        return None
    return Participante(
        nome=nome,
        papel=papel,
        ultima_entrega=ultima_entrega,
        **{campo: bruto[campo] for campo in numeros},
    )


def classificar(participantes: list[Participante]) -> list[Participante]:
    """A ordem do pódio: mais páginas publicadas primeiro, custo menor desempata.

    É a regra do mantenedor, na ordem em que ele a escreveu — página publicada
    manda, e entre duas que publicaram o mesmo tanto ganha quem gastou menos
    linha para chegar lá. Quem não publicou nenhuma página fica atrás de quem
    publicou uma, por mais commits que tenha: o pedido era medir entrega, não
    movimento.
    """
    ordenados = sorted(
        participantes,
        key=lambda p: (
            -p.paginas,
            p.linhas / p.paginas if p.paginas else float("inf"),
            p.nome,
        ),
    )
    return [
        Participante(
            **{
                campo: getattr(participante, campo)
                for campo in (
                    "nome",
                    "papel",
                    "paginas",
                    "entregas",
                    "linhas",
                    "retrabalho",
                    "dias_ativos",
                    "ultima_entrega",
                )
            },
            posicao=lugar + 1,
            plano=PLANOS[lugar][0] if lugar < len(PLANOS) else None,
            consequencia=PLANOS[lugar][1] if lugar < len(PLANOS) else None,
        )
        for lugar, participante in enumerate(ordenados)
    ]


def retrato() -> tuple[dict | None, str | None]:
    """O JSON publicado ou a causa que impede sua leitura."""
    pasta = diretorio_do_painel()
    if pasta is None:
        return None, "ausente"
    arquivo = pasta / ARQUIVO
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, "ausente"
    except (UnicodeError, json.JSONDecodeError):
        return None, "invalido"
    except OSError:
        return None, "ilegivel"
    if not isinstance(dados, dict):
        return None, "invalido"
    if type(dados.get("versao")) is not int or dados["versao"] != 1:
        return None, "incompativel"
    if not isinstance(dados.get("ias"), list) or not dados["ias"]:
        return None, "invalido"
    chaves = [
        linha.get("chave") if isinstance(linha, dict) else None
        for linha in dados["ias"]
    ]
    if any(
        not isinstance(chave, str) or chave not in IDENTIDADES_IAS for chave in chaves
    ):
        return None, "invalido"
    if len(set(chaves)) != len(chaves):
        return None, "invalido"
    if not isinstance(dados.get("commit_da_base"), str):
        return None, "invalido"
    return dados, None


@require_GET
def ranking_das_ias(request):
    """O ranking, ou a explicação de por que ele não está aqui."""
    dados, motivo = retrato()
    if dados is None:
        return render(
            request,
            "admin/ranking_das_ias.html",
            {
                "admin": request.admin,
                "sem_retrato": True,
                "motivo_sem_retrato": motivo,
                "nao_enxergo": O_QUE_NAO_ENXERGO,
            },
            status=200,
        )
    participantes = [
        linha
        for bruto in dados.get("ias", [])
        if isinstance(bruto, dict)
        and (linha := _participante(bruto, *IDENTIDADES_IAS[bruto["chave"]]))
    ]
    sem_assinatura = _participante(
        dados.get("sem_assinatura"), "Sem autoria única", "fora da classificação"
    )
    incompleto = len(participantes) != len(IDENTIDADES_IAS) or sem_assinatura is None
    linhas = participantes
    if not incompleto:
        linhas = classificar(participantes)
    return render(
        request,
        "admin/ranking_das_ias.html",
        {
            "admin": request.admin,
            "participantes": linhas,
            "incompleto": incompleto,
            "sem_assinatura": sem_assinatura,
            "base": dados.get("base"),
            "commit_da_base": (dados.get("commit_da_base") or "")[:8],
            "gerado_em": _data(dados.get("gerado_em")),
            "nao_enxergo": O_QUE_NAO_ENXERGO,
            "dados_livro": dados_do_painel(),
        },
    )
