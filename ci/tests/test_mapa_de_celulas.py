"""O MAPA DAS CÉLULAS e o varredor que o impede de mentir (Onda 5).

Um mapa é lido com confiança — é para isso que ele existe. Por isso o perigo
dele não é estar errado: é estar errado **em silêncio**. Nada quebra
visivelmente quando `celulas.yml` envelhece; o CI só passa a testar a coisa
errada e o deploy a publicar fora de ordem. É a Classe 8 (mapa velho), a única
doença deste projeto que já cobrou dentro do próprio trabalho de curá-la
(`armadilhas/148`).

Daí a forma destes testes: cada um SABOTA o mapa de um jeito diferente e exige
vermelho. Um teste que só rodasse o varredor contra o repositório são provaria
que ele roda — não que ele morde.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "ci"))

import mapa_de_celulas  # noqa: E402
from _nucleo import ErroDeInstrumentacao, Estado  # noqa: E402


def _cenario(tmp_path: Path, mapa_yml: str) -> Path:
    """Uma raiz com o mapa dado e o código real das células copiado por cima.

    O código é o do projeto porque a régua do varredor é o consumo REAL: um
    cenário com código inventado mediria o teste.
    """
    raiz = tmp_path / "repo"
    raiz.mkdir()
    (raiz / "celulas.yml").write_text(mapa_yml, encoding="utf-8")
    (raiz / "ci").mkdir()
    shutil.copy(
        RAIZ / "ci" / "manifesto-de-contratos.json",
        raiz / "ci" / "manifesto-de-contratos.json",
    )
    shutil.copytree(RAIZ / "services", raiz / "services")
    shutil.copytree(RAIZ / "painel", raiz / "painel", dirs_exist_ok=True)
    for marca in ("CONSTITUICAO.md", "INVARIANTES.md"):
        (raiz / marca).write_text("cenario", encoding="utf-8")
    (raiz / "contracts").mkdir(exist_ok=True)
    (raiz / "contracts" / "LEIA-ME.md").write_text("cenario", encoding="utf-8")
    return raiz


def _mapa_real() -> str:
    return (RAIZ / "celulas.yml").read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# O repositório real: o mapa diz a verdade HOJE
# --------------------------------------------------------------------------


def test_o_mapa_do_projeto_diz_a_verdade_sobre_o_codigo():
    relatorio = mapa_de_celulas.verificar(RAIZ)
    assert relatorio.estado is Estado.PASS, relatorio.render()


def test_o_varredor_enxerga_o_consumo_real_e_nao_uma_lista():
    """Se a convenção `<OUTRA>_API_URL` mudar, o varredor fica cego.

    Este teste mede o CONSUMO medido, não o declarado: ele afirma um fato
    conhecido do código (a `checkout` fala com `pagamentos`). Trocar a
    convenção sem ensinar o varredor deixa isto vermelho — que é o ponto.
    """
    mapa = mapa_de_celulas.carregar(RAIZ)
    medido = mapa_de_celulas.consumo_no_codigo(RAIZ, mapa)
    assert "pagamentos" in medido["checkout"]
    assert "identidade" in medido["admin"]
    assert medido["identidade"] == set(), "a identidade não consome ninguém"


# --------------------------------------------------------------------------
# As sabotagens — uma por forma de mentir
# --------------------------------------------------------------------------


def test_dependencia_escondida_reprova(tmp_path: Path):
    """O código consome e o mapa não declara: a ordem de publicação erraria."""
    mapa = _mapa_real().replace(
        "    caminhos: [services/checkout]\n    consome: [catalogo, pagamentos]",
        "    caminhos: [services/checkout]\n    consome: [catalogo]",
    )
    raiz = _cenario(tmp_path, mapa)
    relatorio = mapa_de_celulas.verificar(raiz)
    assert relatorio.estado is Estado.FAIL, relatorio.render()
    assert "checkout lê PAGAMENTOS_API_URL" in relatorio.render()


def test_declaracao_orfa_reprova(tmp_path: Path):
    """O mapa declara e o código não usa: é assim que um mapa envelhece."""
    mapa = _mapa_real().replace(
        "  leads:\n    caminhos: [services/leads]\n    consome: []",
        "  leads:\n    caminhos: [services/leads]\n    consome: [catalogo]",
    )
    raiz = _cenario(tmp_path, mapa)
    relatorio = mapa_de_celulas.verificar(raiz)
    assert relatorio.estado is Estado.FAIL, relatorio.render()
    assert "declara consumir catalogo" in relatorio.render()


def test_celula_no_manifesto_e_ausente_do_mapa_reprova(tmp_path: Path):
    linhas = _mapa_real().splitlines(keepends=True)
    fora = [
        ln
        for i, ln in enumerate(linhas)
        if not (
            ln.startswith("  forum:")
            or (i > 0 and linhas[i - 1].startswith("  forum:"))
            or (i > 1 and linhas[i - 2].startswith("  forum:"))
        )
    ]
    raiz = _cenario(tmp_path, "".join(fora))
    relatorio = mapa_de_celulas.verificar(raiz)
    assert relatorio.estado is Estado.FAIL, relatorio.render()
    assert "forum" in relatorio.render()


def test_caminho_declarado_que_nao_existe_reprova(tmp_path: Path):
    mapa = _mapa_real().replace(
        "    caminhos: [services/quiz]", "    caminhos: [services/quiz, services/nada]"
    )
    raiz = _cenario(tmp_path, mapa)
    relatorio = mapa_de_celulas.verificar(raiz)
    assert relatorio.estado is Estado.FAIL, relatorio.render()
    assert "services/nada" in relatorio.render()


@pytest.mark.parametrize(
    "conteudo",
    [
        "isto: não tem a chave certa\n",
        "celulas: {}\n",
        "celulas:\n  quiz: 'não é bloco'\n",
        "celulas:\n  quiz:\n    consome: []\n",  # sem caminhos
        "celulas:\n  quiz:\n    caminhos: [services/quiz]\n    consome: 'texto'\n",
    ],
)
def test_mapa_malformado_e_ERROR_e_nunca_um_mapa_vazio(tmp_path: Path, conteudo: str):
    """Mapa quebrado não pode virar "nenhuma célula existe".

    Se isso passasse como mapa vazio, o CI concluiria que o PR não toca célula
    nenhuma, pularia a suíte e o gate aceitaria o `skipped` como verde: merge
    liberado sem um único teste ter rodado. Foi um defeito assim que originou
    metade dos portões desta pasta.
    """
    raiz = tmp_path / "repo"
    raiz.mkdir()
    (raiz / "celulas.yml").write_text(conteudo, encoding="utf-8")
    with pytest.raises(ErroDeInstrumentacao):
        mapa_de_celulas.carregar(raiz)


def test_mapa_ausente_e_ERROR(tmp_path: Path):
    with pytest.raises(ErroDeInstrumentacao):
        mapa_de_celulas.carregar(tmp_path)


# --------------------------------------------------------------------------
# A pergunta que o resto do CI faz ao mapa
# --------------------------------------------------------------------------


def test_o_painel_pertence_a_admin_e_um_arquivo_solto_nao_pertence_a_ninguem():
    mapa = mapa_de_celulas.carregar(RAIZ)
    assert mapa_de_celulas.celula_do_caminho("painel/registros/x.js", mapa) == "admin"
    assert mapa_de_celulas.celula_do_caminho("services/quiz/app.py", mapa) == "quiz"
    assert mapa_de_celulas.celula_do_caminho("RITOS.md", mapa) is None
    assert mapa_de_celulas.celula_do_caminho("ci/ci.py", mapa) is None


def test_prefixo_casa_por_SEGMENTO_e_nao_por_texto():
    """`services/quiz` não pode capturar `services/quizzes`.

    Ainda não existe uma célula assim — e é por isso que o teste existe agora:
    no dia em que existir, o erro seria silencioso e o PR dela rodaria a suíte
    da célula errada.
    """
    mapa = mapa_de_celulas.carregar(RAIZ)
    assert mapa_de_celulas.celula_do_caminho("services/quizzes/app.py", mapa) is None


def test_celulas_do_diff_e_ordenado_e_sem_repeticao():
    mapa = mapa_de_celulas.carregar(RAIZ)
    achadas = mapa_de_celulas.celulas_do_diff(
        [
            "services/quiz/a.py",
            "services/quiz/b.py",
            "painel/registros/x.js",
            "README.md",
        ],
        mapa,
    )
    assert achadas == ["admin", "quiz"]


# --------------------------------------------------------------------------
# A fiação
# --------------------------------------------------------------------------


def test_o_varredor_roda_na_muralha():
    fonte = (RAIZ / "ci" / "ci.py").read_text(encoding="utf-8")
    assert "ci/mapa-de-celulas.sh" in fonte, (
        "o varredor saiu da muralha — sem ele o mapa volta a envelhecer em "
        "silêncio, que é o motivo de ele existir"
    )


def test_a_muralha_do_mapa_reprova_de_verdade(tmp_path: Path):
    """O portão inteiro, como processo, contra um mapa sabotado."""
    from conftest import BASH

    if BASH is None:
        pytest.skip("sem bash utilizável")
    mapa = _mapa_real().replace(
        "    caminhos: [services/checkout]\n    consome: [catalogo, pagamentos]",
        "    caminhos: [services/checkout]\n    consome: []",
    )
    raiz = _cenario(tmp_path, mapa)
    shutil.copy(RAIZ / "ci" / "mapa-de-celulas.sh", raiz / "ci" / "mapa-de-celulas.sh")
    for arquivo in ("mapa_de_celulas.py", "_nucleo.py"):
        shutil.copy(RAIZ / "ci" / arquivo, raiz / "ci" / arquivo)
    proc = subprocess.run(
        [BASH, str(raiz / "ci" / "mapa-de-celulas.sh")],
        cwd=str(raiz),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        check=False,
    )
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "PAGAMENTOS_API_URL" in proc.stdout


def test_todo_workflow_que_le_o_mapa_instala_o_leitor():
    """O mapa é YAML: sem PyYAML, quem o lê não conclui — e falha alto.

    Falhar alto é o certo, mas falhar SEMPRE não serve a ninguém. Este guarda
    existe porque o defeito apareceu dez minutos depois de o mapa nascer (run
    33251639130): o `detectar` do ci-celula não instalava o leitor, e o PR
    inteiro ficou vermelho por dependência ausente.
    """
    import yaml as _yaml

    pasta = RAIZ / ".github" / "workflows"
    for arquivo in sorted(pasta.glob("*.yml")):
        texto = arquivo.read_text(encoding="utf-8")
        if "ci.py --detectar-celulas" not in texto and "mapa_de_celulas" not in texto:
            continue
        fluxo = _yaml.safe_load(texto)
        instala = [
            passo
            for job in fluxo["jobs"].values()
            for passo in job.get("steps", [])
            if "pyyaml" in str(passo.get("run", "")).lower()
        ]
        assert instala, (
            f"{arquivo.name} lê o mapa das células e não instala o PyYAML — "
            "a detecção vai falhar alto em TODO PR"
        )
