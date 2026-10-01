"""A operação VPS provisionar recusa scripts que pedem valor externo."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


RAIZ = Path(__file__).resolve().parents[2]
PROVISIONADORES = sorted((RAIZ / "infra").glob("provisionar-*.sh"))
spec = importlib.util.spec_from_file_location("operar_provisionar", RAIZ / "infra" / "operar.py")
operar = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = operar
spec.loader.exec_module(operar)


def _linha_de_uso(script: Path) -> str | None:
    """Obtém o argumento da linha de uso do próprio arquivo."""
    for linha in script.read_text(encoding="utf-8").splitlines():
        if script.name not in linha or "bash /tmp/" not in linha:
            continue
        depois = linha.split("bash /tmp/", 1)[1]
        return depois.split(" ", 1)[1].strip() if " " in depois else ""
    return None


def _ctx(tmp_path: Path, chamadas: list) -> operar.Contexto:
    return operar.Contexto(
        raiz=RAIZ,
        ambiente={"PLATAFORMA_DIR": str(tmp_path), "OPERAR_ESTADO": str(tmp_path / "estado")},
        processo=lambda *args, **kwargs: chamadas.append((args, kwargs)) or (0, ""),
        espera=0,
    )


def test_a_cli_atual_expoe_provisionar_e_a_pasta_tem_os_scripts():
    assert len(PROVISIONADORES) >= 30
    op = operar.OPERACOES["provisionar"]
    assert op.executar is operar.op_provisionar
    assert [p.nome for p in op.params] == ["alvo"]
    assert op.params[0].obrigatorio


def test_a_prova_usa_cabecalhos_reais():
    com_valor = [s.name for s in PROVISIONADORES if _linha_de_uso(s)]
    assert len(com_valor) >= 7, com_valor


@pytest.mark.parametrize("script", PROVISIONADORES, ids=lambda s: s.stem)
def test_recusa_todo_script_que_pede_valor_antes_de_executar(script: Path, tmp_path, capsys):
    uso = _linha_de_uso(script)
    if not uso:
        pytest.skip(f"{script.name} não documenta valor em sua linha de uso")
    chamadas: list = []
    alvo = script.stem.removeprefix("provisionar-")
    assert operar.main(["provisionar", "--alvo", alvo], _ctx(tmp_path, chamadas)) == 1
    assert "espera um valor" in capsys.readouterr().out
    assert chamadas == []
    assert not (tmp_path / "publicacoes").exists()


@pytest.mark.parametrize("alvo", ["../env/admin", "nome;id", "$(id)", "A", "inexistente"])
def test_alvo_invalido_ou_inexistente_nao_executa_nada(alvo, tmp_path):
    chamadas: list = []
    assert operar.main(["provisionar", "--alvo", alvo], _ctx(tmp_path, chamadas)) != 0
    assert chamadas == []
    assert not (tmp_path / "publicacoes").exists()


def test_script_sem_parametro_chega_a_execucao_com_o_arquivo_certo(tmp_path, monkeypatch):
    script = next(s for s in PROVISIONADORES if _linha_de_uso(s) == "" and
                  not any(p in s.read_text(encoding="utf-8") for p in ("${1:-", "$@", "$#")))
    chamadas: list = []
    monkeypatch.setattr(operar, "fcntl", None)
    monkeypatch.setattr(operar, "_provisionar_sob_trava",
                        lambda ctx, alvo, arquivo: chamadas.append((alvo, arquivo)) or 0)
    alvo = script.stem.removeprefix("provisionar-")
    assert operar.main(["provisionar", "--alvo", alvo], _ctx(tmp_path, [])) == 0
    assert chamadas == [(alvo, script)]
