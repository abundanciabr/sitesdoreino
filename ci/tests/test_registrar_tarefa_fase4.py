"""Testes do comando operacional da medição da Fase 4."""

import json
import sys
from pathlib import Path

import pytest

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


def test_manifesto_da_execucao_preenche_so_dados_do_fluxo():
    classificacao = {
        "piloto": "fase1", "condicao": "depois", "par_id": None,
        "tipo": "correcao-transversal", "complexidade": "media",
        "natureza": "codigo", "componentes": "ci",
        "fronteiras_integracao": "telemetria", "migracao": "nao",
        "risco": "medio", "escopo_publicacao": "sem-publicacao",
        "revisao_instrumento": "b" * 40,
    }

    resultado = comando.manifesto_da_execucao(
        classificacao, tarefa="TAR-REAL", tentativa="tentativa-real",
        branch="agent/ci/real", commit="a" * 40, estado="pendente",
        inicio="2026-09-08T10:00:00+00:00", fim=None, pr=None,
    )

    assert resultado["fonte"] == "fila-operacional-fase4"
    assert resultado["metricas"] == {campo: None for campo in telemetria.METRICAS_DA_TAREFA}


def test_reexecucao_do_registrador_nao_duplica_a_identidade(tmp_path, monkeypatch):
    git_dir = preparar_caderno(tmp_path, monkeypatch)
    dados = manifesto()
    manifesto_path = escrever_manifesto(tmp_path, dados)

    assert comando.main(["--manifesto", str(manifesto_path)]) == 0
    assert comando.main(["--manifesto", str(manifesto_path)]) == 0

    eventos = telemetria.ler_tudo(git_dir)
    assert len(eventos) == 1


def test_reexecucao_com_evidencia_conflitante_e_recusada(tmp_path, monkeypatch):
    git_dir = preparar_caderno(tmp_path, monkeypatch)
    original = manifesto()
    escrever_manifesto(tmp_path, original)
    comando.main(["--manifesto", str(tmp_path / "medicao.json")])

    conflito = dict(original, pr=9999)
    with pytest.raises(ValueError, match="commit ou evidência diferente"):
        comando.registrar_manifesto(conflito, cwd=tmp_path)

    assert len(telemetria.ler_tudo(git_dir)) == 1


def test_fluxo_da_tarefa_da_fila_chama_o_registrador_sem_manifesto_manual(tmp_path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    classificacao = {
        "piloto": "fase1", "condicao": "depois", "par_id": None,
        "tipo": "correcao-transversal", "complexidade": "media",
        "natureza": "codigo", "componentes": "ci",
        "fronteiras_integracao": "telemetria", "migracao": "nao",
        "risco": "medio", "escopo_publicacao": "sem-publicacao",
        "revisao_instrumento": "b" * 40,
    }
    tarefa_dir = tmp_path / "fila" / "tarefas"
    tarefa_dir.mkdir(parents=True)
    (tarefa_dir / "001-tarefa-real.json").write_text(json.dumps({
        "arquivo": "001-tarefa-real", "id": "TAR-001", "titulo": "tarefa real",
        "toca": ["ci"], "evidencia_exigida": "prova real", "despacho": "executar",
        "origem": "pedido real", "criada_em": "2026-09-08",
        "medicao_fase4": classificacao,
    }), encoding="utf-8")

    assert comando.registrar_execucao_fase4(
        tmp_path, tarefa="TAR-001", tentativa="tentativa-real",
        branch="agent/ci/tarefa-real", commit="a" * 40, estado="pendente",
        inicio="2026-09-08T10:00:00+00:00", fim=None, pr=None,
    )
    assert comando.registrar_execucao_fase4(
        tmp_path, tarefa="TAR-001", tentativa="tentativa-real",
        branch="agent/ci/tarefa-real", commit="a" * 40, estado="pendente",
        inicio="2026-09-08T10:00:01+00:00", fim=None, pr=None,
    )
    assert comando.registrar_execucao_fase4(
        tmp_path, tarefa="TAR-001", tentativa="tentativa-real",
        branch="agent/ci/tarefa-real", commit="a" * 40, estado="concluida",
        inicio="2026-09-08T10:00:00+00:00", fim="2026-09-08T10:02:00+00:00", pr=1400,
    )
    assert comando.registrar_execucao_fase4(
        tmp_path, tarefa="TAR-001", tentativa="tentativa-real",
        branch="agent/ci/tarefa-real", commit="a" * 40, estado="concluida",
        inicio="2026-09-08T10:00:00+00:00", fim="2026-09-08T10:03:00+00:00", pr=1400,
    )

    eventos = telemetria.ler_tudo(git_dir)
    assert len(eventos) == 2
    assert [evento for evento in eventos if evento["estado"] == "concluida"][0]["pr"] == 1400
