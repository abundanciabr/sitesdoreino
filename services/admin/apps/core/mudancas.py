"""O que mudou desde a semana passada (degrau 6 do plano do painel de gestão).

Scale OS 1.1 §159 pede que a primeira tela diga o que se MOVEU, não só o que
é. Para dizer que um número andou é preciso saber onde ele estava, e esta
casa ainda não tem a célula de medição (`metricas`, degrau 7). Até ela
nascer, a memória é o livro: **a foto da semana** é um registro tipo
`medicao` com o campo `foto`, uma linha `nome=valor; nome=valor` com os
cartões que tinham fonte no dia. Quem tira a foto é o modo reunião, que a
põe no pedido para o robô; quem a grava é o robô, por PR, como todo registro.

Três regras, e cada uma é um teste:

- **Ruído não é movimento.** Um cartão pode declarar `ruido` (na unidade
  dele); só a diferença maior que o ruído aparece. Sem `ruido`, qualquer
  diferença conta, porque com poucos alunos cada pessoa é notícia.
- **A direção quem pinta é o cartão.** `subir` e o número subiu: melhorou;
  `descer` e subiu: piorou; `faixa`: só "mudou". O bloco nunca inventa o
  sentido.
- **Foto velha é dita.** Cada cartão pode declarar `frescor_maximo` (dias);
  passa disso e a comparação vem marcada como feita contra uma foto velha.
  Sem foto nenhuma, o bloco diz como tirar a primeira em vez de mostrar nada.
"""

from __future__ import annotations

import datetime as dt
import re

#: Se o cartão não diz em quantos dias a foto envelhece, é isto (a semana e
#: uma folga de três dias para a reunião de segunda atrasar).
FRESCOR_PADRAO = 10

#: `nome=valor; nome=valor`. O valor aceita decimal com ponto e sinal.
FORMATO_DA_FOTO = re.compile(r"^[a-z0-9-]+=-?\d+(\.\d+)?(; [a-z0-9-]+=-?\d+(\.\d+)?)*$")

#: Os números que zeram no dia 1: comparar setembro com agosto seria falso.
MENSAIS = ("compras-no-mes",)


def _numero(valor: object) -> int | float | None:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    return valor


def valores_atuais(contexto: dict) -> dict[str, int | float]:
    """Os cartões com fonte que o placar mediu AGORA, `nome → valor`.

    Lê a montagem do placar (não as portas): a foto é do que a tela mostra,
    senão a comparação seria entre duas contas diferentes.
    """
    atuais: dict[str, int | float] = {}
    contagem = contexto.get("contagem") or {}
    if _numero(contagem.get("ciclo")) is not None:
        atuais["compras-no-ciclo"] = contagem["ciclo"]
    if _numero(contagem.get("total_de_alunos")) is not None:
        atuais["alunos-na-plataforma"] = contagem["total_de_alunos"]
    direcao = contexto.get("direcao") or {}
    pedidos = direcao.get("pedidos") or {}
    if _numero(pedidos.get("esta_semana")) is not None:
        atuais["pedidos-de-entrada-por-semana"] = pedidos["esta_semana"]
    liberacoes = direcao.get("liberacoes") or {}
    if _numero(liberacoes.get("por_cento")) is not None:
        atuais["liberacoes-em-48h"] = liberacoes["por_cento"]
    for item in contexto.get("doze") or []:
        if item.get("veredito") == "medido" and _numero(item.get("valor")) is not None:
            atuais[item["nome"]] = item["valor"]
    latencias = contexto.get("latencias") or {}
    for chave, nome in (
        ("decisao", "latencia-de-decisao"),
        ("execucao", "latencia-de-execucao"),
        ("aprendizado", "latencia-de-aprendizado"),
    ):
        medida = latencias.get(chave) or {}
        if medida.get("veredito") == "medido":
            if _numero(medida.get("mediana_dias")) is not None:
                atuais[nome] = medida["mediana_dias"]
    return atuais


def foto_em_texto(atuais: dict[str, int | float]) -> str:
    """A linha que vai no campo `foto` do registro."""
    partes = []
    for nome in sorted(atuais):
        valor = atuais[nome]
        partes.append(
            f"{nome}={valor:g}" if isinstance(valor, float) else f"{nome}={valor}"
        )
    return "; ".join(partes)


def ler_foto(texto: object) -> dict[str, int | float] | None:
    """`nome → valor` de uma linha de foto; `None` se a linha está torta."""
    if not isinstance(texto, str) or not FORMATO_DA_FOTO.match(texto):
        return None
    foto: dict[str, int | float] = {}
    for parte in texto.split("; "):
        nome, valor = parte.split("=", 1)
        foto[nome] = float(valor) if "." in valor else int(valor)
    return foto


def _data(texto: object) -> dt.date | None:
    try:
        return dt.date.fromisoformat(str(texto)[:10])
    except (TypeError, ValueError):
        return None


def ultima_foto(registros: list[dict] | None, hoje: dt.date) -> dict | None:
    """A foto mais recente do livro tirada ANTES de hoje: a semana passada.

    A de hoje não serve de comparação (seria o número contra ele mesmo).
    """
    melhor = None
    for r in registros or []:
        if r.get("tipo") != "medicao" or r.get("foto") is None:
            continue
        dia = _data(r.get("quando"))
        valores = ler_foto(r.get("foto"))
        if dia is None or valores is None or dia >= hoje:
            continue
        if melhor is None or dia > melhor["quando"]:
            melhor = {"quando": dia, "arquivo": r.get("arquivo"), "valores": valores}
    return melhor


def comparar(
    atuais: dict[str, int | float],
    foto: dict | None,
    cartoes: dict[str, dict],
    hoje: dt.date,
) -> dict:
    """O bloco: só o que se moveu além do ruído, pintado pela direção do cartão."""
    if foto is None:
        return {"veredito": "sem-foto", "quantos_atuais": len(atuais)}
    idade = (hoje - foto["quando"]).days
    movidos = []
    parados = 0
    sem_par = 0
    for nome, atual in sorted(atuais.items()):
        cartao = cartoes.get(nome) or {}
        if nome in MENSAIS and foto["quando"].strftime("%Y-%m") != hoje.strftime(
            "%Y-%m"
        ):
            continue  # zerou no dia 1: não é queda, é calendário
        antigo = foto["valores"].get(nome)
        if antigo is None:
            sem_par += 1
            continue
        delta = atual - antigo
        ruido = _numero(cartao.get("ruido")) or 0
        if abs(delta) <= ruido:
            parados += 1
            continue
        direcao = cartao.get("direcao")
        if direcao == "subir":
            sentido = "melhorou" if delta > 0 else "piorou"
        elif direcao == "descer":
            sentido = "melhorou" if delta < 0 else "piorou"
        else:
            sentido = "mudou"
        frescor = _numero(cartao.get("frescor_maximo")) or FRESCOR_PADRAO
        movidos.append(
            {
                "nome": nome,
                "pergunta": cartao.get("pergunta") or nome,
                "unidade": cartao.get("unidade") or "",
                "antigo": antigo,
                "atual": atual,
                "delta": delta,
                "sentido": sentido,
                "foto_velha": idade > frescor,
                "acao": cartao.get("acao") if sentido == "piorou" else None,
            }
        )
    return {
        "veredito": "comparado",
        "foto_em": foto["quando"],
        "foto_arquivo": foto["arquivo"],
        "idade_dias": idade,
        "movidos": movidos,
        "parados": parados,
        "sem_par": sem_par,
    }


def o_que_mudou(contexto: dict, registros: list[dict] | None, hoje: dt.date) -> dict:
    """A montagem inteira, para o placar chamar uma vez."""
    if registros is None:
        return {"veredito": "nao-consigo-medir"}
    atuais = valores_atuais(contexto)
    cartoes = {
        d["nome"]: d["cartao"] for d in contexto.get("doze") or [] if d.get("cartao")
    }
    for chave in ("meta", "total", "cartao_pedidos", "cartao_48h"):
        cartao = contexto.get(chave)
        if cartao:
            cartoes[cartao["nome"]] = cartao
    for chave, cartao in (contexto.get("cartoes_de_latencia") or {}).items():
        cartoes[chave] = cartao
    saida = comparar(atuais, ultima_foto(registros, hoje), cartoes, hoje)
    saida["foto_de_hoje"] = foto_em_texto(atuais)
    return saida
