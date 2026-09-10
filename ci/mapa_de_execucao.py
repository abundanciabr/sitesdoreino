"""Materializa orientação de tarefa nova pela fila local, sem executar a tarefa."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath

sys.path.insert(0, str(Path(__file__).resolve().parent))

import economia_da_fabrica as economia  # noqa: E402
import fila  # noqa: E402
import mapa_de_celulas  # noqa: E402
import sessao  # noqa: E402
from _nucleo import ErroDeInstrumentacao, configurar_saida  # noqa: E402


def _ler_revisao(raiz: Path) -> str:
    try:
        resultado = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"], cwd=raiz,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as erro:
        raise ErroDeInstrumentacao("Não foi possível ler git HEAD", str(erro)) from erro
    revisao = resultado.stdout.strip()
    if resultado.returncode or not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", revisao):
        raise ErroDeInstrumentacao("Não foi possível ler git HEAD", resultado.stderr.strip())
    return revisao


def _validar_caminho(raiz: Path, caminho: str) -> None:
    normalizado = caminho.replace("\\", "/")
    windows = PureWindowsPath(caminho)
    inseguro = (
        not caminho.strip() or "\x00" in caminho or windows.drive or windows.root
        or Path(normalizado).is_absolute() or ".." in normalizado.split("/")
    )
    if not inseguro:
        try:
            inseguro = not (raiz / normalizado).resolve().is_relative_to(raiz)
        except (OSError, ValueError):
            inseguro = True
    if inseguro:
        raise ErroDeInstrumentacao(
            f"Caminho recusado: {caminho!r}. Declare um caminho relativo dentro da raiz, "
            "sem '..', e gere a orientação novamente."
        )


def _ler_estado_git(raiz: Path) -> str:
    try:
        resultado = subprocess.run(
            ["git", "--no-optional-locks", "status", "--porcelain", "--untracked-files=all"], cwd=raiz,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as erro:
        raise ErroDeInstrumentacao("Não foi possível conferir as alterações do checkout", str(erro)) from erro
    if resultado.returncode:
        raise ErroDeInstrumentacao("Não foi possível conferir as alterações do checkout", resultado.stderr.strip())
    return resultado.stdout.strip()


def _nao_medido(base: dict, fonte: str, causa: str, proximo_passo: str) -> dict:
    return {
        **base, "tipo": "não_medido", "resultado": "ERROR", "fonte": fonte,
        "causa": causa, "proximo_passo": proximo_passo,
    }


def materializar_pacote(raiz: Path, tar: str, *, agora: datetime) -> dict:
    """Lê fontes locais e deriva um pacote; entrada insegura levanta erro.

    Ausência, estado fora de `na fila` e coleta inconsistente retornam ERROR.
    Exige instante UTC explícito e checkout limpo antes e depois da coleta.
    """
    if not isinstance(tar, str) or not fila.RE_ID.fullmatch(tar):
        raise ErroDeInstrumentacao(
            "Identificador de tarefa inválido. Use TAR-324, com o número registrado na fila."
        )
    if not isinstance(agora, datetime) or agora.utcoffset() != timezone.utc.utcoffset(None):
        raise ErroDeInstrumentacao("Instante inválido. Informe uma data e hora explícita em UTC para reproduzir o pacote.")
    raiz = Path(raiz).resolve()
    base = {"tar": tar, "revisao": None, "instante_utc": agora.isoformat()}
    try:
        base["revisao"] = _ler_revisao(raiz)
        if _ler_estado_git(raiz):
            return _nao_medido(
                base, "git status --porcelain", "O checkout contém alterações; HEAD não identifica o conteúdo atual.",
                "Preserve suas alterações e gere a orientação em um checkout limpo da revisão desejada.",
            )
    except ErroDeInstrumentacao as erro:
        return _nao_medido(base, "git HEAD", erro.resumo, "Confira o checkout e tente gerar a orientação novamente.")

    fonte = "fila/tarefas/ e fila/eventos/"
    try:
        if not fila.pasta_tarefas(raiz).is_dir() or not fila.pasta_eventos(raiz).is_dir():
            raise ErroDeInstrumentacao("Faltam as pastas da fila neste checkout.")
        erros: list[str] = []
        tarefas = fila.carregar_tarefas(raiz, erros)
        if erros:
            raise ErroDeInstrumentacao("; ".join(erros))
        eventos = fila.carregar_eventos(raiz, tarefas, erros)
        if erros:
            raise ErroDeInstrumentacao("; ".join(erros))
        if tar not in tarefas:
            return _nao_medido(
                base, "fila/tarefas/", f"{tar} não existe na fila local.",
                "Confira o identificador com python ci/fila.py listar e gere novamente.",
            )
        tarefa = tarefas[tar]
        estado = fila.calcular_estados(tarefas, eventos)[tar]
        base["estado_fila"] = estado
        if estado["estado"] != fila.NA_FILA:
            return _nao_medido(
                base, fonte, f"{tar} está {estado['estado']}; este pacote só mede tarefa nova na fila.",
                "Confira o estado com python ci/fila.py listar; a retomada exige sua própria orientação.",
            )
        fonte = "celulas.yml"
        celulas = mapa_de_celulas.carregar(raiz)
    except (ErroDeInstrumentacao, OSError, ValueError, TypeError, KeyError) as erro:
        return _nao_medido(base, fonte, str(erro), "Corrija a fonte indicada no checkout e gere a orientação novamente.")

    caminhos = sessao.caminhos_da_tarefa(tarefa, list(celulas))
    for caminho in caminhos:
        _validar_caminho(raiz, caminho)
    observadas = [
        {"caminho": caminho, "celula": mapa_de_celulas.celula_do_caminho(caminho, celulas)}
        for caminho in caminhos
    ]
    fonte_tarefa = f"fila/tarefas/{tarefa['arquivo']}.json"
    try:
        perfil = economia.classificar(tarefa["titulo"] + "\n" + tarefa["despacho"])
        donas = sorted({item["celula"] for item in observadas if item["celula"]})
        brief = economia.compilar_brief(
            raiz, objetivo=tarefa["despacho"], tipo=perfil.tipo,
            celula=", ".join(donas) or "ci", alvos=caminhos, armadilhas=[],
        )
        contexto = sessao.contexto_direcionado(
            raiz, objetivo=tarefa["titulo"], caminhos=caminhos,
            aceite=[tarefa["evidencia_exigida"]],
        )
    except (ErroDeInstrumentacao, OSError, ValueError, TypeError, KeyError) as erro:
        return _nao_medido(
            base, fonte_tarefa, str(erro),
            "Confira a tarefa e as fontes de contexto no checkout; corrija a causa e gere novamente.",
        )
    try:
        if _ler_estado_git(raiz):
            return _nao_medido(
                base, "git status --porcelain", "O checkout recebeu alterações durante a coleta; o pacote foi descartado.",
                "Preserve suas alterações e gere novamente em um checkout limpo da revisão desejada.",
            )
        revisao_final = _ler_revisao(raiz)
    except ErroDeInstrumentacao as erro:
        return _nao_medido(base, "git HEAD", erro.resumo, "Confira o checkout e gere a orientação novamente.")
    if revisao_final != base["revisao"]:
        return _nao_medido(
            base, "git HEAD", "A revisão HEAD mudou durante a coleta; o pacote foi descartado.",
            "Aguarde a mudança de revisão terminar e gere a orientação novamente.",
        )
    return {
        **base, "tipo": "tarefa_nova", "resultado": "PASS", "fonte": fonte_tarefa,
        "titulo": tarefa["titulo"], "objetivo": tarefa["titulo"], "despacho": tarefa["despacho"],
        "aceite": tarefa["evidencia_exigida"], "origem": tarefa["origem"],
        "caminhos_declarados": caminhos, "celulas_observadas": observadas,
        "perfil_economico": asdict(perfil), "brief": brief,
        "contexto": {
            "fontes": [fonte_tarefa, "fila/eventos/", "celulas.yml", "ci/economia_da_fabrica.py", "ci/sessao.py"],
            "texto": contexto,
            "limites": [
                "Estado calculado apenas de tarefas e eventos locais; reservas e PRs remotos não foram consultados.",
                "HEAD e árvore limpa foram conferidos antes e depois; arquivos ignorados pelo Git não têm revisão própria.",
                "Contexto direcionado limitado a oito lições; ausências e truncamento aparecem no texto.",
                "Célula nula significa caminho sem dona declarada em celulas.yml.",
                f"Reproduza na mesma revisão com python -B ci/mapa_de_execucao.py --tar {tar} --instante-utc {agora.isoformat()}.",
            ],
        },
    }


class _Argumentos(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ErroDeInstrumentacao(
            "Argumentos de entrada inválidos. Use --tar TAR-324 e, se necessário, --raiz com o caminho do checkout."
        )


def main(argv: list[str] | None = None) -> int:
    configurar_saida()
    parser = _Argumentos(description=__doc__)
    parser.add_argument("--tar", required=True)
    parser.add_argument("--raiz", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--instante-utc", help="Instante ISO 8601 em UTC para reproduzir o pacote")
    args = None
    agora = datetime.now(timezone.utc)
    try:
        args = parser.parse_args(argv)
        if args.instante_utc:
            try:
                agora = datetime.fromisoformat(args.instante_utc)
            except ValueError as erro:
                raise ErroDeInstrumentacao(
                    "Instante inválido. Use --instante-utc em ISO 8601 UTC, como 2026-09-10T00:00:00+00:00."
                ) from erro
        pacote = materializar_pacote(args.raiz, args.tar, agora=agora)
    except (ErroDeInstrumentacao, OSError, ValueError) as erro:
        pacote = _nao_medido(
            {"tar": args.tar if args else None, "revisao": None, "instante_utc": agora.isoformat()},
            "entrada do comando", str(erro),
            "Confira a entrada e execute python -B ci/mapa_de_execucao.py --tar TAR-324 --raiz <checkout>.",
        )
    print(json.dumps(pacote, ensure_ascii=False, indent=2))
    return 0 if pacote["resultado"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
