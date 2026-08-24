"""Suíte adversarial do portão de rollback — os três estados, sem exceção.

`ci/rollback.py` é a única porta MANUAL para a produção (os dois deploys
recusam `workflow_dispatch` de propósito). Logo, ele precisa provar as três
coisas nos três estados, como todo portão desta CI:

    aceita o certo      alvo ancestral da main, com imagem publicada
    recusa o errado     e DIZ o quê: célula inventada, sha de branch não
                        mergeada, sha abreviado, imagem que nunca existiu
    erro de instrumento NUNCA vira OK: docker mudo, git quebrado, manifesto
                        ilegível — tudo isso é 2, nunca 0 e nunca 1

O git aqui é de VERDADE (um repositório minúsculo em tmp_path, com uma branch
lateral): a ancestralidade é a checagem que impede este workflow de virar um
caminho para rodar código não revisado em produção, e testá-la contra um git
de mentira seria testar o dublê. O docker, sim, é dublê — o que importa dele é
a semântica da resposta, não o registry.

O último teste afirma a FORMA do workflow: é a mitigação do vetor "editar o
YAML e tirar a validação" (mesmo papel que o teste de forma do portão de
deploy) e roda no `muralhas` (PR) e no `alarme-main` (push).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

CI = Path(__file__).resolve().parents[1]
if str(CI) not in sys.path:
    sys.path.insert(0, str(CI))

RAIZ = CI.parent
ROLLBACK = CI / "rollback.py"

MOTIVO_BOM = "drill cronometrado da Fase D"

# Docker de mentira: responde manifesto para as imagens do roteiro e o erro
# LITERAL do registry para as outras. O texto do erro é o que o portão usa
# para separar "tag inexistente" (FAIL) de "registry mudo" (ERROR) — se ele
# mudar aqui sem mudar lá, este teste avisa.
DOCKER_FALSO = """\
import json, os, sys
roteiro = json.loads(os.environ["DOCKER_FALSO_ROTEIRO"])
alvo = sys.argv[-1]
if roteiro.get("morrer"):
    sys.stderr.write(roteiro["morrer"] + chr(10))
    sys.exit(1)
if alvo in roteiro.get("existem", []):
    sys.stdout.write(json.dumps({"schemaVersion": 2, "imagem": alvo}))
    sys.exit(0)
sys.stderr.write(
    "manifest unknown: manifest tagged by " + alvo + " is not found" + chr(10)
)
sys.exit(1)
"""


def _git(raiz: Path, *args: str) -> str:
    proc = subprocess.run(
        [
            "git",
            "-c",
            "user.name=teste",
            "-c",
            "user.email=teste@exemplo.invalido",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        cwd=str(raiz),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return (proc.stdout or "").strip()


@pytest.fixture
def repo_git(repo, tmp_path):
    """Repositório de verdade: dois commits na linha principal e um fora dela.

    Devolve o próprio RepoFalso com três shas anotados:
      `sha_antigo`  ancestral da main — o alvo legítimo de um rollback
      `sha_topo`    o HEAD da main — a base contra a qual medimos
      `sha_lado`    commit de branch nunca mergeada — o alvo que reprova
    """
    raiz = repo.raiz
    repo.criar_celula("checkout")
    repo.declarar({"checkout": {"freeze": "required"}, "funil": {"freeze": "required"}})

    _git(raiz, "init", "-q", "-b", "main")
    (raiz / "marco.txt").write_text("um\n", encoding="utf-8")
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-qm", "primeiro")
    repo.sha_antigo = _git(raiz, "rev-parse", "HEAD")

    (raiz / "marco.txt").write_text("dois\n", encoding="utf-8")
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-qm", "segundo")
    repo.sha_topo = _git(raiz, "rev-parse", "HEAD")

    _git(raiz, "checkout", "-q", "-b", "lado", repo.sha_antigo)
    (raiz / "rascunho.txt").write_text("nunca mergeado\n", encoding="utf-8")
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-qm", "rascunho")
    repo.sha_lado = _git(raiz, "rev-parse", "HEAD")
    _git(raiz, "checkout", "-q", "main")
    return repo


def rodar(
    repo_git,
    tmp_path,
    *,
    celula: str = "checkout",
    alvo: str | None = None,
    motivo: str = MOTIVO_BOM,
    imagens_existentes: list[str] | None = None,
    docker_morre: str | None = None,
    extra: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    alvo = repo_git.sha_antigo if alvo is None else alvo
    if imagens_existentes is None:
        imagens_existentes = [
            f"ghcr.io/abundanciabr/plataforma-{celula}:{alvo}",
            f"ghcr.io/abundanciabr/plataforma-{celula}:main",
        ]
    docker = tmp_path / "docker_falso.py"
    docker.write_text(DOCKER_FALSO, encoding="utf-8")

    env = dict(os.environ)
    env.update(
        {
            "PYTHONUTF8": "1",
            "ROLLBACK_RAIZ": str(repo_git.raiz),
            "ROLLBACK_CELULA": celula,
            "ROLLBACK_ALVO": alvo,
            "ROLLBACK_MOTIVO": motivo,
            "ROLLBACK_DOCKER": json.dumps([sys.executable, str(docker)]),
            "GITHUB_OUTPUT": str(tmp_path / "saidas.txt"),
            "DOCKER_FALSO_ROTEIRO": json.dumps(
                {"existem": imagens_existentes, "morrer": docker_morre}
            ),
        }
    )
    env.pop("ROLLBACK_BASE", None)
    env.pop("ROLLBACK_GIT", None)
    env.update(extra or {})
    return subprocess.run(
        [sys.executable, str(ROLLBACK)],
        cwd=str(repo_git.raiz),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=False,
    )


def saidas(tmp_path) -> dict[str, str]:
    arquivo = tmp_path / "saidas.txt"
    if not arquivo.exists():
        return {}
    linhas = arquivo.read_text(encoding="utf-8").splitlines()
    return dict(linha.split("=", 1) for linha in linhas if "=" in linha)


# ---------------------------------------------------------------------------
# Aceita o certo
# ---------------------------------------------------------------------------


def test_alvo_ancestral_com_imagem_publicada_passa(repo_git, tmp_path):
    proc = rodar(repo_git, tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert saidas(tmp_path) == {
        "celula": "checkout",
        "tag": repo_git.sha_antigo,
        "var_tag": "CHECKOUT_TAG",
    }


def test_alvo_main_desfaz_o_pin_e_passa(repo_git, tmp_path):
    proc = rodar(repo_git, tmp_path, alvo="main")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert saidas(tmp_path)["tag"] == "main"
    assert saidas(tmp_path)["var_tag"] == "CHECKOUT_TAG"


def test_topo_da_main_e_alvo_valido(repo_git, tmp_path):
    # merge-base(HEAD, HEAD) == HEAD: um commit é ancestral de si mesmo.
    # Redeployar o commit corrente é rollback legítimo (container corrompido).
    proc = rodar(repo_git, tmp_path, alvo=repo_git.sha_topo)
    assert proc.returncode == 0, proc.stdout + proc.stderr


# ---------------------------------------------------------------------------
# Recusa o errado — e diz o quê (FAIL = 1, nunca 2)
# ---------------------------------------------------------------------------


def test_celula_fora_do_manifesto_reprova(repo_git, tmp_path):
    proc = rodar(repo_git, tmp_path, celula="pagamentos; rm -rf /")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "não é célula declarada" in proc.stdout
    assert saidas(tmp_path) == {}


def test_celula_vazia_reprova(repo_git, tmp_path):
    proc = rodar(repo_git, tmp_path, celula="")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "nenhuma célula informada" in proc.stdout


def test_sha_abreviado_reprova(repo_git, tmp_path):
    proc = rodar(repo_git, tmp_path, alvo=repo_git.sha_antigo[:12])
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "40 hex" in proc.stdout


def test_alvo_que_nao_e_sha_nem_main_reprova(repo_git, tmp_path):
    proc = rodar(repo_git, tmp_path, alvo="HEAD~1")
    assert proc.returncode == 1, proc.stdout + proc.stderr


def test_commit_de_branch_nao_mergeada_reprova(repo_git, tmp_path):
    # O teste que sustenta o workflow_dispatch: um sha REAL, com imagem REAL,
    # mas que nunca esteve na main. Se este passar a devolver 0, `rollback`
    # virou um caminho para rodar código não revisado em produção.
    proc = rodar(repo_git, tmp_path, alvo=repo_git.sha_lado)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "NÃO é ancestral" in proc.stdout


def test_sha_inexistente_no_repositorio_e_error_nunca_pass(repo_git, tmp_path):
    # ERROR (2), não FAIL (1), de propósito: "o git não conhece esse objeto"
    # pode ser um sha inventado OU um clone raso/desatualizado — não dá para
    # afirmar que o ALVO está errado sem antes saber que o histórico está
    # completo. `(1, 2)` aqui seria asserção frouxa: esconderia uma mudança de
    # comportamento em vez de reprovar.
    proc = rodar(repo_git, tmp_path, alvo="f" * 40)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert saidas(tmp_path) == {}


def test_imagem_que_nunca_foi_publicada_reprova(repo_git, tmp_path):
    proc = rodar(repo_git, tmp_path, imagens_existentes=[])
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "não existe no registry" in proc.stdout


def test_motivo_vazio_reprova(repo_git, tmp_path):
    proc = rodar(repo_git, tmp_path, motivo="")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "mínimo 10" in proc.stdout


def test_motivo_curto_demais_reprova(repo_git, tmp_path):
    proc = rodar(repo_git, tmp_path, motivo="urgente")
    assert proc.returncode == 1, proc.stdout + proc.stderr


# ---------------------------------------------------------------------------
# Erro de instrumento NUNCA vira OK (ERROR = 2)
# ---------------------------------------------------------------------------


def test_registry_mudo_e_error_nunca_fail(repo_git, tmp_path):
    # "não consegui perguntar ao registry" não é "a tag não existe": um vira
    # ERROR (2) e manda consertar a CI; o outro vira FAIL (1) e manda escolher
    # outro sha. Confundir os dois foi a ferida original desta CI.
    proc = rodar(repo_git, tmp_path, docker_morre="dial tcp: i/o timeout")
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert saidas(tmp_path) == {}


def test_docker_ausente_e_error(repo_git, tmp_path):
    proc = rodar(
        repo_git,
        tmp_path,
        extra={"ROLLBACK_DOCKER": json.dumps(["docker-que-nao-existe-nenhum"])},
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr


def test_git_quebrado_e_error(repo_git, tmp_path):
    proc = rodar(
        repo_git,
        tmp_path,
        extra={"ROLLBACK_GIT": json.dumps(["git-que-nao-existe-nenhum"])},
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr


def test_costura_com_json_invalido_e_error(repo_git, tmp_path):
    proc = rodar(repo_git, tmp_path, extra={"ROLLBACK_DOCKER": "docker"})
    assert proc.returncode == 2, proc.stdout + proc.stderr


def test_manifesto_ilegivel_e_error(repo_git, tmp_path):
    (repo_git.raiz / "ci" / "manifesto-de-contratos.json").write_text(
        "{isso não é json", encoding="utf-8"
    )
    proc = rodar(repo_git, tmp_path)
    assert proc.returncode == 2, proc.stdout + proc.stderr


def test_manifesto_sem_celulas_nao_libera_qualquer_nome(repo_git, tmp_path):
    (repo_git.raiz / "ci" / "manifesto-de-contratos.json").write_text(
        json.dumps({"celulas": {}}), encoding="utf-8"
    )
    proc = rodar(repo_git, tmp_path)
    assert proc.returncode == 2, proc.stdout + proc.stderr


def test_raiz_declarada_sem_as_marcas_e_error(repo_git, tmp_path):
    vazio = tmp_path / "vazio"
    vazio.mkdir()
    proc = rodar(repo_git, tmp_path, extra={"ROLLBACK_RAIZ": str(vazio)})
    assert proc.returncode == 2, proc.stdout + proc.stderr


def test_bug_dentro_do_portao_vira_2_nunca_1():
    import rollback as modulo

    def explode():
        raise TypeError("bug nosso, não do alvo pedido")

    assert modulo._blindar("teste", explode)() == 2


# ---------------------------------------------------------------------------
# Forma do workflow — mitigação do vetor "tirar a validação do YAML"
# ---------------------------------------------------------------------------


def _carregar(nome: str) -> dict:
    doc = yaml.safe_load(
        (RAIZ / ".github" / "workflows" / nome).read_text(encoding="utf-8")
    )
    # YAML 1.1 lê `on:` como a chave booleana True.
    doc["on"] = doc.get("on", doc.get(True))
    return doc


def test_workflow_de_rollback_exige_a_validacao():
    wf = _carregar("rollback.yml")
    assert "workflow_dispatch" in wf["on"], (
        "rollback é a válvula de emergência: sem dispatch ela não existe"
    )
    jobs = wf["jobs"]
    assert "validar" in jobs, "o job de validação sumiu do rollback"
    assert "ci/rollback.py" in json.dumps(jobs["validar"]["steps"])

    aplicar = jobs["aplicar"]
    needs = aplicar["needs"]
    assert needs == "validar" or "validar" in needs
    for trecho in (
        "needs.validar.result == 'success'",
        "needs.validar.outputs.celula != ''",
        "needs.validar.outputs.tag != ''",
        "needs.validar.outputs.var_tag != ''",
    ):
        assert trecho in aplicar["if"], f"condição do aplicar perdeu: {trecho}"
    # Quem entra na VPS não precisa do registry, e quem lê o registry não
    # recebe a chave SSH.
    assert "packages" not in aplicar.get("permissions", {})
    assert "DEPLOY_SSH_KEY" not in json.dumps(jobs["validar"])
    # Mesmo grupo dos deploys: dois `docker compose` simultâneos na mesma VPS
    # seriam intercalados.
    assert wf["concurrency"]["group"] == "deploy"


def test_workflow_mede_linhagem_contra_a_MAIN_nao_contra_o_ref_do_disparo():
    """O furo que a auditoria de 23/08/2026 encontrou.

    `workflow_dispatch` aceita `--ref <branch>`. Com o checkout padrão, o
    repositório vinha nesse ref e `ROLLBACK_BASE: ${{ github.sha }}` media a
    ancestralidade contra ELE — ou seja, a promessa "o alvo é ancestral da
    main", escrita em RITOS §4, RUNBOOK §6 e no cabeçalho deste workflow, não
    era a que o código impunha. A checagem de imagem no registry segurava na
    prática (só a main gera imagem), mas garantia declarada que ninguém impõe
    apodrece — este teste é o que a mantém honesta.
    """
    wf = _carregar("rollback.yml")
    passos = wf["jobs"]["validar"]["steps"]
    checkout = next(p for p in passos if "checkout" in str(p.get("uses", "")))
    # `.get`, não `[...]`: sem a chave o teste tem de dizer O QUE FALTA, não
    # estourar KeyError. Guarda que reprova de forma críptica é meio-guarda —
    # quem lê isto vai estar com pressa.
    com = checkout.get("with") or {}
    assert com.get("ref") == "main", (
        "o checkout do job de validação precisa fixar `ref: main` — sem isso a "
        f"régua da linhagem vira a branch de quem disparou (achei: {com.get('ref')!r})"
    )
    assert com.get("fetch-depth") == 0, (
        f"fetch-depth: 0 é obrigatório para medir ancestralidade (achei: {com.get('fetch-depth')!r})"
    )
    base = next(p for p in passos if p.get("id") == "v")["env"]["ROLLBACK_BASE"]
    assert "github.sha" not in str(base), (
        "github.sha é o sha do ref DO DISPARO; a base tem de ser a main "
        "(HEAD, já que o checkout acima a fixa)"
    )


def test_workflow_de_rollback_nao_define_as_costuras_de_teste():
    bruto = (RAIZ / ".github" / "workflows" / "rollback.yml").read_text(
        encoding="utf-8"
    )
    for costura in ("ROLLBACK_DOCKER", "ROLLBACK_GIT", "ROLLBACK_RAIZ"):
        assert costura not in bruto, (
            f"{costura} é costura de teste; no workflow real ela faria o "
            "portão validar um dublê"
        )


def test_motivo_e_texto_livre_e_nunca_entra_no_script_do_ssh():
    # `script:` da ssh-action é substituição de TEXTO: um motivo com aspas e
    # `;` viraria comando na VPS. Célula e tag podem ser interpoladas porque o
    # portão já provou que são um nome do manifesto e um sha/`main`.
    wf = _carregar("rollback.yml")
    for passo in wf["jobs"]["aplicar"]["steps"]:
        script = (passo.get("with") or {}).get("script", "")
        assert "inputs.motivo" not in script, (
            "motivo é texto livre e está sendo interpolado dentro do script "
            "do SSH — isso é injeção de comando na VPS"
        )


def test_opcoes_de_celula_do_workflow_batem_com_o_manifesto():
    # Se uma célula nova nascer e a lista aqui não crescer, ela fica sem
    # rollback — e ninguém descobre isso às 2h da manhã.
    wf = _carregar("rollback.yml")
    opcoes = wf["on"]["workflow_dispatch"]["inputs"]["celula"]["options"]
    manifesto = json.loads(
        (RAIZ / "ci" / "manifesto-de-contratos.json").read_text(encoding="utf-8")
    )
    assert sorted(opcoes) == sorted(manifesto["celulas"])
