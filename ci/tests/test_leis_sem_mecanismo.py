"""O CENSO DAS LEIS — e a catraca que impede a dívida de crescer (Onda 6).

A doença que este portão mede não é bug: é **regra escrita que ninguém impõe**.
Ela não falha, não apita e não aparece em teste nenhum — só é obedecida
enquanto alguém lembrar. A prova mais cara está na Parte 0 do plano mestre: uma
frase desatualizada do `RITOS.md`, lida com sinceridade, virou premissa falsa
entregue a cinco consultorias.

Os testes aqui cobrem os três jeitos de este portão falhar como instrumento:

    ficar cego     (não achar as leis, e chamar isso de "tudo em ordem")
    ficar cínico   (aceitar citação para um arquivo que não existe)
    ficar chato    (reprovar por causa de prosa entre crases, ensinando a ignorá-lo)

O terceiro é o menos óbvio e o mais perigoso: um portão que dá falso vermelho é
desligado por quem trabalha, e aí ele para de existir de verdade.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "ci"))

import leis_sem_mecanismo as censo  # noqa: E402
from _nucleo import ErroDeInstrumentacao, Estado  # noqa: E402


def _cenario(tmp_path: Path, leis: dict[str, str], divida: str = "") -> Path:
    """Uma raiz com arquivos-lei de mentira e a dívida dada."""
    raiz = tmp_path / "repo"
    (raiz / "ci").mkdir(parents=True)
    for nome, conteudo in leis.items():
        (raiz / nome).write_text(conteudo, encoding="utf-8")
    for nome in censo.ARQUIVOS_LEI:
        if not (raiz / nome).exists():
            (raiz / nome).write_text("# vazio\n", encoding="utf-8")
    (raiz / censo.DIVIDA).write_text(divida, encoding="utf-8")
    (raiz / "INVARIANTES.md").write_text("cenario\n", encoding="utf-8")
    (raiz / "contracts").mkdir()
    (raiz / "contracts" / "LEIA-ME.md").write_text("c\n", encoding="utf-8")
    (raiz / "services").mkdir()
    subprocess.run(["git", "init", "-q"], cwd=raiz, check=True)
    subprocess.run(["git", "add", "."], cwd=raiz, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Teste", "-c", "user.email=teste@example.com", "commit", "-qm", "fixture"],
        cwd=raiz,
        check=True,
    )
    subprocess.run(["git", "update-ref", "refs/remotes/origin/main", "HEAD"], cwd=raiz, check=True)
    return raiz


LEI_COM_PORTAO = (
    "# C\n\n## Lei 1 — Alguma coisa\n\nTexto da lei.\n\n"
    "**Quem faz valer:** `ci/existe.py`\n\n"
)
LEI_SEM_PORTAO = "# C\n\n## Lei 2 — Outra coisa\n\nSó texto, ninguém impõe.\n\n"


# --------------------------------------------------------------------------
# O repositório real
# --------------------------------------------------------------------------


def test_o_censo_do_projeto_esta_em_dia():
    # guarda: ci/leis_sem_mecanismo.py:193
    relatorio = censo.conferir(RAIZ)
    assert relatorio.estado is Estado.PASS, relatorio.render()


def test_o_censo_enxerga_as_leis_de_verdade():
    """Se o formato dos títulos mudar, o censo emudece — e emudecer é o pior.

    Um censo que encontra zero leis diria "nenhuma lei fora da lei", que é
    literalmente verdade e completamente falso.
    """
    leis = censo.levantar(RAIZ)
    ids = {lei.id for lei in leis}
    assert len(leis) >= 15, f"o censo só achou {len(leis)} leis"
    assert any("Lei 4" in i for i in ids), "sumiu a Lei 4 (separação de poderes)"
    assert any("§2" in i for i in ids), "sumiu o §2 do RITOS"


# --------------------------------------------------------------------------
# Ficar cego
# --------------------------------------------------------------------------


def test_arquivo_lei_ausente_e_ERROR(tmp_path: Path):
    raiz = tmp_path / "vazio"
    raiz.mkdir()
    with pytest.raises(ErroDeInstrumentacao):
        censo.levantar(raiz)


def test_zero_leis_e_ERROR_nunca_tudo_em_ordem(tmp_path: Path):
    raiz = _cenario(tmp_path, {"CONSTITUICAO.md": "sem títulos de lei aqui\n"})
    with pytest.raises(ErroDeInstrumentacao):
        censo.levantar(raiz)


def test_divida_ausente_e_ERROR(tmp_path: Path):
    raiz = _cenario(tmp_path, {"CONSTITUICAO.md": LEI_COM_PORTAO})
    (raiz / censo.DIVIDA).unlink()
    with pytest.raises(ErroDeInstrumentacao):
        censo.conferir(raiz)


# --------------------------------------------------------------------------
# A catraca
# --------------------------------------------------------------------------


def test_lei_sem_mecanismo_e_fora_da_divida_REPROVA(tmp_path: Path):
    raiz = _cenario(tmp_path, {"CONSTITUICAO.md": LEI_SEM_PORTAO})
    relatorio = censo.conferir(raiz)
    assert relatorio.estado is Estado.FAIL, relatorio.render()
    assert "Lei 2" in relatorio.render()


def test_lei_sem_mecanismo_declarada_na_divida_passa(tmp_path: Path):
    raiz = _cenario(
        tmp_path,
        {"CONSTITUICAO.md": LEI_SEM_PORTAO},
        divida="CONSTITUICAO.md::Lei 2 — Outra coisa   # motivo escrito\n",
    )
    relatorio = censo.conferir(raiz)
    assert relatorio.estado is Estado.PASS, relatorio.render()


def test_citacao_para_arquivo_que_NAO_existe_reprova(tmp_path: Path):
    """Pior que lei sem mecanismo: lei que PARECE imposta.

    Uma citação para um script apagado passa a impressão de garantia e não
    guarda nada — e o dia em que alguém confiar nela é o dia do incidente.
    """
    raiz = _cenario(tmp_path, {"CONSTITUICAO.md": LEI_COM_PORTAO})
    relatorio = censo.conferir(raiz)  # `ci/existe.py` não foi criado
    assert relatorio.estado is Estado.FAIL, relatorio.render()
    assert "ci/existe.py" in relatorio.render()


def test_citacao_para_arquivo_existente_passa(tmp_path: Path):
    raiz = _cenario(tmp_path, {"CONSTITUICAO.md": LEI_COM_PORTAO})
    (raiz / "ci" / "existe.py").write_text("# sou o portão\n", encoding="utf-8")
    relatorio = censo.conferir(raiz)
    assert relatorio.estado is Estado.PASS, relatorio.render()


def test_censo_igual_ao_remoto_PASS(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    raiz = _cenario(tmp_path, {"CONSTITUICAO.md": LEI_COM_PORTAO})
    (raiz / "ci" / "existe.py").write_text("# portão\n", encoding="utf-8")
    monkeypatch.setattr(censo, "_leis_de_origin_main", lambda _: censo.levantar(raiz))
    relatorio = censo.conferir(raiz)
    assert relatorio.estado is Estado.PASS, relatorio.render()


def test_censo_menor_sem_decisao_FAIL(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    raiz = _cenario(tmp_path, {"CONSTITUICAO.md": LEI_COM_PORTAO})
    remotas = censo.levantar(raiz) + [censo.Lei("CONSTITUICAO.md", "Lei remota", ())]
    monkeypatch.setattr(censo, "_leis_de_origin_main", lambda _: remotas)
    monkeypatch.setattr(censo, "_decisoes_novas", lambda _: [])
    relatorio = censo.conferir(raiz)
    assert relatorio.estado is Estado.FAIL, relatorio.render()
    assert "Lei remota" in relatorio.render()


def test_censo_menor_com_decisao_PASS(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    raiz = _cenario(tmp_path, {"CONSTITUICAO.md": LEI_COM_PORTAO})
    (raiz / "ci" / "existe.py").write_text("# portão\n", encoding="utf-8")
    remotas = censo.levantar(raiz) + [censo.Lei("CONSTITUICAO.md", "Lei remota", ())]
    monkeypatch.setattr(censo, "_leis_de_origin_main", lambda _: remotas)
    monkeypatch.setattr(censo, "_decisoes_novas", lambda _: ["docs/decisoes/DECISAO-nova.md"])
    relatorio = censo.conferir(raiz)
    assert relatorio.estado is Estado.PASS, relatorio.render()
    assert "DECISAO-nova.md" in relatorio.render()


def test_arquivo_novo_fora_do_padrao_nao_justifica(tmp_path: Path):
    raiz = _cenario(tmp_path, {"CONSTITUICAO.md": LEI_COM_PORTAO})
    (raiz / "ci" / "existe.py").write_text("# portão\n", encoding="utf-8")
    pasta = raiz / "docs" / "decisoes"
    pasta.mkdir(parents=True)
    (pasta / "nota.md").write_text("n\n", encoding="utf-8")
    (pasta / "DECISAO-x.txt").write_text("n\n", encoding="utf-8")
    (pasta / "DECISAO-x.md").write_text("n\n", encoding="utf-8")
    subprocess.run(["git", "add", "docs/decisoes"], cwd=raiz, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Teste", "-c", "user.email=teste@example.com", "commit", "-qm", "decisão"],
        cwd=raiz,
        check=True,
    )
    assert censo._decisoes_novas(raiz) == ["docs/decisoes/DECISAO-x.md"]
    (pasta / "DECISAO-x.md").unlink()
    subprocess.run(["git", "add", "docs/decisoes"], cwd=raiz, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Teste", "-c", "user.email=teste@example.com", "commit", "-qm", "remover decisão"],
        cwd=raiz,
        check=True,
    )
    assert censo._decisoes_novas(raiz) == []
    remotas = censo.levantar(raiz) + [censo.Lei("CONSTITUICAO.md", "Lei remota", ())]
    original = censo._leis_de_origin_main
    censo._leis_de_origin_main = lambda _: remotas
    try:
        relatorio = censo.conferir(raiz)
    finally:
        censo._leis_de_origin_main = original
    assert relatorio.estado is Estado.FAIL, relatorio.render()


def test_sem_git_e_ERROR(tmp_path: Path):
    raiz = tmp_path / "repo"
    (raiz / "ci").mkdir(parents=True)
    (raiz / "CONSTITUICAO.md").write_text(LEI_COM_PORTAO, encoding="utf-8")
    for nome in censo.ARQUIVOS_LEI:
        if not (raiz / nome).exists():
            (raiz / nome).write_text("# vazio\n", encoding="utf-8")
    (raiz / censo.DIVIDA).write_text("", encoding="utf-8")
    (raiz / "INVARIANTES.md").write_text("cenario\n", encoding="utf-8")
    (raiz / "contracts").mkdir()
    (raiz / "contracts" / "LEIA-ME.md").write_text("c\n", encoding="utf-8")
    (raiz / "services").mkdir()
    (raiz / "ci" / "existe.py").write_text("# portão\n", encoding="utf-8")
    with pytest.raises(ErroDeInstrumentacao, match=r"bancada sem \.git"):
        censo.conferir(raiz)


def test_origin_main_ilegivel_ERROR(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    raiz = _cenario(tmp_path, {"CONSTITUICAO.md": LEI_COM_PORTAO})
    monkeypatch.setattr(
        censo,
        "_leis_de_origin_main",
        lambda _: (_ for _ in ()).throw(
            ErroDeInstrumentacao("origin/main ilegível", "remoto indisponível")
        ),
    )
    with pytest.raises(ErroDeInstrumentacao, match="origin/main ilegível"):
        censo.conferir(raiz)


def test_decisoes_novas_filtra_nome_e_extensao(tmp_path: Path):
    raiz = _cenario(tmp_path, {"CONSTITUICAO.md": LEI_COM_PORTAO})
    pasta = raiz / "docs" / "decisoes"
    pasta.mkdir(parents=True)
    (pasta / "nota.md").write_text("n\n", encoding="utf-8")
    (pasta / "DECISAO-x.txt").write_text("n\n", encoding="utf-8")
    (pasta / "DECISAO-x.md").write_text("n\n", encoding="utf-8")
    subprocess.run(["git", "add", "docs/decisoes"], cwd=raiz, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Teste", "-c", "user.email=teste@example.com", "commit", "-qm", "decisão"],
        cwd=raiz,
        check=True,
    )
    assert censo._decisoes_novas(raiz) == ["docs/decisoes/DECISAO-x.md"]


# --------------------------------------------------------------------------
# Ficar chato — o falso vermelho que ensina a ignorar o portão
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "declaracao",
    [
        "**Quem faz valer:** `ci/existe.py` (recusa `--confirmo` fora da pista)",
        "**Quem faz valer:** `ci/existe.py` — sem `skip`, sem corpo vazio",
        "**Quem faz valer:** `ci/existe.py`; a `main` fica protegida",
    ],
)
def test_prosa_entre_crases_nao_e_caminho(tmp_path: Path, declaracao: str):
    """`--confirmo`, `skip` e `main` estão entre crases e não são arquivos.

    Tratá-los como caminho faria o portão procurar arquivos que nunca
    existiram e reprovar leis perfeitamente impostas. Falso vermelho ensina a
    ignorar o portão — e um portão ignorado morreu.
    """
    raiz = _cenario(
        tmp_path,
        {"CONSTITUICAO.md": f"# C\n\n## Lei 1 — X\n\nTexto.\n\n{declaracao}\n\n"},
    )
    (raiz / "ci" / "existe.py").write_text("#\n", encoding="utf-8")
    relatorio = censo.conferir(raiz)
    assert relatorio.estado is Estado.PASS, relatorio.render()


# --------------------------------------------------------------------------
# A fiação
# --------------------------------------------------------------------------


def test_o_censo_roda_na_muralha():
    fonte = (RAIZ / "ci" / "ci.py").read_text(encoding="utf-8")
    assert "ci/leis-sem-mecanismo.sh" in fonte


def test_a_muralha_erra_sem_git(tmp_path: Path):
    """Sem bancada Git, o processo termina em ERROR."""
    from conftest import BASH

    if BASH is None:
        pytest.skip("sem bash utilizável")
    raiz = tmp_path / "repo"
    (raiz / "ci").mkdir(parents=True)
    (raiz / "CONSTITUICAO.md").write_text(LEI_SEM_PORTAO, encoding="utf-8")
    for arquivo in ("RITOS.md", "CLAUDE.md"):
        (raiz / arquivo).write_text("# vazio\n", encoding="utf-8")
    (raiz / censo.DIVIDA).write_text("", encoding="utf-8")
    (raiz / "INVARIANTES.md").write_text("cenario\n", encoding="utf-8")
    (raiz / "contracts").mkdir()
    (raiz / "contracts" / "LEIA-ME.md").write_text("c\n", encoding="utf-8")
    (raiz / "services").mkdir()
    for arquivo in ("leis_sem_mecanismo.py", "_nucleo.py", "leis-sem-mecanismo.sh"):
        shutil.copy(RAIZ / "ci" / arquivo, raiz / "ci" / arquivo)
    proc = subprocess.run(
        [BASH, str(raiz / "ci" / "leis-sem-mecanismo.sh")],
        cwd=str(raiz),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        check=False,
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "bancada sem .git" in proc.stdout


def test_a_muralha_reprova_de_verdade(tmp_path: Path):
    """O portão inteiro, como processo, contra uma lei órfã."""
    from conftest import BASH

    if BASH is None:
        pytest.skip("sem bash utilizável")
    raiz = _cenario(tmp_path, {"CONSTITUICAO.md": LEI_SEM_PORTAO})
    for arquivo in ("leis_sem_mecanismo.py", "_nucleo.py", "leis-sem-mecanismo.sh"):
        shutil.copy(RAIZ / "ci" / arquivo, raiz / "ci" / arquivo)
    (raiz / "ci" / "ci.py").write_text("# c\n", encoding="utf-8")
    proc = subprocess.run(
        [BASH, str(raiz / "ci" / "leis-sem-mecanismo.sh")],
        cwd=str(raiz),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        check=False,
    )
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "Lei 2" in proc.stdout
