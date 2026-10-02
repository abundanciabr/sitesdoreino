"""A senha do banco não atravessa o caminho automático de publicação.

Os roteiros que a publicação roda na VPS publicam uma célula, copiam o banco e
sincronizam a infraestrutura sem abrir os envs reais nem receber a senha do
Postgres. O infra/restaurar-backup.sh fica fora: roda à mão, e numa VPS nova
ele tira de env/ a senha de cada papel do banco.
"""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]

SCRIPTS_AUTOMATICOS = (
    RAIZ / "infra" / "deploy-celula-na-vps.sh",
    RAIZ / "infra" / "backup-do-banco.sh",
)

NOMES_DA_CREDENCIAL = (
    "SENHA_DB",
    "POSTGRES_PASSWORD",
    "POSTGRES_SUPER_PASSWORD",
    "DATABASE_URL",
)


def _linhas_de_codigo(caminho: Path) -> list[str]:
    return [
        linha
        for linha in caminho.read_text(encoding="utf-8").splitlines()
        if linha.strip() and not linha.lstrip().startswith("#")
    ]


def test_scripts_automaticos_nao_abrem_credencial_do_banco() -> None:
    """O robô publica sem ter a senha, não por confiar num comentário."""
    for caminho in SCRIPTS_AUTOMATICOS:
        codigo = "\n".join(_linhas_de_codigo(caminho))
        for nome in NOMES_DA_CREDENCIAL:
            assert nome not in codigo, (
                f"{caminho.name} alcança {nome}; a publicação deve funcionar "
                "sem abrir a credencial do banco"
            )
        assert not re.search(r"(?:source|\.)\s+[^\n]*\.env", codigo), (
            f"{caminho.name} abre um arquivo .env durante a publicação"
        )
