"""Recusa conclusões novas que deixam a entrega do mesmo PR em alerta.

O livro continua imutável. A dívida histórica não bloqueia outro trabalho:
só um registro novo que afirma sucesso ou dá baixa é examinado. O vínculo
continua sendo responde_a, escalar, compartilhado pelo painel e pelo admin.
"""

from __future__ import annotations

import os
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from _nucleo import ErroDeInstrumentacao, configurar_saida, executar, raiz_do_repo
from verificar_painel import Painel, ids_no_git, registros_da_fonte


def prs_citados(evidencia: object) -> set[tuple[str, str, int]]:
    """Identidade completa: organização, repositório e número, nunca substring."""
    prs = set()
    for texto in re.findall(r"https?://[^\s<>\"']+", str(evidencia or "")):
        try:
            url = urlsplit(texto.rstrip(".,;:)"))
        except ValueError:
            continue
        if url.netloc.lower() != "github.com":
            continue
        caminho = re.fullmatch(
            r"/([^/]+)/([^/]+)/pull/([1-9][0-9]*)(?:/(?:files|commits|checks))?/?",
            url.path,
        )
        if caminho:
            dono, repo, numero = caminho.groups()
            prs.add((dono.lower(), repo.lower(), int(numero)))
    return prs


def entrega_em_alerta(registro: dict) -> bool:
    return registro.get("tipo") == "entrega" and registro.get("gravidade") in ("ambar", "vermelho")


def baixa_comprovada(resposta: dict, alerta: dict) -> bool:
    if resposta.get("gravidade") != "verde" or not str(resposta.get("evidencia") or "").strip():
        return False
    try:
        if date.fromisoformat(resposta.get("verificado_em") or "") < date.fromisoformat(alerta["quando"]):
            return False
    except (ValueError, TypeError, KeyError):
        return False
    prs = prs_citados(alerta.get("evidencia"))
    return not prs or bool(prs & prs_citados(resposta.get("evidencia")))


def conferir_registros(registros: dict[str, dict], novos: set[str]) -> list[str]:
    alertas = {ident: r for ident, r in registros.items() if entrega_em_alerta(r)}
    baixados = {
        r.get("responde_a") for r in registros.values()
        if isinstance(r.get("responde_a"), str)
        and r["responde_a"] in alertas
        and baixa_comprovada(r, alertas[r["responde_a"]])
    }
    problemas = []
    for ident in sorted(novos):
        registro = registros[ident]
        alvo = registro.get("responde_a")
        if alvo is not None and not isinstance(alvo, str):
            problemas.append(f"{ident}: responde_a precisa ser um identificador em texto ou null; use uma baixa por alerta.")
            continue
        if isinstance(alvo, str) and alvo in alertas and not baixa_comprovada(registro, alertas[alvo]):
            problemas.append(
                f"{ident}: baixa de {alvo} sem prova. Use gravidade verde, verificado_em "
                "a partir do alerta e evidencia citando o PR da entrega e a conferência realizada."
            )
        if registro.get("gravidade") != "verde":
            continue
        prs = prs_citados(registro.get("evidencia"))
        for alerta_id, alerta in sorted(alertas.items()):
            if alerta_id == ident or alerta_id in baixados:
                continue
            if prs & prs_citados(alerta.get("evidencia")):
                problemas.append(
                    f"{ident}: conclusão verde deixa {alerta_id} em alerta. "
                    f'Acrescente no mesmo PR uma baixa com responde_a: "{alerta_id}", '
                    "gravidade verde, evidencia do PR e da conferência, e verificado_em. "
                    "O próprio registro de conclusão pode ser essa baixa. "
                    "Preserve o registro anterior; molde em painel/LEIA-ME.md."
                )
    return problemas


def conferir(painel: Painel, base: str) -> list[str]:
    try:
        anteriores = executar(
            ["git", "ls-tree", "-r", "--name-only", base, "--", "painel/registros/"],
            cwd=painel.raiz, descricao=f"ler registros anteriores em {base}",
        )
    except ErroDeInstrumentacao as erro:
        raise ErroDeInstrumentacao(
            f"não consegui ler a base {base!r}",
            f"{erro.detalhe}\nConfira BASE_REF e faça git fetch origin antes de medir.",
        ) from erro
    no_git = ids_no_git(painel)
    novos = no_git - {Path(linha).stem for linha in anteriores.stdout.splitlines()}
    fonte = registros_da_fonte(painel)
    ilegíveis = sorted(ident for ident in no_git if ident not in fonte or "__erro" in fonte[ident])
    if ilegíveis:
        return [f"{ident}: registro ilegível; corrija o arquivo antes de conferir a baixa." for ident in ilegíveis]
    return conferir_registros({ident: fonte[ident] for ident in no_git}, novos)


def main() -> int:
    configurar_saida()
    try:
        problemas = conferir(
            Painel(raiz_do_repo(Path(__file__).resolve().parent)),
            os.environ.get("BASE_REF") or "origin/main",
        )
    except ErroDeInstrumentacao as erro:
        print(f"ERROR encerramento-alertas: {erro.resumo}\n{erro.detalhe}")
        return 2
    if problemas:
        print("FAIL encerramento-alertas:\n" + "\n".join(problemas))
        return 1
    print("PASS encerramento-alertas: conclusões novas não deixam entregas relacionadas sem baixa comprovada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
