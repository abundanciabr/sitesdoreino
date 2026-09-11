"""Testes do comando operacional da medição da Fase 4."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import registrar_tarefa_fase4 as comando  # noqa: E402
import fila  # noqa: E402
import telemetria  # noqa: E402


def manifesto(*, estado="concluida"):
    tarefa = "TAR-F4-REAL-001"
    commit = "a" * 40
    pr = 1
    return {
        "tarefa": tarefa,
        "tentativa": "tentativa-real-001",
        "branch": "agent/admin/tarefa-real",
        "commit": commit,
        "pr": pr,
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
        "revisao_instrumento": "b" * 64,
        "estado": estado,
        "fonte": "registro-operacional-autorizado",
        "inicio": "2026-09-08T10:00:00+00:00",
        "fim": "2026-09-08T10:30:00+00:00" if estado != "pendente" else None,
        "sessao": "sessao-real-001",
        "metricas": {campo: 0 for campo in telemetria.METRICAS_DA_TAREFA},
        "schema_medicao": 2,
        "tarefa_sha256": "c" * 64,
        "classificacao_sha256": "d" * 64,
        "classificada_em": "2026-09-08T09:59:00+00:00",
        "autorizada_por": "maestro-fase4",
        "observado_em": (
            "2026-09-08T10:30:00+00:00"
            if estado != "pendente"
            else "2026-09-08T10:00:00+00:00"
        ),
        "evidencia": (
            {
                "resultado": f"{tarefa} {estado}: PR #{pr} no commit {commit}",
                "fonte": (
                    "https://github.com/abundanciabr/sitesdoreino/pull/"
                    f"{pr}/commits/{commit}"
                ),
                "verificado_em": "2026-09-08T10:30:00+00:00",
            }
            if estado != "pendente"
            else None
        ),
    }


def escrever_manifesto(tmp_path, dados):
    caminho = tmp_path / "medicao.json"
    caminho.write_text(json.dumps(dados), encoding="utf-8")
    return caminho


def preparar_caderno(tmp_path, monkeypatch):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    monkeypatch.setattr(comando.telemetria, "dir_git_comum", lambda _: git_dir)
    monkeypatch.setattr(comando, "_vinculo_confere", lambda *_: True)
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

    for valor in (float("nan"), float("inf"), float("-inf")):
        dados = manifesto()
        dados["metricas"]["runner_minutos"] = valor
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
        "piloto": "fase1",
        "condicao": "depois",
        "par_id": None,
        "tipo": "correcao-transversal",
        "complexidade": "media",
        "natureza": "codigo",
        "componentes": "ci",
        "fronteiras_integracao": "telemetria",
        "migracao": "nao",
        "risco": "medio",
        "escopo_publicacao": "sem-publicacao",
        "revisao_instrumento": "b" * 40,
        "classificada_em": "2026-09-08T09:59:00+00:00",
        "autorizada_por": "maestro-fase4",
    }

    resultado = comando.manifesto_da_execucao(
        classificacao,
        tarefa="TAR-REAL",
        tentativa="tentativa-real",
        branch="agent/ci/real",
        commit="a" * 40,
        estado="pendente",
        inicio="2026-09-08T10:00:00+00:00",
        fim=None,
        pr=None,
        tarefa_sha256="c" * 64,
        classificacao_sha256="d" * 64,
        revisao_instrumento="e" * 64,
        observado_em="2026-09-08T10:00:00+00:00",
    )

    assert resultado["fonte"] == "fila-operacional-fase4"
    assert resultado["metricas"] == {
        campo: None for campo in telemetria.METRICAS_DA_TAREFA
    }


def test_reexecucao_do_registrador_nao_duplica_a_identidade(tmp_path, monkeypatch):
    git_dir = preparar_caderno(tmp_path, monkeypatch)
    dados = manifesto()
    hostil = dict(dados, evento="tarefa_medida")
    hostil["id"] = telemetria.identidade_tarefa(hostil)
    hostil["branch"] = "agent/hostil/mesmo-id"
    pasta = git_dir / telemetria.PASTA
    pasta.mkdir()
    (pasta / "sessao-real-001.jsonl").write_text(
        json.dumps(hostil) + "\n", encoding="utf-8"
    )
    manifesto_path = escrever_manifesto(tmp_path, dados)

    assert comando.main(["--manifesto", str(manifesto_path)]) == 0
    assert comando.main(["--manifesto", str(manifesto_path)]) == 0

    eventos = telemetria.ler_tudo(git_dir)
    assert len(eventos) == 2
    assert sum(
        telemetria.identidade_tarefa(evento) == evento.get("id")
        for evento in eventos
    ) == 1


def test_reexecucao_com_evidencia_conflitante_e_recusada(tmp_path, monkeypatch):
    git_dir = preparar_caderno(tmp_path, monkeypatch)
    original = manifesto()
    escrever_manifesto(tmp_path, original)
    comando.main(["--manifesto", str(tmp_path / "medicao.json")])

    conflito = dict(original, pr=9999)
    conflito["evidencia"] = dict(
        original["evidencia"],
        resultado=(
            f"{conflito['tarefa']} {conflito['estado']}: PR #9999 "
            f"no commit {conflito['commit']}"
        ),
        fonte=(
            "https://github.com/abundanciabr/sitesdoreino/pull/9999/commits/"
            + conflito["commit"]
        ),
    )
    with pytest.raises(ValueError, match="mesma observação tem conteúdo diferente"):
        comando.registrar_manifesto(conflito, cwd=tmp_path)

    assert len(telemetria.ler_tudo(git_dir)) == 1


def test_fluxo_da_tarefa_da_fila_chama_o_registrador_sem_manifesto_manual(
    tmp_path, monkeypatch
):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    classificacao = {
        "piloto": "fase1",
        "condicao": "depois",
        "par_id": None,
        "tipo": "correcao-transversal",
        "complexidade": "media",
        "natureza": "codigo",
        "componentes": "ci",
        "fronteiras_integracao": "telemetria",
        "migracao": "nao",
        "risco": "medio",
        "escopo_publicacao": "sem-publicacao",
        "revisao_instrumento": "b" * 40,
    }
    tarefa_dir = tmp_path / "fila" / "tarefas"
    tarefa_dir.mkdir(parents=True)
    (tarefa_dir / "001-tarefa-real.json").write_text(
        json.dumps(
            {
                "arquivo": "001-tarefa-real",
                "id": "TAR-001",
                "titulo": "tarefa real",
                "toca": ["ci"],
                "evidencia_exigida": "prova real",
                "despacho": "executar",
                "origem": "pedido real",
                "criada_em": "2026-09-08",
                "medicao_fase4": classificacao,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        comando,
        "vinculo_da_tarefa",
        lambda *_: {
            "classificacao": classificacao,
            "tarefa_sha256": "c" * 64,
            "classificacao_sha256": "d" * 64,
            "classificada_em": "2026-09-08T09:59:00+00:00",
            "autorizada_por": "fila-versionada:" + "e" * 40,
            "commit_classificacao": "e" * 40,
        },
    )
    monkeypatch.setattr(comando, "_classificacao_antecede_commit", lambda *_: True)
    monkeypatch.setattr(comando, "_pr_confere_tarefa_commit", lambda *_: True)
    monkeypatch.setattr(comando, "revisao_do_instrumento", lambda _: "b" * 40)

    assert comando.registrar_execucao_fase4(
        tmp_path,
        tarefa="TAR-001",
        tentativa="tentativa-real",
        branch="agent/ci/tarefa-real",
        commit="a" * 40,
        estado="pendente",
        inicio="2026-09-08T10:00:00+00:00",
        fim=None,
        pr=None,
    )
    with pytest.raises(ValueError, match="início da tentativa mudou"):
        comando.registrar_execucao_fase4(
            tmp_path,
            tarefa="TAR-001",
            tentativa="tentativa-real",
            branch="agent/ci/tarefa-real",
            commit="a" * 40,
            estado="pendente",
            inicio="2026-09-08T10:00:01+00:00",
            fim=None,
            pr=None,
        )
    assert comando.registrar_execucao_fase4(
        tmp_path,
        tarefa="TAR-001",
        tentativa="tentativa-real",
        branch="agent/ci/tarefa-real",
        commit="a" * 40,
        estado="concluida",
        inicio="2026-09-08T10:00:00+00:00",
        fim="2026-09-08T10:02:00+00:00",
        pr=1400,
    )
    assert comando.registrar_execucao_fase4(
        tmp_path,
        tarefa="TAR-001",
        tentativa="tentativa-real",
        branch="agent/ci/tarefa-real",
        commit="a" * 40,
        estado="concluida",
        inicio="2026-09-08T10:00:00+00:00",
        fim="2026-09-08T10:03:00+00:00",
        pr=1400,
    )

    eventos = telemetria.ler_tudo(git_dir)
    assert len(eventos) == 3
    encerrados = [evento for evento in eventos if evento["estado"] == "concluida"]
    assert encerrados[0]["pr"] == 1400
    assert encerrados[0]["evidencia"] == {
        "resultado": "TAR-001 concluida: PR #1400 no commit " + "a" * 40,
        "fonte": "https://github.com/abundanciabr/sitesdoreino/pull/1400/commits/"
        + "a" * 40,
        "verificado_em": "2026-09-08T10:02:00+00:00",
    }
def test_classificacao_posterior_ao_inicio_nao_entra_no_caderno(tmp_path, monkeypatch):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    tarefa_dir = tmp_path / "fila" / "tarefas"
    tarefa_dir.mkdir(parents=True)
    classificacao = {
        "piloto": "fase1",
        "condicao": "depois",
        "par_id": None,
        "tipo": "produto",
        "complexidade": "alta",
        "natureza": "codigo",
        "componentes": "ci",
        "fronteiras_integracao": "telemetria",
        "migracao": "nao",
        "risco": "alto",
        "escopo_publicacao": "sem-publicacao",
        "revisao_instrumento": "b" * 40,
    }
    (tarefa_dir / "001-tarefa-real.json").write_text(
        json.dumps(
            {
                "arquivo": "001-tarefa-real",
                "id": "TAR-001",
                "titulo": "tarefa real",
                "toca": ["ci"],
                "evidencia_exigida": "prova real",
                "despacho": "executar",
                "origem": "pedido real",
                "criada_em": "2026-09-08",
                "medicao_fase4": classificacao,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        comando,
        "vinculo_da_tarefa",
        lambda *_: {
            "classificacao": classificacao,
            "tarefa_sha256": "c" * 64,
            "classificacao_sha256": "d" * 64,
            "classificada_em": "2026-09-08T10:01:00+00:00",
            "autorizada_por": "fila-versionada:" + "e" * 40,
            "commit_classificacao": "e" * 40,
        },
    )
    monkeypatch.setattr(comando, "revisao_do_instrumento", lambda _: "f" * 40)

    assert not comando.registrar_execucao_fase4(
        tmp_path,
        tarefa="TAR-001",
        tentativa="tentativa-real",
        branch="agent/ci/tarefa-real",
        commit="a" * 40,
        estado="pendente",
        inicio="2026-09-08T10:00:00+00:00",
        fim=None,
        pr=None,
    )
    assert telemetria.ler_tudo(git_dir) == []


def test_revisao_declarada_precisa_corresponder_ao_conteudo_do_instrumento(
    tmp_path, monkeypatch
):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    tarefa_dir = tmp_path / "fila" / "tarefas"
    tarefa_dir.mkdir(parents=True)
    classificacao = {
        "piloto": "fase1",
        "condicao": "depois",
        "par_id": None,
        "tipo": "produto",
        "complexidade": "alta",
        "natureza": "codigo",
        "componentes": "ci",
        "fronteiras_integracao": "telemetria",
        "migracao": "nao",
        "risco": "alto",
        "escopo_publicacao": "sem-publicacao",
        "revisao_instrumento": "b" * 40,
    }
    (tarefa_dir / "001-tarefa-real.json").write_text(
        json.dumps(
            {
                "arquivo": "001-tarefa-real",
                "id": "TAR-001",
                "titulo": "tarefa real",
                "toca": ["ci"],
                "evidencia_exigida": "prova real",
                "despacho": "executar",
                "origem": "pedido real",
                "criada_em": "2026-09-08",
                "medicao_fase4": classificacao,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        comando,
        "vinculo_da_tarefa",
        lambda *_: {
            "classificacao": classificacao,
            "tarefa_sha256": "c" * 64,
            "classificacao_sha256": "d" * 64,
            "classificada_em": "2026-09-08T09:59:00+00:00",
            "autorizada_por": "fila-versionada:" + "e" * 40,
            "commit_classificacao": "e" * 40,
        },
    )
    monkeypatch.setattr(comando, "_classificacao_antecede_commit", lambda *_: True)
    monkeypatch.setattr(
        comando, "revisao_do_instrumento", lambda _: "d" * 40, raising=False
    )

    assert not comando.registrar_execucao_fase4(
        tmp_path,
        tarefa="TAR-001",
        tentativa="tentativa-real",
        branch="agent/ci/tarefa-real",
        commit="a" * 40,
        estado="pendente",
        inicio="2026-09-08T10:00:00+00:00",
        fim=None,
        pr=None,
    )
    assert telemetria.ler_tudo(git_dir) == []

    classificacao["revisao_instrumento"] = "d" * 40
    assert comando.registrar_execucao_fase4(
        tmp_path,
        tarefa="TAR-001",
        tentativa="tentativa-real",
        branch="agent/ci/tarefa-real",
        commit="a" * 40,
        estado="pendente",
        inicio="2026-09-08T10:00:00+00:00",
        fim=None,
        pr=None,
    )
    evento = telemetria.ler_tudo(git_dir)[0]
    assert evento["revisao_instrumento"] == "d" * 40


def test_revisao_do_instrumento_muda_quando_o_codigo_muda(tmp_path):
    for relativo in comando.ARQUIVOS_DO_INSTRUMENTO:
        caminho = tmp_path / relativo
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_bytes(f"conteudo de {relativo}\nlinha\n".encode("utf-8"))
    primeira = comando.revisao_do_instrumento(tmp_path)
    (tmp_path / "ci" / "analise_fase4.py").write_bytes(
        b"conteudo de ci/analise_fase4.py\r\nlinha\r\n"
    )
    mesma_revisao = comando.revisao_do_instrumento(tmp_path)
    (tmp_path / "ci" / "analise_fase4.py").write_bytes(b"codigo revisado\n")

    segunda = comando.revisao_do_instrumento(tmp_path)

    assert len(primeira) == 40
    assert primeira == mesma_revisao
    assert primeira != segunda


def test_vinculo_usa_o_commit_em_que_a_classificacao_entrou(tmp_path, monkeypatch):
    classificacao = {
        "piloto": "fase1",
        "condicao": "depois",
        "tipo": "produto",
        "complexidade": "alta",
        "natureza": "codigo",
        "componentes": "ci",
        "fronteiras_integracao": "telemetria",
        "migracao": "nao",
        "risco": "alto",
        "escopo_publicacao": "sem-publicacao",
        "revisao_instrumento": "b" * 40,
    }
    tarefa = {
        "arquivo": "001-tarefa-real",
        "id": "TAR-001",
        "titulo": "tarefa real",
        "toca": ["ci"],
        "depende_de": [],
        "cria": [],
        "move": ["manutencao"],
        "evidencia_exigida": "prova real",
        "despacho": "executar",
        "origem": "pedido real",
        "criada_em": "2026-09-08",
        "responsabilidade_obrigatoria": True,
        "responsabilidade": "operacao-tecnica",
    }
    tarefa_dir = tmp_path / "fila" / "tarefas"
    tarefa_dir.mkdir(parents=True)
    caminho = tarefa_dir / "001-tarefa-real.json"
    caminho.write_text(json.dumps(tarefa), encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "add", caminho.relative_to(tmp_path)], cwd=tmp_path, check=True
    )
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Teste",
            "-c",
            "user.email=teste@example.test",
            "commit",
            "-qm",
            "tarefa",
        ],
        cwd=tmp_path,
        check=True,
    )
    commit_anterior = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    tarefa["medicao_fase4"] = classificacao
    caminho.write_text(json.dumps(tarefa), encoding="utf-8")
    subprocess.run(
        ["git", "add", caminho.relative_to(tmp_path)], cwd=tmp_path, check=True
    )
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Teste",
            "-c",
            "user.email=teste@example.test",
            "commit",
            "-qm",
            "classifica",
        ],
        cwd=tmp_path,
        check=True,
    )
    commit_classificacao = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    vinculo = comando.vinculo_da_tarefa(tmp_path, "TAR-001")

    assert vinculo is not None
    assert vinculo["autorizada_por"] == f"fila-versionada:{commit_classificacao}"
    assert vinculo["commit_classificacao"] == commit_classificacao
    assert vinculo["classificacao"] == classificacao
    assert comando._classificacao_antecede_commit(
        tmp_path, vinculo, commit_classificacao
    )
    assert not comando._classificacao_antecede_commit(
        tmp_path, vinculo, commit_anterior
    )
    url = "https://github.com/abundanciabr/sitesdoreino/pull/1400"
    monkeypatch.setattr(fila, "carregar_tarefas", lambda *_: {"TAR-001": tarefa})
    monkeypatch.setattr(
        fila,
        "carregar_eventos",
        lambda *_: [
            {
                "evento": "submetida",
                "tarefa": "TAR-001",
                "pr": url,
                "revisao": commit_classificacao,
            }
        ],
    )
    monkeypatch.setattr(
        comando.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            [], 0, json.dumps({"url": url, "commits": [{"oid": commit_classificacao}]}), ""
        ),
    )
    assert comando._pr_confere_tarefa_commit(
        tmp_path, "TAR-001", 1400, commit_classificacao
    )
    assert not comando._pr_confere_tarefa_commit(
        tmp_path, "TAR-001", 1400, commit_anterior
    )


def test_avanco_legitimo_de_commit_e_append_only_e_repeticao_exata_e_idempotente(
    tmp_path, monkeypatch
):
    git_dir = preparar_caderno(tmp_path, monkeypatch)
    primeiro = manifesto(estado="pendente")
    primeiro["observado_em"] = "2026-09-08T10:01:00+00:00"
    primeiro["evidencia"] = None
    segundo = dict(primeiro, commit="b" * 40, observado_em="2026-09-08T10:02:00+00:00")

    assert comando.registrar_manifesto(primeiro, cwd=tmp_path)[0] is not None
    assert comando.registrar_manifesto(segundo, cwd=tmp_path)[0] is not None
    assert comando.registrar_manifesto(segundo, cwd=tmp_path)[1]
    eventos = telemetria.ler_tudo(git_dir)
    assert len(eventos) == 2
    assert [evento["commit"] for evento in eventos] == ["a" * 40, "b" * 40]
