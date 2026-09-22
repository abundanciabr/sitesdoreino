from pathlib import Path


RAIZ = Path(__file__).resolve().parents[2]


def test_instrucoes_ativas_nao_devolvem_pouso_ou_conferencia_ao_mantenedor():
    arquivos = (
        ".claude/agents/despacho.md",
        ".codex/agents/despacho.toml",
        "PLAYBOOK.md",
        "RUNBOOK-LOTES.md",
        "docs/despachos/DESPACHO-PARTE-DO-SITE.md",
        "docs/caixa-de-sugestoes/MODELO-DESPACHO.md",
    )
    proibidas = (
        "pede pouso à mão",
        "pede pouso a mão",
        "mantenedor cola",
        "autorize o disparo",
        "confira o merge",
    )
    for nome in arquivos:
        texto = (RAIZ / nome).read_text(encoding="utf-8").lower()
        assert not any(frase in texto for frase in proibidas), nome


def test_vigia_dispara_a_pista_em_vez_de_abrir_fila_humana():
    workflow = (RAIZ / ".github/workflows/vigia-do-pouso.yml").read_text(
        encoding="utf-8"
    )

    assert "pull-requests: write" in workflow
    assert "actions: write" in workflow
    assert "ci/mergear.py --automatico" in workflow
    assert "gh issue create" in workflow
    assert "gh pr edit" not in workflow
    assert "gh workflow run pouso.yml" not in workflow
    assert "issues: write" not in workflow
