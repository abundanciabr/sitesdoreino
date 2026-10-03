"""Atribuição que chega do funil: UTMs e os parâmetros do quiz.

Só entram chaves conhecidas e valores curtos, sem caracteres de controle.
O que não passa é descartado em silêncio; nada aqui é dado pessoal.
"""

import re

CHAVES_UTM = ("utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content")
# v versão, fmt formato, seg segmento, src/med/cpg/ctv origem/mídia/campanha/
# criativo, qa tentativa opaca do quiz, qz slug do quiz.
CHAVES_QUIZ = ("v", "fmt", "seg", "src", "med", "cpg", "ctv", "qa", "qz")
_VALOR = re.compile(r"[\w .:+/-]{1,100}")


def _limpo(valor) -> str | None:
    if isinstance(valor, str) and _VALOR.fullmatch(valor):
        return valor
    return None


def separar_atribuicao(bruto: dict) -> tuple[dict, dict]:
    """(utm, contexto) a partir de um dicionário misto. Mantém o valor
    original. As UTMs seguem como sempre (texto como veio); só os parâmetros do
    quiz passam pelo filtro de charset e tamanho."""
    utm = {
        str(k): str(v) for k, v in bruto.items() if str(k) not in CHAVES_QUIZ
    }
    contexto = {}
    for chave in CHAVES_QUIZ:
        valor = _limpo(bruto.get(chave))
        if valor is not None:
            contexto[chave] = valor
    return utm, contexto


def atribuicao_da_consulta(consulta) -> dict:
    """Parâmetros da URL da página de dados, prontos para ir à sessão."""
    bruto = {k: consulta.get(k) for k in (*CHAVES_UTM, *CHAVES_QUIZ) if consulta.get(k)}
    utm, contexto = separar_atribuicao(bruto)
    return {**utm, **contexto}
