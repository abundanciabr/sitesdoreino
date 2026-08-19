"""RUNNER CANÔNICO DA CI LOCAL — a implementação, não a fachada.

              ci/ci.py
                 ▲
           ┌─────┼─────┐
           │     │     │
       Makefile  CI   Agentes

`make ci` na raiz delega para cá. Se `make` não existir numa máquina, o caminho
oficial continua existindo:

    python ci/ci.py

Separação semântica com o doctor:

    doctor  ->  "o ambiente consegue executar o trabalho?"
    ci      ->  "a mudança respeita as invariantes?"

Uso:

    python ci/ci.py                     # todos os portões de repositório
    python ci/ci.py --celula pagamentos # + lint/type/test daquela célula
    python ci/ci.py --apenas freeze     # um portão só
    python ci/ci.py --listar            # que portões existem

Exit codes: 0 = PASS/SKIP · 1 = invariante violada · 2 = não foi possível medir.

[INV-CI01] Este runner é fail-closed em duas camadas: cada portão devolve o
próprio estado semântico, e um portão que não conseguiu rodar contamina o
agregado como ERROR. Não existe caminho em que "não consegui medir" chegue ao
fim como sucesso — inclusive o caso degenerado de nenhum portão ter rodado,
que `Relatorio` já trata como ERROR.

Este runner é READ-ONLY: não formata código, não regenera contrato, não
conserta nada para ficar verde.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import contract_freeze  # noqa: E402
from _nucleo import (  # noqa: E402
    ErroDeInstrumentacao,
    Estado,
    Relatorio,
    Resultado,
    configurar_saida,
    raiz_do_repo,
    recortar,
)


def _bash() -> str:
    """Um bash que PROVADAMENTE roda — sondado, não apenas encontrado.

    No Windows, `shutil.which("bash")` acha primeiro o stub do WSL em System32,
    que estoura `execvpe(/bin/bash) failed` ao rodar script do Git Bash.
    Procurar sem sondar seria a mesma classe de erro que este repositório está
    fechando: aceitar a aparência da ferramenta como prova de que ela funciona.
    """
    candidatos = [
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files (x86)\Git\bin\bash.exe",
        "/usr/bin/bash",
        "/bin/bash",
    ]
    encontrado = shutil.which("bash")
    if encontrado:
        candidatos.append(encontrado)
    for candidato in candidatos:
        if not Path(candidato).exists():
            continue
        try:
            proc = subprocess.run(
                [candidato, "-c", "printf sondagem-ok"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                check=False,
            )
        except OSError:
            continue
        if proc.returncode == 0 and "sondagem-ok" in (proc.stdout or ""):
            return candidato
    raise ErroDeInstrumentacao(
        "nenhum bash utilizável encontrado",
        "Candidatos sondados:\n"
        + "\n".join(f"  - {c}" for c in candidatos)
        + "\n\nOs portões de muralha são scripts de shell. Sem bash eles não rodam — "
        "e não rodar não é passar.",
    )


@dataclass
class PortaoDeShell:
    """Um dos scripts de muralha, com a semântica de exit code declarada.

    0 = OK, 1 = violação (FAIL), qualquer outra coisa = ERROR. É esse contrato
    que faz `exit 2` dos scripts corrigidos chegar aqui como ERROR em vez de
    ser confundido com uma reprovação comum.
    """

    nome: str
    script: str
    descricao: str

    def rodar(self, raiz: Path) -> Resultado:
        try:
            bash = _bash()
        except ErroDeInstrumentacao as erro:
            return Resultado.de_erro(self.nome, erro)

        caminho = raiz / self.script
        if not caminho.is_file():
            return Resultado(
                self.nome,
                Estado.ERROR,
                "script do portão não encontrado",
                f"Esperado em:\n  {caminho}\n\nPortão ausente não é portão satisfeito.",
            )
        proc = subprocess.run(
            [bash, str(caminho)],
            cwd=str(raiz),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
            check=False,
        )
        saida = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode == 0:
            ultima = [ln for ln in (proc.stdout or "").splitlines() if ln.strip()]
            return Resultado(
                self.nome, Estado.PASS, ultima[-1].strip() if ultima else "ok"
            )
        if proc.returncode == 1:
            return Resultado(self.nome, Estado.FAIL, self.descricao, saida.strip())
        return Resultado(
            self.nome,
            Estado.ERROR,
            f"o portão não conseguiu rodar (exit {proc.returncode})",
            f"Comando:\n  {bash} {caminho}\nExit code:\n  {proc.returncode}\n"
            f"Saída:\n{recortar(saida)}",
        )


MURALHAS = [
    PortaoDeShell(
        "cerca-de-celula",
        "ci/cerca-de-celula.sh",
        "1 PR = 1 célula; contrato só muda com rito (RITOS.md §1 e §3)",
    ),
    PortaoDeShell(
        "orcamento-de-mudanca",
        "ci/orcamento-de-mudanca.sh",
        "escopo estourou o orçamento de arquivos sem label 'arquitetural'",
    ),
    PortaoDeShell(
        "guarda-de-segredos",
        "ci/guarda-de-segredos.sh",
        "segredo de produção alcançável do repositório (INV-P8)",
    ),
]


def rodar_freeze(raiz: Path) -> list[Resultado]:
    """Reusa contract_freeze — uma única fonte de verdade para o freeze."""
    return contract_freeze.rodar(raiz=raiz).resultados


def rodar_testes_do_testador(raiz: Path) -> Resultado:
    """A suíte que prova que o próprio instrumento de medição funciona."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", str(raiz / "ci" / "tests"), "-q"],
        cwd=str(raiz),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=900,
        check=False,
    )
    saida = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode == 0:
        ultima = [ln for ln in (proc.stdout or "").splitlines() if ln.strip()]
        return Resultado(
            "testar-o-testador", Estado.PASS, ultima[-1].strip() if ultima else "ok"
        )
    if proc.returncode == 1:
        return Resultado(
            "testar-o-testador",
            Estado.FAIL,
            "a suíte adversarial do próprio portão reprovou",
            recortar(saida, 4000),
        )
    return Resultado(
        "testar-o-testador",
        Estado.ERROR,
        f"pytest não conseguiu rodar (exit {proc.returncode})",
        recortar(saida, 4000),
    )


def rodar_celula(raiz: Path, celula: str) -> Resultado:
    """Delega o `make ci` da célula — sem reimplementar lint/type/test aqui."""
    destino = raiz / "services" / celula
    if not destino.is_dir():
        return Resultado(
            f"celula/{celula}",
            Estado.ERROR,
            "célula inexistente",
            f"Esperada em:\n  {destino}",
        )
    make = shutil.which("make")
    if make is None:
        return Resultado(
            f"celula/{celula}",
            Estado.ERROR,
            "GNU Make ausente — a CI da célula ainda depende dele",
            "O `make ci` de cada célula encadeia lint/type/test/contrato-check.\n"
            "Enquanto essa camada não for portada, rodar a CI de UMA célula exige make.\n"
            "Os portões de repositório (`python ci/ci.py --apenas freeze,muralhas`)\n"
            "continuam disponíveis sem make.",
        )
    proc = subprocess.run(
        [make, "-C", str(destino), "ci"],
        cwd=str(raiz),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=1800,
        check=False,
    )
    saida = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode == 0:
        return Resultado(f"celula/{celula}", Estado.PASS, "make ci verde")
    if proc.returncode == 1:
        return Resultado(
            f"celula/{celula}", Estado.FAIL, "make ci reprovou", recortar(saida, 4000)
        )
    return Resultado(
        f"celula/{celula}",
        Estado.ERROR,
        f"make ci não conseguiu rodar (exit {proc.returncode})",
        recortar(saida, 4000),
    )


PORTOES = ("freeze", "muralhas", "testador")


def rodar(apenas: list[str] | None = None, celula: str | None = None) -> Relatorio:
    relatorio = Relatorio("SITE DO REINO — CI LOCAL (runner canônico)")
    escolhidos = apenas or list(PORTOES)

    try:
        raiz = raiz_do_repo()
    except ErroDeInstrumentacao as erro:
        relatorio.registrar(Resultado.de_erro("repositorio", erro))
        return relatorio

    desconhecidos = [p for p in escolhidos if p not in PORTOES]
    if desconhecidos:
        relatorio.registrar(
            Resultado(
                "selecao",
                Estado.ERROR,
                f"portão desconhecido: {', '.join(desconhecidos)}",
                f"Disponíveis: {', '.join(PORTOES)}",
            )
        )
        return relatorio

    if "freeze" in escolhidos:
        for r in rodar_freeze(raiz):
            relatorio.registrar(r)
    if "muralhas" in escolhidos:
        for portao in MURALHAS:
            relatorio.registrar(portao.rodar(raiz))
    if "testador" in escolhidos:
        relatorio.registrar(rodar_testes_do_testador(raiz))
    if celula:
        relatorio.registrar(rodar_celula(raiz, celula))
    return relatorio


def main(argv: list[str] | None = None) -> int:
    configurar_saida()
    parser = argparse.ArgumentParser(
        description="Runner canônico da CI local — fail-closed [INV-CI01]"
    )
    parser.add_argument(
        "--apenas",
        default="",
        help=f"portões separados por vírgula ({', '.join(PORTOES)})",
    )
    parser.add_argument(
        "--celula", default=None, help="também roda o `make ci` da célula"
    )
    parser.add_argument("--listar", action="store_true", help="lista os portões e sai")
    args = parser.parse_args(argv)

    if args.listar:
        print("Portões disponíveis:")
        print(
            "  freeze     — contrato vivo × contrato congelado (ci/contract_freeze.py)"
        )
        print(
            "  muralhas   — cerca de célula, orçamento de mudança, guarda de segredos"
        )
        print(
            "  testador   — a suíte adversarial que prova que o freeze falha quando deve"
        )
        print("\nAlém deles: --celula <nome> encadeia o `make ci` daquela célula.")
        return 0

    apenas = [p.strip() for p in args.apenas.split(",") if p.strip()] or None
    relatorio = rodar(apenas=apenas, celula=args.celula)
    print(relatorio.render())
    return relatorio.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
