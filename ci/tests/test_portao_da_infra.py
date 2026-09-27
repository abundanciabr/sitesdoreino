"""O portão `infra` reprova quando um teste de `infra/test_*.py` reprova.

Até 27/09/2026 `infra/test_*.py` existia e não rodava em workflow nenhum: a
ativação da Appmax e o canário (TAR-802) só eram medidos na máquina de quem os
escreveu. Estes testes provam as duas metades do conserto: o portão distingue
teste bom de teste sabotado (num `infra/` falso, para que os testes reais sejam
medidos só pelo próprio portão) e o job `muralhas`, check obrigatório de todo
PR, continua chamando o portão.
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


def _infra_falsa(raiz: Path, esperado: str) -> Path:
    (raiz / "infra").mkdir(parents=True)
    (raiz / "infra" / "test_operacao.py").write_text(
        f"def test_a_operacao_devolve_o_esperado():\n    assert 'ativado' == {esperado!r}\n",
        encoding="utf-8",
    )
    return raiz


def test_teste_de_infra_bom_passa(tmp_path: Path) -> None:
    resultado = runner.rodar_testes_da_infra(_infra_falsa(tmp_path, "ativado"))
    assert resultado.estado is Estado.PASS, resultado


def test_teste_de_infra_sabotado_reprova(tmp_path: Path) -> None:
    resultado = runner.rodar_testes_da_infra(_infra_falsa(tmp_path, "desligado"))
    assert resultado.estado is Estado.FAIL, resultado


def test_o_job_muralhas_roda_o_portao_da_infra() -> None:
    workflow = yaml.safe_load(
        (RAIZ / ".github" / "workflows" / "muralhas.yml").read_text(encoding="utf-8")
    )
    comandos = [passo.get("run", "") for passo in workflow["jobs"]["muralhas"]["steps"]]
    assert "python ci/ci.py --apenas infra" in comandos, comandos
