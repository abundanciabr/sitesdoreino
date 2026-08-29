"""Guardas da régua viva (ci/medir_tempos.py + ci/tempos_esperados.json).

O teste mais importante deste arquivo é o do DECAIMENTO: ele roda o
`--conferir` contra o relógio REAL, e vai ficar vermelho sozinho quando a
régua passar de 45 dias sem recalibrar. Isso é DE PROPÓSITO — régua que
envelhece em silêncio é uma mentira confortável (RETROSPECTIVA-FASE-D §8), e
silêncio aqui vira check vermelho com instrução de conserto no texto.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

RAIZ_DO_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ_DO_REPO / "ci"))

import medir_tempos  # noqa: E402


# ------------------------------------------------------------ o decaimento --


def test_a_regua_esta_dentro_do_prazo_o_decaimento_mecanico(capsys):
    """ESTE TESTE APODRECE DE PROPÓSITO. Quando ficar vermelho, a régua passou
    de 45 dias: rode `python ci/medir_tempos.py --escrever` e commite o
    tempos_esperados.json recalculado — é o preço declarado de ter uma régua
    que nunca mente por velhice."""
    assert medir_tempos.conferir() == 0, capsys.readouterr().out


def test_regua_velha_reprova_com_instrucao_de_conserto(capsys):
    codigo = medir_tempos.conferir(agora=datetime(2099, 1, 1))
    saida = capsys.readouterr().out
    assert codigo == 1
    assert "FAIL" in saida
    assert "medir_tempos.py --escrever" in saida, "reprovou sem ensinar o conserto"


def test_regua_ilegivel_e_error_nunca_pass(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(medir_tempos, "REGUA", tmp_path / "nao-existe.json")
    assert medir_tempos.conferir() == 2
    assert "ERROR" in capsys.readouterr().out


# ------------------------------------------------------------- a medição ----


def _gh_de_mentira(tmp_path, monkeypatch, respostas: list, exit_code: int = 0):
    fita = tmp_path / "fita.json"
    fita.write_text(json.dumps(respostas), encoding="utf-8")
    fake = tmp_path / "gh_de_mentira.py"
    fake.write_text(
        "import json, sys, pathlib\n"
        f"fita = pathlib.Path(r'{fita}')\n"
        "respostas = json.loads(fita.read_text(encoding='utf-8'))\n"
        f"if {exit_code} != 0 or not respostas:\n"
        "    print('gh de mentira: caiu', file=sys.stderr)\n"
        f"    sys.exit({exit_code or 1})\n"
        "atual = respostas.pop(0)\n"
        "fita.write_text(json.dumps(respostas), encoding='utf-8')\n"
        "print(json.dumps(atual))\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MEDIR_GH", json.dumps([sys.executable, str(fake)]))


def _runs_de_checks(sha: str, inicio: str, fim: str) -> list[dict]:
    return [
        {"path": ".github/workflows/muralhas.yml", "status": "completed",
         "head_sha": sha, "run_started_at": inicio, "updated_at": fim},
        {"path": ".github/workflows/ci-celula.yml", "status": "completed",
         "head_sha": sha, "run_started_at": inicio, "updated_at": fim},
    ]


def test_medir_atualiza_checks_pouso_e_o_carimbo(tmp_path, monkeypatch):
    # duas voltas de checks: 60s e 120s → p50 = 90
    runs_pr = {"workflow_runs": (
        _runs_de_checks("aaa", "2026-08-29T10:00:00Z", "2026-08-29T10:01:00Z")
        + _runs_de_checks("bbb", "2026-08-29T11:00:00Z", "2026-08-29T11:02:00Z")
    )}
    runs_push = {"workflow_runs": [
        {"path": ".github/workflows/deploy-celula.yml", "status": "completed",
         "run_started_at": "2026-08-29T10:05:00Z",
         "updated_at": "2026-08-29T10:07:00Z"},
    ]}
    _gh_de_mentira(tmp_path, monkeypatch, [runs_pr, runs_push])
    log = tmp_path / "esperas.jsonl"
    log.write_text(
        json.dumps({"alvo": "pouso:452", "desfecho": "verde", "decorrido_s": 155})
        + "\n"
        + json.dumps({"alvo": "pouso:454", "desfecho": "estouro", "decorrido_s": 2700})
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MEDIR_LOG", str(log))

    nova, avisos = medir_tempos.medir(agora=datetime(2026, 9, 2))
    assert nova["esperas"]["checks"]["p50_s"] == 90
    assert nova["esperas"]["checks"]["amostra"] == 2
    assert nova["esperas"]["deploy-celula"]["p50_s"] == 120
    # estouro NÃO é duração medida — só o verde de 155s conta
    assert nova["esperas"]["pouso"]["p50_s"] == 155
    assert nova["esperas"]["pouso"]["amostra"] == 1
    assert nova["medido_em"] == "2026-09-02"


def test_fonte_que_falha_mantem_o_numero_antigo_nunca_inventa(tmp_path, monkeypatch):
    _gh_de_mentira(tmp_path, monkeypatch, [], exit_code=1)  # gh caiu
    monkeypatch.setenv("MEDIR_LOG", str(tmp_path / "nao-existe.jsonl"))
    antiga = json.loads(medir_tempos.REGUA.read_text(encoding="utf-8"))

    nova, avisos = medir_tempos.medir(agora=datetime(2026, 9, 2))
    # nada mediu ⇒ números antigos E carimbo antigo (o carimbo velho denuncia)
    assert nova["esperas"]["checks"] == antiga["esperas"]["checks"]
    assert nova["medido_em"] == antiga["medido_em"]
    assert any("mantive o antigo" in a for a in avisos)


def test_escrever_grava_via_cli(tmp_path, monkeypatch):
    copia = tmp_path / "tempos.json"
    copia.write_text(medir_tempos.REGUA.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(medir_tempos, "REGUA", copia)
    runs_pr = {"workflow_runs": _runs_de_checks(
        "aaa", "2026-08-29T10:00:00Z", "2026-08-29T10:01:00Z")}
    _gh_de_mentira(tmp_path, monkeypatch, [runs_pr, {"workflow_runs": []}])
    monkeypatch.setenv("MEDIR_LOG", str(tmp_path / "vazio.jsonl"))

    assert medir_tempos.main(["--escrever"]) == 0
    gravada = json.loads(copia.read_text(encoding="utf-8"))
    assert gravada["esperas"]["checks"]["p50_s"] == 60
    assert gravada["_leia_me"], "o cabeçalho explicativo não pode sumir na gravação"
