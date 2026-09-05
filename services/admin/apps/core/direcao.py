"""A direção da semana: o que a casa move na semana, e o que ainda não mede.

Degrau 2 do `docs/decisoes/PLANO-PAINEL-DE-GESTAO.md` (§3 bloco 3, §8). É a
segunda disciplina das 4 Disciplinas da Execução, que os documentos do Scale
OS mantêm (1 §5; 2 Parte VI §24 a §27): a meta grande é retrovisor; a medida
de direção é volante, e tem duas propriedades que nenhuma outra tem: **prevê
a meta** e **pode ser movida esta semana**. Uma ou duas, nunca dez.

## A premissa que o mantenedor corrigiu em 05/09/2026

As duas medidas deste módulo nasceram em 03/09/2026 chamando a fila de
liberação de "pedidos de entrada", e a primeira delas se declarava a torneira
da meta. As palavras dele, dois dias depois: *"ninguém pede entrada na escola,
todos entram apenas e unicamente pela matrícula mediante a compra do curso"*, e
*"os alunos dos quais estamos falando no painel das vendas são de vendas que
foram efetuadas via checkout"*.

Quem está na fila **já comprou, fora do site, e espera confirmação**. É uma
sala de espera. As duas contas continuam exatas (o que envelheceu foi o nome),
e por isso a correção é de texto e de versão de cartão, não de fórmula. O que
some é a afirmação de que este é o caminho da venda: não é, e o caminho de
verdade tem dois cartões próprios, `visitas-na-pagina-de-venda-por-semana` e
`compras-pelo-checkout-por-semana`, ambos apagados enquanto o checkout estiver
congelado pela decisão dele de 22/08/2026. Quem os lê e os põe na tela é
`placar.py`; aqui não há conta para eles, porque não há fonte.

## As duas medidas acesas de hoje, e por quê estas

1. **Chegadas à sala de espera, por semana.** Quantas compras feitas fora do
   site chegaram para confirmação nos últimos 7 dias. A meta da semana, quando
   o mantenedor não fixa uma, é a fatia semanal da régua do ciclo, e isso vale
   enquanto toda compra passar por aqui: no dia em que o checkout abrir, quem
   responde pela semana é o cartão da compra pelo site.
2. **Confirmações em até 48 horas.** A parte da jornada que depende SÓ da
   casa: quem já pagou espera o mantenedor confirmar. Meta: 100% das
   confirmações dos últimos 28 dias em até 2 dias, e ninguém esperando há
   mais que isso agora.

## Os compromissos da semana

O Scale OS pede "commitments" com dono e um veredito na semana seguinte
(feito, parcial, não feito). Aqui um compromisso é um **registro do livro**,
tipo `compromisso`, com `vence_em_dias` (7, normalmente). O veredito é
CALCULADO, nunca marcado à mão: compromisso com um registro que `responde_a`
ele é *cumprido*; vencido sem resposta é *não cumprido*; o resto está *em
aberto*. Sem tabela nova, sem estado em lugar nenhum: a reunião de segunda
(degrau 3) escreve o registro, e esta tela lê.

A leitura dos registros aqui é a MESMA fotografia que a `admin` serve em
`/admin/painel/` (`painel_embutido/registros/`), lida por um leitor mínimo em
Python que só extrai os campos de que esta tela precisa. É o precedente de
`ci/divida_do_livro.py`: ler o livro do lado de fora sem reimplementar a
lógica dele; a validação continua sendo a de `painel/logica.js`.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

from .painel import CANDIDATOS
from .placar import STATUS_QUE_COMPRARAM, dia_em_sao_paulo, esperado_em

#: Confirmar em até 48 horas: o mesmo limiar da restrição.
DIAS_PARA_LIBERAR = 2
#: Quantas semanas a tela olha para trás (a sequência).
SEMANAS_OLHADAS = 4
#: O tipo de registro que é um compromisso da semana.
TIPO_DO_COMPROMISSO = "compromisso"

_CAMPO = {
    nome: re.compile(r"^\s*" + nome + r':\s*(null|true|false|"([^"]*)"|(\d+))', re.M)
    for nome in (
        "arquivo",
        "tipo",
        "quando",
        "titulo",
        "responde_a",
        "vence_em_dias",
        "precisa_do_dono",
        "foto",
    )
}


# ------------------------------------------------------------------ o livro


def diretorio_dos_registros() -> Path | None:
    for candidato in CANDIDATOS:
        pasta = candidato / "registros"
        if pasta.is_dir():
            return pasta
    return None


def _campo(texto: str, nome: str):
    m = _CAMPO[nome].search(texto)
    if not m:
        return None
    if m.group(1) == "null":
        return None
    if m.group(1) in ("true", "false"):
        return m.group(1) == "true"
    if m.group(3) is not None:
        return int(m.group(3))
    return m.group(2)


def ler_registros(pasta: Path | None = None) -> list[dict] | None:
    """Os campos de cabeçalho de cada registro; `None` se o livro não veio.

    Só cabeçalho: `detalhe` é concatenação de várias linhas e esta tela não o
    lê. Quem valida o livro é `painel/logica.js`; aqui só se lê o que passou.
    """
    pasta = pasta if pasta is not None else diretorio_dos_registros()
    if pasta is None:
        return None
    registros = []
    for arquivo in sorted(pasta.glob("*.js")):
        texto = arquivo.read_text(encoding="utf-8")
        registros.append(
            {
                "arquivo": _campo(texto, "arquivo") or arquivo.stem,
                "tipo": _campo(texto, "tipo"),
                "quando": _campo(texto, "quando"),
                "titulo": _campo(texto, "titulo"),
                "responde_a": _campo(texto, "responde_a"),
                "vence_em_dias": _campo(texto, "vence_em_dias"),
                "precisa_do_dono": _campo(texto, "precisa_do_dono") is True,
                "foto": _campo(texto, "foto"),
            }
        )
    return registros


def compromissos(registros: list[dict] | None, hoje: dt.date) -> list[dict] | None:
    """Os compromissos das últimas semanas, cada um com o veredito calculado."""
    if registros is None:
        return None
    respondidos = {r["responde_a"] for r in registros if r.get("responde_a")}
    saida = []
    for r in registros:
        if r.get("tipo") != TIPO_DO_COMPROMISSO:
            continue
        quando = _data(r.get("quando"))
        if quando is None or (hoje - quando).days > SEMANAS_OLHADAS * 7:
            continue
        prazo = r.get("vence_em_dias")
        vence = quando + dt.timedelta(days=prazo) if isinstance(prazo, int) else None
        if r["arquivo"] in respondidos:
            veredito = "cumprido"
        elif vence is not None and hoje > vence:
            veredito = "nao-cumprido"
        else:
            veredito = "em-aberto"
        saida.append(
            {
                "arquivo": r["arquivo"],
                "titulo": r.get("titulo") or r["arquivo"],
                "quando": quando,
                "vence": vence,
                "veredito": veredito,
            }
        )
    saida.sort(key=lambda c: c["quando"], reverse=True)
    return saida


def _data(texto: object) -> dt.date | None:
    try:
        return dt.date.fromisoformat(str(texto))
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- as medidas


def _semana_de(dia: dt.date, hoje: dt.date) -> int | None:
    """0 = esta semana (os 7 dias até hoje), 1 = a anterior... `None` fora."""
    dias = (hoje - dia).days
    if dias < 0:
        return None
    semana = dias // 7
    return semana if semana < SEMANAS_OLHADAS else None


def medir_pedidos(
    aguardando: list[dict] | None,
    recusados: list[dict] | None,
    alunos: list[dict] | None,
    hoje: dt.date,
) -> list[int] | None:
    """Chegadas à sala de espera por semana, da atual (índice 0) para trás.

    O nome da função e a chave `pedidos` do resultado são anteriores à correção
    de 05/09/2026 e continuam sendo a chave da foto do livro (`mudancas.py`).
    Trocá-los é a mesma dívida do nome do arquivo do cartão, declarada lá.
    """
    if aguardando is None or recusados is None or alunos is None:
        return None
    liberados = [
        a
        for a in alunos
        if a.get("origem") == "liberado" and a.get("status") in STATUS_QUE_COMPRARAM
    ]
    semanas = [0] * SEMANAS_OLHADAS
    for linha in list(aguardando) + list(recusados) + liberados:
        dia = dia_em_sao_paulo(linha.get("criada_em"))
        if dia is None:
            continue
        s = _semana_de(dia, hoje)
        if s is not None:
            semanas[s] += 1
    return semanas


def medir_liberacoes_em_48h(
    aguardando: list[dict] | None, alunos: list[dict] | None, hoje: dt.date
) -> dict | None:
    """Das confirmações dos últimos 28 dias, quantas saíram em até 2 dias; e
    quantas pessoas esperam na sala há mais que isso agora."""
    if aguardando is None or alunos is None:
        return None
    no_prazo = total = 0
    for a in alunos:
        if a.get("origem") != "liberado" or a.get("status") not in STATUS_QUE_COMPRARAM:
            continue
        liberacao = dia_em_sao_paulo(a.get("virou_aluno_em"))
        pedido = dia_em_sao_paulo(a.get("criada_em"))
        if liberacao is None or pedido is None:
            continue
        if not 0 <= (hoje - liberacao).days < SEMANAS_OLHADAS * 7:
            continue
        total += 1
        if (liberacao - pedido).days <= DIAS_PARA_LIBERAR:
            no_prazo += 1
    esperando_ha_muito = sum(
        1
        for p in aguardando
        if isinstance(p.get("esperando_ha_dias"), int)
        and p["esperando_ha_dias"] > DIAS_PARA_LIBERAR
    )
    return {
        "no_prazo": no_prazo,
        "total": total,
        "por_cento": (round(100 * no_prazo / total) if total else None),
        "esperando_ha_muito": esperando_ha_muito,
    }


def meta_semanal_de_pedidos(
    cartao: dict, meta: dict | None, hoje: dt.date
) -> tuple[int | None, bool]:
    """`(meta, derivada)`: a do cartão, ou a fatia de 7 dias da régua do ciclo.

    Comparar as chegadas à sala de espera com a fatia da meta do ciclo só é
    honesto enquanto TODA compra passar pela sala. Quando o checkout abrir, a
    fatia da semana passa a ser cobrada de `compras-pelo-checkout-por-semana`.
    """
    fixa = cartao.get("meta_semanal")
    if fixa is not None:
        return int(fixa), False
    if meta is None or meta.get("alvo") is None:
        return None, False
    return (
        esperado_em(meta, hoje) - esperado_em(meta, hoje - dt.timedelta(days=7)),
        True,
    )


def calcular_direcao(
    cartao_pedidos: dict,
    cartao_48h: dict,
    meta: dict | None,
    pedidos: list[int] | None,
    liberacoes: dict | None,
    hoje: dt.date,
) -> dict:
    """As duas medidas com meta, valor de hoje, veredito e sequência."""
    meta_pedidos, derivada = meta_semanal_de_pedidos(cartao_pedidos, meta, hoje)
    if pedidos is None:
        bloco_pedidos = {
            "veredito": "nao-consigo-medir",
            "meta": meta_pedidos,
            "meta_derivada": derivada,
        }
    else:
        sequencia = 0
        if meta_pedidos is not None:
            for n in pedidos[1:]:
                if n >= meta_pedidos:
                    sequencia += 1
                else:
                    break
        bloco_pedidos = {
            "veredito": (
                "sem-meta"
                if meta_pedidos is None
                else ("cumprida" if pedidos[0] >= meta_pedidos else "abaixo")
            ),
            "esta_semana": pedidos[0],
            "semanas": pedidos,
            "meta": meta_pedidos,
            "meta_derivada": derivada,
            "sequencia": sequencia,
        }
    if liberacoes is None:
        bloco_48h = {"veredito": "nao-consigo-medir"}
    elif liberacoes["total"] == 0 and liberacoes["esperando_ha_muito"] == 0:
        bloco_48h = {**liberacoes, "veredito": "sem-liberacoes"}
    else:
        em_dia = (
            liberacoes["por_cento"] in (None, 100)
            and liberacoes["esperando_ha_muito"] == 0
        )
        bloco_48h = {**liberacoes, "veredito": "cumprida" if em_dia else "abaixo"}
    return {"pedidos": bloco_pedidos, "liberacoes": bloco_48h}
