import importlib.util
import json
from pathlib import Path

import pytest


RAIZ = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("operacoes_vps_coordenacao", RAIZ / "ci/operacoes_vps.py")
ops = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ops)


def test_leitura_coordenacao_usa_postgres_fixo_e_aspas_de_identificadores(monkeypatch):
    chamadas = []
    respostas = [
        json.dumps(["admin", "coordenacao_db", "postgres"]),
        json.dumps(["public", 'um"esquema']),
        json.dumps([{"esquema": 'um"esquema', "tabela": 'um"nome'}]),
        "7",
    ]

    def comando(argumentos, prazo_segundos=30):
        chamadas.append(argumentos)
        return respostas.pop(0)

    monkeypatch.setattr(ops, "comando", comando)
    assert ops.medir_coordenacao_db("a" * 64) == {
        "bancos": ["admin", "coordenacao_db", "postgres"],
        "esquemas": ["public", 'um"esquema'],
        "tabelas": [{"esquema": 'um"esquema', "tabela": 'um"nome', "linhas": 7}],
    }
    assert [chamada[chamada.index("-d") + 1] for chamada in chamadas] == [
        "postgres", "coordenacao_db", "coordenacao_db", "coordenacao_db"
    ]
    assert all(
        any(valor.startswith("PGOPTIONS=-c default_transaction_read_only=on") for valor in chamada)
        and "-w" in chamada and "ON_ERROR_STOP=1" in chamada
        for chamada in chamadas
    )
    assert chamadas[-1][-1] == 'SELECT count(*) FROM "um""esquema"."um""nome"'


def test_banco_ausente_e_inacessivel_tem_erros_explicitos(monkeypatch):
    monkeypatch.setattr(ops, "comando", lambda *args, **kwargs: '["postgres"]')
    with pytest.raises(ops.Falha, match="banco_ausente"):
        ops.medir_coordenacao_db("a" * 64)

    def falhar(*args, **kwargs):
        raise ops.Falha("instrumento")

    monkeypatch.setattr(ops, "comando", falhar)
    with pytest.raises(ops.Falha, match="banco_inacessivel"):
        ops.medir_coordenacao_db("a" * 64)


def test_operacao_aceita_so_servico_postgres_e_metadados():
    ops.validar("coordenacao-db", "postgres", {"postgres"})
    with pytest.raises(ops.Falha, match="entrada"):
        ops.validar("coordenacao-db", "admin", {"admin", "postgres"})
    with pytest.raises(ops.Falha, match="entrada"):
        ops.validar("coordenacao-db", "postgres", {"postgres"}, "valor")
    with pytest.raises(ops.Falha, match="formato"):
        ops.conferir_medicao("coordenacao-db", {
            "bancos": ["coordenacao_db"], "esquemas": ["public"],
            "tabelas": [{"esquema": "public", "tabela": "x", "linhas": 1, "conteudo": "segredo"}],
        })


@pytest.mark.parametrize("erro", ["banco_ausente", "banco_inacessivel"])
def test_workflow_mostra_erro_do_banco_sem_mostrar_saida_livre(monkeypatch, erro):
    monkeypatch.setenv("OPERACAO", "coordenacao-db")
    monkeypatch.setenv("SAIDA", json.dumps({"resultado": "ERROR", "erro": erro, "acao": "livre"}))
    with pytest.raises(ops.Falha, match=erro):
        ops.conferir()
