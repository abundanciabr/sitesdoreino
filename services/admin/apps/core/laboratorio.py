"""`/admin/placar/laboratorio/` — onde uma aposta da escola vira aprendizado.

Degrau 12 do `docs/decisoes/PLANO-PAINEL-DE-GESTAO.md`. Uma escola pode vender
muito e aprender pouco. O laboratório é a tela que mede a segunda coisa: quantas
apostas estão rodando, quais terminaram, quais venceram, e quais não deram para
saber.

## O desenho, e o que ele recusa

**Um experimento é um REGISTRO do livro, não uma tabela.** É a lei desta casa:
acontecimento se acrescenta, estado se calcula. O experimento é uma `medicao`
que declara a aposta ANTES de saber o resultado (o problema que dói, a
hipótese, qual número ela quer mover, o que a faz parar antes da hora, e o
prazo em `vence_em_dias`). O contrato desses campos é imposto por
`painel/logica.js`, dos dois lados: o gerador do livro RECUSA construir com um
experimento pela metade.

**O resultado é um registro NOVO que aponta para o experimento** (`responde_a`),
com o `veredito`. Nunca a edição do experimento — e é justamente por isso que a
aposta escrita antes vale alguma coisa: ninguém pode reescrever a hipótese
depois de ver o número.

**O estado é CALCULADO, nunca digitado.** Nenhum campo `status` em lugar nenhum:

- **rodando** — sem resposta, dentro do prazo;
- **vencido** — sem resposta, e o prazo passou. Não é fracasso do experimento:
  é dívida de quem prometeu julgá-lo, e por isso ele grita na tela;
- **encerrado** — tem resposta, e o veredito dela manda: venceu, perdeu, ou
  não deu para saber.

## "Não deu para saber" tem nome próprio, e conta separado

Metade do valor de um laboratório é poder dizer isso em voz alta. Um
experimento inconclusivo não é derrota (a hipótese continua de pé) nem
aprendizado (nada foi validado). Achatá-lo em "perdeu" ensinaria a casa a fazer
experimentos que sempre respondem alguma coisa, que é a forma mais cara de
mentir para si mesma.

Por isso ele **não entra** na velocidade de aprendizado validado: o 12º do
placar de doze conta os experimentos que venceram OU perderam, porque nos dois
casos a casa passou a saber algo que não sabia. O inconclusivo aparece na tela,
contado, com o nome dele.

## Este módulo é a ÚNICA contagem — e ele corrigiu um número que mentia

Até 05/09/2026 o cartão `aprendizados-validados-no-ciclo` contava "toda
`medicao` com `responde_a` desde a partida do ciclo". Medido no livro real
naquele dia: **6**, e os seis eram vereditos de deploy respondendo a registros
de entrega. Nenhum experimento existia. O número não estava quebrado por bug —
ele media a coisa errada com precisão, que é como um indicador morre
(`armadilhas/303`).

`doze.aprendizados_validados` passou a chamar `aprendizados_validados` daqui.
Uma regra só, dois leitores, zero divergência: a tela do laboratório e o 12º do
placar não conseguem discordar, porque são a mesma conta.
"""

from __future__ import annotations

import datetime as dt

from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from .direcao import ler_registros

#: O tipo de registro que carrega um experimento e o resultado dele.
TIPO = "medicao"

#: Os três desfechos, com o nome que aparece na tela. O vocabulário é o mesmo
#: de `VEREDITOS` em `painel/logica.js`, que é quem o IMPÕE na escrita; aqui ele
#: se repete pelo mesmo motivo de `TIPO_DO_COMPROMISSO` em `direcao.py` — o
#: livro é JavaScript e esta tela é Python, e um dos dois lados tem de dizer as
#: palavras. Quem reprova palavra inventada é o gerador do livro, na escrita.
VEREDITOS = {
    "venceu": "Venceu",
    "perdeu": "Perdeu",
    "nao-deu-para-saber": "Não deu para saber",
}

#: Os dois desfechos que ensinaram alguma coisa. "Perdeu" é aprendizado: a casa
#: passou a saber que a hipótese era falsa, e isso vale tanto quanto acertar.
APRENDERAM = ("venceu", "perdeu")


def eh_experimento(registro: dict) -> bool:
    """Uma `medicao` que declara uma hipótese. Os outros quatro campos vêm com
    ela por contrato (`painel/logica.js` recusa experimento pela metade)."""
    return registro.get("tipo") == TIPO and bool(registro.get("hipotese"))


def _data(texto: object) -> dt.date | None:
    try:
        return dt.date.fromisoformat(str(texto))
    except (TypeError, ValueError):
        return None


def montar(registros: list[dict] | None, hoje: dt.date) -> dict | None:
    """Os experimentos com o estado calculado; `None` se o livro não veio.

    `None` NUNCA é lista vazia. Livro ausente é "não consegui olhar"; lista
    vazia é "olhei e não há experimento nenhum". A tela diz coisas diferentes
    nos dois casos, e achatá-los faria a tela afirmar que não há apostas
    justamente quando ela não conseguiu ler o livro.
    """
    if registros is None:
        return None
    resultados = {
        r["responde_a"]: r
        for r in registros
        if r.get("tipo") == TIPO and r.get("responde_a")
    }
    rodando: list[dict] = []
    vencidos: list[dict] = []
    encerrados: list[dict] = []
    for r in registros:
        if not eh_experimento(r):
            continue
        quando = _data(r.get("quando"))
        prazo = r.get("vence_em_dias")
        vence = (
            quando + dt.timedelta(days=prazo)
            if quando is not None and isinstance(prazo, int)
            else None
        )
        item = {
            "arquivo": r["arquivo"],
            "titulo": r.get("titulo") or r["arquivo"],
            "problema": r.get("problema"),
            "hipotese": r.get("hipotese"),
            "metrica": r.get("metrica"),
            "guarda": r.get("guarda"),
            "quando": quando,
            "vence": vence,
            "dias": (vence - hoje).days if vence is not None else None,
        }
        resultado = resultados.get(r["arquivo"])
        if resultado is not None:
            veredito = resultado.get("veredito")
            item["veredito"] = veredito
            item["veredito_nome"] = VEREDITOS.get(veredito, "Sem veredito escrito")
            item["aprendeu"] = veredito in APRENDERAM
            item["resultado"] = {
                "arquivo": resultado["arquivo"],
                "titulo": resultado.get("titulo") or resultado["arquivo"],
                "quando": _data(resultado.get("quando")),
            }
            encerrados.append(item)
        elif vence is not None and hoje > vence:
            vencidos.append(item)
        else:
            rodando.append(item)
    rodando.sort(key=lambda x: (x["dias"] is None, x["dias"]))
    vencidos.sort(key=lambda x: x["dias"])
    encerrados.sort(key=lambda x: x["resultado"]["quando"] or dt.date.min, reverse=True)
    return {
        "rodando": rodando,
        "vencidos": vencidos,
        "encerrados": encerrados,
        "por_veredito": [
            {
                "chave": chave,
                "nome": nome,
                "itens": [e for e in encerrados if e.get("veredito") == chave],
            }
            for chave, nome in VEREDITOS.items()
        ],
        "total": len(rodando) + len(vencidos) + len(encerrados),
    }


def aprendizados_validados(
    registros: list[dict] | None, partida_em: dt.date
) -> int | None:
    """O 12º do placar de doze: experimentos que ensinaram algo, neste ciclo.

    Conta pelo dia do RESULTADO, e não pelo dia em que o experimento começou:
    o aprendizado acontece quando alguém escreve o veredito. Uma aposta feita
    antes da partida do ciclo e fechada dentro dele é aprendizado deste ciclo.
    """
    if registros is None:
        return None
    # O `hoje` não entra nesta conta: quem é "encerrado" não depende do relógio,
    # só de existir um resultado. A data sentinela deixa isso explícito em vez
    # de esconder um relógio dentro de uma contagem de ciclo.
    encerrados = montar(registros, dt.date.min)["encerrados"]
    return sum(
        1
        for e in encerrados
        if e["aprendeu"]
        and e["resultado"]["quando"] is not None
        and e["resultado"]["quando"] >= partida_em
    )


@require_GET
def laboratorio(request):
    """A tela. Fail-OPEN, como o placar: ela abre e DIZ o que não conseguiu ver."""
    return render(
        request,
        "admin/laboratorio.html",
        {
            "admin": request.admin,
            "lab": montar(ler_registros(), timezone.localdate()),
        },
    )
