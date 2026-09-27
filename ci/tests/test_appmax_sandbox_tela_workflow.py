"""O passo que julga a matriz Appmax não pode ser pulado quando o remoto dá ERROR.

Achado replicado do PR #2249 (TAR-868) e desta mesma rodada em
`ci/operacoes_vps.py` e `ci/appmax_estorno_sandbox.py`: o script que a
`appleboy/ssh-action` roda pode sair 0 sempre (o veredito vem do JSON), mas o
passo que lê `steps.remoto.outputs.stdout` também precisa de `if: always()`
para nunca ser pulado quando o GitHub marca o passo remoto como falho por
outro motivo.
"""

from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[2]
WORKFLOW = RAIZ / ".github/workflows/appmax-sandbox-tela.yml"


def test_passo_de_julgamento_roda_sempre_mesmo_com_remoto_marcado_falho():
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    passos = doc["jobs"]["matriz"]["steps"]
    remoto = next(i for i, p in enumerate(passos) if p.get("id") == "remoto")
    julgamento = passos[remoto + 1]
    assert "steps.remoto.outputs.stdout" in julgamento["env"]["SAIDA"]
    assert julgamento.get("if") == "always() && steps.remoto.outcome != 'skipped'"
