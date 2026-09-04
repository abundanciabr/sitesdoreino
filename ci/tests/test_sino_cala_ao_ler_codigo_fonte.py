"""O SINO CALA QUANDO O COMANDO SÓ LÊ CÓDIGO-FONTE, e continua tocando na falha real.

O DEFEITO, MEDIDO (TAR-043 em 30/08/2026; remedido em 04/09/2026 para este PR)
-----------------------------------------------------------------------------
A assinatura de uma armadilha baseada em MENSAGEM aparece, inevitavelmente, no
arquivo que imprime a mensagem, e em teste, registro, workflow e documento que a
citam. Na véspera deste conserto, **43 das 81 armadilhas com sinal casavam texto
benigno do próprio repositório (205 arquivos)**, e um `cat` em qualquer um deles
fazia o sino tocar como se a falha estivesse acontecendo. A sessão principal
viveu isso quatro vezes num dia, uma delas lendo `ci/mergear.py`.

Estreitar o sinal não cura (a TAR-043 mediu que leva à cegueira). O que
distingue é o CONTEXTO: um comando cuja natureza é LER não produz o evento de
uma falha. O conserto é `e_so_leitura()` em `ci/sino_das_armadilhas.py`, e a
régua é FAIL-NOISY: basta um executor em qualquer segmento do encanamento, ou a
leitura de um artefato de saída (`.log`, `tasks/`, `/tmp`), para o sino seguir
acordado.

AS TRÊS PROVAS QUE A TAREFA EXIGE, POR ASSERÇÃO (`armadilhas/195`)
------------------------------------------------------------------
1. leitura de código-fonte com a assinatura  ⇒ SILÊNCIO;
2. falha de verdade com a mesma assinatura   ⇒ TOCA (inclusive filtrada por `grep`);
3. o número: quantos arquivos benignos ainda fazem o sino tocar ao serem lidos.
   A varredura do repositório REAL está em `test_nenhum_arquivo_versionado_toca_ao_ser_lido`.

As provas 1 e 2 usam só `sino.decidir`, de propósito: contra o código antigo, a
prova 1 morre na ASSERÇÃO (`is None` contra um aviso), e não na construção.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

CI = Path(__file__).resolve().parents[1]
if str(CI) not in sys.path:
    sys.path.insert(0, str(CI))

import sino_das_armadilhas as sino  # noqa: E402
from _nucleo import raiz_do_repo  # noqa: E402

RAIZ = raiz_do_repo()

# Uma assinatura REAL da armadilhas/185 (a entrada que tocou quatro vezes em
# 30/08/2026), escolhida porque a frase está LITERALMENTE em `ci/mergear.py`
# (linha `f"{len(devedores)} merge(s) sem registro"`), e a linha de FALHA que ela
# descreve, tal como `ci/mergear.py --conferir` imprime.
SINAL_185 = r"merge\(s\) sem registro"
SAIDA_DE_FALHA = (
    "  dívida do livro       FAIL   2 merge(s) sem registro\n"
    "RESULTADO  FAIL\n"
)
SINAIS = [{
    "armadilha": "185", "arquivo": "armadilhas/185-x.md",
    "titulo": "dívida do livro", "regex": SINAL_185,
}]


def _decidir(comando: str, saida: str, ferramenta: str = "Bash"):
    return sino.decidir({
        "tool_name": ferramenta,
        "tool_input": {"command": comando},
        "tool_response": {"stdout": saida},
    }, SINAIS)


def _codigo_que_imprime_a_mensagem() -> str:
    """O código-fonte REAL que carrega a assinatura: `ci/mergear.py`.

    Se um dia ele deixar de conter a frase, o teste diz isso em vez de passar
    por acaso: a premissa (código-fonte benigno contém a assinatura) é medida.
    """
    texto = (RAIZ / "ci" / "mergear.py").read_text(encoding="utf-8")
    assert re.search(SINAL_185, texto), (
        "ci/mergear.py deixou de conter a assinatura da 185; escolha outro "
        "arquivo-fonte REAL para esta prova em vez de afrouxá-la."
    )
    return texto


# ---------------------------------------------------------------------------
# PROVA 1: LER código-fonte com a assinatura ⇒ silêncio.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("comando", [
    "cat ci/mergear.py",
    "sed -n '1,200p' ci/mergear.py",
    "grep -n 'FAIL' ci/mergear.py",
    "grep -rn \"d[íi]vida do livro\" ci/ | head -20",
    "git show origin/main:ci/mergear.py | sed -n '1,80p'",
    "cd C:/Users/x/wt-ci && head -120 ci/mergear.py; echo ---; tail -40 ci/fila.py",
    "for f in ci/mergear.py ci/fila.py; do echo \"== $f\"; cat $f; done",
    "rg -n 'd[íi]vida do livro' ci/",
    "grep -E \"FAIL|PASS\" ci/mergear.py",
], ids=["cat", "sed-n", "grep", "grep-r-pipe-head", "git-show", "cd-head-tail",
        "for-do-cat", "rg", "grep-alternacao-em-aspas-duplas"])
def test_ler_codigo_fonte_com_a_assinatura_deixa_o_sino_em_silencio(comando: str) -> None:
    assert _decidir(comando, _codigo_que_imprime_a_mensagem()) is None, (
        f"o sino tocou ao LER código-fonte: {comando!r}"
    )


def test_ler_codigo_fonte_pelo_powershell_tambem_cala() -> None:
    comando = "Get-Content ci/mergear.py | Select-String FAIL"
    assert _decidir(comando, _codigo_que_imprime_a_mensagem(), "PowerShell") is None


# ---------------------------------------------------------------------------
# PROVA 2: a FALHA de verdade, com a mesma assinatura ⇒ toca.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("comando", [
    "python ci/mergear.py 963 --conferir",
    "python ci/mergear.py 963 --conferir 2>&1 | grep FAIL",
    "python ci/mergear.py 963 --pousar | tail -20",
    "make ci",
    "cat ci/mergear.py && python ci/mergear.py 963 --conferir",
    "echo \"$(python ci/mergear.py 963 --conferir)\"",
    "cat `python ci/mergear.py 963 --conferir`",
    "timeout 30 python ci/mergear.py 963 --conferir",
    "cd ../wt && bash ci/muralha-do-painel.sh 2>&1 | tail -5",
    "gh run view 123 --log-failed | tail -50",
    "cat <<'EOF' | python -\nimport mergear\nEOF",
    "find . -name '*.py' -exec python {} \\;",
    "xargs python ci/mergear.py",
], ids=["portao", "portao-filtrado-por-grep", "pousar-tail", "make", "cat-e-depois-executa",
        "substituicao-em-aspas-duplas", "crase", "timeout", "bash-script", "gh-run-view",
        "heredoc-para-python", "find-exec", "xargs-python"])
def test_a_falha_real_com_a_mesma_assinatura_faz_o_sino_tocar(comando: str) -> None:
    aviso = _decidir(comando, SAIDA_DE_FALHA)
    assert aviso is not None and "armadilhas/185" in aviso, (
        f"o sino CALOU numa falha real: {comando!r}. Isto é cegueira, e cegueira "
        "não se cura (a TAR-043 mediu)."
    )


@pytest.mark.parametrize("comando", [
    "cat deploy.log",
    "grep FAIL /tmp/saida.log",
    "cat C:\\Users\\x\\AppData\\Local\\Temp\\claude\\proj\\tasks\\abc123.output",
    "tail -50 $TMPDIR/ci_saida",
    "cat ../scratchpad/ci_saida.txt",
    "type saida.out",
], ids=["log", "tmp-log", "tasks-do-harness", "TMPDIR", "scratchpad", "out"])
def test_ler_artefato_de_saida_de_outro_comando_mantem_o_sino_acordado(comando: str) -> None:
    """Um `.log` ou a pasta `tasks/` carregam a falha de um comando REAL que rodou
    em segundo plano, onde o PostToolUse pode não ter passado. Ler isso é o
    momento em que o sino mais serve."""
    aviso = _decidir(comando, SAIDA_DE_FALHA)
    assert aviso is not None, f"o sino calou lendo artefato de saída: {comando!r}"


def test_saida_vazia_e_comando_vazio_continuam_em_silencio() -> None:
    assert _decidir("", SAIDA_DE_FALHA) is not None, "comando vazio não é leitura"
    assert _decidir("cat ci/mergear.py", "") is None


# ---------------------------------------------------------------------------
# PROVA 3: o número, no repositório REAL.
# ---------------------------------------------------------------------------
def _arquivos_versionados_fora_do_catalogo() -> list[Path]:
    saida = subprocess.run(
        ["git", "ls-files"], cwd=RAIZ, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=60,
    ).stdout.split("\n")
    return [RAIZ / a for a in saida if a and not a.startswith("armadilhas/")]


def test_nenhum_arquivo_versionado_toca_ao_ser_lido() -> None:
    """A varredura da TAR-043, agora como guarda.

    Para cada arquivo versionado fora de `armadilhas/` cujo texto casa alguma
    assinatura REAL do catálogo, um `cat` nele tem de deixar o sino em silêncio.
    Também mede e afirma a PREMISSA: existe texto benigno casando assinatura
    (se zerar, a razão de este guarda existir mudou, e alguém deve saber).
    """
    sinais = sino.carregar_sinais()
    compilados = []
    for s in sinais:
        try:
            compilados.append(re.compile(s["regex"]))
        except re.error:
            continue
    benignos: list[Path] = []
    for arquivo in _arquivos_versionados_fora_do_catalogo():
        try:
            texto = arquivo.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if any(rx.search(texto) for rx in compilados):
            benignos.append(arquivo)
    assert len(benignos) >= 10, (
        f"só {len(benignos)} arquivo(s) benigno(s) carregam assinatura; a premissa "
        "deste guarda (43 armadilhas em 205 arquivos, 04/09/2026) mudou. Meça de novo."
    )
    tocaram = []
    for arquivo in benignos:
        relativo = arquivo.relative_to(RAIZ).as_posix()
        texto = arquivo.read_text(encoding="utf-8")
        for comando in (f"cat {relativo}", f"sed -n '1,200p' {relativo}",
                        f"grep -n FAIL {relativo}", f"git show origin/main:{relativo}"):
            if sino.decidir({
                "tool_name": "Bash", "tool_input": {"command": comando},
                "tool_response": {"stdout": texto},
            }, sinais):
                tocaram.append(comando)
                break
    assert not tocaram, (
        f"{len(tocaram)} de {len(benignos)} leitura(s) de arquivo benigno ainda "
        f"tocam o sino:\n  " + "\n  ".join(tocaram[:20])
    )


# ---------------------------------------------------------------------------
# A régua em si, caso a caso (para a mutação ter onde morder).
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("comando, esperado", [
    ("cat ci/mergear.py", True),
    ("PYTHONUTF8=1 cat x.py", True),
    ("[ -f x ] && cat x", True),
    ("if grep -q x f; then echo sim; else echo nao; fi", True),
    ("awk '/x/{print}' file", True),
    ("find . -name '*.py' | xargs grep -l FAIL", True),
    ("git diff --stat origin/main...HEAD", True),
    ("git log --oneline -5", True),
    ("ls -la ci/tests", True),
    ("export PYTHONUTF8=1 && grep -n x ci/y.py | cut -c1-100", True),
    ("git fetch origin && git worktree add ../x -b y origin/main", False),
    ("node painel/gerar_manifesto.js | tail -2", False),
    ("docker compose logs api | grep -i error", False),
    ("curl -sI https://meshcraft.top/admin/", False),
    ("pytest ci/tests -q | tail -3", False),
    ("gh pr view 963 --json state", False),
    ("sed -i 's/a/b/' f && python -m pytest", False),
    ("python ci/x.py; Get-Content log.txt", False),
    ("cat ci/x.py | python -c \"import sys\"", False),
    ("python - <<'EOF'\nprint(1)\nEOF", False),
    ("", False),
])
def test_e_so_leitura_caso_a_caso(comando: str, esperado: bool) -> None:
    assert sino.e_so_leitura(comando) is esperado, repr(comando)


def test_o_corpo_do_heredoc_e_texto_mas_a_linha_de_abertura_e_comando() -> None:
    """`cat > x.sh <<'EOF' … python … EOF` só ESCREVE (o `python` do corpo é texto);
    `cat <<'EOF' | python -` EXECUTA (o `python` está na linha de abertura)."""
    assert sino.e_so_leitura("cat > x.sh <<'EOF'\npython ci/x.py | grep FAIL\nEOF\n") is True
    assert sino.e_so_leitura("cat <<'EOF' | python -\nimport x\nEOF\n") is False


def test_a_lista_de_leitores_nao_tem_executor() -> None:
    """A régua só funciona enquanto nenhum executor entrar na lista por engano."""
    executores = {"python", "python3", "node", "make", "bash", "sh", "pwsh", "powershell",
                  "docker", "gh", "curl", "pytest", "npm", "npx", "pip", "ruff", "mypy",
                  "django-admin", "manage.py", "psql", "ssh", "scp", "git"}
    assert not (executores & sino.LEITORES), executores & sino.LEITORES
    assert not ({"fetch", "push", "pull", "commit", "merge", "rebase", "checkout",
                 "switch", "worktree", "add", "reset", "stash"} & sino.LEITORES_DO_GIT)
