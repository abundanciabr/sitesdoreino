"""Entrada da recuperação aceita célula provada ou seleção automática."""
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rollback


def test_manual_valida_celula_e_motivo_antes_de_ssh(monkeypatch, tmp_path):
    destino = tmp_path / "outputs"
    monkeypatch.setenv("ROLLBACK_CELULA", "funil")
    monkeypatch.setenv("ROLLBACK_MOTIVO", "endereço indisponível")
    monkeypatch.setenv("ROLLBACK_MODO", "recuperar")
    monkeypatch.setenv("GITHUB_OUTPUT", str(destino))
    assert rollback.main(["validar-celula"]) == 0
    assert "celula=funil" in destino.read_text()


def test_vigia_pode_selecionar_automaticamente(monkeypatch):
    monkeypatch.setenv("ROLLBACK_CELULA", "")
    monkeypatch.setenv("ROLLBACK_MOTIVO", "indisponibilidade confirmada")
    monkeypatch.setenv("ROLLBACK_MODO", "recuperar-auto")
    monkeypatch.setattr(rollback, "recuperar", lambda: 0)
    assert rollback.main([]) == 0
    assert rollback.os.environ["REVERSAO_CELULA"] == ""


@pytest.mark.parametrize("celula,modo,motivo", [("inventada", "recuperar", "falha"), ("funil", "recuperar-auto", "falha"), ("funil", "recuperar", ""), ("", "congelar", "falha")])
def test_entrada_invalida_nao_acessa_recuperacao(monkeypatch, celula, modo, motivo):
    monkeypatch.setenv("ROLLBACK_CELULA", celula)
    monkeypatch.setenv("ROLLBACK_MOTIVO", motivo)
    monkeypatch.setenv("ROLLBACK_MODO", modo)
    monkeypatch.setattr(rollback, "recuperar", lambda: pytest.fail("não recuperar"))
    assert rollback.main([]) == 1
