"""TESTAR O TESTADOR — a cadeia que decide o merge, não só o gate isolado.

[INV-CI01] Um portão fail-closed não basta: a CADEIA que decide o merge também
precisa ser. O elo mais frágil era o job terminal de `.github/workflows/
ci-celula.yml`, que aceitava qualquer `skipped` como verde:

    git falha -> célula vazia -> job `rodar` pulado -> gate verde -> merge

Estes testes extraem o script de decisão DO PRÓPRIO YAML e o executam sob bash
com cada estado possível dos jobs. Não é uma reimplementação da lógica: é o
mesmo texto que o GitHub Actions vai rodar, lido do arquivo. Se alguém afrouxar
o gate no YAML, estes testes ficam vermelhos.

O que isto NÃO prova: que o GitHub Actions orquestra os jobs como modelado
(que `detectar` falhando torna `rodar` `skipped`, etc.). Isso é comportamento
da plataforma e só a CI canônica confirma. Aqui provamos a tabela de decisão.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from conftest import BASH
from _nucleo import Estado, Relatorio, Resultado
import ci as runner_ci

CI = Path(__file__).resolve().parents[1]
WORKFLOW = CI.parent / ".github" / "workflows" / "ci-celula.yml"

# O gate ANTIGO, preservado como controle histórico. É contra ele que se mede o
# que mudou — sem isto, "corrigimos o bypass" seria narrativa, não evidência.
GATE_ANTIGO = """
R="$R"
if [ "$R" = "failure" ] || [ "$R" = "cancelled" ]; then
  echo "ci-celula: a celula tocada falhou (rodar=$R)"; exit 1
fi
echo "ci-celula-gate OK (rodar=$R)"
"""

pytestmark = pytest.mark.skipif(
    BASH is None, reason="nenhum bash utilizável foi encontrado neste ambiente"
)


def _script_do_gate() -> str:
    """Lê o script de decisão direto do workflow — nunca de uma cópia."""
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    passos = doc["jobs"]["gate"]["steps"]
    scripts = [p["run"] for p in passos if "run" in p]
    assert len(scripts) == 1, f"esperava 1 step com `run` no gate, achei {len(scripts)}"
    return scripts[0]


def _rodar(script: str, **estado: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [BASH, "-c", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={"PATH": "/usr/bin:/bin", **estado},
        timeout=60,
        check=False,
    )


def _estado(
    d_result: str = "success",
    d_status: str = "ok",
    celulas: str = '["catalogo"]',
    n: str = "1",
    r: str = "success",
) -> dict[str, str]:
    """O estado que o gate enxerga.

    Desde a Onda 5 o job da célula é uma MATRIZ e o detectar publica a LISTA em
    json (`celulas`), não mais a primeira célula (`celula`). O gate confere que
    a lista e a contagem concordam — duas medidas da mesma coisa que discordam
    é instrumento quebrado.
    """
    return {
        "D_RESULT": d_result,
        "D_STATUS": d_status,
        "CELULAS": celulas,
        "N": n,
        "R": r,
    }


# ---------------------------------------------------------------------------
# A tabela-verdade nova, estado por estado
# ---------------------------------------------------------------------------

VERDE = 0
VERMELHO = 1

TABELA = [
    # (descrição, estado, exit esperado)
    ("célula testada e verde ⇒ PASS", _estado(), VERDE),
    ("célula testada e vermelha ⇒ FAIL", _estado(r="failure"), VERMELHO),
    ("job da célula cancelado ⇒ ERROR", _estado(r="cancelled"), VERMELHO),
    (
        "célula detectada mas o job não rodou ⇒ ERROR",
        _estado(r="skipped"),
        VERMELHO,
    ),
    (
        "detecção concluiu e não há célula ⇒ SKIP permitido",
        _estado(celulas="[]", n="0", r="skipped"),
        VERDE,
    ),
    (
        "sem célula mas o job rodou ⇒ ERROR (estado incoerente)",
        _estado(celulas="[]", n="0", r="success"),
        VERMELHO,
    ),
    (
        "O BYPASS: detecção falhou ⇒ ERROR, nunca verde",
        _estado(d_result="failure", d_status="", celulas="", n="", r="skipped"),
        VERMELHO,
    ),
    (
        "detecção cancelada ⇒ ERROR",
        _estado(d_result="cancelled", d_status="", celulas="", n="", r="skipped"),
        VERMELHO,
    ),
    (
        "detecção pulada ⇒ ERROR",
        _estado(d_result="skipped", d_status="", celulas="", n="", r="skipped"),
        VERMELHO,
    ),
    (
        "detecção 'passou' sem carimbar que mediu ⇒ ERROR",
        _estado(d_status="", celulas="[]", n="0", r="skipped"),
        VERMELHO,
    ),
    (
        "DUAS células tocadas e as DUAS verdes ⇒ PASS (Onda 5)",
        _estado(celulas='["checkout", "pagamentos"]', n="2", r="success"),
        VERDE,
    ),
    (
        "duas células e uma reprovou ⇒ FAIL",
        _estado(celulas='["checkout", "pagamentos"]', n="2", r="failure"),
        VERMELHO,
    ),
    (
        "a lista e a contagem discordam ⇒ ERROR (instrumento quebrado)",
        _estado(celulas='["checkout"]', n="2", r="success"),
        VERMELHO,
    ),
    (
        "contagem de células corrompida ⇒ ERROR",
        _estado(n="lixo"),
        VERMELHO,
    ),
    (
        "contagem de células ausente ⇒ ERROR",
        _estado(n=""),
        VERMELHO,
    ),
    (
        "estado desconhecido do job da célula ⇒ ERROR",
        _estado(r="alguma-coisa-nova-do-github"),
        VERMELHO,
    ),
]


@pytest.mark.parametrize(
    "descricao,estado,esperado", TABELA, ids=[t[0][:45] for t in TABELA]
)
def test_tabela_verdade_do_gate(
    descricao: str, estado: dict[str, str], esperado: int
) -> None:
    proc = _rodar(_script_do_gate(), **estado)
    assert proc.returncode == esperado, (
        f"{descricao}\nestado={estado}\n"
        f"exit={proc.returncode} (esperado {esperado})\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )


def test_o_bypass_existia_de_verdade_no_gate_antigo() -> None:
    """Controle histórico: o gate ANTIGO ficava verde com a detecção quebrada.

    Sem esta prova, "corrigimos o bypass" seria apenas afirmação. Aqui o estado
    exato do bypass roda contra os dois scripts: o antigo aprova, o novo reprova.
    """
    estado_do_bypass = _estado(
        d_result="failure", d_status="", celulas="", n="", r="skipped"
    )
    # O gate ANTIGO lia `CELULA` (singular); o novo lê `CELULAS` (a lista). O
    # estado precisa falar as duas línguas para que a comparação seja honesta:
    # o antigo tem de receber exatamente o que ele receberia no dia do bypass.
    estado_do_bypass = {**estado_do_bypass, "CELULA": ""}
    antigo = _rodar(GATE_ANTIGO, **estado_do_bypass)
    novo = _rodar(_script_do_gate(), **estado_do_bypass)

    assert antigo.returncode == 0, "o gate antigo deveria aprovar — é o bypass"
    assert novo.returncode != 0, "o gate novo NÃO pode aprovar o mesmo estado"


def test_gate_e_o_job_terminal_e_sempre_conclui() -> None:
    """Se o gate deixar de rodar `always()`, ele para de ser o check terminal."""
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    gate = doc["jobs"]["gate"]
    assert gate["if"] == "always()"
    assert set(gate["needs"]) == {"detectar", "rodar"}


def test_deteccao_usa_o_runner_canonico() -> None:
    """O YAML não pode voltar a reimplementar a detecção de escopo em shell.

    A semântica de "quais células este PR toca" vive em ci/ci.py, que é o mesmo
    caminho que o agente roda localmente. Duplicá-la em YAML é como o drift
    entre runner local e CI canônica começa.
    """
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    passos = doc["jobs"]["detectar"]["steps"]
    scripts = "\n".join(p["run"] for p in passos if "run" in p)
    assert "ci/ci.py --detectar-celulas" in scripts
    linhas_ativas = [
        ln for ln in scripts.splitlines() if not ln.lstrip().startswith("#")
    ]
    for proibido in ("|| true", "set +e"):
        ofensas = [ln.strip() for ln in linhas_ativas if proibido in ln]
        assert not ofensas, f"padrão de falso positivo em `detectar`: {ofensas}"


MURALHAS_YML = CI.parent / ".github" / "workflows" / "muralhas.yml"


def test_muralhas_usa_o_runner_canonico() -> None:
    """O workflow não pode listar os portões à mão.

    Enquanto o YAML enumerava `bash ci/cerca-de-celula.sh`, `bash ci/...` etc., a
    lista de muralhas do GitHub e a de `ci/ci.py` podiam divergir sem ninguém
    perceber — o agente rodaria um conjunto de portões, o CI outro. Agora os
    dois lados executam literalmente o mesmo comando.
    """
    doc = yaml.safe_load(MURALHAS_YML.read_text(encoding="utf-8"))
    scripts = "\n".join(
        p["run"] for p in doc["jobs"]["muralhas"]["steps"] if "run" in p
    )
    assert "ci/ci.py --apenas muralhas" in scripts
    assert "ci/ci.py --apenas testador" in scripts
    for portao in (
        "cerca-de-celula.sh",
        "orcamento-de-mudanca.sh",
        "guarda-de-segredos.sh",
    ):
        assert portao not in scripts, (
            f"o workflow voltou a chamar {portao} direto — a semântica dos "
            "portões precisa vir de ci/ci.py, não de uma lista paralela no YAML"
        )


def test_o_detectar_publica_a_LISTA_e_nao_a_primeira_celula():
    """A matriz sai de `celulas`; publicar `celula` (singular) a deixaria vazia.

    Este teste existe porque o defeito aconteceu: no primeiro PR da matriz, o
    passo de detecção continuava escrevendo `celula=` e a matriz nasceu sem
    nada. O gate pegou (lista 0 contra contagem 1) — mas um guarda que lê o
    WORKFLOW pega antes de gastar uma rodada de CI.
    """
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    detectar = doc["jobs"]["detectar"]
    assert "celulas" in detectar["outputs"], "o job precisa publicar a LISTA"
    assert "celula" not in detectar["outputs"], (
        "`celula` (singular) era o `head -1` que fazia o escopo caber numa "
        "célula só — ele não pode voltar"
    )
    # Comentários fora: eles CITAM o `head -1` para explicar por que ele saiu, e
    # um guarda que confundisse a explicação com o código proibiria escrever a
    # história — que é metade do valor destes arquivos.
    linhas = [
        ln
        for passo in detectar["steps"]
        for ln in str(passo.get("run", "")).splitlines()
        if not ln.strip().startswith("#")
    ]
    script = chr(10).join(linhas)
    assert "celulas=" in script, "nada escreve `celulas=` no GITHUB_OUTPUT"
    assert "head -1" not in script, "o `head -1` do escopo estreito voltou"


def test_a_matriz_sai_da_lista_detectada():
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    rodar = doc["jobs"]["rodar"]
    matriz = str(rodar["strategy"]["matrix"]["celula"])
    assert "needs.detectar.outputs.celulas" in matriz
    assert rodar["strategy"]["fail-fast"] is False, (
        "com duas células tocadas, parar na primeira falha esconde a segunda"
    )


def test_workflow_delega_a_validacao_da_celula_ao_runner_python():
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    scripts = "\n".join(
        passo["run"]
        for passo in doc["jobs"]["rodar"]["steps"]
        if "run" in passo
    )
    assert "python ci/ci.py --apenas celula --celula" in scripts
    assert "make -C" not in scripts
    assert "cross-smoke.sh" not in scripts


def test_catalogo_deixa_o_cross_smoke_na_mesma_definicao():
    pagamentos = runner_ci.verificacoes_da_celula(
        Path("services/pagamentos"), "pagamentos"
    )
    catalogo = runner_ci.verificacoes_da_celula(
        Path("services/catalogo"), "catalogo"
    )
    assert pagamentos[-1].nome == "e2e/cross-smoke"
    assert all(verificacao.nome != "e2e/cross-smoke" for verificacao in catalogo)


def test_cross_smoke_reprova_se_o_git_nao_medir_o_diff(monkeypatch, tmp_path):
    def git_quebrado(*args, **kwargs):
        raise runner_ci.ErroDeInstrumentacao("git indisponível", "diff não medido")

    monkeypatch.setattr(runner_ci, "executar", git_quebrado)
    resultado = runner_ci._rodar_cross_smoke(tmp_path, "origin/main")
    assert resultado.estado is Estado.ERROR
    assert "não medido" in resultado.detalhe


def test_makefiles_preservam_os_portoes_que_o_catalogo_python_mede():
    makefiles = sorted((WORKFLOW.parents[2] / "services").glob("*/Makefile"))
    assert makefiles
    for makefile in makefiles:
        _assert_makefile_equivalente_ao_catalogo_python(
            makefile.read_text(encoding="utf-8"), origem=str(makefile)
        )


def test_makefile_com_alvo_obrigatorio_extra_exige_catalogo_python_equivalente():
    texto = (WORKFLOW.parents[2] / "services" / "catalogo" / "Makefile").read_text(
        encoding="utf-8"
    )
    mutante = texto.replace(
        "ci: lint type test contrato-check",
        "ci: lint type test contrato-check seguranca",
    )

    with pytest.raises(AssertionError, match="dependências exatas"):
        _assert_makefile_equivalente_ao_catalogo_python(mutante, origem="mutante")


@pytest.mark.parametrize(
    "mutacao",
    [
        lambda texto: texto.replace(
            "black --check .",
            "black --check .\n\tpython seguranca.py",
        ),
        lambda texto: texto.replace(
            "\t@if [ -f .importlinter ]; then lint-imports; fi\n",
            "",
        ),
        lambda texto: texto.replace(
            "python -m pytest -q",
            "pytest -q",
        ),
    ],
    ids=("comando-extra", "comando-omitido", "comando-trocado"),
)
def test_makefile_com_receita_obrigatoria_alterada_reprova(mutacao):
    texto = (WORKFLOW.parents[2] / "services" / "catalogo" / "Makefile").read_text(
        encoding="utf-8"
    )

    with pytest.raises(AssertionError, match="receita exata"):
        _assert_makefile_equivalente_ao_catalogo_python(
            mutacao(texto), origem="mutante"
        )


def _assert_makefile_equivalente_ao_catalogo_python(texto: str, origem: str) -> None:
    receitas = _receitas_do_makefile(texto)
    dependencias = _dependencias_do_alvo_ci(receitas, origem)
    esperadas = tuple(
        verificacao.nome
        for verificacao in runner_ci.VERIFICACOES_OBRIGATORIAS_DA_CELULA
    )
    alvos_equivalentes = {
        "lint": ("lint/black", "lint/import-linter"),
        "type": ("type/mypy",),
        "test": ("test/pytest",),
        "contrato-check": ("contrato/freeze",),
    }
    assert dependencias == tuple(alvos_equivalentes), (
        f"{origem}: dependências exatas do alvo ci divergem do catálogo Python; "
        f"make={dependencias}, esperado={tuple(alvos_equivalentes)}"
    )
    medidos_pelo_make = tuple(
        item for alvo in dependencias for item in alvos_equivalentes[alvo]
    )
    assert medidos_pelo_make == esperadas, (
        f"{origem}: dependências exatas do alvo ci divergem do catálogo Python; "
        f"make={dependencias}, catálogo={esperadas}"
    )
    receitas_autorizadas = {
        "lint": (
            (
                "black --check .",
                "@if [ -f .importlinter ]; then lint-imports; fi",
            ),
            (
                "black --check .",
                "$(if $(wildcard .importlinter),lint-imports)",
            ),
        ),
        "type": (
            (
                '@if [ -f mypy.ini ]; then mypy .; else echo "ℹ sem mypy nesta célula"; fi',
            ),
            (
                '$(if $(wildcard mypy.ini),mypy .,@echo "ℹ sem mypy nesta célula")',
            ),
        ),
        "test": (("python -m pytest -q",),),
        "contrato-check": (
            ("bash ../../ci/freeze-de-contrato.sh $(CELULA)",),
            (
                'python ../../ci/contract_freeze.py $(CELULA) && echo "✅ ci/contract_freeze.py: portão verificado (adaptador: ci/freeze-de-contrato.sh)"',
            ),
        ),
    }
    for alvo, autorizadas in receitas_autorizadas.items():
        assert receitas.get(alvo) in autorizadas, (
            f"{origem}: receita exata de {alvo} diverge do catálogo Python; "
            f"make={receitas.get(alvo)}, autorizado={autorizadas}"
        )


def _dependencias_do_alvo_ci(
    receitas: dict[str, tuple[str, ...]], origem: str
) -> tuple[str, ...]:
    for linha in receitas.get("ci", ()):
        if linha.startswith("@echo "):
            continue
        raise AssertionError(f"{origem}: receita exata de ci contém comando estranho")
    cabecalho = receitas.get("__ci_deps__")
    if cabecalho is not None:
        return cabecalho
    raise AssertionError(f"{origem}: alvo ci ausente")


def _receitas_do_makefile(texto: str) -> dict[str, tuple[str, ...]]:
    receitas: dict[str, list[str]] = {}
    alvo_atual: str | None = None
    for bruto in texto.splitlines():
        linha = bruto.rstrip()
        if not linha or linha.lstrip().startswith("#"):
            continue
        if not linha.startswith(("\t", " ")):
            alvo_atual = None
            if ":" not in linha or linha.startswith(".PHONY:"):
                continue
            alvo, resto = linha.split(":", 1)
            alvo = alvo.strip()
            if not alvo:
                continue
            alvo_atual = alvo
            receitas.setdefault(alvo, [])
            if alvo == "ci":
                receitas["__ci_deps__"] = resto.split()
            continue
        if alvo_atual is not None:
            receitas.setdefault(alvo_atual, []).append(linha.strip())
    return {alvo: tuple(linhas) for alvo, linhas in receitas.items()}


def _raiz_com_celula(tmp_path: Path, celula: str = "catalogo") -> Path:
    raiz = tmp_path
    destino = raiz / "services" / celula
    destino.mkdir(parents=True)
    for marca in ("CONSTITUICAO.md", "INVARIANTES.md"):
        (raiz / marca).write_text("fonte\n", encoding="utf-8")
    for pasta in ("ci", "contracts"):
        (raiz / pasta).mkdir()
    return raiz


def _freeze_verde(nome: str = "contrato/catalogo") -> Relatorio:
    relatorio = Relatorio("freeze")
    relatorio.registrar(Resultado(nome, Estado.PASS, "idêntico"))
    return relatorio


def test_ci_da_celula_declara_todas_as_verificacoes_obrigatorias() -> None:
    nomes = [v.nome for v in runner_ci.VERIFICACOES_OBRIGATORIAS_DA_CELULA]
    assert nomes == [
        "lint/black",
        "lint/import-linter",
        "type/mypy",
        "test/pytest",
        "contrato/freeze",
    ]


def test_ci_da_celula_sem_lista_obrigatoria_nao_vira_pass(
    tmp_path: Path, monkeypatch
) -> None:
    raiz = _raiz_com_celula(tmp_path)
    monkeypatch.setattr(runner_ci, "VERIFICACOES_OBRIGATORIAS_DA_CELULA", ())

    relatorio = runner_ci.rodar_celula(raiz, "catalogo")

    assert relatorio.estado is Estado.ERROR
    assert relatorio.exit_code == 2


def test_ci_da_celula_roda_sem_make_e_preserva_o_freeze(
    tmp_path: Path, monkeypatch
) -> None:
    raiz = _raiz_com_celula(tmp_path)
    chamadas: list[str] = []

    def rodar(verificacao, destino, prazo):
        chamadas.append(verificacao.nome)
        assert verificacao.nome != "make"
        return Resultado(
            f"celula/{destino.name}/{verificacao.nome}",
            Estado.PASS,
            "verificação verde",
        )

    def freeze(**kwargs):
        assert kwargs["celula"] == "catalogo"
        return _freeze_verde()

    monkeypatch.setattr(runner_ci, "_rodar_comando_da_celula", rodar)
    monkeypatch.setattr(runner_ci.contract_freeze, "rodar", freeze)

    relatorio = runner_ci.rodar_celula(raiz, "catalogo")

    assert relatorio.estado is Estado.PASS
    assert "lint/black" in chamadas
    assert "test/pytest" in chamadas
    assert any(
        r.nome == "celula/catalogo/contrato/freeze/contrato/catalogo"
        for r in relatorio.resultados
    )


def test_ci_da_celula_skip_e_declarado_por_arquivo_ausente(
    tmp_path: Path, monkeypatch
) -> None:
    raiz = _raiz_com_celula(tmp_path)
    chamadas: list[str] = []

    def rodar(verificacao, destino, prazo):
        chamadas.append(verificacao.nome)
        return Resultado(
            f"celula/{destino.name}/{verificacao.nome}",
            Estado.PASS,
            "verificação verde",
        )

    monkeypatch.setattr(runner_ci, "_rodar_comando_da_celula", rodar)
    monkeypatch.setattr(
        runner_ci.contract_freeze, "rodar", lambda **kwargs: _freeze_verde()
    )

    relatorio = runner_ci.rodar_celula(raiz, "catalogo")

    por_nome = {r.nome: r.estado for r in relatorio.resultados}
    assert por_nome["celula/catalogo/lint/import-linter"] is Estado.SKIP
    assert por_nome["celula/catalogo/type/mypy"] is Estado.SKIP
    assert "lint/import-linter" not in chamadas
    assert "type/mypy" not in chamadas


def test_ci_da_celula_timeout_nao_vira_fail(tmp_path: Path, monkeypatch) -> None:
    raiz = _raiz_com_celula(tmp_path)

    def run(comando, **kwargs):
        if comando[:3] == [sys.executable, "-m", "pytest"]:
            raise subprocess.TimeoutExpired(comando, kwargs["timeout"])
        return subprocess.CompletedProcess(comando, 0, "ok\n", "")

    monkeypatch.setattr(runner_ci.subprocess, "run", run)
    monkeypatch.setattr(
        runner_ci.contract_freeze, "rodar", lambda **kwargs: _freeze_verde()
    )

    relatorio = runner_ci.rodar_celula(raiz, "catalogo")

    assert relatorio.estado is Estado.TIMEOUT
    assert any(r.estado is Estado.TIMEOUT for r in relatorio.resultados)


def test_ci_da_celula_cancelamento_nao_vira_fail(
    tmp_path: Path, monkeypatch
) -> None:
    raiz = _raiz_com_celula(tmp_path)

    def run(comando, **kwargs):
        if comando[:3] == [sys.executable, "-m", "pytest"]:
            return subprocess.CompletedProcess(comando, 130, "", "cancelado")
        return subprocess.CompletedProcess(comando, 0, "ok\n", "")

    monkeypatch.setattr(runner_ci.subprocess, "run", run)
    monkeypatch.setattr(
        runner_ci.contract_freeze, "rodar", lambda **kwargs: _freeze_verde()
    )

    relatorio = runner_ci.rodar_celula(raiz, "catalogo")

    assert relatorio.estado is Estado.CANCELLED
    assert any(r.estado is Estado.CANCELLED for r in relatorio.resultados)
