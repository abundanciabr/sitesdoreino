"""Testes do comando operacional da medição da Fase 4."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import registrar_tarefa_fase4 as comando  # noqa: E402
import telemetria  # noqa: E402


def manifesto(*, estado="concluida"):
    return {
        "tarefa": "TAR-F4-REAL-001",
        "tentativa": "tentativa-real-001",
        "branch": "agent/admin/tarefa-real",
        "commit": "a" * 40,
        "piloto": "fase3",
        "condicao": "depois",
        "par_id": "par-real-001",
        "tipo": "correcao-transversal",
        "complexidade": "media",
        "natureza": "codigo",
        "componentes": "alunos,identidade",
        "fronteiras_integracao": "outbox",
        "migracao": "nao",
        "risco": "medio",
        "escopo_publicacao": "publicacao-verificada",
        "revisao_instrumento": "b" * 40,
        "estado": estado,
        "fonte": "registro-operacional-autorizado",
        "inicio": "2026-09-08T10:00:00+00:00",
        "fim": "2026-09-08T10:30:00+00:00" if estado != "pendente" else None,
        "sessao": "sessao-real-001",
        "metricas": {campo: 0 for campo in telemetria.METRICAS_DA_TAREFA},
    }


def escrever_manifesto(tmp_path, dados):
    caminho = tmp_path / "medicao.json"
    caminho.write_text(json.dumps(dados), encoding="utf-8")
    return caminho


def preparar_caderno(tmp_path, monkeypatch):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    monkeypatch.setattr(comando.telemetria, "dir_git_comum", lambda _: git_dir)
    return git_dir


def test_comando_registra_manifesto_valido_no_caderno_existente(tmp_path, monkeypatch):
    git_dir = preparar_caderno(tmp_path, monkeypatch)
    manifesto_path = escrever_manifesto(tmp_path, manifesto())

    assert comando.main(["--manifesto", str(manifesto_path)]) == 0

    eventos = telemetria.ler_tudo(git_dir)
    assert len(eventos) == 1
    assert eventos[0]["evento"] == "tarefa_medida"
    assert eventos[0]["condicao"] == "depois"


def test_comando_recusa_campo_obrigatorio_ausente(tmp_path, monkeypatch):
    preparar_caderno(tmp_path, monkeypatch)
    dados = manifesto()
    del dados["fim"]
    manifesto_path = escrever_manifesto(tmp_path, dados)

    assert comando.main(["--manifesto", str(manifesto_path)]) == 2


def test_comando_recusa_metrica_omitida_em_vez_de_inferir_zero(tmp_path, monkeypatch):
    preparar_caderno(tmp_path, monkeypatch)
    dados = manifesto()
    del dados["metricas"]["runner_minutos"]
    manifesto_path = escrever_manifesto(tmp_path, dados)

    assert comando.main(["--manifesto", str(manifesto_path)]) == 2


def test_comando_aceita_pendente_com_fim_ausente(tmp_path, monkeypatch):
    git_dir = preparar_caderno(tmp_path, monkeypatch)
    manifesto_path = escrever_manifesto(tmp_path, manifesto(estado="pendente"))

    assert comando.main(["--manifesto", str(manifesto_path)]) == 0
    assert telemetria.ler_tudo(git_dir)[0]["estado"] == "pendente"


def test_comando_recusa_fim_antes_do_inicio(tmp_path, monkeypatch):
    preparar_caderno(tmp_path, monkeypatch)
    dados = manifesto()
    dados["fim"] = "2026-09-08T09:59:00+00:00"
    manifesto_path = escrever_manifesto(tmp_path, dados)

    assert comando.main(["--manifesto", str(manifesto_path)]) == 2
