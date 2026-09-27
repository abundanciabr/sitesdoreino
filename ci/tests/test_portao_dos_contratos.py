"""O portão `contratos` reprova quando um esquema de `contracts/` quebra.

Até 26/09/2026 `contracts/test_*.py` existia e não rodava em workflow nenhum.
Estes testes provam as duas metades do conserto: o portão distingue esquema
bom de esquema sabotado (num `contracts/` falso, para que os esquemas reais
sejam medidos só pelo próprio portão) e o job `muralhas`, check obrigatório de
todo PR, continua chamando o portão.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

CI = Path(__file__).resolve().parents[1]
if str(CI) not in sys.path:
    sys.path.insert(0, str(CI))

import ci as runner  # noqa: E402
from _nucleo import Estado  # noqa: E402

RAIZ = CI.parent

TESTE_DO_ESQUEMA = '''
import json
from pathlib import Path


def test_o_esquema_exige_o_campo():
    esquema = json.loads((Path(__file__).parent / "eventos" / "evento.v1.json").read_text())
    assert esquema["required"] == ["campo"]
'''


def _contratos_falsos(raiz: Path, esquema: str) -> Path:
    (raiz / "contracts" / "eventos").mkdir(parents=True)
    (raiz / "contracts" / "eventos" / "evento.v1.json").write_text(esquema, encoding="utf-8")
    (raiz / "contracts" / "test_evento.py").write_text(TESTE_DO_ESQUEMA, encoding="utf-8")
    return raiz


def test_esquema_bom_passa(tmp_path: Path) -> None:
    raiz = _contratos_falsos(tmp_path, '{"required": ["campo"]}')
    resultado = runner.rodar_testes_de_contrato(raiz)
    assert resultado.estado is Estado.PASS, resultado


def test_esquema_que_aceita_tudo_reprova(tmp_path: Path) -> None:
    raiz = _contratos_falsos(tmp_path, "{}")
    resultado = runner.rodar_testes_de_contrato(raiz)
    assert resultado.estado is Estado.FAIL, resultado


def test_o_job_muralhas_roda_o_portao_dos_contratos() -> None:
    workflow = yaml.safe_load(
        (RAIZ / ".github" / "workflows" / "muralhas.yml").read_text(encoding="utf-8")
    )
    comandos = [passo.get("run", "") for passo in workflow["jobs"]["muralhas"]["steps"]]
    assert "python ci/ci.py --apenas contratos" in comandos, comandos
