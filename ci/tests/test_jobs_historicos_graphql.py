"""Oito leituras de jobs viram uma consulta, sem perder identidade ou cobertura."""

import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import estado_da_entrega as entrega
from _nucleo import ErroDeInstrumentacao


def lote():
    return [dict(id=n, node_id=f"WFR_{n}", run_attempt=2) for n in range(1, 9)]


def resposta():
    return {"data": {"nodes": [
        dict(id=r["node_id"], databaseId=r["id"], runAttempt=r["run_attempt"],
             checkSuite={"checkRuns": dict(totalCount=2, pageInfo={"hasNextPage": False}, nodes=[
                 dict(name="deploy (admin)", status="COMPLETED", conclusion="FAILURE"),
                 dict(name="deploy (quiz)", status="COMPLETED", conclusion="SKIPPED"),
             ])}) for r in lote()
    ]}}


def test_oito_runs_em_uma_consulta_com_latest_e_tentativa(monkeypatch):
    chamadas = []
    dado = resposta()
    dado["data"]["nodes"].reverse()

    def executar(args, **kw):
        chamadas.append(args)
        return SimpleNamespace(stdout=json.dumps(dado))

    monkeypatch.setattr(entrega, "executar", executar)
    jobs = entrega.consultar_jobs_em_lote(Path.cwd(), lote())
    assert list(jobs) == list(range(1, 9))
    assert jobs[1] == [dict(name="deploy (admin)", status="completed", conclusion="failure"),
                       dict(name="deploy (quiz)", status="completed", conclusion="skipped")]
    assert len(chamadas) == 1
    assert chamadas[0][:3] == ["gh", "api", "graphql"]
    assert [a for a in chamadas[0] if a.startswith("ids[]=")] == [f"ids[]=WFR_{n}" for n in range(1, 9)]
    query = next(a for a in chamadas[0] if a.startswith("query="))
    assert "checkType: LATEST" in query and "runAttempt" in query


@pytest.mark.parametrize("defeito", [
    "errors", "sem_data", "sem_no", "id_errado", "database_errado", "tentativa_nova", "sem_suite",
    "paginado", "total_errado", "total_booleano", "jobs_ausentes", "status", "conclusao", "nome_vazio",
    "json_quebrado", "no_duplicado",
])
def test_resposta_parcial_ou_de_outra_tentativa_e_erro(monkeypatch, defeito):
    dado = resposta()
    no = dado["data"]["nodes"][0]
    checks = no["checkSuite"]["checkRuns"]
    if defeito == "errors": dado["errors"] = [{"message": "rate limit"}]
    elif defeito == "sem_data": dado.pop("data")
    elif defeito == "sem_no": dado["data"]["nodes"][0] = None
    elif defeito == "id_errado": no["id"] = "outro"
    elif defeito == "database_errado": no["databaseId"] = 100
    elif defeito == "tentativa_nova": no["runAttempt"] = 3
    elif defeito == "sem_suite": no["checkSuite"] = None
    elif defeito == "paginado": checks["pageInfo"]["hasNextPage"] = True
    elif defeito == "total_errado": checks["totalCount"] = 3
    elif defeito == "total_booleano": checks["totalCount"] = True
    elif defeito == "jobs_ausentes": checks["nodes"] = None
    elif defeito == "status": checks["nodes"][0]["status"] = "novo_enum"
    elif defeito == "conclusao": checks["nodes"][0]["conclusion"] = "novo_enum"
    elif defeito == "nome_vazio": checks["nodes"][0]["name"] = ""
    elif defeito == "no_duplicado": dado["data"]["nodes"][1] = copy.deepcopy(no)
    chamadas = []

    def executar(args, **kw):
        chamadas.append(args)
        return SimpleNamespace(stdout="{" if defeito == "json_quebrado" else json.dumps(dado))

    monkeypatch.setattr(entrega, "executar", executar)
    with pytest.raises(ErroDeInstrumentacao, match="confira|repita"):
        entrega.consultar_jobs_em_lote(Path.cwd(), lote())
    assert len(chamadas) == 1


def test_node_id_ausente_nao_inventa_identidade(monkeypatch):
    runs = lote()
    runs[0].pop("node_id")
    monkeypatch.setattr(entrega, "executar", lambda *a, **kw: pytest.fail("consultou sem node_id"))
    with pytest.raises(ErroDeInstrumentacao):
        entrega.consultar_jobs_em_lote(Path.cwd(), runs)
