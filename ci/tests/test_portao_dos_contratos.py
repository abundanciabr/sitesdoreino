"""O portão `contratos` reprova quando um esquema de `contracts/` quebra.

Até 26/09/2026 `contracts/test_*.py` existia e não rodava em workflow nenhum.
Estes testes provam as duas metades do conserto: o portão morde num esquema
sabotado (numa cópia, nunca no repositório real) e o job `muralhas`, check
obrigatório de todo PR, continua chamando o portão.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import yaml

CI = Path(__file__).resolve().parents[1]
if str(CI) not in sys.path:
    sys.path.insert(0, str(CI))

import ci as runner  # noqa: E402
from _nucleo import Estado  # noqa: E402

RAIZ = CI.parent


def _copia_dos_contratos(destino: Path) -> Path:
    shutil.copytree(RAIZ / "contracts", destino / "contracts")
    return destino


def test_contratos_intactos_passam(tmp_path: Path) -> None:
    resultado = runner.rodar_testes_de_contrato(_copia_dos_contratos(tmp_path))
    assert resultado.estado is Estado.PASS, resultado


def test_esquema_que_aceita_tudo_reprova(tmp_path: Path) -> None:
    raiz = _copia_dos_contratos(tmp_path)
    (raiz / "contracts" / "eventos" / "funil.pagina-vista.v1.json").write_text(
        "{}", encoding="utf-8"
    )
    resultado = runner.rodar_testes_de_contrato(raiz)
    assert resultado.estado is Estado.FAIL, resultado


def test_o_job_muralhas_roda_o_portao_dos_contratos() -> None:
    workflow = yaml.safe_load(
        (RAIZ / ".github" / "workflows" / "muralhas.yml").read_text(encoding="utf-8")
    )
    comandos = [passo.get("run", "") for passo in workflow["jobs"]["muralhas"]["steps"]]
    assert "python ci/ci.py --apenas contratos" in comandos, comandos
