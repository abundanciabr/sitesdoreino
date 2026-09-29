"""Rodadas de validação preservam o vínculo entre início e resultado."""
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import telemetria


def observacao(**campos):
    return dict(tarefa="TAR-959", tentativa="tentativa-1", branch="codex/pme01-medicao",
                commit="a" * 40, pr=None, fase="validacao", resultado="iniciado",
                contexto_bytes=None, **campos)


def test_identidade_legada_permanece_a_mesma():
    dados = observacao()
    esperado = hashlib.sha256(json.dumps(dados, sort_keys=True).encode()).hexdigest()
    assert telemetria.identidade_fase(dados) == esperado


def test_rodadas_do_mesmo_candidato_nao_se_confundem():
    assert telemetria.identidade_fase(observacao(rodada=1)) != telemetria.identidade_fase(observacao(rodada=2))


@pytest.mark.parametrize("rodada", [True, 0, -1, "1", 1.5])
def test_rodada_invalida_nao_vira_observacao(rodada):
    assert telemetria.identidade_fase(observacao(rodada=rodada)) is None


def test_escrita_preserva_rodada_e_candidato(tmp_path):
    (tmp_path / ".git").mkdir()
    campos = dict(tarefa="TAR-959", tentativa="tentativa-1", branch="codex/pme01-medicao",
                  commit="a" * 40, cwd=str(tmp_path))
    assert telemetria.registrar_fase("candidato", "concluido", **campos)
    for resultado in ("iniciado", "falhou"):
        assert telemetria.registrar_fase("validacao", resultado, rodada=123, **campos)
    eventos = telemetria.ler_tudo(tmp_path / ".git")
    assert [(e["fase"], e["resultado"], e.get("rodada")) for e in eventos] == [
        ("candidato", "concluido", None), ("validacao", "iniciado", 123), ("validacao", "falhou", 123)]
    assert all(e["id"] == telemetria.identidade_fase(e) for e in eventos)
