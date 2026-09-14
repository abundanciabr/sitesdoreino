import json
from datetime import datetime, timezone

import pytest
import fila
import radio
from test_fila import tarefa, evento, montar


@pytest.fixture
def envios(monkeypatch):
    enviados = []
    monkeypatch.setattr(
        radio,
        "_chamar",
        lambda metodo, dados: enviados.append(dados)
        or {"sequencia": len(enviados), **dados},
    )
    return enviados


def test_mudanca_real_emite_boletim_com_tarefa_estado_e_instante(tmp_path, envios):
    # guarda: ci/fila.py:1451
    montar(tmp_path, [tarefa()])
    fila._escrever_evento(
        tmp_path,
        "TAR-001",
        "reivindicada",
        "codex",
        agora=datetime(2026, 9, 13, 12, tzinfo=timezone.utc),
    )
    assert envios == [
        {
            "autor": "fila",
            "tipo": "boletim",
            "tarefa": "TAR-001",
            "texto": "TAR-001: reivindicada em 2026-09-13T12:00:00+00:00",
        }
    ]


def test_repetir_mesmo_estado_nao_emite(tmp_path, envios):
    montar(tmp_path, [tarefa()], [evento()])
    fila._escrever_evento(tmp_path, "TAR-001", "reivindicada", "codex")
    assert envios == []


def test_concluir_emite_tambem_dependencia_destravada(tmp_path, envios):
    montar(tmp_path, [tarefa(), tarefa("002", deps=("TAR-001",))], [evento()])
    fila._escrever_evento(
        tmp_path,
        "TAR-001",
        "concluida",
        "codex",
        evidencia="https://github.com/abundanciabr/sitesdoreino/pull/1",
        verificado_em="2026-09-13",
    )
    assert [e["tarefa"] for e in envios] == ["TAR-001", "TAR-002"]
    assert "concluída" in envios[0]["texto"]
    assert "na fila" in envios[1]["texto"]


def test_radio_offline_preserva_evento_e_comando_de_reenvio(
    tmp_path, monkeypatch, capsys
):
    montar(tmp_path, [tarefa()])

    def falha(*args, **kwargs):
        raise RuntimeError("rádio indisponível")

    monkeypatch.setattr(radio, "_chamar", falha)
    caminho = fila._escrever_evento(tmp_path, "TAR-001", "reivindicada", "codex")
    assert json.loads(caminho.read_text(encoding="utf-8"))["evento"] == "reivindicada"
    saida = capsys.readouterr().err
    assert "python ci/radio.py dizer" in saida
    assert "--autor fila --tipo boletim" in saida


def test_explicacao_nao_emite_estado_repetido(tmp_path, envios):
    montar(tmp_path, [tarefa()])
    fila._escrever_evento(
        tmp_path,
        "TAR-001",
        "explicada",
        "codex",
        explicacao={
            "o_que_e": "O que existe",
            "o_que_muda": "O que melhora",
            "exemplo": "Exemplo concreto",
            "importancia": 50,
        },
    )
    assert envios == []


def test_submissao_emite_uma_vez_por_mudanca(tmp_path, envios, monkeypatch):
    from test_fila import args_de_submeter

    montar(tmp_path, [tarefa()], [evento()])
    monkeypatch.setattr(fila, "_parar_se_for_o_espelho", lambda *args: None)
    monkeypatch.setattr(fila, "_soltar_reserva_se_houver", lambda *args: None)
    args = args_de_submeter()
    assert fila.cmd_submeter(tmp_path, args) == 0
    assert fila.cmd_submeter(tmp_path, args) == 0
    assert len(envios) == 1
    assert "em execução" in envios[0]["texto"]


def test_criacao_emite_primeiro_estado(tmp_path, envios):
    montar(tmp_path)
    dados = tarefa()
    fila._gravar_fila(tmp_path, tmp_path / "fila/tarefas/001-exemplo.json", dados)
    assert len(envios) == 1
    assert "na fila" in envios[0]["texto"]


def test_escrita_falha_nao_emite_boletim(tmp_path, envios, monkeypatch):
    montar(tmp_path, [tarefa()])

    def falha(*args):
        raise OSError("disco indisponível")

    monkeypatch.setattr(fila, "_escrever_json", falha)
    with pytest.raises(OSError):
        fila._escrever_evento(tmp_path, "TAR-001", "reivindicada", "codex")
    assert envios == []
