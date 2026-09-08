"""Consolidação de snapshots e percurso sem publicar transcrições."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import metricas_da_fabrica as metricas
import telemetria


def mensagem(id="m1", sessao="s1", model="claude", **uso):
    return {"type": "assistant", "sessionId": sessao,
            "message": {"role": "assistant", "id": id, "model": model,
                        "usage": uso, "content": []}}


def arquivo(tmp_path, nome, eventos):
    p = tmp_path / nome
    p.write_text("\n".join(json.dumps(e) for e in eventos) + "\n", encoding="utf-8")
    return p


def test_snapshot_repetido_parcial_e_final_usa_maximo_por_campo(tmp_path):
    a = mensagem(input_tokens=12, output_tokens=2)
    b = mensagem(input_tokens=12, output_tokens=8, cache_read_input_tokens=20,
                 cache_creation_input_tokens=4, cache_creation={"ephemeral_5m_input_tokens": 4})
    p = arquivo(tmp_path, "a.jsonl", [a, b, b])
    r = metricas.consolidar_uso([p])
    assert r["mensagens"] == 1
    assert r["tokens"] == {"entrada_nova": 12, "leitura_cache": 20, "escrita_cache": 4, "saida": 8}
    assert r["cobertura"]["snapshots_consolidados"] == 2
    assert r == metricas.consolidar_uso([p])


def test_sobreposicao_modelo_namespace_e_mensagens_distintas(tmp_path):
    a = mensagem(output_tokens=3)
    p = arquivo(tmp_path, "a.jsonl", [a])
    q = arquivo(tmp_path, "b.jsonl", [a, mensagem("m2", output_tokens=3),
        mensagem(model="outro", output_tokens=3), mensagem(sessao="s2", output_tokens=3)])
    r = metricas.consolidar_uso([p, q, p])
    assert r["mensagens"] == 4
    assert r["tokens"]["saida"] == 12
    assert r == metricas.consolidar_uso([q, p])


def test_ausencia_invalido_incremental_e_sem_id_nao_viram_zero(tmp_path):
    incremental = mensagem(output_tokens=9)
    incremental["usage_mode"] = "incremental"
    p = arquivo(tmp_path, "a.jsonl", [mensagem(input_tokens=0), mensagem("m2", output_tokens=4),
        mensagem(None, output_tokens=300), incremental, mensagem("m3", output_tokens=-1)])
    r = metricas.consolidar_uso([p])
    assert r["tokens"]["entrada_nova"] == 0
    assert r["tokens"]["leitura_cache"] is None
    assert r["tokens"]["saida"] == 4
    assert r["cobertura"]["campos"]["saida"] == {"conhecidas": 1, "mensagens": 3}
    assert r["cobertura"]["incompleta"] is True
    assert r["cobertura"]["sem_identidade"] == 1
    assert r["cobertura"]["incompativeis"] == 1


def test_ferramentas_sao_unicas_e_nao_mensagens(tmp_path):
    e = mensagem(output_tokens=3)
    e["message"]["content"] = [{"type": "tool_use", "id": "t1", "name": "Bash", "input": {"secret": "NUNCA PUBLICAR"}}]
    p = arquivo(tmp_path, "a.jsonl", [e, e, {"type": "user", "message": {"role": "user", "content": []}}])
    r = metricas.consolidar_uso([p])
    assert r["ferramentas"] == 1 and r["mensagens"] == 1
    assert "NUNCA PUBLICAR" not in json.dumps(r)
    assert "Bash" not in json.dumps(r)


def test_arquivo_ilegivel_e_linha_interrompida_sinalizam_cobertura(tmp_path):
    p = arquivo(tmp_path, "a.jsonl", [mensagem(output_tokens=5), ["inesperado"]])
    with p.open("a") as f:
        f.write('{"type":')
    r = metricas.consolidar_uso([p, tmp_path / "ausente"])
    assert r["tokens"]["saida"] == 5
    assert r["cobertura"]["arquivos_ilegiveis"] == 1
    assert r["cobertura"]["linhas_invalidas"] == 2
    assert r["cobertura"]["incompleta"]
    p.write_text(json.dumps(mensagem(output_tokens=5)) + "\n", encoding="utf-8")
    assert metricas.consolidar_uso([p])["tokens"]["saida"] == 5


def test_registrar_fase_idempotente_preserva_tentativas_e_revisoes(tmp_path):
    (tmp_path / ".git").mkdir()
    args = dict(tarefa="TAR-123", tentativa="s1", branch="agent/ci/teste", commit="a" * 40, cwd=str(tmp_path))
    for _ in range(2):
        assert telemetria.registrar_fase("validacao", "falhou", **args)
    telemetria.registrar_fase("validacao", "concluido", **dict(args, tentativa="s2", commit="b" * 40))
    r = metricas.consolidar_percurso(telemetria.ler_tudo(tmp_path / ".git"))
    assert r["tarefas"] == 1 and r["tentativas"] == 2
    assert len(r["eventos"]) == 2
    assert {e["resultado"] for e in r["eventos"]} == {"falhou", "concluido"}
    assert {e["commit"] for e in r["eventos"]} == {"a" * 40, "b" * 40}
    assert r["publicacoes_verificadas"] == 0


def test_telemetria_mede_bytes_da_resposta_e_fica_privada(tmp_path):
    (tmp_path / ".git").mkdir()
    args = dict(tarefa="TAR-123", tentativa="s1", branch="agent/ci/teste", commit="a" * 40, cwd=str(tmp_path))
    telemetria.registrar_fase("contexto", "concluido", contexto_bytes=len("lição".encode()), **args)
    r = metricas.consolidar_percurso(telemetria.ler_tudo(tmp_path / ".git"))
    assert r["eventos"][0]["contexto_bytes"] == 7
    assert r["eventos"][0]["quando"].endswith("+00:00")
    assert telemetria.registrar_fase("inventada", "concluido", **args) is None
    assert telemetria.registrar_fase("contexto", "concluido", **dict(args, tentativa="--token segredo")) is None


def test_publicacao_exige_observacao_explicita_e_ausencia_permanece_ausente(tmp_path):
    (tmp_path / ".git").mkdir()
    args = dict(tarefa="TAR-123", tentativa="s1", branch="agent/ci/teste", commit="a" * 40, cwd=str(tmp_path))
    telemetria.registrar_fase("fechamento", "concluido", pr=123, **args)
    r = metricas.consolidar_percurso(telemetria.ler_tudo(tmp_path / ".git"))
    assert r["publicacoes_verificadas"] == 0
    assert r["eventos"][0]["contexto_bytes"] is None
    assert r["cobertura"]["fases_ausentes"]
    telemetria.registrar_fase("publicacao", "verificado", pr=123, **args)
    assert metricas.consolidar_percurso(telemetria.ler_tudo(tmp_path / ".git"))["publicacoes_verificadas"] == 1


def test_registro_sem_disco_nao_derruba_operacao(tmp_path):
    assert telemetria.registrar_fase("abertura", "iniciado", tarefa="TAR-1", tentativa="s1",
        branch="agent/ci/teste", commit="a" * 40, cwd=str(tmp_path)) is None


def test_leitura_do_percurso_nao_oculta_corrupcao(tmp_path):
    pasta = tmp_path / telemetria.PASTA
    pasta.mkdir()
    arquivo(pasta, "a.jsonl", [{"evento": "antigo"}, []])
    with (pasta / "a.jsonl").open("a") as f:
        f.write("interrompido")
    cobertura = {}
    assert telemetria.ler_tudo(tmp_path, cobertura) == [{"evento": "antigo"}]
    assert cobertura == {"arquivos": 1, "arquivos_ilegiveis": 0, "linhas_invalidas": 2}


def test_eventos_adulterados_ou_sensiveis_nao_entram_relatorio(tmp_path):
    (tmp_path / ".git").mkdir()
    telemetria.registrar_fase("validacao", "concluido", tarefa="TAR-1", tentativa="s1",
        branch="agent/ci/teste", commit="a" * 40, cwd=str(tmp_path))
    e = telemetria.ler_tudo(tmp_path / ".git")[0]
    e["branch"] = "ghp_" + "a" * 36
    r = metricas.consolidar_percurso([e])
    assert r["cobertura"]["eventos_invalidos"] == 1
    assert "ghp_" not in json.dumps(r)
    e["branch"] = "agent/ci/teste"
    e["commit"] = "b" * 40
    assert metricas.consolidar_percurso([e])["eventos"] == []


def test_cli_local_sem_github_e_com_arquivo_ausente(tmp_path, monkeypatch, capsys):
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(metricas, "raiz_do_repo", lambda: tmp_path)
    monkeypatch.setattr(metricas, "coletar", lambda *a: pytest.fail("consultou rede"))
    assert metricas.main(["--local", "--transcricoes", str(tmp_path / "ausente")]) == 0
    r = json.loads(capsys.readouterr().out)
    assert r["uso"]["tokens"]["saida"] is None
    assert r["uso"]["cobertura"]["incompleta"] is True
    assert r["percurso"]["cobertura"]["fases_ausentes"] == list(telemetria.FASES)


@pytest.mark.parametrize("mudanca", [{"quando": "2026-01-01T00:00:00"}, {"quando": "inválido"},
    {"pr": 0}, {"contexto_bytes": -1}, {"commit": "a" * 41}, {"resultado": "aprovado"}])
def test_percurso_recusa_metadados_invalidos(tmp_path, mudanca):
    (tmp_path / ".git").mkdir()
    telemetria.registrar_fase("validacao", "concluido", tarefa="TAR-1", tentativa="s1",
        branch="agent/ci/teste", commit="a" * 40, cwd=str(tmp_path))
    e = telemetria.ler_tudo(tmp_path / ".git")[0]
    e.update(mudanca)
    assert metricas.consolidar_percurso([e])["cobertura"]["eventos_invalidos"] == 1


def test_registrar_fase_fail_open_quando_escritor_falha(monkeypatch):
    def falha(*a, **k):
        raise OSError("instrumento indisponível")
    monkeypatch.setattr(telemetria, "registrar", falha)
    assert telemetria.registrar_fase("validacao", "concluido", tarefa="TAR-1", tentativa="s1",
        branch="agent/ci/teste", commit="a" * 40) is None


def test_escrita_recusa_segredo_em_identificador(tmp_path):
    (tmp_path / ".git").mkdir()
    assert telemetria.registrar_fase("abertura", "iniciado", tarefa="TAR-1", tentativa="s1",
        branch="ghp_" + "a" * 36, commit="a" * 40, cwd=str(tmp_path)) is None
    assert telemetria.ler_tudo(tmp_path / ".git") == []
