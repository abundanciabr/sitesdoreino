"""Leitura estrita do apply_patch nativo, sem gravar os arquivos."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Alteracao:
    operacao: str
    origem: Path
    destino: Path
    linhas: list[str]


def _caminho(bruto: str, cwd: Path) -> Path:
    normal = bruto.replace("\\", "/")
    if not normal.strip() or "\x00" in normal or ".." in normal.split("/"):
        raise ValueError("caminho vazio ou com travessia; use o caminho direto da bancada")
    caminho = Path(normal)
    return (caminho if caminho.is_absolute() else cwd / caminho).resolve()


def ler_patch(dados: dict) -> list[Alteracao]:
    entrada = dados.get("tool_input")
    patch = entrada.get("command") if isinstance(entrada, dict) else None
    if not isinstance(patch, str):
        raise ValueError("apply_patch sem tool_input.command; envie o patch completo")
    linhas = patch.splitlines()
    if len(linhas) < 3 or linhas[0] != "*** Begin Patch" or linhas[-1] != "*** End Patch":
        raise ValueError("patch sem delimitadores completos; corrija Begin/End Patch")
    cwd = Path(dados.get("cwd") or ".")
    alteracoes = []
    usados: set[Path] = set()
    i = 1
    while i < len(linhas) - 1:
        cabeca = linhas[i]
        operacao = next((op for op in ("Add", "Update", "Delete")
                         if cabeca.startswith(f"*** {op} File: ")), None)
        if operacao is None:
            raise ValueError("cabeçalho de arquivo inválido; use Add, Update ou Delete File")
        origem = _caminho(cabeca.split(": ", 1)[1], cwd)
        destino = origem
        i += 1
        if operacao == "Update" and linhas[i].startswith("*** Move to: "):
            destino = _caminho(linhas[i].split(": ", 1)[1], cwd)
            i += 1
        corpo = []
        while i < len(linhas) - 1 and not linhas[i].startswith(("*** Add File: ", "*** Update File: ", "*** Delete File: ")):
            corpo.append(linhas[i])
            i += 1
        if origem in usados or destino in usados:
            raise ValueError("arquivo repetido no patch; reúna a alteração em uma operação")
        usados.update((origem, destino))
        if operacao == "Add" and any(not linha.startswith("+") for linha in corpo):
            raise ValueError("Add File exige linhas começando com +")
        if operacao == "Delete" and corpo:
            raise ValueError("Delete File não aceita conteúdo")
        if operacao == "Update":
            _hunks(corpo)
        alteracoes.append(Alteracao(operacao, origem, destino, corpo))
    if not alteracoes:
        raise ValueError("patch vazio; declare pelo menos um arquivo")
    return alteracoes


def _hunks(linhas: list[str]) -> list[tuple[str, list[str], bool]]:
    hunks = []
    i = 0
    while i < len(linhas):
        contexto = ""
        if linhas[i] == "@@" or linhas[i].startswith("@@ "):
            contexto = linhas[i][3:] if linhas[i] != "@@" else ""
            i += 1
        elif hunks:
            raise ValueError("hunk sem @@; reenvie o contexto da alteração")
        corpo = []
        while i < len(linhas) and not linhas[i].startswith("@@") and linhas[i] != "*** End of File":
            linha = linhas[i]
            if not linha or linha[0] not in " +-":
                raise ValueError("linha de hunk inválida; use espaço, + ou -")
            corpo.append(linha)
            i += 1
        eof = i < len(linhas) and linhas[i] == "*** End of File"
        if eof:
            i += 1
            if i != len(linhas):
                raise ValueError("conteúdo após End of File; corrija o patch")
        if not corpo:
            raise ValueError("Update File sem conteúdo; informe o hunk")
        hunks.append((contexto, corpo, eof))
    if not hunks:
        raise ValueError("Update File vazio; informe o hunk")
    return hunks


def texto_proposto(alteracao: Alteracao) -> str | None:
    if alteracao.operacao == "Delete":
        return None
    if alteracao.operacao == "Add":
        return "\n".join(linha[1:] for linha in alteracao.linhas) + "\n"
    original = alteracao.origem.read_text(encoding="utf-8")
    linhas = original.splitlines()
    resultado = []
    cursor = 0
    for contexto, corpo, eof in _hunks(alteracao.linhas):
        inicio = cursor
        if contexto:
            try:
                inicio = linhas.index(contexto, cursor) + 1
            except ValueError as erro:
                raise ValueError("contexto @@ não encontrado; releia o arquivo") from erro
        antes = [linha[1:] for linha in corpo if linha[0] in " -"]
        depois = [linha[1:] for linha in corpo if linha[0] in " +"]
        if antes:
            candidatos = [pos for pos in range(inicio, len(linhas) - len(antes) + 1)
                          if linhas[pos:pos + len(antes)] == antes
                          and (not eof or pos + len(antes) == len(linhas))]
            if not candidatos:
                raise ValueError("contexto do patch não encontrado; releia o arquivo")
            posicao = candidatos[0]
        else:
            posicao = len(linhas)
        resultado.extend(linhas[cursor:posicao])
        resultado.extend(depois)
        cursor = posicao + len(antes)
    resultado.extend(linhas[cursor:])
    return "\n".join(resultado) + ("\n" if resultado else "")
