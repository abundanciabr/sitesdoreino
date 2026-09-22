"""O fecho vivo não entrega a continuação a um papel que não está na sessão."""

from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
FRASE = "devolva à maestro"
ARQUIVOS = (
    "ci/pr.py",
    "ci/mandato_por_faixa.py",
    "CAMINHO-DOURADO.md",
)


def linhas_ativas(relativo: str) -> list[str]:
    texto = (RAIZ / relativo).read_text(encoding="utf-8")
    return [
        linha
        for linha in texto.splitlines()
        if not linha.lstrip().startswith("#") and not linha.lstrip().startswith("pass ")
    ]


def test_os_caminhos_vivos_nao_entregam_a_continuacao_a_outro_papel():
    # guarda: ci/pr.py:822
    for relativo in ARQUIVOS:
        ativas = "\n".join(linhas_ativas(relativo))
        assert FRASE not in ativas, relativo
    fecho = [
        linha
        for linha in linhas_ativas("ci/pr.py")
        if "PR {numero} aberto com recibo" in linha
    ]
    assert len(fecho) == 1
    assert "A sessão encerra aqui." in fecho[0]


@pytest.mark.parametrize("relativo", (
    "00-LEIA-PRIMEIRO.md",
    "ARMADILHAS.md",
    "ARMADILHAS-OPERACAO.md",
    "CAMINHO-DOURADO.md",
    "docs/guia-mantenedor.md",
))
def test_orientacao_ativa_nao_reativa_papeis_fixos(relativo):
    texto = (RAIZ / relativo).read_text(encoding="utf-8").lower()
    if relativo == "ARMADILHAS-OPERACAO.md":
        texto = texto.split("---", 1)[0]
    for frase in ("a maestro", "à maestro", "maestro (claude code)",
                  "codex, o executor", "codex executa", "antigravity audita"):
        assert frase not in texto, (relativo, frase)
