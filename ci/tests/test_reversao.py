"""A REVERSÃO AUTOMÁTICA, provada nos três estados (INV-CI01).

O que este arquivo guarda não é "o script roda": é que ele **prefere não
reverter a reverter para o lugar errado**. Uma reversão que escolhe mal troca
uma célula doente por uma célula parada — e faz isso sozinha, de madrugada,
sem ninguém para conferir. Por isso cada cenário aqui é uma pergunta sobre o
que ele faz quando NÃO sabe:

    registry mudo            -> ERROR, nunca "não existe"
    nenhuma imagem na janela -> FAIL, e sem plano publicado
    célula fora do manifesto -> FAIL antes de qualquer consulta

O registry é falsificado por um script de mentira (a costura `REVERSAO_DOCKER`,
igual à do `ci/rollback.py`): a resposta "essa tag não existe" e a resposta "não
consegui perguntar" são estados que não se produzem sob encomenda contra o
registry de verdade — e são justamente os dois que decidem se este portão presta.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[2]
DEPLOY = RAIZ / ".github" / "workflows" / "deploy-celula.yml"
MARCAS_DA_RAIZ = ("CONSTITUICAO.md", "INVARIANTES.md", "contracts")

pytestmark = pytest.mark.skipif(
    not (RAIZ / "ci" / "reversao.py").is_file(), reason="ci/reversao.py ausente"
)


def _git(raiz: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=str(raiz), check=True, capture_output=True, timeout=120
    )


def _repo_falso(tmp_path: Path, entregas: int = 3) -> tuple[Path, list[str]]:
    """Um repositório de verdade com N entregas que tocam `services/quiz`.

    Precisa ser Git de verdade: a busca por entregas anteriores é `git rev-list
    --first-parent -- <caminhos>`, e é exatamente esse comportamento (só os
    commits que tocaram a célula) que o portão promete.
    """
    raiz = tmp_path / "repo"
    (raiz / "ci").mkdir(parents=True)
    (raiz / "services" / "quiz").mkdir(parents=True)
    (raiz / "contracts").mkdir()
    for marca in MARCAS_DA_RAIZ:
        alvo = raiz / marca
        if not alvo.exists() and marca.endswith(".md"):
            alvo.write_text("cenário de teste\n", encoding="utf-8")
    (raiz / "ci" / "manifesto-de-contratos.json").write_text(
        '{"celulas": {"quiz": {"freeze": "not-applicable", "reason": "cenário"},'
        ' "admin": {"freeze": "not-applicable", "reason": "cenário"}}}',
        encoding="utf-8",
    )

    _git(raiz, "init", "-q", "-b", "main")
    _git(raiz, "config", "user.email", "teste@exemplo")
    _git(raiz, "config", "user.name", "teste")
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-q", "-m", "base")

    shas: list[str] = []
    for n in range(entregas):
        (raiz / "services" / "quiz" / "app.py").write_text(
            f"versao = {n}\n", encoding="utf-8"
        )
        _git(raiz, "add", "-A")
        _git(raiz, "commit", "-q", "-m", f"entrega {n}")
        shas.append(
            subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(raiz),
                check=True,
                capture_output=True,
                text=True,
                timeout=60,
            ).stdout.strip()
        )
    return raiz, shas


def _docker_de_mentira(tmp_path: Path, conhece: list[str], modo: str = "ausente") -> str:
    """Um `docker` falso: 0 para as tags que conhece, e o resto conforme `modo`.

    `modo="ausente"` imita o registry dizendo "manifest unknown" (a tag não
    existe). `modo="mudo"` imita qualquer OUTRA falha — rede, login expirado —,
    que é o caso em que este portão tem de dizer ERROR em vez de seguir
    procurando um alvo mais velho.
    """
    script = tmp_path / f"docker_falso_{modo}.py"
    script.write_text(
        "import sys\n"
        f"CONHECE = {conhece!r}\n"
        f"MODO = {modo!r}\n"
        "alvo = sys.argv[-1]\n"
        "if any(alvo.endswith(':' + t) for t in CONHECE):\n"
        "    print('{\"schemaVersion\": 2}')\n"
        "    sys.exit(0)\n"
        "if MODO == 'ausente':\n"
        "    sys.stderr.write('manifest unknown: manifest unknown\\n')\n"
        "else:\n"
        "    sys.stderr.write('dial tcp: lookup ghcr.io: no such host\\n')\n"
        "sys.exit(1)\n",
        encoding="utf-8",
    )
    import json

    return json.dumps([sys.executable, str(script)])


def _roda(raiz: Path, **env_extra: str) -> subprocess.CompletedProcess[str]:
    import os

    env = dict(os.environ)
    env["REVERSAO_RAIZ"] = str(raiz)
    env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(RAIZ / "ci" / "reversao.py")],
        cwd=str(raiz),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        env=env,
        check=False,
    )


# --------------------------------------------------------------------------
# O caminho verde — e a propriedade que o define: NUNCA o sha que falhou
# --------------------------------------------------------------------------


def test_escolhe_a_entrega_anterior_e_nunca_a_que_falhou(tmp_path: Path) -> None:
    raiz, shas = _repo_falso(tmp_path)
    atual, anterior = shas[-1], shas[-2]
    saida = tmp_path / "saida.txt"
    proc = _roda(
        raiz,
        REVERSAO_CELULA="quiz",
        REVERSAO_ATUAL=atual,
        # O registry conhece TODAS as tags, inclusive a que acabou de falhar:
        # se o portão olhasse o sha atual, escolheria justamente a imagem
        # doente — e a reversão viraria um deploy do mesmo defeito.
        REVERSAO_DOCKER=_docker_de_mentira(tmp_path, shas),
        GITHUB_OUTPUT=str(saida),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    escrito = saida.read_text(encoding="utf-8")
    assert f"tag={anterior}" in escrito
    assert atual not in escrito, "a imagem que falhou não pode ser o destino"
    assert "celula=quiz" in escrito
    assert "var_tag=QUIZ_TAG" in escrito


def test_pula_as_entregas_que_nunca_viraram_imagem(tmp_path: Path) -> None:
    """Commit da main não é imagem: o deploy só constrói a célula tocada.

    Aqui o registry só conhece a entrega MAIS VELHA. O portão precisa passar
    por cima das intermediárias — e dizer quais inspecionou, para quem ler o
    log não achar que ele adivinhou.
    """
    raiz, shas = _repo_falso(tmp_path, entregas=4)
    saida = tmp_path / "saida.txt"
    proc = _roda(
        raiz,
        REVERSAO_CELULA="quiz",
        REVERSAO_ATUAL=shas[-1],
        REVERSAO_DOCKER=_docker_de_mentira(tmp_path, [shas[0]]),
        GITHUB_OUTPUT=str(saida),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert f"tag={shas[0]}" in saida.read_text(encoding="utf-8")
    assert "candidato" in proc.stdout, "a busca precisa dizer por onde passou"


# --------------------------------------------------------------------------
# Os dois "não sei" — e eles não podem virar a mesma coisa
# --------------------------------------------------------------------------


def test_registry_mudo_e_ERROR_e_nao_um_alvo_mais_velho(tmp_path: Path) -> None:
    raiz, shas = _repo_falso(tmp_path)
    saida = tmp_path / "saida.txt"
    proc = _roda(
        raiz,
        REVERSAO_CELULA="quiz",
        REVERSAO_ATUAL=shas[-1],
        REVERSAO_DOCKER=_docker_de_mentira(tmp_path, [], modo="mudo"),
        GITHUB_OUTPUT=str(saida),
    )
    assert proc.returncode == 2, (
        "falha de rede no registry NÃO é 'a tag não existe' — se virar FAIL, a "
        "reversão passa a escolher alvos velhos por causa de um blip:\n"
        + proc.stdout
    )
    assert not saida.exists() or "tag=" not in saida.read_text(encoding="utf-8")


def test_nenhuma_imagem_na_janela_e_FAIL_e_ninguem_reverte(tmp_path: Path) -> None:
    raiz, shas = _repo_falso(tmp_path)
    saida = tmp_path / "saida.txt"
    proc = _roda(
        raiz,
        REVERSAO_CELULA="quiz",
        REVERSAO_ATUAL=shas[-1],
        REVERSAO_DOCKER=_docker_de_mentira(tmp_path, []),
        GITHUB_OUTPUT=str(saida),
    )
    assert proc.returncode == 1, proc.stdout
    assert not saida.exists() or "tag=" not in saida.read_text(encoding="utf-8")
    assert "célula parada" in proc.stdout


def test_primeira_entrega_da_celula_nao_tem_para_onde_voltar(tmp_path: Path) -> None:
    raiz, shas = _repo_falso(tmp_path, entregas=1)
    proc = _roda(
        raiz,
        REVERSAO_CELULA="quiz",
        REVERSAO_ATUAL=shas[0],
        REVERSAO_DOCKER=_docker_de_mentira(tmp_path, shas),
    )
    assert proc.returncode == 1, proc.stdout
    assert "PRIMEIRA entrega" in proc.stdout


# --------------------------------------------------------------------------
# O que nem chega a perguntar ao registry
# --------------------------------------------------------------------------


def test_celula_fora_do_manifesto_reprova_antes_de_qualquer_consulta(
    tmp_path: Path,
) -> None:
    raiz, shas = _repo_falso(tmp_path)
    proc = _roda(
        raiz,
        REVERSAO_CELULA="inventada; rm -rf /",
        REVERSAO_ATUAL=shas[-1],
        REVERSAO_DOCKER=_docker_de_mentira(tmp_path, shas),
    )
    assert proc.returncode == 1, proc.stdout
    assert "não é célula declarada" in proc.stdout


@pytest.mark.parametrize("sha", ["", "abc123", "main", "z" * 40])
def test_sha_que_nao_e_sha_reprova(tmp_path: Path, sha: str) -> None:
    raiz, shas = _repo_falso(tmp_path)
    proc = _roda(
        raiz,
        REVERSAO_CELULA="quiz",
        REVERSAO_ATUAL=sha,
        REVERSAO_DOCKER=_docker_de_mentira(tmp_path, shas),
    )
    assert proc.returncode == 1, proc.stdout
    assert "40 hex" in proc.stdout


def test_limite_invalido_e_ERROR_e_nao_uma_busca_curta(tmp_path: Path) -> None:
    raiz, shas = _repo_falso(tmp_path)
    proc = _roda(
        raiz,
        REVERSAO_CELULA="quiz",
        REVERSAO_ATUAL=shas[-1],
        REVERSAO_LIMITE="zero",
        REVERSAO_DOCKER=_docker_de_mentira(tmp_path, shas),
    )
    assert proc.returncode == 2, proc.stdout


# --------------------------------------------------------------------------
# A fiação: o workflow de verdade
# --------------------------------------------------------------------------


def _passos_do_deploy() -> list[dict]:
    fluxo = yaml.safe_load(DEPLOY.read_text(encoding="utf-8"))
    return fluxo["jobs"]["deploy"]["steps"]


def test_o_workflow_reverte_so_quando_a_entrega_falha():
    """Reverter em `always()` desfaria deploys que deram certo.

    A condição precisa ser de FALHA. Este teste existe porque a diferença entre
    `if: failure()` e `if: always()` é invisível numa leitura rápida e catastrófica
    em produção.
    """
    passos = _passos_do_deploy()
    reversao = [p for p in passos if "reversao.py" in str(p.get("run", ""))]
    assert reversao, "o deploy não chama ci/reversao.py em lugar nenhum"
    condicao = str(reversao[0].get("if", ""))
    assert "failure()" in condicao, (
        "o passo que escolhe o alvo da reversão tem de rodar SÓ quando a "
        f"entrega falha. Condição atual: {condicao!r}"
    )


def test_o_workflow_nao_usa_as_costuras_de_teste():
    """As costuras existem para os testes. No workflow real, elas seriam um
    caminho para apontar o `docker`, o `git` ou a raiz medida para outro lugar."""
    texto = DEPLOY.read_text(encoding="utf-8")
    for costura in ("REVERSAO_DOCKER", "REVERSAO_GIT", "REVERSAO_RAIZ"):
        assert costura not in texto, f"{costura} não pode aparecer no workflow real"


def test_a_reversao_exige_a_sentinela_da_vps():
    """Conectar sem executar já ficou verde uma vez (28/08/2026, `script_file`).

    Numa reversão isso é pior: o run anunciaria "revertido" com a imagem doente
    ainda no ar. A prova é a marca que o script imprime no fim.
    """
    texto = DEPLOY.read_text(encoding="utf-8")
    assert "REVERSAO-CONCLUIDA:" in texto, (
        "o deploy precisa EXIGIR a marca de conclusão da reversão — sem ela, "
        "'a porta abriu' voltaria a ser lido como 'o trabalho foi feito'"
    )


def test_a_reversao_e_o_rollback_usam_o_MESMO_script_na_vps():
    """Uma definição de 'voltar uma célula', não duas.

    Duas cópias divergem no primeiro dia em que alguém mexer numa delas — e a
    que vai rodar às 2h da manhã será, por lei de Murphy, a que ficou para trás.
    """
    deploy = DEPLOY.read_text(encoding="utf-8")
    rollback = (RAIZ / ".github" / "workflows" / "rollback.yml").read_text(
        encoding="utf-8"
    )
    caminho = "infra/reverter-celula-na-vps.sh"
    assert caminho in deploy and caminho in rollback, (
        "o deploy-celula (reversão automática) e o rollback (manual) precisam "
        f"apontar para o mesmo {caminho}"
    )
    assert (RAIZ / caminho).is_file(), f"{caminho} não existe"
