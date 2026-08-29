"""A muralha do painel, testada nos três estados (INV-CI01).

Um portão que nunca foi visto reprovando é um portão que ninguém sabe se
reprova. Aqui a muralha roda de verdade, como processo, nos TRÊS estados do
dialeto: contra o repositório real (PASS, exit 0), contra cópias sabotadas
(FAIL, exit 1 — manifesto atrasado, registro inválido, livro apagado) e contra
uma cópia onde o INSTRUMENTO não consegue medir (ERROR, exit 2).

O caso de ERROR só entrou na auditoria de 26/08/2026 — e ele faltava porque a
muralha lia o código do passo com `$?` depois de um `if !`, recebendo sempre 0:
ela imprimia "(exit 0)" ao reprovar e rebaixava todo ERROR a FAIL. O estado que
este arquivo dizia cobrir era exatamente o único que ninguém media.

A suíte adversarial fina do gerador (sintaxe quebrada, nome errado, ERROR de
pasta ausente) mora em painel/testes/teste_gerador.js e roda DENTRO da própria
muralha — reprovar lá reprova aqui.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import BASH

RAIZ = Path(__file__).resolve().parents[2]
MURALHA = RAIZ / "ci" / "muralha-do-painel.sh"

pytestmark = pytest.mark.skipif(
    BASH is None or shutil.which("node") is None,
    reason="a muralha do painel precisa de bash utilizável E node no PATH",
)


def _roda(cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [BASH, str(MURALHA)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        check=False,
    )


def _copia_painel(tmp_path: Path) -> Path:
    """Uma raiz falsa com painel/ copiado do repositório real."""
    raiz_falsa = tmp_path / "repo"
    raiz_falsa.mkdir()
    shutil.copytree(RAIZ / "painel", raiz_falsa / "painel")
    return raiz_falsa


MARCAS_DA_RAIZ = ("CONSTITUICAO.md", "INVARIANTES.md", "ci", "contracts", "services")


def _copia_com_git(tmp_path: Path) -> Path:
    """A raiz falsa completa: painel/, ci/ e um repositório Git de verdade.

    O último passo da muralha (`ci/verificar_painel.py`) parte de `git ls-files`
    — sem repositório ele não tem como medir, e o cenário mediria outra coisa.
    """
    raiz = _copia_painel(tmp_path)
    shutil.copy(RAIZ / ".gitignore", raiz / ".gitignore")
    (raiz / "ci").mkdir(exist_ok=True)
    for arquivo in ("verificar_painel.py", "_nucleo.py"):
        shutil.copy(RAIZ / "ci" / arquivo, raiz / "ci" / arquivo)
    for marca in MARCAS_DA_RAIZ:
        alvo = raiz / marca
        if not alvo.exists():
            if marca.endswith(".md"):
                alvo.write_text("cenário de teste" + chr(10), encoding="utf-8")
            else:
                alvo.mkdir(exist_ok=True)
    for comando in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "teste@exemplo"],
        ["git", "config", "user.name", "teste"],
        ["git", "add", "-A"],
        ["git", "commit", "-q", "-m", "cenário"],
    ):
        subprocess.run(comando, cwd=str(raiz), check=True, capture_output=True, timeout=120)
    return raiz


def test_passa_no_repositorio_real() -> None:
    proc = _roda(RAIZ)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_registro_novo_e_MATERIALIZADO_e_nao_reprovado(tmp_path: Path) -> None:
    """A lei mudou em 28/08/2026, e este teste é onde ela se lê.

    ANTES: registro novo sem regenerar o manifesto REPROVAVA — e é por isso que
    todo PR carregava dois arquivos gerados, que colidiam entre si a cada dia
    movimentado (`armadilhas/156`).

    AGORA: os artefatos não moram mais no Git. A muralha os CONSTRÓI, e um
    registro novo é simplesmente materializado. O que continua reprovando é
    registro INVÁLIDO (teste abaixo) e artefato gerado de volta no índice.
    """
    raiz_falsa = _copia_com_git(tmp_path)
    registro_novo = raiz_falsa / "painel" / "registros" / "20260826-999-registro-do-teste.js"
    registro_novo.write_text(
        '(function(){ (window.REGISTROS = window.REGISTROS || []).push({'
        'arquivo: "20260826-999-registro-do-teste", tipo: "nota", quando: "2026-08-26",'
        'titulo: "t", detalhe: "d", autoridade: "sessao", evidencia: null,'
        'verificado_em: null, precisa_do_dono: false, responde_a: null,'
        'gravidade: "info", frente: null, vence_em_dias: null});})();' + chr(10),
        encoding="utf-8",
    )
    subprocess.run(
        ["git", "add", "-A"], cwd=str(raiz_falsa), check=True, capture_output=True, timeout=120
    )
    proc = _roda(raiz_falsa)
    assert proc.returncode == 0, (
        "registro novo tem de ser MATERIALIZADO pela muralha, não reprovado:"
        + chr(10) + proc.stdout + proc.stderr
    )
    assert (raiz_falsa / "painel" / "painel.html").is_file()


def test_reprova_com_gerado_de_volta_no_indice_do_git(tmp_path: Path) -> None:
    """O escritor único, medido: artefato commitado tem de ficar vermelho.

    É a única divergência do painel que não se conserta regenerando — e é a que
    reabriria, em silêncio, a colisão diária que a Onda 3 fechou.
    """
    raiz_falsa = _copia_com_git(tmp_path)
    subprocess.run(
        ["node", "painel/gerar_manifesto.js"],
        cwd=str(raiz_falsa), check=True, capture_output=True, timeout=300,
    )
    subprocess.run(
        ["git", "add", "-f", "painel/painel.html"],
        cwd=str(raiz_falsa), check=True, capture_output=True, timeout=120,
    )
    proc = _roda(raiz_falsa)
    saida = proc.stdout + proc.stderr
    assert proc.returncode == 1, "gerado no índice do Git TEM de reprovar:" + chr(10) + saida
    assert "painel/painel.html" in saida and "git rm --cached" in saida


def test_reprova_com_registro_invalido(tmp_path: Path) -> None:
    raiz_falsa = _copia_painel(tmp_path)
    algum = next((raiz_falsa / "painel" / "registros").glob("*.js"))
    algum.write_text(algum.read_text(encoding="utf-8").replace('tipo: "', 'tipo: "inventado-'),
                     encoding="utf-8")
    proc = _roda(raiz_falsa)
    assert proc.returncode == 1, "registro com tipo inventado TEM de reprovar"


def test_instrumento_que_nao_mede_e_error_2_nunca_fail_1(tmp_path: Path) -> None:
    """ERROR (2) tem de chegar inteiro ao runner — não pode virar FAIL (1).

    A pasta de registros existe mas está VAZIA: o gerador chama isso de ERROR
    ("livro vazio é sinal de pasta errada, não de projeto parado"), e a muralha
    precisa repassar esse 2. Enquanto ela lia o código com `$?` depois de um
    `if !`, este caso saía como exit 1 com "(exit 0)" impresso na tela — FAIL de
    conteúdo no lugar de instrumento quebrado, que é o falso-verde ao contrário.
    """
    raiz_falsa = _copia_painel(tmp_path)
    for registro in (raiz_falsa / "painel" / "registros").glob("*.js"):
        registro.unlink()
    proc = _roda(raiz_falsa)
    saida = proc.stdout + proc.stderr
    assert proc.returncode == 2, f"instrumento que não mede é ERROR (2), veio {proc.returncode}: {saida}"
    assert "(exit 2)" in saida, "a muralha tem de IMPRIMIR o código real do passo, não um 0 inventado"
    assert "NÃO é um OK" in saida


def test_reprova_sem_o_livro(tmp_path: Path) -> None:
    raiz_sem_painel = tmp_path / "repo-vazio"
    raiz_sem_painel.mkdir()
    proc = _roda(raiz_sem_painel)
    assert proc.returncode == 1, "apagar/mover painel/registros não pode passar verde"
    assert "não existe" in proc.stdout
