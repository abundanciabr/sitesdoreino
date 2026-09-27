"""Núcleo dos portões de CI — [INV-CI01] portão crítico é fail-closed.

A regra que este módulo mecaniza é uma só:

    ausência de evidência nunca é evidência de sucesso.

Todo portão construído sobre este núcleo devolve um de quatro estados
semânticos, e nenhum deles pode ser produzido por acidente:

    PASS   a medição rodou e não encontrou violação
    FAIL   a medição rodou e encontrou violação
    ERROR  a medição NÃO pôde ser feita de forma confiável
    SKIP   a medição foi DECLARADA não aplicável (nunca inferida)

O modo de falha que originou este arquivo: `freeze-de-contrato.sh` chamava
`python3`, que nesta máquina não existia; as duas pontas do `diff` viraram
vazio; `diff(vazio, vazio)` deu igualdade; o portão imprimiu "OK". Uma
ferramenta ausente virou um PASS. Aqui isso é estruturalmente impossível:
qualquer coisa que impeça a medição levanta `ErroDeInstrumentacao`, que vira
ERROR, que vira exit code 2.
"""

from __future__ import annotations

import enum
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

# As marcas que provam que um diretório é a raiz DESTE repositório. Resolver a
# raiz sem conferir isso foi a segunda falha da ferida original: sem git, a
# resolução caía para "." e o contrato "não era encontrado" — o que o script
# lia como "nada a checar".
MARCAS_DA_RAIZ = ("CONSTITUICAO.md", "INVARIANTES.md", "ci", "contracts", "services")


class Estado(enum.Enum):
    """Os quatro estados semânticos. A ordem é a de gravidade crescente."""

    PASS = "PASS"
    SKIP = "SKIP"
    FAIL = "FAIL"
    ERROR = "ERROR"

    @property
    def gravidade(self) -> int:
        return {"PASS": 0, "SKIP": 0, "FAIL": 1, "ERROR": 2}[self.value]

    @property
    def exit_code(self) -> int:
        """0 = PASS/SKIP · 1 = violação detectada · 2 = validação impossível.

        A distinção entre 1 e 2 existe para que "o contrato divergiu" nunca
        seja confundido com "a CI não conseguiu comparar contrato nenhum". Os
        dois deixam a CI vermelha; só um deles é culpa do código sob teste.
        """
        return self.gravidade


class ErroDeInstrumentacao(Exception):
    """A validação não pôde ser executada de forma confiável.

    Levantar isto é sempre preferível a devolver um resultado "provavelmente
    ok". Quem captura converte em ERROR — nunca em PASS, nunca em SKIP.
    """

    def __init__(self, resumo: str, detalhe: str = "") -> None:
        super().__init__(resumo)
        self.resumo = resumo
        self.detalhe = detalhe


@dataclass
class Resultado:
    """O veredito de uma checagem, com a evidência que o sustenta."""

    nome: str
    estado: Estado
    resumo: str
    detalhe: str = ""

    @classmethod
    def de_erro(cls, nome: str, erro: ErroDeInstrumentacao) -> Resultado:
        return cls(
            nome=nome, estado=Estado.ERROR, resumo=erro.resumo, detalhe=erro.detalhe
        )


@dataclass
class Relatorio:
    """Coleção de resultados com veredito agregado — o pior estado vence."""

    titulo: str
    resultados: list[Resultado] = field(default_factory=list)

    def registrar(self, resultado: Resultado) -> Resultado:
        self.resultados.append(resultado)
        return resultado

    @property
    def estado(self) -> Estado:
        """ERROR domina FAIL, que domina PASS/SKIP.

        Um relatório VAZIO é ERROR, não PASS: um portão que não mediu nada não
        provou nada. Este é o coração do INV-CI01.
        """
        if not self.resultados:
            return Estado.ERROR
        return max((r.estado for r in self.resultados), key=lambda e: e.gravidade)

    @property
    def exit_code(self) -> int:
        return self.estado.exit_code

    def render(self) -> str:
        largura = max((len(r.nome) for r in self.resultados), default=0)
        linhas = [self.titulo, ""]
        for r in self.resultados:
            linhas.append(f"  {r.nome.ljust(largura)}  {r.estado.value:<5}  {r.resumo}")
        linhas.append("")
        for r in self.resultados:
            if r.detalhe and r.estado in (Estado.FAIL, Estado.ERROR):
                risca = "-" * max(3, 60 - len(r.nome))
                linhas.append(f"--- {r.estado.value} {r.nome} {risca}")
                linhas.append(r.detalhe.rstrip())
                linhas.append("")
        if not self.resultados:
            linhas.append("  (nenhuma checagem foi executada)")
            linhas.append("")
        linhas.append(f"RESULTADO  {self.estado.value}")
        if self.estado is Estado.ERROR:
            linhas.append(
                "A CI NÃO conseguiu completar a medição. "
                "Este resultado NÃO é um PASS."
            )
        return "\n".join(linhas)


# ---------------------------------------------------------------------------
# Resolução de raiz — positiva ou ERROR, nunca "."
# ---------------------------------------------------------------------------


def _tem_marcas(caminho: Path) -> bool:
    return all((caminho / marca).exists() for marca in MARCAS_DA_RAIZ)


def raiz_declarada(caminho: Path) -> Path:
    """Aceita um diretório como raiz SOMENTE se ele exibir as marcas.

    Existe porque `raiz_do_repo` sobe a árvore procurando as marcas — o que é
    certo para descoberta automática e errado para um caminho que alguém
    DECLAROU ser a raiz. Sem esta função, `--raiz /diretorio/vazio` subia até
    encontrar o repositório verdadeiro e media outra coisa em silêncio: o mesmo
    padrão de fallback que este módulo existe para eliminar.
    """
    caminho = caminho.resolve()
    if not caminho.is_dir():
        raise ErroDeInstrumentacao(
            "raiz declarada não existe",
            f"Caminho informado:\n  {caminho}\n\nA medição não foi tentada.",
        )
    faltando = [m for m in MARCAS_DA_RAIZ if not (caminho / m).exists()]
    if faltando:
        raise ErroDeInstrumentacao(
            "raiz declarada não é a raiz do repositório",
            f"Caminho informado:\n  {caminho}\n"
            f"Marcas ausentes: {', '.join(faltando)}\n\n"
            "Subir a árvore para achar outra raiz seria medir um repositório "
            "diferente do que foi pedido.",
        )
    return caminho


def raiz_do_repo(inicio: Path | None = None) -> Path:
    """Devolve a raiz do repositório, PROVADA por marcas em disco.

    Duas vias, ambas verificadas; nenhuma delas é um fallback silencioso:

    1. `git rev-parse --show-toplevel`, cujo resultado ainda precisa exibir as
       MARCAS_DA_RAIZ (git pode apontar para outro repositório que contenha
       este diretório — um worktree aninhado, por exemplo).
    2. Sem git, subida a partir de `inicio` procurando as mesmas marcas.

    Se nenhuma via produzir um diretório com as marcas, isto levanta
    ErroDeInstrumentacao. Nunca devolve "." nem o diretório corrente.
    """
    inicio = (inicio or Path(__file__).resolve().parent).resolve()
    base = inicio if inicio.is_dir() else inicio.parent
    tentativas: list[str] = []

    if shutil.which("git") is not None:
        try:
            saida = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=str(base) if base.is_dir() else None,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
        except OSError as exc:  # git está no PATH mas não executa
            tentativas.append(f"git rev-parse falhou ao executar: {exc}")
        else:
            if saida.returncode == 0 and saida.stdout.strip():
                candidato = Path(saida.stdout.strip()).resolve()
                if _tem_marcas(candidato):
                    return candidato
                tentativas.append(
                    f"git apontou para {candidato}, que não tem as marcas da raiz "
                    f"({', '.join(MARCAS_DA_RAIZ)})"
                )
            else:
                tentativas.append(
                    "git rev-parse --show-toplevel saiu com "
                    f"{saida.returncode}: {saida.stderr.strip() or '(sem stderr)'}"
                )
    else:
        tentativas.append("git não está no PATH")

    for candidato in [base, *base.parents]:
        if _tem_marcas(candidato):
            return candidato
    tentativas.append(
        f"subida por marcas a partir de {base} não encontrou nenhum diretório com "
        f"{', '.join(MARCAS_DA_RAIZ)}"
    )

    raise ErroDeInstrumentacao(
        "raiz do repositório não resolvida",
        "Nenhuma via de resolução produziu uma raiz verificável:\n"
        + "\n".join(f"  - {t}" for t in tentativas)
        + "\n\nSem raiz não há como localizar contracts/ — e não localizar o "
        "contrato NÃO é o mesmo que não haver contrato.",
    )


# ---------------------------------------------------------------------------
# Execução de subprocesso — exit code e stdout vazio são fatos, não detalhes
# ---------------------------------------------------------------------------


@dataclass
class Execucao:
    comando: list[str]
    cwd: Path
    exit_code: int
    stdout: str
    stderr: str

    @property
    def comando_legivel(self) -> str:
        return " ".join(self.comando)


def executar(
    comando: list[str],
    *,
    cwd: Path,
    descricao: str,
    exigir_stdout: bool = False,
    env_extra: dict[str, str] | None = None,
    timeout: int = 300,
) -> Execucao:
    """Roda um subprocesso e transforma QUALQUER anomalia em ERROR.

    Anomalias tratadas, todas ex-fontes de falso positivo:
      - executável inexistente (FileNotFoundError) — a ferida original;
      - exit code != 0;
      - timeout;
      - stdout vazio quando o chamador declarou que precisa de conteúdo.

    Nada aqui usa `|| true`, `2>/dev/null` ou `check=False` silencioso: o
    stderr do processo entra no diagnóstico em vez de ser descartado.
    """
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    # Sem PYTHONUTF8 a saída acentuada do exportador quebra no console cp1252
    # do Windows — e isso apareceria como "o exportador falhou" sem ter falhado.
    env.setdefault("PYTHONUTF8", "1")

    if not cwd.is_dir():
        raise ErroDeInstrumentacao(
            f"{descricao}: diretório de trabalho inexistente",
            f"cwd esperado: {cwd}\nEle não existe. A medição não foi tentada.",
        )

    try:
        proc = subprocess.run(
            comando,
            cwd=str(cwd),
            # Portão nunca espera teclado: stdin fechado por construção. Sem
            # isto, um subprocesso que resolva perguntar algo (ex.: `gh pr
            # merge` com TTY) ficaria travado até o timeout — e com stdin
            # fechado o `gh` nem pergunta, age direto (docs/historico/RESOLVIDAS.md §5.9.1/H6).
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ErroDeInstrumentacao(
            f"{descricao}: comando não encontrado",
            f"Comando:\n  {' '.join(comando)}\ncwd: {cwd}\n\n{exc}\n\n"
            "Ferramenta ausente NÃO é validação bem-sucedida.",
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise ErroDeInstrumentacao(
            f"{descricao}: timeout após {timeout}s",
            f"Comando:\n  {' '.join(comando)}\ncwd: {cwd}\n\n{exc}",
        ) from exc
    except OSError as exc:
        raise ErroDeInstrumentacao(
            f"{descricao}: falha ao executar o subprocesso",
            f"Comando:\n  {' '.join(comando)}\ncwd: {cwd}\n\n{exc}",
        ) from exc

    execucao = Execucao(
        comando=comando,
        cwd=cwd,
        exit_code=proc.returncode,
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
    )

    if proc.returncode != 0:
        raise ErroDeInstrumentacao(
            f"{descricao}: exit code {proc.returncode}",
            diagnostico(execucao),
        )
    if exigir_stdout and not execucao.stdout.strip():
        raise ErroDeInstrumentacao(
            f"{descricao}: stdout vazio com exit code 0",
            diagnostico(execucao)
            + "\nO comando declarou sucesso sem produzir saída. Comparar esse "
            "vazio com qualquer coisa seria medir o nada.",
        )
    return execucao


def diagnostico(execucao: Execucao) -> str:
    """Diagnóstico cru o bastante para outro agente achar a causa sozinho."""
    return (
        f"Comando:\n  {execucao.comando_legivel}\n"
        f"cwd:\n  {execucao.cwd}\n"
        f"Exit code:\n  {execucao.exit_code}\n"
        f"stdout ({len(execucao.stdout)} bytes):\n"
        + recortar(execucao.stdout)
        + f"\nstderr ({len(execucao.stderr)} bytes):\n"
        + recortar(execucao.stderr)
    )


def recortar(texto: str, limite: int = 2000) -> str:
    texto = texto.strip()
    if not texto:
        return "  (vazio)"
    if len(texto) > limite:
        texto = texto[:limite] + f"\n  … (+{len(texto) - limite} bytes)"
    return "\n".join(f"  {linha}" for linha in texto.splitlines())


# ---------------------------------------------------------------------------
# O make do PATH roda as receitas das células? Medido, nunca deduzido.
# ---------------------------------------------------------------------------
#
# `ci/ci.py` (`rodar_celula`) e `ci/sessao.py` (baseline) perguntam a mesma
# coisa antes do `make ci`, e por isso a resposta mora aqui, uma vez só.
# Conferir `make --version` pegava a fachada do Codex (`armadilhas/529`), mas
# não o GNU Make do Windows sem `sh` no PATH: ele roda a receita no cmd.exe, o
# `if [ ... ]` das células quebra no shell e a célula leva a culpa
# (`armadilhas/536`). A sonda roda uma receita com uma linha simples e uma de
# shell POSIX, do mesmo jeito que a porta vai rodar o `make ci`.
#
# Os exit codes que o PRÓPRIO executor inventa quando o comando não chegou a
# rodar (127 ausente, 126 erro de SO, 124 timeout). Só eles significam "não
# foi possível medir"; qualquer outro número veio do programa e é veredito
# dele. Moram aqui porque a sonda, o `make ci` do `ci.py` e o do baseline de
# `sessao.py` leem a mesma tabela.
SENTINELAS_DE_INSTRUMENTACAO = frozenset({124, 126, 127})

MAKEFILE_DA_SONDA = (
    "sonda:\n"
    "\t@echo linha-simples\n"
    "\t@test -n x && echo linha-posix\n"
)

O_QUE_FAZER_COM_O_MAKE = (
    "Nada foi medido e a célula não reprovou: o defeito é do instrumento, não da base.\n"
    "No Windows, deixe o GNU Make na frente do PATH (`winget install ezwinports.make`,\n"
    "que fica em %LOCALAPPDATA%\\Microsoft\\WinGet\\Links) e `C:\\Program Files\\Git\\usr\\bin`\n"
    "no FIM do PATH. Só o GNU Make não basta, e `Git\\bin` no lugar de `Git\\usr\\bin`\n"
    "também não. Fora do Windows, instale o GNU Make e um `sh` POSIX. Depois abra uma\n"
    "janela nova e repita. Veja armadilhas/529 e armadilhas/536."
)


def _correr_a_sonda(comando: list[str]) -> tuple[int, str]:
    """Ausência, erro de SO e timeout viram as sentinelas 127, 126 e 124."""
    try:
        proc = subprocess.run(comando, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=120, check=False)
    except FileNotFoundError as exc:
        return 127, str(exc)
    except subprocess.TimeoutExpired:
        return 124, f"{comando[0]}: timeout após 120s"
    except OSError as exc:
        return 126, str(exc)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def defeito_do_make(
    make: str,
    correr: Callable[[list[str]], tuple[int, str]] = _correr_a_sonda,
    argumentos_do_make: Sequence[str] = (),
) -> tuple[str, str] | None:
    """None se `make` roda receita de shell POSIX; senão (resumo, detalhe) do defeito.

    `correr` devolve (exit, stdout+stderr). `argumentos_do_make` são os mesmos
    que a porta acrescenta ao `make ci` (o baseline passa `SHELL=`), para a
    sonda medir o instrumento do jeito que ele vai ser usado. Sem cache: são
    dois processos curtos por célula, e o `make ci` que vem depois custa minutos.
    """
    with tempfile.TemporaryDirectory(prefix="sonda-do-make-") as pasta:
        Path(pasta, "Makefile").write_text(MAKEFILE_DA_SONDA, encoding="utf-8", newline="\n")
        codigo, saida = correr([make, "-C", pasta, "sonda", *argumentos_do_make])
    linhas = {linha.strip() for linha in saida.splitlines()}
    if codigo == 0 and "linha-posix" in linhas:
        return None
    _, versao = correr([make, "--version"])
    resumo = f"o `make` do PATH não roda as receitas das células: {make}"
    causa = "A receita de prova não imprimiu o que devia; a saída acima mostra onde ela parou."
    if "linha-simples" not in linhas:
        resumo = f"o `make` do PATH é GNU Make, mas não executa nem `echo` numa receita: {make}"
        causa = ("O GNU Make achou um `sh`, mas não as ferramentas POSIX ao lado dele. No\n"
                 "Windows isso é `Git\\bin` no PATH no lugar de `Git\\usr\\bin`.")
    if "linha-simples" in linhas and "linha-posix" not in linhas:
        resumo = f"o `make` do PATH é GNU Make, mas roda as receitas sem shell POSIX: {make}"
        causa = ("O GNU Make rodou a linha simples e quebrou na de shell POSIX: sem `sh` no\n"
                 "PATH, no Windows, ele usa o cmd.exe. Todo Makefile de célula usa shell POSIX\n"
                 "(`if [ ... ]`, `&&`), e o `make ci` quebraria no shell, não no código.")
    if not versao.startswith("GNU Make"):
        resumo = f"o `make` do PATH não é GNU Make: {make}"
        causa = "Um programa chamado `make` que não é o GNU Make não roda o `make ci` das células."
    if codigo in SENTINELAS_DE_INSTRUMENTACAO:
        resumo = f"a sonda do `make` do PATH não chegou a rodar (exit {codigo}): {make}"
        causa = ("O make não abriu ou não terminou a tempo (124 = tempo esgotado, 126 = erro do\n"
                 "sistema, 127 = não encontrado). Com a máquina carregada, espere e repita.")
    comando = subprocess.list2cmdline([make, "-C", "<pasta temporária>", "sonda", *argumentos_do_make])
    detalhe = (
        f"A sonda `{comando}`, com a receita\n{recortar(MAKEFILE_DA_SONDA)}\n"
        f"saiu {codigo}:\n{recortar(saida, 1500)}\n"
        f"`{make} --version` respondeu:\n{recortar(versao, 500)}\n\n"
        f"{causa}\n\n{O_QUE_FAZER_COM_O_MAKE}"
    )
    return resumo, detalhe


def configurar_saida() -> None:
    """UTF-8 na minha saída E na de todo filho meu.

    A primeira metade (reconfigurar `stdout`/`stderr`) é antiga: console cp1252
    do Windows não pode virar "erro".

    A SEGUNDA metade entrou em 04/09/2026 e é a que faltava. Reconfigurar a
    minha saída não diz nada sobre a do meu filho: um `python` filho, no
    Windows, escreve no cano pela codepage do console (cp1252), enquanto todo
    leitor desta casa decodifica utf-8. O `í` de "assíncrona" viaja como
    `\\xed`, chega como `\\ufffd`, e o texto nunca casa com o que o pai procura.

    Medido nesta máquina em 04/09/2026, com o comando abaixo:

        filho escreveu ... b'calcula isso de forma ass\\xedncrona\\r\\n'
        o pai leu ....... 'calcula isso de forma ass\\ufffdncrona\\n'
        a marca casa? ... False        ← e a decisão do pai virou pó

    Foi assim que a remedição do ERROR do portão (`ci/esperar.py`, construída
    em 03/09/2026 porque os PRs #954 e #956 morreram sem ela) nasceu MORTA
    nesta máquina, que é justamente a única onde ela roda: verde na CI (Linux,
    utf-8 por padrão), inerte em casa. Dois testes de `ci/tests/test_espera.py`
    reprovavam aqui e passavam lá — e a `armadilhas/138` já tinha previsto essa
    cegueira por escrito em 27/08/2026, sem que nada fosse construído.

    Por que AQUI, e não em cada chamada de `subprocess`: são 90 fronteiras que
    decodificam texto em `ci/`, e 89 delas não declaravam ambiente nenhum
    (medido em 04/09/2026). Filho herda `os.environ`, então uma linha na porta
    por onde as 33 ferramentas desta casa já passam cobre as 90 de uma vez.
    Remendar chamada por chamada seria a esteira infinita: quem escrevesse a
    de número 91 recomeçaria a doença. `setdefault` porque quem já escolheu o
    próprio ambiente continua mandando nele.

    Não cobre filho que não é Python (`git`, `gh`, `node`) — `PYTHONUTF8` é uma
    chave do interpretador, e dizer o contrário seria garantia sem mecanismo.
    O que cobre é a classe que mordeu: ferramenta desta casa chamando outra.
    """
    os.environ.setdefault("PYTHONUTF8", "1")
    for fluxo in (sys.stdout, sys.stderr):
        reconfigure = getattr(fluxo, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
