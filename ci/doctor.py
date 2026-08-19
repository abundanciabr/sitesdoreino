"""SITE DO REINO — ENVIRONMENT DOCTOR.

Responde a UMA pergunta: *este ambiente consegue executar o trabalho?*

A separação semântica com o runner é deliberada:

    doctor  ->  "o ambiente consegue executar o trabalho?"
    ci      ->  "a mudança respeita as invariantes?"

O doctor NÃO substitui a CI e não conserta nada: é read-only e idempotente.
Rodar duas vezes produz o mesmo diagnóstico e não altera estado nenhum.

    python ci/doctor.py            # diagnóstico completo
    python ci/doctor.py --breve    # só o veredito

Exit codes: 0 = READY · 2 = alguma dependência OBRIGATÓRIA não pôde ser
validada. Dependência declarada opcional que falta vira SKIP com motivo — e
SKIP declarado nunca deixa o veredito vermelho.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _nucleo import (  # noqa: E402
    ErroDeInstrumentacao,
    Estado,
    Relatorio,
    Resultado,
    configurar_saida,
    raiz_do_repo,
)

PYTHON_MINIMO = (3, 10)


def _sondar(comando: list[str], timeout: int = 30) -> tuple[int, str, str]:
    """Roda um comando de diagnóstico. Devolve (exit, stdout, stderr).

    Diferente de `_nucleo.executar`, aqui exit != 0 é INFORMAÇÃO (é o que o
    doctor foi feito para descobrir), não erro fatal. Quem chama decide o
    estado — nada é engolido: os três valores voltam inteiros.
    """
    try:
        proc = subprocess.run(
            comando,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return 127, "", f"{comando[0]}: não encontrado no PATH"
    except subprocess.TimeoutExpired:
        return 124, "", f"{comando[0]}: timeout após {timeout}s"
    except OSError as exc:
        return 126, "", f"{comando[0]}: {exc}"
    return proc.returncode, (proc.stdout or "").strip(), (proc.stderr or "").strip()


def _ausente(nome: str, resumo: str, obrigatorio: bool, detalhe: str) -> Resultado:
    """Ausência de dependência: ERROR se obrigatória, SKIP declarado se não.

    O SKIP daqui não é inferido de 'não achei o arquivo': ele vem da decisão,
    escrita no código, de que aquela dependência é opcional para este repositório.
    """
    if obrigatorio:
        return Resultado(nome, Estado.ERROR, resumo, detalhe)
    return Resultado(nome, Estado.SKIP, f"OPCIONAL — {resumo}", "")


# ---------------------------------------------------------------------------
# As checagens
# ---------------------------------------------------------------------------


def checar_python() -> Resultado:
    v = sys.version_info
    versao = f"{v.major}.{v.minor}.{v.micro}"
    if (v.major, v.minor) < PYTHON_MINIMO:
        return Resultado(
            "Python",
            Estado.ERROR,
            f"{versao} — abaixo do mínimo {'.'.join(map(str, PYTHON_MINIMO))}",
            f"Interpretador: {sys.executable}",
        )
    return Resultado("Python", Estado.PASS, f"{versao} ({platform.system()})")


def checar_interpretador_canonico() -> Resultado:
    """`python` precisa existir no PATH — o repositório não depende de `python3`.

    Nesta máquina `python3` é um shim local do dono. O shim resolve a máquina;
    virar requisito arquitetural ele não pode. Por isso o comando canônico do
    projeto é `python`, e é a existência DELE que o doctor exige.
    """
    caminho = shutil.which("python")
    if caminho is None:
        return Resultado(
            "python no PATH",
            Estado.ERROR,
            "não encontrado",
            "Os comandos canônicos do projeto (`python ci/ci.py`, `python ci/doctor.py`,\n"
            "`make ci`) chamam `python`. Sem ele no PATH nada disso roda.",
        )
    codigo, saida, erro = _sondar([caminho, "--version"])
    if codigo != 0:
        return Resultado(
            "python no PATH",
            Estado.ERROR,
            f"encontrado mas não executa (exit {codigo})",
            f"Caminho: {caminho}\n{erro or saida}\n\n"
            "É exatamente o sintoma do stub da Microsoft Store: o binário existe,\n"
            "responde ao `command -v` e não roda.",
        )
    return Resultado("python no PATH", Estado.PASS, f"{saida or 'ok'}")


def checar_git() -> Resultado:
    codigo, saida, erro = _sondar(["git", "--version"])
    if codigo != 0:
        return _ausente(
            "Git",
            "não encontrado no PATH",
            obrigatorio=True,
            detalhe=f"{erro or saida}\n\nAs muralhas (cerca, orçamento, segredos) leem o\n"
            "diff via git. Sem git elas não têm o que medir.",
        )
    return Resultado("Git", Estado.PASS, saida)


def checar_raiz() -> tuple[Resultado, Path | None]:
    try:
        raiz = raiz_do_repo()
    except ErroDeInstrumentacao as erro:
        return Resultado.de_erro("Repositório", erro), None
    return Resultado("Repositório", Estado.PASS, f"raiz resolvida em {raiz}"), raiz


def checar_virtualenv() -> Resultado:
    dentro = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    if dentro:
        return Resultado("Virtualenv", Estado.PASS, f"ativo em {sys.prefix}")
    if os.environ.get("VIRTUAL_ENV"):
        return Resultado("Virtualenv", Estado.PASS, os.environ["VIRTUAL_ENV"])
    return _ausente(
        "Virtualenv",
        "rodando com o Python do sistema (nenhum venv ativo)",
        obrigatorio=False,
        detalhe="",
    )


def checar_modulo(
    nome: str, rotulo: str, obrigatorio: bool, para_que: str, distribuicao: str = ""
) -> Resultado:
    spec = importlib.util.find_spec(nome)
    if spec is None:
        return _ausente(
            rotulo,
            f"módulo '{nome}' não importável",
            obrigatorio,
            detalhe=f"{para_que}\nInstale com: pip install -r services/<celula>/requirements.txt",
        )
    versao = ""
    try:
        from importlib.metadata import version

        versao = version(distribuicao or nome.replace("_", "-"))
    except Exception:  # noqa: BLE001 - versão é cosmética; a importabilidade é o fato
        versao = "versão não declarada"
    return Resultado(rotulo, Estado.PASS, versao)


def checar_executavel(
    comando: list[str], rotulo: str, obrigatorio: bool, para_que: str
) -> Resultado:
    codigo, saida, erro = _sondar(comando)
    if codigo != 0:
        return _ausente(
            rotulo,
            f"'{comando[0]}' indisponível (exit {codigo})",
            obrigatorio,
            detalhe=f"{erro or saida}\n{para_que}",
        )
    return Resultado(rotulo, Estado.PASS, saida.splitlines()[0] if saida else "ok")


def checar_docker() -> list[Resultado]:
    """CLI e Engine são coisas DIFERENTES — não confundir desligado com ausente."""
    codigo, saida, erro = _sondar(["docker", "--version"])
    if codigo != 0:
        return [
            _ausente(
                "Docker CLI",
                "não encontrado no PATH",
                obrigatorio=False,
                detalhe=f"{erro or saida}",
            ),
            _ausente(
                "Docker Engine",
                "não sondado (sem CLI para perguntar)",
                obrigatorio=False,
                detalhe="",
            ),
        ]
    resultados = [Resultado("Docker CLI", Estado.PASS, saida)]
    codigo, servidor, erro = _sondar(
        ["docker", "info", "--format", "{{.ServerVersion}}"]
    )
    if codigo != 0 or not servidor:
        resultados.append(
            Resultado(
                "Docker Engine",
                Estado.SKIP,
                "OPCIONAL — CLI instalado, daemon não responde (Docker Desktop desligado?)",
                "",
            )
        )
    else:
        resultados.append(
            Resultado("Docker Engine", Estado.PASS, f"running {servidor}")
        )
    return resultados


def checar_contratos(raiz: Path) -> list[Resultado]:
    """Reusa o manifesto e a auditoria do freeze — sem segunda implementação."""
    import contract_freeze

    try:
        celulas = contract_freeze.carregar_manifesto(
            raiz / contract_freeze.MANIFESTO_PADRAO
        )
        contract_freeze.auditar_manifesto(raiz, celulas)
    except ErroDeInstrumentacao as erro:
        return [Resultado.de_erro("Contratos", erro)]

    resultados = [
        Resultado(
            "Contratos",
            Estado.PASS,
            f"manifesto coerente — {len(celulas)} célula(s) declarada(s)",
        )
    ]
    for nome, spec in sorted(celulas.items()):
        if spec.get("freeze") == "required":
            alvo = raiz / spec["frozen"]
            tamanho = alvo.stat().st_size if alvo.is_file() else 0
            resultados.append(
                Resultado(
                    f"  contrato/{nome}", Estado.PASS, f"congelado ({tamanho} bytes)"
                )
            )
        else:
            resultados.append(
                Resultado(
                    f"  contrato/{nome}", Estado.SKIP, spec.get("reason", "")[:70]
                )
            )
    return resultados


def checar_arquivos_fundamentais(raiz: Path) -> Resultado:
    esperados = [
        "CONSTITUICAO.md",
        "INVARIANTES.md",
        "RITOS.md",
        "ci/contract_freeze.py",
        "ci/manifesto-de-contratos.json",
        ".github/workflows/muralhas.yml",
        ".github/workflows/ci-celula.yml",
    ]
    faltando = [a for a in esperados if not (raiz / a).exists()]
    if faltando:
        return Resultado(
            "Arquivos fundamentais",
            Estado.ERROR,
            f"{len(faltando)} ausente(s)",
            "Não encontrados sob a raiz resolvida:\n"
            + "\n".join(f"  - {a}" for a in faltando),
        )
    return Resultado(
        "Arquivos fundamentais", Estado.PASS, f"{len(esperados)}/{len(esperados)}"
    )


# ---------------------------------------------------------------------------


def diagnosticar() -> Relatorio:
    relatorio = Relatorio("SITE DO REINO — ENVIRONMENT DOCTOR")
    relatorio.registrar(checar_python())
    relatorio.registrar(checar_interpretador_canonico())
    relatorio.registrar(checar_git())
    resultado_raiz, raiz = checar_raiz()
    relatorio.registrar(resultado_raiz)
    relatorio.registrar(checar_virtualenv())
    relatorio.registrar(
        checar_modulo(
            "yaml",
            "PyYAML",
            True,
            "O freeze lê o contrato congelado em YAML.",
            "PyYAML",
        )
    )
    relatorio.registrar(
        checar_modulo(
            "pytest", "Pytest", True, "É o motor dos testes-guarda das células."
        )
    )
    relatorio.registrar(
        checar_modulo("black", "Black", True, "É o `lint` do `make ci` de cada célula.")
    )
    relatorio.registrar(
        checar_executavel(
            ["lint-imports", "--help"],
            "Import Linter",
            False,
            "Só services/pagamentos declara .importlinter hoje.",
        )
    )
    relatorio.registrar(
        checar_executavel(
            ["make", "--version"],
            "GNU Make",
            False,
            "Conveniência: `make ci` é fachada de `python ci/ci.py`, que roda sem make.",
        )
    )
    for r in checar_docker():
        relatorio.registrar(r)

    if raiz is not None:
        relatorio.registrar(checar_arquivos_fundamentais(raiz))
        for r in checar_contratos(raiz):
            relatorio.registrar(r)
    return relatorio


def main(argv: list[str] | None = None) -> int:
    configurar_saida()
    parser = argparse.ArgumentParser(description="Environment doctor do Site do Reino")
    parser.add_argument("--breve", action="store_true", help="imprime só o veredito")
    args = parser.parse_args(argv)

    relatorio = diagnosticar()
    veredito = (
        "READY" if relatorio.estado in (Estado.PASS, Estado.SKIP) else "NÃO PRONTO"
    )
    if args.breve:
        print(veredito)
    else:
        print(relatorio.render().replace(f"RESULTADO  {relatorio.estado.value}", ""))
        print(f"RESULTADO\n  {veredito}")
        if veredito != "READY":
            print(
                "\nUma dependência OBRIGATÓRIA não pôde ser validada. Rodar a CI "
                "neste estado\nproduziria resultados em que não se pode confiar."
            )
    return 0 if veredito == "READY" else 2


def _blindar(rotulo: str, funcao):
    """Última linha de defesa: exceção não prevista vira ERROR, nunca FAIL.

    [INV-CI01] Sem isto, um bug NOSSO (um TypeError no meio da checagem)
    derrubava o processo com o exit code 1 do Python — que neste repositório
    significa "violação detectada". Ou seja: "o portão quebrou" chegava
    disfarçado de "o código está errado", mandando quem lê investigar o lugar
    errado. Exceção inesperada é falha de instrumentação: exit 2.
    """

    def blindada(*args, **kwargs):
        try:
            return funcao(*args, **kwargs)
        except SystemExit:
            raise
        except BaseException:  # noqa: BLE001 - a fronteira do processo é aqui
            import traceback

            print("")
            print(f"ERROR {rotulo}: exceção não tratada dentro do próprio portão.")
            print(traceback.format_exc())
            print(
                "A medição NÃO foi concluída. Este resultado NÃO é um PASS "
                "nem um FAIL: nada foi provado sobre o código sob teste."
            )
            return 2

    return blindada


if __name__ == "__main__":
    raise SystemExit(_blindar("doctor", main)())
