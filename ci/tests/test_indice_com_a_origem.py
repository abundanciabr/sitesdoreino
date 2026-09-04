"""O ÍNDICE (E O SINO) DO ESPELHO ATRASADO SE GERAM DA ORIGEM, NÃO DA PASTA VELHA.

O DEFEITO (TAR-050, medido em 30/08/2026 por dois robôs e remedido em 04/09/2026)
--------------------------------------------------------------------------------
Os hooks rodam de `${CLAUDE_PROJECT_DIR}`, o clone PRINCIPAL, que é espelho e
fica semanas atrás de `origin/main`. `SINAIS.json` é gerado ali, no
`SessionStart`, a partir dos `armadilhas/*.md` DAQUELA pasta. Resultado: o sino
de toda sessão enxergava as assinaturas do dia em que o espelho parou (7 em vez
de 45 em 30/08; 151 em vez de 168 em 04/09, com 195 commits de atraso), e
consertos já mergeados não valiam para ninguém.

A CURA, E O QUE ESTES TESTES PROVAM
-----------------------------------
`rodar(..., com_a_origem=True)` gera da UNIÃO das entradas de `origin/main`
(lidas do cache do git, sem rede) com as da pasta, a pasta vencendo por número.
`--tambem-aqui` (o modo do `SessionStart`) liga isso sozinho quando a árvore é
o clone principal.

1. Numa árvore DELIBERADAMENTE atrasada, o número de assinaturas ANTES (só a
   pasta) e DEPOIS (união) — e o depois é maior.
2. Uma entrada NOVA, que só existe na pasta (ainda não em `origin/main`),
   continua sendo enxergada.
3. A pasta vence quando os dois lados têm o mesmo número.
4. "Não consegui ler a origem" fala e gera só da pasta — nunca finge que a
   origem está vazia.
5. Dono de guarda que só existe na origem não é referência morta.
6. No repositório REAL, a união não perde nenhuma entrada local.

Tudo por ASSERÇÃO e sem rede (`armadilhas/195`): os repositórios são fabricados
em `tmp_path` com um `origin` de mentira (bare) ao lado.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

CI = Path(__file__).resolve().parents[1]
if str(CI) not in sys.path:
    sys.path.insert(0, str(CI))

import indice_de_armadilhas as indice  # noqa: E402
from _nucleo import raiz_do_repo  # noqa: E402

RAIZ = raiz_do_repo()

GIT = ["git", "-c", "user.name=teste", "-c", "user.email=teste@exemplo.test",
       "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false"]


def _git(pasta: Path, *args: str) -> str:
    proc = subprocess.run(
        [*GIT, "-C", str(pasta), *args], capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False, timeout=60,
    )
    assert proc.returncode == 0, f"git {' '.join(args)} falhou:\n{proc.stderr}"
    return proc.stdout


def _entrada(numero: int, sinal: str, dono: str = "ci/indice_de_armadilhas.py") -> str:
    return (
        "---\nschema_version: 2\n"
        f"armadilha: {numero}\nestado: guardada\ndegrau: 3\nconfianca: alta\n"
        "custo_por_queda: alto\nguarda:\n  tipo: CI\n"
        f"  dono: {dono}\nsinal:\n  - `{sinal}`\n---\n\n"
        f"# Entrada {numero}\n\n**Sintoma:** o comando morre com {sinal}.\n"
    )


def _escrever(raiz: Path, relativo: str, conteudo: str) -> None:
    alvo = raiz / relativo
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(conteudo, encoding="utf-8", newline="\n")


@pytest.fixture()
def casa(tmp_path: Path) -> dict[str, Path]:
    """Um `origin` bare, um clone PRINCIPAL que vai ficar atrasado, e um segundo
    clone (a "outra sessão") que empurra a entrada 002 para a origem."""
    origem = tmp_path / "origem.git"
    _git(tmp_path, "init", "--bare", "-b", "main", str(origem))

    principal = tmp_path / "principal"
    _git(tmp_path, "clone", "-q", str(origem), str(principal))
    _escrever(principal, "ci/indice_de_armadilhas.py", "# dublê do dono\n")
    _escrever(principal, f"{indice.PASTA}/001-primeira.md",
              _entrada(1, "ErroUm: coisa \\d+ nao encontrada"))
    _git(principal, "add", "-A")
    _git(principal, "commit", "-q", "-m", "primeira")
    _git(principal, "push", "-q", "-u", "origin", "main")

    outra = tmp_path / "outra-sessao"
    _git(tmp_path, "clone", "-q", str(origem), str(outra))
    _escrever(outra, f"{indice.PASTA}/002-segunda.md",
              _entrada(2, "ErroDois: schema \\d+ ausente", dono="ci/so_na_origem.py"))
    _escrever(outra, "ci/so_na_origem.py", "# o dono da 002 só existe na origem\n")
    _git(outra, "add", "-A")
    _git(outra, "commit", "-q", "-m", "segunda")
    _git(outra, "push", "-q", "origin", "main")

    # O espelho faz `git fetch` (permitido) mas o HEAD não anda: exatamente o
    # estado do clone principal desta casa.
    _git(principal, "fetch", "-q", "origin")
    assert _git(principal, "rev-list", "--count", "HEAD..origin/main").strip() == "1"
    return {"principal": principal, "origem": origem, "outra": outra}


def _sinais(raiz: Path) -> list[str]:
    corpo = json.loads((raiz / indice.PASTA / indice.NOME_DOS_SINAIS).read_text(encoding="utf-8"))
    return sorted(s["regex"] for s in corpo["sinais"])


# ---------------------------------------------------------------------------
# 1 e 2: o número antes e depois, e a entrada nova que só existe na pasta.
# ---------------------------------------------------------------------------
def test_arvore_atrasada_ve_mais_assinaturas_com_a_origem_e_nao_perde_a_nova(casa) -> None:
    principal = casa["principal"]
    # A entrada NOVA desta sessão: só na pasta, ainda não commitada em lugar nenhum.
    _escrever(principal, f"{indice.PASTA}/003-nova.md",
              _entrada(3, "ErroTres: porta \\d+ fechada"))

    assert indice.rodar(principal, conferir=False) == 0
    antes = _sinais(principal)
    assert antes == ["ErroTres: porta \\d+ fechada", "ErroUm: coisa \\d+ nao encontrada"], (
        "ANTES: só a pasta velha — a 002, já mergeada na origem, é invisível"
    )

    assert indice.rodar(principal, conferir=False, com_a_origem=True) == 0
    depois = _sinais(principal)
    assert depois == [
        "ErroDois: schema \\d+ ausente",
        "ErroTres: porta \\d+ fechada",
        "ErroUm: coisa \\d+ nao encontrada",
    ], "DEPOIS: a 002 da origem entrou, e a 003 (nova, só local) continua lá"
    assert len(depois) > len(antes)

    texto = (principal / indice.PASTA / indice.NOME_DO_INDICE).read_text(encoding="utf-8")
    assert "[002](002-segunda.md)" in texto
    assert "[003](003-nova.md)" in texto
    assert "1 entrada(s) deste índice ainda NÃO existem nesta pasta" in texto
    assert "`002-segunda.md`" in texto
    assert f"git show {indice.REF_DA_VERDADE}:{indice.PASTA}/<arquivo>" in texto


def test_a_uniao_e_idempotente_e_o_conferir_concorda(casa) -> None:
    principal = casa["principal"]
    assert indice.rodar(principal, conferir=False, com_a_origem=True) == 0
    primeira = (principal / indice.PASTA / indice.NOME_DO_INDICE).read_bytes()
    assert indice.rodar(principal, conferir=True, com_a_origem=True) == 0
    assert indice.rodar(principal, conferir=False, com_a_origem=True) == 0
    assert (principal / indice.PASTA / indice.NOME_DO_INDICE).read_bytes() == primeira


# ---------------------------------------------------------------------------
# 3: a pasta vence pelo número.
# ---------------------------------------------------------------------------
def test_a_pasta_local_vence_quando_o_numero_e_o_mesmo(casa) -> None:
    principal = casa["principal"]
    # A sessão editou a 001 localmente (sinal novo). A origem tem a versão antiga.
    _escrever(principal, f"{indice.PASTA}/001-primeira.md",
              _entrada(1, "ErroUm: coisa \\d+ SUMIU de vez"))
    assert indice.rodar(principal, conferir=False, com_a_origem=True) == 0
    sinais = _sinais(principal)
    assert "ErroUm: coisa \\d+ SUMIU de vez" in sinais
    assert "ErroUm: coisa \\d+ nao encontrada" not in sinais, "a origem passou por cima da pasta"


# ---------------------------------------------------------------------------
# 4: não medir a origem FALA, e nunca vira "origem vazia".
# ---------------------------------------------------------------------------
def test_sem_origem_gera_so_da_pasta_e_avisa(tmp_path: Path, capsys) -> None:
    raiz = tmp_path / "sem-git"
    _escrever(raiz, "ci/indice_de_armadilhas.py", "# dublê\n")
    _escrever(raiz, f"{indice.PASTA}/001-primeira.md", _entrada(1, "ErroUm: coisa \\d+ nao encontrada"))
    assert indice.coletar_da_origem(raiz) is None
    assert indice.rodar(raiz, conferir=False, com_a_origem=True) == 0
    assert _sinais(raiz) == ["ErroUm: coisa \\d+ nao encontrada"]
    err = capsys.readouterr().err
    assert "não consegui ler `origin/main`" in err
    assert "TAR-050" in err


def test_clone_sem_a_ref_da_origem_tambem_e_nao_medi(casa) -> None:
    outra = casa["outra"]
    _git(outra, "remote", "rename", "origin", "espelho")
    assert indice.coletar_da_origem(outra) is None
    assert indice.caminhos_da_origem(outra) is None


# ---------------------------------------------------------------------------
# 5: dono que só existe na origem não é referência morta.
# ---------------------------------------------------------------------------
def test_dono_de_guarda_que_so_existe_na_origem_nao_e_referencia_morta(casa) -> None:
    principal = casa["principal"]
    assert not (principal / "ci" / "so_na_origem.py").exists(), "premissa: o dono da 002 não está aqui"
    assert indice.rodar(principal, conferir=False, com_a_origem=True) == 0
    assert "ErroDois: schema \\d+ ausente" in _sinais(principal)


def test_dono_morto_na_origem_e_no_disco_continua_ERROR(casa) -> None:
    """Conferir contra a origem afrouxa só o que a origem prova; um dono que não
    existe em lugar nenhum continua sendo ERROR."""
    outra = casa["outra"]
    _escrever(outra, f"{indice.PASTA}/004-quarta.md",
              _entrada(4, "ErroQuatro: nada \\d+", dono="ci/nao_existe_em_lugar_nenhum.py"))
    _git(outra, "add", "-A")
    _git(outra, "commit", "-q", "-m", "quarta com dono morto")
    _git(outra, "push", "-q", "origin", "main")
    principal = casa["principal"]
    _git(principal, "fetch", "-q", "origin")
    with pytest.raises(indice.ErroDeInstrumentacao, match="004-quarta.md"):
        indice.rodar(principal, conferir=False, com_a_origem=True)


# ---------------------------------------------------------------------------
# A fiação: --tambem-aqui liga a origem SÓ no clone principal.
# ---------------------------------------------------------------------------
def test_e_o_principal_distingue_clone_de_worktree(casa) -> None:
    principal = casa["principal"]
    assert indice.e_o_principal(principal) is True
    bancada = principal.parent / "bancada"
    _git(principal, "worktree", "add", "-q", str(bancada), "origin/main")
    try:
        assert indice.e_o_principal(bancada) is False
    finally:
        _git(principal, "worktree", "remove", "--force", str(bancada))


def test_tambem_aqui_liga_a_origem_no_principal(casa, monkeypatch) -> None:
    principal = casa["principal"]
    monkeypatch.setattr(indice, "raiz_do_repo", lambda inicio=None: principal)
    monkeypatch.chdir(principal)
    assert indice.main(["--tambem-aqui"]) == 0
    assert "ErroDois: schema \\d+ ausente" in _sinais(principal), (
        "o SessionStart do espelho (--tambem-aqui) tem de gerar da origem"
    )


def test_sem_flag_nenhuma_o_comportamento_antigo_continua(casa, monkeypatch) -> None:
    """`make indice`, o pre-commit e a muralha do CI chamam sem flag: nada muda para eles."""
    principal = casa["principal"]
    monkeypatch.setattr(indice, "raiz_do_repo", lambda inicio=None: principal)
    monkeypatch.chdir(principal)
    assert indice.main([]) == 0
    assert _sinais(principal) == ["ErroUm: coisa \\d+ nao encontrada"]


# ---------------------------------------------------------------------------
# 6: prova de fora, no repositório real.
# ---------------------------------------------------------------------------
def test_no_repositorio_real_a_uniao_nao_perde_nenhuma_entrada_local() -> None:
    locais = indice.coletar(RAIZ)
    da_origem = indice.coletar_da_origem(RAIZ)
    if da_origem is None:
        pytest.skip("origin/main não está no cache deste checkout (clone raso?)")
    todas, so_na_origem = indice.unir(locais, da_origem)
    nomes = {e.nome for e in todas}
    assert {e.nome for e in locais} <= nomes, "a união perdeu entrada local"
    assert sum(len(e.sinais) for e in todas) >= sum(len(e.sinais) for e in locais)
    assert all(e.origem != "local" for e in so_na_origem)
