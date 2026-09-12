"""A fila pode aguardar checks; o portão do merge continua recusando-os."""
import json

import pytest

import mergear
from _nucleo import Estado, Relatorio, Resultado


def relatorio(*resultados):
    r = Relatorio("pedido de pouso")
    for resultado in resultados:
        r.registrar(resultado)
    return r


def pr(checks=None, **campos):
    return {"number": 99, "state": "OPEN", "isDraft": False,
            "mergeable": "MERGEABLE", "mergeStateStatus": "CLEAN",
            "headRefOid": "a" * 40, "statusCheckRollup": checks or [], **campos}


@pytest.mark.parametrize("status", ["IN_PROGRESS", "QUEUED", "WAITING", "REQUESTED"])
def test_pendente_entra_na_fila_mas_nao_passa_no_portao(status):
    dados = pr([{"name": "muralhas", "status": status, "conclusion": None}])
    r = relatorio(*mergear.checar_checks(dados))
    assert r.estado is Estado.ERROR
    assert mergear.pode_aguardar_na_pista(r, dados)


def test_checks_ainda_nao_criados_podem_aguardar_na_fila():
    # guarda: ci/mergear.py:999
    dados = pr()
    r = relatorio(*mergear.checar_checks(dados))
    assert r.estado is Estado.ERROR
    assert mergear.pode_aguardar_na_pista(r, dados)


@pytest.mark.parametrize("nome,estado", [
    ("consulta GitHub", Estado.ERROR), ("registro a bordo", Estado.ERROR),
    ("revisão independente", Estado.FAIL), ("dívida do livro", Estado.FAIL),
])
def test_pendencia_de_checks_nao_esconde_recusa(nome, estado):
    dados = pr()
    r = relatorio(*mergear.checar_checks(dados), Resultado(nome, estado, "recusado"))
    assert not mergear.pode_aguardar_na_pista(r, dados)


def test_check_reprovado_nao_e_espera():
    # guarda: ci/mergear.py:1006
    dados = pr([{"name": "muralhas", "status": "COMPLETED", "conclusion": "FAILURE"}])
    assert not mergear.pode_aguardar_na_pista(relatorio(*mergear.checar_checks(dados)), dados)


@pytest.mark.parametrize("mergeable", ["CONFLICTING", None, "corrompido"])
def test_conflito_ou_resposta_invalida_nao_entra_na_fila(mergeable):
    dados = pr(mergeable=mergeable)
    r = relatorio(mergear.checar_mergeabilidade(dados), *mergear.checar_checks(dados))
    assert not mergear.pode_aguardar_na_pista(r, dados)


def test_base_atrasada_e_checks_pendentes_sao_responsabilidade_da_pista():
    dados = pr(mergeStateStatus="BEHIND")
    r = relatorio(mergear.checar_mergeabilidade(dados), *mergear.checar_checks(dados))
    assert mergear.pode_aguardar_na_pista(r, dados)


def test_fila_devolve_json_e_confere_etiqueta_sem_merge(monkeypatch, capsys):
    dados = pr()
    chamadas = []
    monkeypatch.setattr(mergear, "conferir", lambda n: (relatorio(*mergear.checar_checks(dados)), dados))
    monkeypatch.setattr(mergear, "raiz_do_repo", lambda: ".")

    def gh(args, *resto, **kwargs):
        chamadas.append(args)
        return json.dumps({"state": "OPEN", "headRefOid": "a" * 40,
                           "labels": [{"name": "pousar"}]}) if args[:2] == ["pr", "view"] else ""

    monkeypatch.setattr(mergear, "_gh", gh)
    assert mergear.main(["99", "--pousar"]) == 0
    saida = capsys.readouterr().out
    assert len(saida.encode()) < 500
    assert json.loads(saida)["estado"] == "ENFILEIRADO"
    assert any(c[:2] == ["pr", "view"] for c in chamadas)
    assert not any(c[:2] == ["pr", "merge"] for c in chamadas)


def test_etiqueta_nao_confirmada_nao_anuncia_sucesso(monkeypatch, capsys):
    # guarda: ci/mergear.py:1028
    monkeypatch.setattr(mergear, "raiz_do_repo", lambda: ".")
    monkeypatch.setattr(mergear, "_gh", lambda *a, **k: json.dumps({"state": "OPEN", "headRefOid": "a" * 40, "labels": []}))
    assert mergear.pedir_pouso(99, "a" * 40) == 2
    assert json.loads(capsys.readouterr().out)["estado"] == "ERROR"


@pytest.mark.parametrize("remoto", [
    {"state": "OPEN", "headRefOid": "b" * 40, "labels": [{"name": "pousar"}]},
    {"state": "CLOSED", "headRefOid": "a" * 40, "labels": [{"name": "pousar"}]},
    {"state": "OPEN", "headRefOid": "a" * 40, "labels": None},
    [], "resposta inválida",
])
def test_resposta_remota_incoerente_nao_confirma_pedido(monkeypatch, capsys, remoto):
    monkeypatch.setattr(mergear, "raiz_do_repo", lambda: ".")
    monkeypatch.setattr(mergear, "_gh", lambda *a, **k: json.dumps(remoto))
    assert mergear.pedir_pouso(99, "a" * 40) == 2
    assert json.loads(capsys.readouterr().out)["estado"] == "ERROR"


def test_falha_de_consulta_nao_empresta_aprovacao(monkeypatch, capsys):
    monkeypatch.setattr(mergear, "raiz_do_repo", lambda: ".")
    def falhar(*args, **kwargs):
        raise mergear.ErroDeInstrumentacao("consulta falhou", "sem rede")
    monkeypatch.setattr(mergear, "_gh", falhar)
    assert mergear.pedir_pouso(99, "a" * 40) == 2
    assert json.loads(capsys.readouterr().out)["acao"]


@pytest.mark.parametrize("campos", [{"state": "CLOSED"}, {"isDraft": True}])
def test_pr_fechado_ou_rascunho_nao_entra_na_fila(campos):
    dados = pr(**campos)
    assert not mergear.pode_aguardar_na_pista(relatorio(*mergear.checar_checks(dados)), dados)


def test_github_calculando_mergeabilidade_pode_aguardar():
    dados = pr(mergeable="UNKNOWN")
    r = relatorio(mergear.checar_mergeabilidade(dados), *mergear.checar_checks(dados))
    assert mergear.pode_aguardar_na_pista(r, dados)


@pytest.mark.parametrize("mergeable", ["UNKNOWN", "MERGEABLE", "CONFLICTING"])
def test_estado_dirty_recusa_fila_e_merge(mergeable):
    dados = pr(mergeable=mergeable, mergeStateStatus="DIRTY")
    conflito = mergear.checar_mergeabilidade(dados)
    assert conflito.estado is Estado.FAIL
    r = relatorio(conflito, *mergear.checar_checks(dados))
    assert not mergear.pode_aguardar_na_pista(r, dados)


def test_recusa_estruturada_preserva_diagnostico_sem_etiquetar(monkeypatch, capsys):
    dados = pr()
    r = relatorio(Resultado("recibo", Estado.FAIL, "recibo ausente"))
    monkeypatch.setattr(mergear, "conferir", lambda n: (r, dados))
    monkeypatch.setattr(mergear, "_gh", lambda *a, **k: pytest.fail("não pode etiquetar"))
    assert mergear.main(["99", "--pousar"]) == 1
    saida = json.loads(capsys.readouterr().out)
    assert saida["estado"] == "RECUSADO"
    assert saida["motivos"] == [{"verificacao": "recibo", "estado": "FAIL", "resumo": "recibo ausente"}]
