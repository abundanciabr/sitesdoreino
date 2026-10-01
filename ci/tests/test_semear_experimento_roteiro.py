"""O experimento recebe apenas uma das três ações pela operação VPS atual."""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import BASH


RAIZ = Path(__file__).resolve().parents[2]
ROTEIRO = RAIZ / "infra" / "semear-experimento.sh"
COMANDO = RAIZ / "services" / "admin" / "apps" / "core" / "management" / "commands" / "semear_experimento.py"
spec = importlib.util.spec_from_file_location("operar_experimento", RAIZ / "infra" / "operar.py")
operar = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = operar
spec.loader.exec_module(operar)


def _rodar(*argumentos: str, tmp_path: Path) -> subprocess.CompletedProcess:
    assert BASH, "sem bash utilizável nesta máquina o roteiro não tem como ser medido"
    return subprocess.run(
        [BASH, str(ROTEIRO), *argumentos], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=60, check=False,
        env={"PATH": "/usr/bin:/bin", "PLATAFORMA_DIR": str(tmp_path / "nao-existe")},
    )


def test_host_no_lugar_da_acao_e_recusado_antes_da_vps(tmp_path):
    for host in ("outro.site", "meshcraft.top", "basileiatoutheou.org"):
        resultado = _rodar(host, "iniciar-aa", tmp_path=tmp_path)
        assert resultado.returncode == 0, resultado.stderr
        saida = resultado.stdout
        assert "PAROU POR SEGURANÇA: o semeador não recebe o site" in saida
        assert f"('{host}')" in saida
        assert "só serve meshcraft.top" in saida and "congelado" in saida
        assert "não achei" not in saida


def test_acao_desconhecida_e_recusada_antes_da_vps(tmp_path):
    resultado = _rodar("promover", tmp_path=tmp_path)
    assert resultado.returncode == 0, resultado.stderr
    assert "a ação 'promover' não existe" in resultado.stdout
    assert "não achei" not in resultado.stdout


def test_a_operacao_so_recebe_acao_por_argv_e_entrega_por_env(tmp_path):
    op = operar.OPERACOES["semear-experimento"]
    assert [p.nome for p in op.params] == ["acao"]
    assert op.params[0].obrigatorio and op.params[0].env == "ACAO_EXPERIMENTO"
    chamadas = []

    def processo(comando, *, env, timeout, **_):
        chamadas.append((comando, env.copy(), timeout))
        return 0, "PRONTO: ok\n"

    ctx = operar.Contexto(
        raiz=RAIZ, ambiente={"PLATAFORMA_DIR": str(tmp_path),
                            "OPERAR_ESTADO": str(tmp_path / "estado"),
                            "ACAO_EXPERIMENTO": "encerrar"},
        processo=processo, espera=0,
    )
    assert operar.main(["semear-experimento", "--acao", "medir"], ctx) == 0
    assert chamadas[0][0] == ["bash", "-n", str(ROTEIRO)]
    assert chamadas[1][0] == ["bash", str(ROTEIRO)]
    assert chamadas[1][1]["ACAO_EXPERIMENTO"] == "medir"
    assert chamadas[1][2] == 5 * 60


def test_as_tres_acoes_sao_as_mesmas_na_cli_no_roteiro_e_no_comando():
    (do_roteiro,) = re.findall(
        r"^  ([a-z|-]+)\) ;;$", ROTEIRO.read_text(encoding="utf-8"), re.MULTILINE
    )
    (do_comando,) = re.findall(r"choices=\(([^)]*)\)", COMANDO.read_text(encoding="utf-8"))
    esperadas = ["iniciar-aa", "encerrar", "medir"]
    assert list(operar.OPERACOES["semear-experimento"].params[0].escolhas) == esperadas
    assert do_roteiro.split("|") == esperadas
    assert re.findall(r'"([a-z-]+)"', do_comando) == esperadas


@pytest.mark.parametrize("argumentos", [[], ["--acao", "promover"], ["--acao", "medir;id"],
                                         ["--host", "outro.site", "--acao", "medir"]])
def test_cli_recusa_pedido_invalido_antes_de_chamar_script(argumentos, tmp_path):
    chamadas = []
    ctx = operar.Contexto(
        raiz=RAIZ,
        ambiente={"PLATAFORMA_DIR": str(tmp_path), "OPERAR_ESTADO": str(tmp_path / "estado")},
        processo=lambda *args, **kwargs: chamadas.append((args, kwargs)) or (0, ""), espera=0,
    )
    assert operar.main(["semear-experimento", *argumentos], ctx) == 2
    assert chamadas == []
