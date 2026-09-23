"""O fecho vivo não entrega a continuação a um papel que não está na sessão."""

from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
FRASE = "devolva à maestro"
ARQUIVOS = (
    "ci/pr.py",
    "ci/mandato_por_faixa.py",
    "ci/sessao.py",
    "ci/esperar.py",
    "ci/mapa_de_execucao.py",
    ".codex/agents/despacho.toml",
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
    # guarda: ci/pr.py:832
    for relativo in ARQUIVOS:
        ativas = "\n".join(linhas_ativas(relativo))
        assert FRASE not in ativas, relativo
    fecho = [
        linha
        for linha in linhas_ativas("ci/pr.py")
        if "PR {numero} aberto com recibo" in linha
    ]
    assert len(fecho) == 1
    assert "A sessão encerra aqui." not in "\n".join(linhas_ativas("ci/pr.py"))
    assert "Meça o desfecho nesta sessão" in "\n".join(linhas_ativas("ci/pr.py"))


def test_o_mapa_atribui_acompanhamento_a_quem_executa():
    texto = (RAIZ / "ci/mapa_de_execucao.py").read_text(encoding="utf-8")
    assert 'dono="executor"' in texto
    assert 'dono="maestro"' not in texto
    assert '"Maestro:' not in texto


def test_o_resumo_da_fabrica_nao_usa_o_papel_encerrado_no_nome():
    assert (RAIZ / "ci/resumo_da_fabrica.py").is_file()
    assert not (RAIZ / "ci/resumo_maestro.py").exists()


@pytest.mark.parametrize("relativo", (
    "00-LEIA-PRIMEIRO.md",
    "ARMADILHAS.md",
    "ARMADILHAS-OPERACAO.md",
    "CAMINHO-DOURADO.md",
    "docs/guia-mantenedor.md",
    "PLAYBOOK.md",
    "docs/caixa-de-sugestoes/MODELO-DESPACHO.md",
    "RUNBOOK-LOTES.md",
    "docs/decisoes/DECISAO-triade-de-ias.md",
    "docs/decisoes/DECISAO-revisao-e-publicacao.md",
    "docs/decisoes/PLANO-ORQUESTRACAO-AUTONOMA-DOS-ROBOS.md",
))
def test_orientacao_ativa_nao_reativa_papeis_fixos(relativo):
    texto = (RAIZ / relativo).read_text(encoding="utf-8").lower()
    if relativo == "ARMADILHAS-OPERACAO.md":
        texto = texto.split("---", 1)[0]
    for frase in ("a maestro", "à maestro", "maestro (claude code)",
                  "codex, o executor", "codex executa", "antigravity audita"):
        assert frase not in texto, (relativo, frase)


def test_protocolos_revogados_apontam_para_o_historico_sem_instruir_a_sessao():
    for relativo in (
        "RUNBOOK-LOTES.md",
        "docs/decisoes/DECISAO-triade-de-ias.md",
        "docs/decisoes/DECISAO-revisao-e-publicacao.md",
        "docs/decisoes/PLANO-ORQUESTRACAO-AUTONOMA-DOS-ROBOS.md",
    ):
        texto = (RAIZ / relativo).read_text(encoding="utf-8").lower()
        assert "históric" in texto, relativo
        assert "https://github.com/abundanciabr/sitesdoreino/blob/" in texto, relativo
        assert "a maestro entrega" not in texto, relativo
