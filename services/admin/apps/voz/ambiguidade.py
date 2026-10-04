"""O que no áudio pode ter sido ouvido errado: nome, produto ou condição.

O atendente não chuta: quando o trecho é incerto, ele pede esclarecimento antes
de falar de preço, produto ou nome. Três sinais, sem chamar modelo nenhum:

1. Pouca certeza do transcritor (`logprobs`) numa palavra que é nome próprio,
   número ou condição de compra.
2. Produto citado que bate com mais de um produto do catálogo, ou que parece
   um produto sem ser exatamente ele.
3. Condição ou produto citado por referência vaga ("aquele desconto", "esse
   curso"), sem dizer qual.
"""
from __future__ import annotations

import math
import re
import unicodedata
from difflib import SequenceMatcher

LIMIAR_DE_CERTEZA = 0.6
PALAVRAS_DE_CONDICAO = {
    "vezes", "vez", "parcela", "parcelas", "parcelado", "parcelada", "desconto", "descontos",
    "reais", "real", "pix", "boleto", "cartao", "vista", "mil", "cem", "cento", "promocao",
    "cupom", "preco", "valor", "juros", "entrada", "mensal", "mensalidade", "anual", "porcento",
}
NUMEROS_POR_EXTENSO = {
    "um", "uma", "dois", "duas", "tres", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez",
    "onze", "doze", "treze", "quinze", "vinte", "trinta", "quarenta", "cinquenta", "sessenta",
    "setenta", "oitenta", "noventa", "duzentos", "trezentos", "quinhentos",
}
GENERICOS_DE_PRODUTO = {"curso", "cursos", "mentoria", "pacote", "plano", "kit", "produto",
                        "turma", "aula", "aulas", "programa", "assinatura", "ebook", "livro"}
REFERENCIA_VAGA = re.compile(
    r"\b(aquel[ea]|ess[ea]|est[ea]|o mesmo|a mesma|o outro|a outra)\s+"
    r"(desconto|preco|valor|condicao|promocao|plano|curso|pacote|kit|produto|mentoria|parcelamento|oferta)\b"
)
VAZIAS = {"de", "da", "do", "das", "dos", "e", "o", "a", "os", "as", "em", "para", "com", "no", "na"}


def normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9% ]+", " ", sem_acento.lower()).strip()


PONTUACAO = " .,!?;:\"'()…“”"


def _palavras_com_certeza(logprobs: list[dict]) -> list[tuple[str, float]]:
    """Junta os tokens em palavras (com a pontuação colada); a certeza da
    palavra é o produto das partes."""
    palavras: list[list] = []
    for parte in logprobs:
        token = str(parte.get("token") or "")
        try:
            lp = float(parte.get("logprob"))
        except (TypeError, ValueError):
            continue
        if not token:
            continue
        if palavras and not token[0].isspace():
            palavras[-1][0] += token
            palavras[-1][1] += lp
        else:
            palavras.append([token.strip(), lp])
    return [(p, math.exp(lp)) for p, lp in palavras if p.strip(PONTUACAO)]


def _tipo_da_palavra(palavra: str, inicio_de_frase: bool) -> str | None:
    base = normalizar(palavra)
    if not base:
        return None
    if any(c.isdigit() for c in base) or "%" in palavra or base in PALAVRAS_DE_CONDICAO or base in NUMEROS_POR_EXTENSO:
        return "condicao"
    if base in GENERICOS_DE_PRODUTO:
        return "produto"
    if palavra[:1].isupper() and not inicio_de_frase:
        return "nome"
    return None


def _incertezas(texto: str, logprobs: list[dict]) -> list[dict]:
    achados, vistos = [], set()
    anterior = "."
    for bruta, certeza in _palavras_com_certeza(logprobs):
        inicio = anterior.endswith((".", "!", "?"))
        anterior = bruta
        palavra = bruta.strip(PONTUACAO)
        tipo = _tipo_da_palavra(palavra, inicio)
        if tipo and certeza < LIMIAR_DE_CERTEZA and (tipo, palavra) not in vistos:
            vistos.add((tipo, palavra))
            achados.append({"tipo": tipo, "trecho": palavra,
                            "motivo": f"o áudio não ficou claro neste ponto (certeza {certeza:.0%})", "opcoes": []})
    return achados


def _ngramas(palavras: list[str], n: int):
    for i in range(0, max(len(palavras) - n + 1, 0)):
        yield " ".join(palavras[i:i + n])


def _produtos(texto: str, vocabulario: list[str]) -> list[dict]:
    palavras = normalizar(texto).split()
    if not palavras or not vocabulario:
        return []
    junto = " " + " ".join(palavras) + " "
    exatos, parecidos = [], []
    for nome in vocabulario:
        alvo = normalizar(nome)
        if not alvo:
            continue
        if f" {alvo} " in junto:
            exatos.append(nome)
            continue
        n = len(alvo.split())
        melhor, trecho = 0.0, ""
        for tamanho in {max(n - 1, 1), n, n + 1}:
            for grama in _ngramas(palavras, tamanho):
                razao = SequenceMatcher(None, grama, alvo).ratio()
                if razao > melhor:
                    melhor, trecho = razao, grama
        if melhor >= 0.75:
            parecidos.append((nome, trecho, melhor))
    if exatos:
        return []
    achados = []
    if parecidos:
        parecidos.sort(key=lambda p: -p[2])
        opcoes = [p[0] for p in parecidos if parecidos[0][2] - p[2] < 0.08][:3]
        achados.append({"tipo": "produto", "trecho": parecidos[0][1],
                        "motivo": "parece com um produto, sem ser exatamente o nome dele"
                        if len(opcoes) == 1 else "pode ser mais de um produto",
                        "opcoes": opcoes})
        return achados
    # Palavra genérica ("o curso") com mais de um produto daquele tipo.
    for generica in GENERICOS_DE_PRODUTO & set(palavras):
        candidatos = [n for n in vocabulario if generica in normalizar(n).split()]
        if len(candidatos) >= 2:
            achados.append({"tipo": "produto", "trecho": generica, "opcoes": candidatos[:3],
                            "motivo": "não disse qual, e há mais de um"})
            break
    return achados


def _referencias_vagas(texto: str) -> list[dict]:
    achados = []
    for casamento in REFERENCIA_VAGA.finditer(normalizar(texto)):
        coisa = casamento.group(2)
        tipo = "produto" if coisa in {"plano", "curso", "pacote", "kit", "produto", "mentoria", "oferta"} else "condicao"
        achados.append({"tipo": tipo, "trecho": casamento.group(0), "opcoes": [],
                        "motivo": "fala de algo combinado antes sem dizer qual"})
    return achados


def pergunta(ambiguidades: list[dict]) -> str:
    if not ambiguidades:
        return ""
    partes = []
    for tipo in ("produto", "condicao", "nome"):
        item = next((a for a in ambiguidades if a["tipo"] == tipo), None)
        if item is None:
            continue
        if tipo == "produto" and len(item.get("opcoes") or []) >= 2:
            partes.append("você está falando de " + " ou de ".join(item["opcoes"][:3]) + "?")
        elif tipo == "produto":
            partes.append(f"qual produto você quis dizer com “{item['trecho']}”?")
        elif tipo == "condicao":
            partes.append(f"pode confirmar por escrito “{item['trecho']}”?")
        else:
            partes.append(f"pode escrever o nome “{item['trecho']}” para eu não errar?")
    return "Só para eu não entender errado o seu áudio: " + " E ".join(partes[:2])


def avaliar(texto: str, logprobs: list[dict] | None = None, vocabulario: list[str] | None = None) -> dict:
    """{ambiguidades: [...], pergunta_de_esclarecimento: str}."""
    achados = _incertezas(texto, logprobs or []) + _produtos(texto, vocabulario or []) + _referencias_vagas(texto)
    unicos, vistos = [], set()
    for item in achados:
        chave = (item["tipo"], normalizar(item["trecho"]))
        if chave not in vistos:
            vistos.add(chave)
            unicos.append(item)
    if not (texto or "").strip():
        unicos = [{"tipo": "audio", "trecho": "", "opcoes": [], "motivo": "não deu para entender o áudio"}]
        return {"ambiguidades": unicos,
                "pergunta_de_esclarecimento": "Não consegui entender o seu áudio. Pode repetir ou escrever?"}
    return {"ambiguidades": unicos[:10], "pergunta_de_esclarecimento": pergunta(unicos)}
