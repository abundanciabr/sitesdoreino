"""A senha do banco não atravessa o caminho automático de publicação.

O workflow só precisa da chave SSH para chegar à VPS. O script remoto pode
publicar uma célula, sincronizar a infraestrutura e restaurar um backup sem
abrir os envs reais nem receber a senha do Postgres.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[2]

SCRIPTS_AUTOMATICOS = (
    RAIZ / "infra" / "deploy-celula-na-vps.sh",
    RAIZ / "infra" / "sincronizar-infra-na-vps.sh",
    RAIZ / "infra" / "restaurar-backup.sh",
)

WORKFLOWS_DE_PUBLICACAO = (
    RAIZ / ".github" / "workflows" / "deploy-celula.yml",
    RAIZ / ".github" / "workflows" / "deploy-infra.yml",
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


def test_workflows_de_publicacao_nao_transportam_credencial_do_banco() -> None:
    """O canal automático leva somente o acesso SSH, nunca o env da produção."""
    for caminho in WORKFLOWS_DE_PUBLICACAO:
        fluxo = json.dumps(
            yaml.safe_load(caminho.read_text(encoding="utf-8")),
            ensure_ascii=False,
        )
        for nome in NOMES_DA_CREDENCIAL:
            assert nome not in fluxo, (
                f"{caminho.name} passou a transportar {nome} no Actions"
            )
        assert '"env/' not in fluxo, (
            f"{caminho.name} passou a copiar um env real para a publicação"
        )
