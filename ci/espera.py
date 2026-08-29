"""O LAÇO DE ESPERA DA CASA — extraído do portão de deploy, agora com voz.

POR QUE ESTE ARQUIVO EXISTE
---------------------------
Em 29/08/2026 o mantenedor descreveu o pior modo de falha do projeto, nas
palavras dele: a janela mostra o robô "trabalhando, executando, fazendo algo",
passam horas, e no fim o robô confessa que estava esperando algo que quebrou.
Espera sem fim é visualmente idêntica a trabalho — e a lição ("esperas em
segundo plano precisam de limite"; custou 2h de silêncio em 28/08) morava só na
memória privada do mantenedor, fora do repositório. Detalhes: armadilhas/161.

A espera CORRETA já existia: `esperar_workflows()` do `ci/portao_de_deploy.py`
— fail-closed em três tempos (graça vencida sem o alvo aparecer · teto vencido
sem concluir · falhas seguidas demais da medição), só que MUDA e presa dentro
do CI. Este módulo extrai o laço para um primitivo compartilhado; o portão
passa a importá-lo. Duas definições de "esperar" divergiriam no primeiro dia em
que alguém mexesse numa só (a mesma lei que `services/admin/apps/core/divida.py`
aplica à regra da dívida).

O CONTRATO, EM QUATRO FRASES
----------------------------
1. `observar()` olha o mundo de fora UMA vez e devolve uma `Olhada` (ou levanta
   `ErroDeInstrumentacao` quando não conseguiu medir).
2. `vigiar()` repete a observação até desfecho, e NUNCA espera calado: a cada
   volta chama `ao_observar` — a voz é efeito colateral da espera, não promessa
   de comportamento do agente.
3. Todo desfecho é barulhento: sucesso devolve a `Olhada` final; graça, teto e
   falhas seguidas levantam exceções TIPADAS que carregam o contexto.
4. Um contador de tempo sem estado observado é o mesmo silêncio com batimento
   bonito — por isso a `Olhada` sempre carrega o `resumo` do que foi VISTO, e a
   volta com falha carrega o erro, nunca um relógio nu.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _nucleo import ErroDeInstrumentacao, executar  # noqa: E402

FALHAS_MAX_PADRAO = 5  # o limite herdado do portão — nunca invente um segundo


@dataclass
class Olhada:
    """Uma observação do mundo externo, com o que foi visto por escrito."""

    pronta: bool          # a condição terminou (o veredito é de quem observa)
    resumo: str           # uma frase do estado OBSERVADO — nunca vazia à toa
    apareceu: bool = True  # False = o alvo ainda nem existe (conta contra a graça)
    dados: Any = None     # payload para o chamador (runs, conclusão, etc.)


@dataclass
class Volta:
    """O que a voz recebe a cada volta do laço."""

    decorrido: float               # segundos desde o início
    olhada: Olhada | None = None   # a observação desta volta (ou None se falhou)
    erro: ErroDeInstrumentacao | None = None
    falhas_seguidas: int = 0


class EsperaFalhou(Exception):
    """Base das saídas ruidosas do laço. Carrega o contexto do momento."""

    def __init__(
        self,
        mensagem: str,
        *,
        decorrido: float,
        olhada: Olhada | None = None,
        erro: ErroDeInstrumentacao | None = None,
        falhas_seguidas: int = 0,
    ) -> None:
        super().__init__(mensagem)
        self.decorrido = decorrido
        self.olhada = olhada
        self.erro = erro
        self.falhas_seguidas = falhas_seguidas


class FalhasSeguidas(EsperaFalhou):
    """A medição falhou vezes demais em sequência — não dá para medir."""


class GracaVencida(EsperaFalhou):
    """O alvo não APARECEU dentro da graça — deletado, renomeado ou nunca disparou."""


class TetoVencido(EsperaFalhou):
    """O teto estourou sem desfecho. `erro` preenchido = estourou no meio de
    uma sequência de falhas de medição; `olhada` preenchida = estourou com o
    alvo ainda pendente."""


def vigiar(
    observar: Callable[[], Olhada],
    *,
    teto: float,
    intervalo: float,
    graca: float | None = None,
    falhas_max: int = FALHAS_MAX_PADRAO,
    relogio: Callable[[], float] = time.monotonic,
    dormir: Callable[[float], None] = time.sleep,
    ao_observar: Callable[[Volta], None] | None = None,
) -> Olhada:
    """Observa até desfecho — a ordem das checagens é a do portão, preservada.

    Durante uma sequência de falhas de medição só o teto e o limite de falhas
    valem (graça compara com o alvo, e sem medição não se sabe do alvo). Depois
    de uma observação boa o contador de falhas zera — falha TRANSITÓRIA não
    derruba a espera, só falha PERSISTENTE (INV-CI01: cinco "não sei" seguidos
    não são um "não").
    """
    inicio = relogio()
    falhas_seguidas = 0
    while True:
        try:
            olhada = observar()
            falhas_seguidas = 0
        except ErroDeInstrumentacao as erro:
            falhas_seguidas += 1
            decorrido = relogio() - inicio
            if ao_observar is not None:
                ao_observar(
                    Volta(decorrido=decorrido, erro=erro, falhas_seguidas=falhas_seguidas)
                )
            if falhas_seguidas >= falhas_max:
                raise FalhasSeguidas(
                    f"a medição falhou {falhas_seguidas} vezes seguidas",
                    decorrido=decorrido,
                    erro=erro,
                    falhas_seguidas=falhas_seguidas,
                ) from erro
            if decorrido >= teto:
                raise TetoVencido(
                    f"teto de {teto:.0f}s vencido no meio de falhas de medição",
                    decorrido=decorrido,
                    erro=erro,
                    falhas_seguidas=falhas_seguidas,
                ) from erro
            dormir(intervalo)
            continue

        decorrido = relogio() - inicio
        if ao_observar is not None:
            ao_observar(Volta(decorrido=decorrido, olhada=olhada))
        if olhada.pronta:
            return olhada
        if graca is not None and not olhada.apareceu and decorrido >= graca:
            raise GracaVencida(
                f"o alvo não apareceu em {graca:.0f}s de graça",
                decorrido=decorrido,
                olhada=olhada,
            )
        if decorrido >= teto:
            raise TetoVencido(
                f"teto de {teto:.0f}s vencido com o alvo ainda pendente",
                decorrido=decorrido,
                olhada=olhada,
            )
        dormir(intervalo)


def chamar_gh(gh: list[str], caminho: str) -> Any:
    """Uma chamada `gh api`, com JSON provado — a definição única da casa.

    Sem `--paginate`: com resposta-objeto (actions/runs) ele concatena páginas
    em documentos JSON justapostos, que `json.loads` não lê. `per_page=100`
    nos chamadores cobre com folga um SHA (runs) e um run (jobs).
    O portão de deploy importa daqui; quem precisar de `gh api` num laço de
    espera usa esta, nunca uma cópia.
    """
    execucao = executar(
        [*gh, "api", caminho],
        cwd=Path.cwd(),
        descricao=f"gh api {caminho}",
        exigir_stdout=True,
        timeout=120,
    )
    try:
        return json.loads(execucao.stdout)
    except ValueError as exc:
        raise ErroDeInstrumentacao(
            f"gh api {caminho}: resposta não é JSON",
            f"stdout recebido ({len(execucao.stdout)} bytes):\n"
            + execucao.stdout[:2000],
        ) from exc
