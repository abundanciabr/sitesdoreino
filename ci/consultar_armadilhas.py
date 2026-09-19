"""Consulta local sob demanda; índices gerados, até três lições de 500 caracteres."""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
from pathlib import Path

from _nucleo import ErroDeInstrumentacao, configurar_saida
from indice_de_armadilhas import ler_frontmatter

RAIZ = Path(__file__).resolve().parents[1]
REGERAR = 'Execute python ci/indice_de_armadilhas.py na bancada e repita a consulta.'


def extrair_licao(caminho: Path) -> str:
    texto = caminho.read_text(encoding='utf-8')
    dados = ler_frontmatter(texto.splitlines(), caminho.name) or {}
    if isinstance(dados.get('licao'), str) and dados['licao'].strip():
        return ' '.join(dados['licao'].split())[:500]
    inicio = re.search(r'(?im)^(?:\*\*(?:solução|lição|correção|antídoto):?\*\*:?[ \t]*|#{2,6}[ \t]+(?:solução|lição|correção|antídoto)[^\n]*\n)', texto)
    if inicio:
        trecho = texto[inicio.end():]
        trecho = re.split(r'(?m)^#{1,6} |^\*\*[^*\n]+:?\*\*:?', trecho, maxsplit=1)[0]
        return ' '.join(trecho.split())[:500]
    return 'Lição não declarada. Abra somente esta entrada e confira a orientação antes de agir.'


def ler_indice(raiz: Path, nome: str, chave: str, campos: tuple[str, ...]) -> list[dict]:
    dados = json.loads((raiz / 'armadilhas' / nome).read_text(encoding='utf-8'))
    if not isinstance(dados, dict) or dados.get('versao') != 1 or not isinstance(dados.get(chave), list):
        raise ValueError(f'{nome}: formato inválido')
    for item in dados[chave]:
        if not isinstance(item, dict) or any(not isinstance(item.get(c), str) or not item[c] for c in campos):
            raise ValueError(f'{nome}: entrada inválida')
    return dados[chave]


def consultar(raiz: Path, sintoma: str = '', caminho: str = '') -> dict:
    try:
        if not sintoma.strip() and not caminho.strip():
            return {'estado': 'ERROR', 'resultados': [], 'acao': 'Informe a mensagem de erro ou --caminho arquivo.'}
        candidatos = []
        if sintoma.strip():
            sinais = ler_indice(raiz, 'SINAIS.json', 'sinais', ('armadilha', 'arquivo', 'regex'))
            for sinal in sinais:
                if re.search(sinal['regex'], sintoma, re.IGNORECASE):
                    candidatos.append(sinal)
            indice = (raiz / 'armadilhas/INDICE.md').read_text(encoding='utf-8')
            if not re.search(r'^\| # \| Sintoma', indice, re.M):
                raise ValueError('INDICE.md: tabela ausente')
            for linha in indice.splitlines():
                if sintoma.casefold() not in linha.casefold():
                    continue
                entrada = re.match(r'^\|\s*\[(\d+)\]\(([^)]+)\)', linha)
                if entrada:
                    candidatos.append({'armadilha': entrada[1], 'arquivo': 'armadilhas/' + entrada[2]})
        if caminho.strip():
            gatilhos = ler_indice(raiz, 'GATILHOS.json', 'gatilhos', ('armadilha', 'arquivo', 'caminho', 'licao'))
            alvo = caminho.replace('\\', '/')
            if Path(alvo).is_absolute():
                alvo = Path(alvo).resolve().relative_to(raiz.resolve()).as_posix()
            for gatilho in gatilhos:
                padrao = gatilho['caminho']
                if padrao.endswith('/'):
                    padrao += '*'
                if fnmatch.fnmatchcase(alvo.removeprefix('./'), padrao):
                    candidatos.append(gatilho)
        resultados = []
        vistos = set()
        for item in candidatos:
            if item['armadilha'] in vistos:
                continue
            fonte = (raiz / item['arquivo']).resolve()
            fonte.relative_to((raiz / 'armadilhas').resolve())
            licao = extrair_licao(fonte)
            resultados.append({'id': item['armadilha'], 'arquivo': item['arquivo'], 'licao': licao})
            vistos.add(item['armadilha'])
            if len(resultados) == 3:
                break
        return {'estado': 'PASS', 'resultados': resultados, 'acao': 'Confira as origens antes de agir.' if resultados else 'Refine o sintoma ou consulte --caminho; nenhuma lição encontrada não significa ausência de restrições.'}
    except (OSError, ValueError, re.error, ErroDeInstrumentacao) as erro:
        return {'estado': 'ERROR', 'resultados': [], 'erro': str(erro)[:200], 'acao': REGERAR}


def main(argv: list[str] | None = None) -> int:
    configurar_saida()
    parser = argparse.ArgumentParser(description=__doc__, exit_on_error=False)
    parser.add_argument('sintoma', nargs='?', default='')
    parser.add_argument('--caminho', default='')
    try:
        args, extras = parser.parse_known_args(argv)
        if extras:
            raise ValueError('Argumento desconhecido.')
        resultado = consultar(RAIZ, args.sintoma, args.caminho)
    except (argparse.ArgumentError, ValueError):
        resultado = {'estado': 'ERROR', 'resultados': [], 'acao': 'Use uma mensagem entre aspas ou --caminho arquivo.'}
    print(json.dumps(resultado, ensure_ascii=False, separators=(',', ':')))
    return 2 if resultado['estado'] == 'ERROR' else 0


if __name__ == '__main__':
    raise SystemExit(main())
