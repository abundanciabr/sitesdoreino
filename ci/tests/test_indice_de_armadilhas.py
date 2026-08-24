"""Guardas do índice das armadilhas — e das referências que apontam para ele.

Duas famílias de teste, com motivos diferentes:

1. **O índice está em dia.** Ele é gerado; gerado que ninguém confere volta a
   divergir na primeira entrada nova, e uma armadilha fora do índice é uma
   armadilha que ninguém acha — o mesmo efeito de ela não existir.
2. **Toda referência `§X.Y` ainda resolve.** O repositório cita armadilhas por
   número em mais de 200 lugares, 20 deles dentro de `services/**` — que a cerca
   (1 PR = 1 célula) proíbe reescrever num PR só. Por isso a âncora `§X.Y`
   continua sendo a forma canônica de citar, e a garantia de que ela aponta para
   algum lugar precisa ser MECÂNICA, não uma promessa do agente que particionou
   o arquivo.

Estes testes rodam dentro de `python ci/ci.py` (portão `testar-o-testador`) —
nenhum portão novo foi inventado para eles.
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

import indice_de_armadilhas as indice  # noqa: E402
from _nucleo import raiz_do_repo  # noqa: E402

RAIZ = raiz_do_repo()

# Este próprio arquivo cita `§X.Y` em exemplos e mensagens; varrê-lo tornaria o
# guarda um teste sobre si mesmo.
ARQUIVO_DESTE_TESTE = Path(__file__).resolve()


def _entrada(pasta: Path, nome: str, titulo: str, sintoma: str = "") -> Path:
    corpo = f"# {titulo}\n"
    if sintoma:
        corpo += f"\n**Sintoma:** {sintoma}\n"
    caminho = pasta / nome
    caminho.write_text(corpo, encoding="utf-8", newline="\n")
    return caminho


@pytest.fixture()
def repo_falso(tmp_path: Path) -> Path:
    pasta = tmp_path / indice.PASTA
    pasta.mkdir()
    _entrada(pasta, "001-primeira.md", "3.1 `Erro: coisa` explodindo", "o comando morre.")
    _entrada(pasta, "002-segunda.md", "Entrada nova sem § histórico", "outro erro cru.")
    return tmp_path


# --------------------------------------------------------------- geração


def test_regenerar_cria_o_indice_e_e_idempotente(repo_falso: Path) -> None:
    """Rodar duas vezes não pode produzir um byte diferente.

    Gerador não-idempotente vira diff em todo PR e, pior, ensina o agente a
    ignorar a mudança do índice — que é justamente onde a entrada nova aparece.
    """
    assert indice.rodar(repo_falso, conferir=False) == 0
    destino = repo_falso / indice.PASTA / indice.NOME_DO_INDICE
    primeira = destino.read_bytes()

    assert indice.rodar(repo_falso, conferir=False) == 0
    assert destino.read_bytes() == primeira


def test_toda_entrada_vira_uma_linha_do_indice(repo_falso: Path) -> None:
    indice.rodar(repo_falso, conferir=False)
    texto = (repo_falso / indice.PASTA / indice.NOME_DO_INDICE).read_text(
        encoding="utf-8"
    )
    assert "001-primeira.md" in texto
    assert "002-segunda.md" in texto
    assert "**2 entradas.**" in texto


def test_o_indice_nao_indexa_a_si_mesmo(repo_falso: Path) -> None:
    indice.rodar(repo_falso, conferir=False)
    indice.rodar(repo_falso, conferir=False)
    texto = (repo_falso / indice.PASTA / indice.NOME_DO_INDICE).read_text(
        encoding="utf-8"
    )
    assert "**2 entradas.**" in texto


def test_o_id_historico_do_titulo_vira_a_coluna_de_de_para(repo_falso: Path) -> None:
    indice.rodar(repo_falso, conferir=False)
    linhas = (repo_falso / indice.PASTA / indice.NOME_DO_INDICE).read_text(
        encoding="utf-8"
    ).splitlines()
    da_primeira = next(ln for ln in linhas if "001-primeira.md" in ln)
    assert da_primeira.endswith("| §3.1 |")
    da_segunda = next(ln for ln in linhas if "002-segunda.md" in ln)
    assert da_segunda.endswith("| — |")


# --------------------------------------------------------------- conferência


def test_conferir_reprova_quando_uma_entrada_nova_nao_foi_indexada(
    repo_falso: Path,
) -> None:
    """FAIL (1), não ERROR: o instrumento mediu, o conteúdo é que está velho."""
    assert indice.rodar(repo_falso, conferir=False) == 0
    assert indice.rodar(repo_falso, conferir=True) == 0

    _entrada(repo_falso / indice.PASTA, "003-terceira.md", "Armadilha recém-nascida")
    assert indice.rodar(repo_falso, conferir=True) == 1


def test_conferir_nao_escreve_nada(repo_falso: Path) -> None:
    """`--conferir` é read-only: um portão que conserta esconde a violação."""
    indice.rodar(repo_falso, conferir=False)
    destino = repo_falso / indice.PASTA / indice.NOME_DO_INDICE
    destino.write_text("índice sabotado\n", encoding="utf-8", newline="\n")

    assert indice.rodar(repo_falso, conferir=True) == 1
    assert destino.read_text(encoding="utf-8") == "índice sabotado\n"


# --------------------------------------------------- ERROR nunca vira PASS


def test_pasta_ausente_e_ERROR_e_nao_indice_vazio(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """[INV-CI01] 'não achei a pasta' é indistinguível de 'não há entradas'.

    Se isto virasse um índice vazio bem-sucedido, apagar `armadilhas/` deixaria
    a CI verde — a mesma família de falso-verde que este repositório inteiro
    combate. Medimos pelo `main`, que é o que produz o exit code de verdade.
    """
    monkeypatch.setattr(indice, "raiz_do_repo", lambda: tmp_path)
    assert indice.main([]) == 2


def test_pasta_vazia_e_ERROR(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / indice.PASTA).mkdir()
    monkeypatch.setattr(indice, "raiz_do_repo", lambda: tmp_path)
    assert indice.main([]) == 2


def test_entrada_sem_titulo_e_ERROR(
    repo_falso: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (repo_falso / indice.PASTA / "004-muda.md").write_text(
        "sem heading nenhum\n", encoding="utf-8", newline="\n"
    )
    monkeypatch.setattr(indice, "raiz_do_repo", lambda: repo_falso)
    assert indice.main(["--conferir"]) == 2


def test_conferir_do_repositorio_real_pela_linha_de_comando() -> None:
    """O caminho oficial (`python ci/indice_de_armadilhas.py --conferir`) roda.

    Testar só a função deixaria passar um script que estoura no argparse ou no
    import — portão que não consegue ser invocado não é portão.
    """
    proc = subprocess.run(
        [sys.executable, str(CI / "indice_de_armadilhas.py"), "--conferir"],
        cwd=str(RAIZ),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


# ------------------------------------------------- o repositório de verdade


def test_o_indice_do_repositorio_esta_em_dia() -> None:
    """O guarda que impede o inchaço de voltar por esquecimento."""
    assert indice.rodar(RAIZ, conferir=True) == 0


def test_nenhuma_entrada_ficou_fora_do_indice_real() -> None:
    pasta = RAIZ / indice.PASTA
    arquivos = {p.name for p in pasta.glob("*.md") if p.name != indice.NOME_DO_INDICE}
    texto = (pasta / indice.NOME_DO_INDICE).read_text(encoding="utf-8")
    faltando = sorted(n for n in arquivos if n not in texto)
    assert not faltando, f"entradas fora do índice: {faltando}"


# ------------------------------------------------- referências §X.Y resolvem

RE_CITACAO = re.compile(
    r"(?:ARMADILHAS[A-Z\-]*(?:\.md)?|RESOLVIDAS\.md)`?,?\s*"
    r"§([0-9]+(?:\.[0-9]+)*)"
)
RE_ID_DE_ENTRADA = re.compile(r"ID historico: §([0-9]+(?:\.[0-9]+)*)")
RE_H1_COM_ID = re.compile(r"^#\s+([0-9]+(?:\.[0-9]+)+)\s")
RE_H_COM_ID = re.compile(r"^#{2,3}\s+§?([0-9]+(?:\.[0-9]+)*)\s")

PASTAS_IGNORADAS = {".git", "__pycache__", "node_modules", ".pytest_cache"}
EXTENSOES_VARRIDAS = {".md", ".py", ".sh", ".yml", ".yaml", ".txt", ".exemplo", ".json"}


def _ids_conhecidos() -> set[str]:
    """Todo § que hoje resolve para algum lugar de verdade."""
    conhecidos: set[str] = set()

    for arquivo in (RAIZ / indice.PASTA).glob("*.md"):
        if arquivo.name == indice.NOME_DO_INDICE:
            continue
        texto = arquivo.read_text(encoding="utf-8")
        for achado in RE_ID_DE_ENTRADA.finditer(texto):
            conhecidos.add(achado.group(1))
        for linha in texto.splitlines():
            achado = RE_H1_COM_ID.match(linha)
            if achado:
                conhecidos.add(achado.group(1))

    for arquivo in (
        RAIZ / "ARMADILHAS.md",
        RAIZ / "ARMADILHAS-OPERACAO.md",
        RAIZ / "docs" / "historico" / "RESOLVIDAS.md",
    ):
        for linha in arquivo.read_text(encoding="utf-8").splitlines():
            achado = RE_H_COM_ID.match(linha)
            if achado:
                conhecidos.add(achado.group(1))

    # a seção-mãe de cada entrada continua sendo citável ("ARMADILHAS §4")
    conhecidos |= {ident.split(".")[0] for ident in conhecidos}
    return conhecidos


def _arquivos_do_repo() -> list[Path]:
    saida: list[Path] = []
    for caminho in RAIZ.rglob("*"):
        if not caminho.is_file():
            continue
        if any(parte in PASTAS_IGNORADAS for parte in caminho.parts):
            continue
        if caminho.resolve() == ARQUIVO_DESTE_TESTE:
            continue
        if caminho.suffix not in EXTENSOES_VARRIDAS and caminho.name != "Makefile":
            continue
        saida.append(caminho)
    return saida


def test_toda_referencia_a_uma_armadilha_resolve() -> None:
    """Referência pendurada custa a próxima sessão inteira.

    O agente lê "ARMADILHAS §5.3", não acha nada, e ou refaz a investigação do
    zero ou conclui que o documento mente. Este teste varre o repositório todo
    (inclusive `services/**`, que a cerca proíbe EDITAR mas não proíbe LER) e
    exige que cada número citado exista em `armadilhas/`, em
    `ARMADILHAS-OPERACAO.md`, no `ARMADILHAS.md` ou no histórico.
    """
    conhecidos = _ids_conhecidos()
    penduradas: list[str] = []
    for caminho in _arquivos_do_repo():
        try:
            texto = caminho.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if "ARMADILHAS" not in texto and "RESOLVIDAS" not in texto:
            continue
        for numero, linha in enumerate(texto.splitlines(), start=1):
            for achado in RE_CITACAO.finditer(linha):
                if achado.group(1) not in conhecidos:
                    rel = caminho.relative_to(RAIZ).as_posix()
                    penduradas.append(f"{rel}:{numero} -> §{achado.group(1)}")
    assert not penduradas, (
        "referência(s) a armadilha que não existe mais:\n  "
        + "\n  ".join(penduradas)
        + "\n\nOu a entrada foi renomeada sem atualizar quem a cita, ou o número "
        "está errado. Conserte a referência — nunca a ignore."
    )


def test_o_guarda_de_referencias_reprova_de_verdade() -> None:
    """Prova falsificável: um § inventado NÃO pode estar no conjunto conhecido."""
    conhecidos = _ids_conhecidos()
    assert "3.3" in conhecidos, "o §3.3 real sumiu — o guarda mediu a coisa errada"
    assert "1" in conhecidos, "o §1 (ARMADILHAS-OPERACAO) deveria resolver"
    assert "99.99" not in conhecidos
    achado = RE_CITACAO.search("ver ARMADILHAS §99.99 para detalhes")
    assert achado is not None and achado.group(1) == "99.99"
