"""Seleciona exclusivamente uma aprovação registrada na VPS, nunca uma tag histórica."""
from __future__ import annotations
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _nucleo import ErroDeInstrumentacao, executar, raiz_do_repo

SHA = re.compile(r"[0-9a-f]{40}\Z")
ID = re.compile(r"[A-Za-z0-9_.:-]{1,120}\Z")


def celulas_declaradas() -> list[str]:
    try:
        celulas = json.loads((raiz_do_repo() / "ci/manifesto-de-contratos.json").read_text(encoding="utf-8"))["celulas"]
        if not isinstance(celulas, dict) or not celulas:
            raise ValueError("células ausentes")
        return sorted(celulas)
    except (OSError, ValueError, KeyError) as exc:
        raise ErroDeInstrumentacao("manifesto ilegível", str(exc)) from exc


def selecionar_estado(bruto: str, celula: str = "") -> dict:
    try:
        dados = json.loads(bruto)
        if isinstance(dados, dict) and "publicacoes" in dados:
            if dados.get("recuperacao_global"):
                raise ValueError("tentativa automática global já encerrada; aguarde nova publicação aprovada")
            lista = dados["publicacoes"]
        else:
            lista = dados if isinstance(dados, list) else [dados]
        if not isinstance(lista, list):
            raise ValueError("lista de publicações inválida")
        if not lista or any(not isinstance(e, dict) or e.get("celula") not in celulas_declaradas() or (not isinstance(e.get("atual"), str) or not SHA.fullmatch(e["atual"])) for e in lista):
            raise ValueError("journal inválido ou célula desconhecida")
        if celula:
            encontrados = [e for e in lista if e["celula"] == celula]
            if len(encontrados) != 1:
                raise ValueError("journal da célula ausente ou duplicado")
            return encontrados[0]
        # Horários precisam ser explícitos, com fuso; um empate não escolhe arbitrariamente.
        horarios = []
        for estado in lista:
            hora = datetime.fromisoformat(estado["publicada_em"].replace("Z", "+00:00"))
            if hora.tzinfo is None:
                raise ValueError("horário sem fuso")
            horarios.append((hora, estado))
        recente = max(h for h, _ in horarios)
        encontrados = [e for h, e in horarios if h == recente]
        if len(encontrados) != 1:
            raise ValueError("última publicação ambígua")
        return encontrados[0]
    except (ValueError, TypeError, KeyError) as exc:
        raise ErroDeInstrumentacao("journal ausente ou incerto; recuperação interrompida", str(exc)) from exc


def escolher_alvo(estado: dict) -> dict:
    if estado.get("recuperacao"):
        raise ValueError("recuperação já tentada; consulte o journal; nova tentativa automática encerrada")
    compat = estado.get("compatibilidade")
    if not isinstance(compat, dict) or any(not isinstance(compat.get(k), str) or not ID.fullmatch(compat[k]) for k in ("dados", "configuracao")):
        raise ErroDeInstrumentacao("compatibilidade de dados e configuração não comprovada")
    aprovada = estado.get("aprovada")
    if not isinstance(aprovada, dict):
        raise ValueError("primeiro destino recuperável não aprovado; prove a versão em uso antes da primeira troca")
    alvo = estado.get("anterior_aprovada") if aprovada.get("sha") == estado["atual"] else aprovada
    if not isinstance(alvo, dict) or (not isinstance(alvo.get("sha"), str) or not SHA.fullmatch(alvo["sha"])) or alvo["sha"] == estado["atual"]:
        raise ValueError("sem aprovada anterior distinta; reiniciar a mesma imagem não é reversão")
    try:
        prova_em = datetime.fromisoformat(alvo["verificada_em"].replace("Z", "+00:00"))
        if prova_em.tzinfo is None:
            raise ValueError("prova sem fuso")
    except (KeyError, ValueError, AttributeError, TypeError) as exc:
        raise ErroDeInstrumentacao("aprovação sem prova registrada", str(exc)) from exc
    if any(alvo.get(k) != compat[k] for k in ("dados", "configuracao")):
        raise ValueError("aprovada incompatível com dados/configuração; banco não será restaurado")
    return alvo


def imagem_existe(celula: str, tag: str) -> bool:
    try:
        comando = json.loads(os.environ["REVERSAO_DOCKER"]) if os.environ.get("REVERSAO_DOCKER") else ["docker"]
        if not isinstance(comando, list) or not comando or not all(isinstance(s, str) for s in comando):
            raise ValueError("comando Docker inválido")
    except ValueError as exc:
        raise ErroDeInstrumentacao("REVERSAO_DOCKER inválido", str(exc)) from exc
    prefixo = os.environ.get("REVERSAO_IMAGEM_PREFIXO") or "ghcr.io/abundanciabr/plataforma-"
    try:
        executar([*comando, "manifest", "inspect", f"{prefixo}{celula}:{tag}"], cwd=raiz_do_repo(), descricao="verificar imagem aprovada", exigir_stdout=True, timeout=120)
    except ErroDeInstrumentacao as exc:
        if any(m in f"{exc.resumo} {exc.detalhe}".lower() for m in ("manifest unknown", "manifest_unknown", "no such manifest")):
            return False
        raise
    return True


def publicar_saidas(valores: dict[str, str]) -> None:
    if destino := os.environ.get("GITHUB_OUTPUT"):
        with open(destino, "a", encoding="utf-8") as saida:
            for chave, valor in valores.items():
                saida.write(f"{chave}={valor}\n")


def main() -> int:
    try:
        estado = selecionar_estado(os.environ.get("REVERSAO_ESTADO_PUBLICACAO", ""), os.environ.get("REVERSAO_CELULA", ""))
        # Identifica o journal mesmo quando não existir um destino recuperável.
        publicar_saidas({"celula": estado["celula"], "atual": estado["atual"]})
        alvo = escolher_alvo(estado)
        if not imagem_existe(estado["celula"], alvo["sha"]):
            raise ValueError("imagem aprovada ausente no registry; recuperação encerrada")
        publicar_saidas({"celula": estado["celula"], "tag": alvo["sha"], "var_tag": f"{estado['celula'].upper()}_TAG", "atual": estado["atual"], "dados": alvo["dados"], "configuracao": alvo["configuracao"]})
        print(f"APROVADA: {estado['celula']} -> {alvo['sha']}; receptor revalidará o journal sob trava.")
        return 0
    except ErroDeInstrumentacao as exc:
        print(f"PAROU SEM MEDIÇÃO: {exc.resumo}\n{exc.detalhe}")
        return 2
    except ValueError as exc:
        print(f"PAROU: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
