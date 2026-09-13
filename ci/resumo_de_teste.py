"""Resumo do pytest: 0 PASS/SKIP, 1 FAIL, 2 ERROR; o log completo fica no disco.

Uso: python ci/resumo_de_teste.py <relatorio.json>
O runner canônico informa o caminho de cada execução, sem reutilizar JSON antigo.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from _nucleo import Estado, Resultado, configurar_saida


def tem_plugin_json() -> bool:
    try:
        import pytest_jsonreport  # noqa: F401
    except ImportError:
        return False
    return True


def analisar(data: dict) -> Resultado:
    """Confere exit, contagem e resultados antes de resumir a evidência."""
    try:
        codigo = data["exitcode"]
        total = data["summary"]["total"]
        testes = data["tests"]
        if type(codigo) is not int or type(total) is not int or total < 0:
            raise ValueError("contagem ou exit inválido")
        if not isinstance(testes, list) or len(testes) != total:
            raise ValueError("contagem não corresponde aos testes")
        contagens = Counter(t["outcome"] for t in testes)
        if set(contagens) - {"passed", "failed", "error", "skipped", "xfailed", "xpassed"}:
            raise ValueError("resultado de teste desconhecido")
        if any(not isinstance(t["nodeid"], str) or not t["nodeid"] for t in testes):
            raise ValueError("teste sem identificação")
        for outcome in {"passed", "failed", "error", "skipped", "xfailed", "xpassed"}:
            informado = data["summary"].get(outcome, 0)
            if type(informado) is not int or informado != contagens[outcome]:
                raise ValueError("resumo diverge dos resultados individuais")
        if codigo not in (0, 1) or total == 0:
            return Resultado("pytest", Estado.ERROR, f"pytest não mediu a suíte (exit {codigo}); confira o log")
        erros = contagens["error"] or any(
            t.get(fase, {}).get("outcome") == "failed"
            for t in testes for fase in ("setup", "teardown")
        )
        if erros:
            estado = Estado.ERROR
        elif contagens["failed"]:
            if codigo != 1:
                raise ValueError("falha com exit de sucesso")
            estado = Estado.FAIL
        elif codigo != 0:
            raise ValueError("exit de falha sem teste reprovado")
        else:
            estado = Estado.PASS if contagens["passed"] or contagens["xpassed"] else Estado.SKIP
        mensagem = f"{estado.value}: {contagens['passed']}/{total} passaram, {contagens['failed']} falhas, {contagens['error']} erros"
        if estado in (Estado.FAIL, Estado.ERROR):
            for teste in testes:
                if teste["outcome"] not in ("failed", "error"):
                    continue
                fase = next((teste.get(f, {}) for f in ("setup", "call", "teardown")
                             if teste.get(f, {}).get("outcome") == "failed"), {})
                curta = " ".join(str(fase.get("crash", {}).get("message", "")).split())[:100]
                mensagem += f"; {teste['nodeid'][:100]}: {curta}"
                break
        return Resultado("pytest", estado, mensagem)
    except (KeyError, TypeError, ValueError, AttributeError) as erro:
        return Resultado("pytest", Estado.ERROR, f"JSON inválido ({str(erro)[:100]}); execute pytest novamente")


def ler(caminho: Path) -> Resultado:
    try:
        data = json.loads(caminho.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as erro:
        return Resultado("pytest", Estado.ERROR, f"Não foi possível ler o JSON ({type(erro).__name__}); execute pytest novamente")
    return analisar(data)


def compacto(resultado: Resultado, evidencia: dict) -> str:
    payload = {"estado": resultado.estado.value, "resumo": resultado.resumo}
    payload.update({chave: evidencia[chave] for chave in ("log", "relatorio") if evidencia.get(chave)})
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def com_evidencia(resultado: Resultado, evidencia: dict) -> tuple[Resultado, dict]:
    resultado.resumo = compacto(resultado, evidencia)
    return resultado, evidencia


def executar_pytest(raiz: Path, argumentos: list[str], *, exigir_json: bool = False,
                    prazo: float = 900) -> tuple[Resultado, dict]:
    """Cada execução tem log próprio; pacote ausente conserva o executor anterior."""
    pasta = Path(tempfile.mkdtemp(prefix="pytest-"))
    log = pasta / "pytest.log"
    caminho = pasta / "resultado.json"
    plugin = tem_plugin_json()
    evidencia = {"log": str(log), "relatorio": str(caminho) if plugin else None}
    if exigir_json and not plugin:
        log.write_text("Instale python -m pip install -r requirements-ci.txt\n", encoding="utf-8")
        return com_evidencia(Resultado("pytest", Estado.ERROR, "Instale python -m pip install -r requirements-ci.txt para provar guardas"), evidencia)
    comando = [sys.executable, "-m", "pytest", *argumentos]
    if plugin:
        comando.extend(["--json-report", f"--json-report-file={caminho}"])
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        with log.open("w", encoding="utf-8") as saida:
            saida.write(json.dumps(comando, ensure_ascii=False) + "\n")
            saida.flush()
            proc = subprocess.run(comando, cwd=raiz, env=env, stdout=saida, stderr=subprocess.STDOUT,
                                  timeout=prazo, check=False)
    except (OSError, subprocess.TimeoutExpired) as erro:
        with log.open("a", encoding="utf-8") as saida:
            saida.write(f"\nERROR: {erro}\n")
        return com_evidencia(Resultado("pytest", Estado.ERROR, f"pytest interrompido ({type(erro).__name__}); confira o log"), evidencia)
    evidencia["exitcode"] = proc.returncode
    if plugin:
        resultado = ler(caminho)
        try:
            data = json.loads(caminho.read_text(encoding="utf-8"))
            if data["exitcode"] != proc.returncode:
                resultado = Resultado("pytest", Estado.ERROR, "exit do processo diverge do JSON; confira o log")
            evidencia["dados"] = data
        except (OSError, ValueError, KeyError, TypeError):
            pass  # ler() já classificou o relatório ausente ou inválido como ERROR.
    else:
        estado = {0: Estado.PASS, 1: Estado.FAIL}.get(proc.returncode, Estado.ERROR)
        resultado = Resultado("pytest", estado, f"pytest exit {proc.returncode}, sem JSON")
    return com_evidencia(resultado, evidencia)


def main(argv: list[str] | None = None) -> int:
    configurar_saida()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("relatorio", type=Path, nargs="?", default=Path(".test-result.json"))
    args = parser.parse_args(argv)
    resultado = ler(args.relatorio)
    evidencia = {"relatorio": str(args.relatorio)}
    log = args.relatorio.parent / "pytest.log"
    if log.is_file():
        evidencia["log"] = str(log)
    print(compacto(resultado, evidencia))
    return resultado.estado.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
