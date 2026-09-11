"""A instalação do navegador se recupera sozinha de falhas transitórias."""

from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "muralhas.yml"


def test_navegador_tem_tres_tentativas_automaticas():
    texto = WORKFLOW.read_text(encoding="utf-8")
    assert "for tentativa in 1 2 3; do" in texto
    assert "npx playwright install --with-deps chromium" in texto
    assert "sudo rm -rf /var/lib/apt/lists/*" in texto
    assert "sudo apt-get clean" in texto
    assert "falhou após 3 tentativas automáticas" in texto
