"""Lane `traducoes` do orçamento de mudança (PLANO-I18N.md, decisão D9).

O portão `ci/orcamento-de-mudanca.sh` reprova PR com mais de 15 arquivos; a
única válvula era a label `arquitetural`. A lane `traducoes` é a segunda
válvula: um lote de tradução pode exceder o teto SE E SOMENTE SE todo caminho
do diff estiver em `services/<celula>/traducoes/**` e todo arquivo entrar como
dado (regular ou remoção — nada executável, nada symlink).

Como nos demais testes desta suíte, o instrumento roda DE VERDADE: cada teste
monta um repositório git descartável em tmp_path, cria o diff exato do cenário
e executa o script real sob bash. Se alguém afrouxar (ou apertar) o portão,
estes testes ficam vermelhos.

A condição "validadores i18n verdes" da D9 não é testada aqui de propósito:
ela é imposta pelo rito de merge (ci/mergear.py exige todos os checks do PR
verdes), não pelo orçamento.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import BASH

CI = Path(__file__).resolve().parents[1]
SCRIPT = CI / "orcamento-de-mudanca.sh"

PASS = 0
FAIL = 1
ERROR = 2

pytestmark = pytest.mark.skipif(
    BASH is None or shutil.which("git") is None,
    reason="a lane precisa de bash utilizável E git no PATH",
)


def _git(raiz: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(raiz),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, f"git {args} falhou:\n{proc.stderr}"
    return (proc.stdout or "").strip()


@pytest.fixture
def repo_git(tmp_path: Path) -> tuple[Path, str]:
    """Repositório real mínimo: um commit de base para servir de BASE_REF."""
    raiz = tmp_path / "repo-git"
    raiz.mkdir()
    _git(raiz, "init", "-q")
    _git(raiz, "config", "user.email", "ci@teste.local")
    _git(raiz, "config", "user.name", "Suite da lane traducoes")
    _git(raiz, "config", "commit.gpgsign", "false")
    (raiz / "README.md").write_text("base\n", encoding="utf-8")
    # Uma tradução pré-existente, para os cenários de REMOÇÃO terem o que remover.
    antiga = raiz / "services" / "funil" / "traducoes" / "en" / "antiga.yaml"
    antiga.parent.mkdir(parents=True)
    antiga.write_text("chave: antiga\n", encoding="utf-8")
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-q", "-m", "base")
    return raiz, _git(raiz, "rev-parse", "HEAD")


def _comitar(raiz: Path, caminhos: list[str], executaveis: tuple[str, ...] = ()) -> None:
    for rel in caminhos:
        arquivo = raiz / rel
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        arquivo.write_text("chave: valor\n", encoding="utf-8")
    _git(raiz, "add", "-A")
    for rel in executaveis:
        # `--chmod=+x` grava o modo 100755 no índice mesmo no Windows
        # (core.filemode=false) — é assim que um executável entraria de verdade.
        _git(raiz, "update-index", "--chmod=+x", rel)
    _git(raiz, "commit", "-q", "-m", "mudança do cenário")


def _rodar_portao(raiz: Path, base: str, labels: str) -> subprocess.CompletedProcess:
    # Diferente dos testes do gate (env mínimo), aqui o script precisa achar o
    # `git` real dentro do bash — o PATH herdado fica, o resto é controlado.
    env = {**os.environ, "BASE_REF": base, "PR_LABELS": labels}
    return subprocess.run(
        [BASH, str(SCRIPT)],
        cwd=str(raiz),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=120,
        check=False,
    )


def _lote_de_traducao(n: int = 16) -> list[str]:
    """N arquivos de dados espalhados pela árvore de traduções — inclui célula
    diferente e subdiretório fundo, porque a lane promete `**`, não 1 nível."""
    caminhos = [f"services/funil/traducoes/en/pagina_{i}.yaml" for i in range(n - 2)]
    caminhos.append("services/funil/traducoes/pt-br/sub/dir/fundo.yaml")
    caminhos.append("services/quiz/traducoes/es.yaml")
    return caminhos


# ---------------------------------------------------------------------------
# (a) A válvula abre: lote só-traduções acima do teto passa
# ---------------------------------------------------------------------------


def test_lane_aceita_lote_so_traducoes_acima_do_teto(repo_git) -> None:
    raiz, base = repo_git
    _comitar(raiz, _lote_de_traducao(16))
    proc = _rodar_portao(raiz, base, "ci,traducoes")
    assert proc.returncode == PASS, f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    assert "lane traducoes" in proc.stdout


def test_lane_aceita_tambem_remocao_de_traducao(repo_git) -> None:
    """Remover arquivo de tradução (modo 000000 no diff) é lote de tradução
    tanto quanto criar um — a remoção vem da base, então aparece no diff."""
    raiz, base = repo_git
    (raiz / "services/funil/traducoes/en/antiga.yaml").unlink()
    _comitar(raiz, _lote_de_traducao(16))
    proc = _rodar_portao(raiz, base, "traducoes")
    assert proc.returncode == PASS, f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"


# ---------------------------------------------------------------------------
# (b) A válvula NÃO abre com 1 arquivo fora do padrão — e diz qual
# ---------------------------------------------------------------------------

FORA_DO_PADRAO = [
    # (id do cenário, caminho que NÃO pode passar pela lane)
    ("codigo-de-celula", "services/funil/apps/core/views.py"),
    ("fora-de-services", "ci/mergear.py"),
    ("sem-segmento-de-celula", "services/traducoes/en.yaml"),
    ("arquivo-chamado-traducoes", "services/funil/traducoes.yaml"),
    ("prefixo-enganoso", "outra/services/funil/traducoes/en.yaml"),
]


@pytest.mark.parametrize(
    "cenario,violador", FORA_DO_PADRAO, ids=[c[0] for c in FORA_DO_PADRAO]
)
def test_lane_reprova_qualquer_arquivo_fora_do_padrao(
    repo_git, cenario: str, violador: str
) -> None:
    raiz, base = repo_git
    _comitar(raiz, _lote_de_traducao(16) + [violador])
    proc = _rodar_portao(raiz, base, "traducoes")
    assert proc.returncode == FAIL, f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    assert violador in proc.stdout, (
        "a mensagem de FAIL precisa NOMEAR o arquivo que violou o padrão:\n"
        f"{proc.stdout}"
    )


def test_lane_reprova_executavel_mesmo_dentro_da_arvore(repo_git) -> None:
    """D9: 'zero arquivo executável'. Caminho certo + modo 100755 = não é dado."""
    raiz, base = repo_git
    intruso = "services/funil/traducoes/en/gerar.sh"
    _comitar(raiz, _lote_de_traducao(16) + [intruso], executaveis=(intruso,))
    proc = _rodar_portao(raiz, base, "traducoes")
    assert proc.returncode == FAIL, f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    assert intruso in proc.stdout
    assert "100755" in proc.stdout


# ---------------------------------------------------------------------------
# (c) Sem a label, nada muda: >15 reprova como sempre
# ---------------------------------------------------------------------------


def test_sem_label_o_teto_continua_valendo_ate_para_traducoes(repo_git) -> None:
    raiz, base = repo_git
    _comitar(raiz, _lote_de_traducao(16))
    proc = _rodar_portao(raiz, base, "")
    assert proc.returncode == FAIL, f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    assert "arquitetural" in proc.stdout


# ---------------------------------------------------------------------------
# (d) A válvula `arquitetural` continua exatamente como hoje
# ---------------------------------------------------------------------------


def test_valvula_arquitetural_intocada(repo_git) -> None:
    raiz, base = repo_git
    _comitar(raiz, [f"services/funil/apps/modulo_{i}.py" for i in range(17)])
    proc = _rodar_portao(raiz, base, "arquitetural")
    assert proc.returncode == PASS, f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"


def test_traducoes_junto_de_arquitetural_nao_aperta_o_portao(repo_git) -> None:
    """Válvula é concessão: uma label extra jamais pode REPROVAR o que a
    `arquitetural` sozinha aprovaria."""
    raiz, base = repo_git
    _comitar(raiz, [f"services/funil/apps/modulo_{i}.py" for i in range(17)])
    proc = _rodar_portao(raiz, base, "arquitetural,traducoes")
    assert proc.returncode == PASS, f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"


# ---------------------------------------------------------------------------
# Espec. 2: com N ≤ 15 a label `traducoes` não muda NADA (não aperta o portão)
# ---------------------------------------------------------------------------


def test_com_poucos_arquivos_a_label_nao_aperta_o_portao(repo_git) -> None:
    raiz, base = repo_git
    _comitar(raiz, ["services/funil/apps/core/views.py", "ci/qualquer.py"])
    proc = _rodar_portao(raiz, base, "traducoes")
    assert proc.returncode == PASS, f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"


# ---------------------------------------------------------------------------
# Espec. 5: fail-closed preservado — diff incalculável segue ERROR (exit 2)
# ---------------------------------------------------------------------------


def test_diff_incalculavel_continua_error(repo_git) -> None:
    raiz, _ = repo_git
    _comitar(raiz, _lote_de_traducao(16))
    proc = _rodar_portao(raiz, "ref-que-nao-existe", "traducoes")
    assert proc.returncode == ERROR, f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    assert "NÃO foi medido" in proc.stdout
