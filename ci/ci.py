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

import contract_freeze
import mapa_de_celulas  # noqa: E402
import guarda_dos_guardas  # noqa: E402
from _nucleo import (  # noqa: E402
    ErroDeInstrumentacao,
    Estado,
    Relatorio,
    Resultado,
    configurar_saida,
    executar,
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
        "contrato só muda com rito (RITOS.md §3) — a cerca de largura caiu na Onda 5",
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
    PortaoDeShell(
        "muralha-do-painel",
        "ci/muralha-do-painel.sh",
        "o livro de ocorrências (painel/) inválido ou com manifesto desatualizado",
    ),
    PortaoDeShell(
        "mapa-de-celulas",
        "ci/mapa-de-celulas.sh",
        "celulas.yml discorda do código (dependência escondida ou declaração órfã)",
    ),
    PortaoDeShell(
        "mapa-do-site",
        "ci/mapa-do-site.sh",
        "painel/mapa-do-site.json discorda do roteamento (endereço novo fora do "
        "mapa do dono, ou linha sobrando)",
    ),
    PortaoDeShell(
        "contrato-aditivo",
        "ci/contrato-aditivo.sh",
        "a mudança de contrato REMOVE algo sem a etiqueta 'contrato-remocao'",
    ),
    PortaoDeShell(
        "leis-sem-mecanismo",
        "ci/leis-sem-mecanismo.sh",
        "lei sem quem a faça valer e fora da dívida declarada (Onda 6, B10)",
    ),
    PortaoDeShell(
        "catraca-de-testes",
        "ci/catraca-de-testes.sh",
        "teste apagado, reduzido ou desligado sem a etiqueta 'remove-teste'",
    ),
    PortaoDeShell(
        "muralha-da-fila",
        "ci/muralha-da-fila.sh",
        "a fila de trabalho (fila/) inválida — tarefa/evento fora do molde",
    ),
    PortaoDeShell(
        "muralha-do-travessao",
        "ci/muralha-do-travessao.sh",
        "travessão em texto que vai ser publicado online (decisão de 30/08/2026)",
    ),
    PortaoDeShell(
        "muralha-das-reservas",
        "ci/muralha-das-reservas.sh",
        "armadilha nova com número escolhido à mão em vez de pedido ao almoxarife",
    ),
    PortaoDeShell(
        "muralha-do-indice",
        "ci/muralha-do-indice.sh",
        "os gerados de armadilhas/ (INDICE.md, GUARDAS.json, SINAIS.json) não "
        "constroem, não reconstroem iguais, ou voltaram ao índice do Git",
    ),
]


def rodar_freeze(raiz: Path) -> list[Resultado]:
    """Reusa contract_freeze — uma única fonte de verdade para o freeze."""
    return contract_freeze.rodar(raiz=raiz).resultados


def rodar_guardas(raiz: Path) -> list[Resultado]:
    """O portão que prova que os OUTROS guardas continuam existindo e mordendo.

    Ele também roda dentro do `testador` (há um teste em `ci/tests/` que chama
    a mesma função contra o repositório real), e é por lá que ele chega aos
    workflows `muralhas` e `alarme-main` sem uma linha de YAML nova. Aqui ele é
    portão de primeira classe para que a saída local diga o nome dele.
    """
    return guarda_dos_guardas.rodar(raiz=raiz).resultados


def _em_paralelo() -> list[str]:
    """`-n auto` quando o pytest-xdist existe; nada quando não existe.

    Medido em 04/09/2026, nesta suíte de 1685 testes, numa máquina Windows:

        em série ...................... 8min55s
        4 processos (= runner do CI) .. 3min31s
        12 processos (a máquina toda) . 3min07s

    O que a suíte faz o tempo todo é ABRIR OUTROS PROGRAMAS — 119 fronteiras de
    subprocesso, e os doze testes mais lentos gastam de 10 a 24 segundos cada um
    só nisso. Criar processo no Windows custa perto de dez vezes o que custa no
    Linux, e é daí que vinham os 9 minutos: não de "o Windows é lento", mas de
    esperar processo em fila indiana. Passar de 4 para 12 rende pouco porque o
    piso passa a ser o teste mais lento, que não se divide.

    Isto não é enfeite de velocidade: sem ele, o job `windows-a-maquina-dos-robos`
    (que existe porque nenhum outro job desta casa roda no sistema onde os robôs
    trabalham) fazia a espera de TODO PR pular de ~1min36s para ~10min. Desde
    05/09/2026 esse job mora em `.github/workflows/rede-do-windows.yml` e roda
    na `main`, fora do caminho do PR; o paralelo continua valendo lá e na
    máquina de todo agente.

    CONDICIONAL de propósito: quem não tiver o xdist instalado continua rodando
    em série, mais devagar e igualmente correto. Um portão que passa a EXIGIR
    uma dependência nova quebra a máquina de quem só fez `git pull` — e portão
    que não roda não protege ninguém.
    """
    try:
        import xdist  # noqa: F401
    except ImportError:
        return []
    return ["-n", "auto"]


def rodar_testes_do_testador(raiz: Path) -> Resultado:
    """A suíte que prova que o próprio instrumento de medição funciona."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", str(raiz / "ci" / "tests"), "-q",
         *_em_paralelo()],
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


# Os exit codes que o PRÓPRIO executor inventa quando o comando não chegou a
# rodar (ausente, erro de SO, timeout). Só eles significam "não foi possível
# medir" — qualquer outro número veio do programa e é veredito dele.
#
# Este conjunto é DELIBERADAMENTE igual ao de `ci/sessao.py`, que encapsula o
# mesmo `make ci` para o baseline de sessão. Duplicação consciente é aceitável;
# duplicação sem guarda é armadilha com data marcada — por isso
# `ci/tests/test_exit_do_make.py` lê os DOIS arquivos e reprova se as cópias
# divergirem.
SENTINELAS_DE_INSTRUMENTACAO = frozenset({124, 126, 127})


def classificar_exit_do_make(codigo: int) -> Estado:
    """FAIL ou ERROR para o exit de um `make` cujo alvo JÁ se provou planejável.

    O GNU Make **não** repassa o exit da receita: devolve **2** para toda receita
    que falhou (`black --check` sai 1, o make imprime `Error 1` e sai com 2) — e
    **2** também para alvo inexistente. A tabela antiga daqui era a do `_nucleo`
    (`1 = FAIL, resto = ERROR`), certa para os portões escritos em Python e
    errada para o make: como ele quase nunca devolve 1, TODA reprovação de célula
    (lint, mypy, pytest, contrato) chegava classificada como ERROR — mandando
    quem lê investigar o instrumento quando o que reprovou foi o código. É o
    §5.6 ao contrário: em vez de um verde que não mediu, um "não medi" que mediu
    e reprovou (`armadilhas/107`).

    A ambiguidade do 2 ("receita reprovou" × "não há regra para o alvo") NÃO se
    resolve lendo a mensagem do make — ela é traduzível pelo locale, e um portão
    que depende do idioma do runner é um portão com data para quebrar. Resolve-se
    ANTES, em `rodar_celula`: um ensaio (`make -n`) prova que o alvo existe e é
    planejável. Provado isso, um 2 só pode ser reprovação.
    """
    if codigo in SENTINELAS_DE_INSTRUMENTACAO:
        return Estado.ERROR
    return Estado.FAIL


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
    if not (destino / "Makefile").is_file():
        return Resultado(
            f"celula/{celula}",
            Estado.ERROR,
            "a célula não tem Makefile",
            f"Esperado em:\n  {destino / 'Makefile'}\n\n"
            "A Definição de Pronto da célula mora no `make ci` dela. Portão\n"
            "ausente não é portão satisfeito.",
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

    def _correr(argumentos: list[str], limite: int) -> subprocess.CompletedProcess | int:
        """Roda o make; devolve o processo, ou 124 se estourou o tempo.

        `subprocess.run(timeout=...)` LEVANTA em vez de devolver um código —
        deixar a exceção subir derrubaria o runner inteiro com traceback, que é
        o oposto de fail-closed legível. 124 é a sentinela de timeout, a mesma
        que `ci/sessao.py` usa.
        """
        try:
            return subprocess.run(
                [make, "-C", str(destino), *argumentos],
                cwd=str(raiz),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=limite,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return 124

    # ENSAIO: `make -n ci` planeja sem executar. Ele existe para desambiguar o
    # exit 2 do make — se o alvo `ci` não existe, ou o Makefile não é analisável,
    # é AQUI que se descobre, e isso é ERROR de verdade. Nenhum Makefile de
    # célula recorre com `$(MAKE)`, então o ensaio não dispara trabalho real.
    ensaio = _correr(["-n", "ci"], 120)
    if isinstance(ensaio, int) or ensaio.returncode != 0:
        codigo = ensaio if isinstance(ensaio, int) else ensaio.returncode
        detalhe = "" if isinstance(ensaio, int) else (ensaio.stdout or "") + (
            ensaio.stderr or ""
        )
        return Resultado(
            f"celula/{celula}",
            Estado.ERROR,
            f"o alvo `ci` da célula não é sequer planejável (make -n saiu {codigo})",
            f"Comando:\n  {make} -C {destino} -n ci\n\n"
            + recortar(detalhe, 4000)
            + "\n\nIsto NÃO é uma reprovação da célula: o `make ci` não chegou a\n"
            "rodar. Alvo ausente, Makefile ilegível ou make quebrado.",
        )

    proc = _correr(["ci"], 1800)
    if isinstance(proc, int):
        return Resultado(
            f"celula/{celula}",
            Estado.ERROR,
            "o `make ci` da célula estourou o tempo (30 min)",
            f"Comando:\n  {make} -C {destino} ci\n\n"
            "Nada foi provado sobre o código — este resultado NÃO é um FAIL.",
        )
    saida = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode == 0:
        return Resultado(f"celula/{celula}", Estado.PASS, "make ci verde")
    estado = classificar_exit_do_make(proc.returncode)
    if estado is Estado.ERROR:
        return Resultado(
            f"celula/{celula}",
            Estado.ERROR,
            f"o `make ci` da célula não chegou a rodar (exit {proc.returncode})",
            recortar(saida, 4000)
            + "\n\nNada foi provado sobre o código — este resultado NÃO é um FAIL.",
        )
    return Resultado(
        f"celula/{celula}",
        Estado.FAIL,
        f"make ci reprovou (exit {proc.returncode})",
        recortar(saida, 4000),
    )


def celulas_tocadas(raiz: Path, base: str) -> list[str]:
    """Quais células o diff contra `base` toca. Falha do git é ERROR, não lista vazia.

    Esta é a MEDIÇÃO que decide o escopo da CI da célula e a matriz do deploy.
    O workflow calculava isso em YAML com `... | head -1 || true`: o `|| true`
    cobria o pipeline inteiro, então um `git diff` que falhasse devolvia string
    vazia — indistinguível de "nenhuma célula foi tocada". Daí o job da célula
    era pulado e o gate aceitava `skipped` como verde: merge liberado sem que um
    único teste tivesse rodado. Aqui as duas situações são separadas na origem.

    **Quem responde "este arquivo é de quem" é `celulas.yml`** (Onda 5). Até
    28/08/2026 o mapa morava dentro desta função E dentro de
    `ci/cerca-de-celula.sh`, e os dois já discordavam: aqui `painel/` contava
    como a célula `admin`, lá não. A divergência estava escrita num comentário,
    isto é, era conhecida e tolerada. Agora existe um mapa só, e um varredor que
    o impede de mentir (`ci/mapa_de_celulas.py`).
    """
    execucao = executar(
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        cwd=raiz,
        descricao=f"detectar células tocadas contra '{base}'",
        # Diff vazio é resposta legítima ("nada mudou"), não instrumento quebrado
        # — o que não pode passar é exit != 0, e disso `executar` já cuida.
        exigir_stdout=False,
    )
    arquivos = [ln.strip() for ln in execucao.stdout.splitlines() if ln.strip()]
    mapa = mapa_de_celulas.carregar(raiz)
    return mapa_de_celulas.celulas_do_diff(arquivos, mapa)


PORTOES = ("freeze", "muralhas", "guardas", "testador")


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
    if "guardas" in escolhidos:
        for r in rodar_guardas(raiz):
            relatorio.registrar(r)
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
    parser.add_argument(
        "--detectar-celulas",
        action="store_true",
        help="imprime em stdout, uma por linha, as células tocadas pelo diff contra --base",
    )
    parser.add_argument(
        "--base", default=None, help="ref base do diff (ex.: origin/main, HEAD^)"
    )
    args = parser.parse_args(argv)

    if args.detectar_celulas:
        # Modo máquina: stdout carrega SÓ os nomes das células (o workflow lê
        # daqui). Diagnóstico vai para stderr para não contaminar a leitura.
        if not args.base:
            print("ERROR: --detectar-celulas exige --base <ref>", file=sys.stderr)
            return 2
        try:
            raiz = raiz_do_repo()
            for nome in celulas_tocadas(raiz, args.base):
                print(nome)
        except ErroDeInstrumentacao as erro:
            print(f"ERROR {erro.resumo}\n{erro.detalhe}", file=sys.stderr)
            print(
                "\nA detecção de escopo NÃO concluiu. Tratar isto como 'nenhuma "
                "célula tocada' seria aprovar sem saber o que deveria testar.",
                file=sys.stderr,
            )
            return 2
        return 0

    if args.listar:
        print("Portões disponíveis:")
        print(
            "  freeze     — contrato vivo × contrato congelado (ci/contract_freeze.py)"
        )
        print(
            "  muralhas   — cerca de célula, orçamento de mudança, guarda de "
            "segredos, muralha do painel"
        )
        print(
            "  guardas    — INVARIANTES.md × disco: todo teste-guarda existe e ainda "
            "morde (ci/guarda_dos_guardas.py)"
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
    raise SystemExit(_blindar("ci", main)())
