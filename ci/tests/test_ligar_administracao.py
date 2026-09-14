import io
import json
import subprocess

import pytest

import ligar_administracao as local


def test_falha_de_rede_diz_o_que_fazer(monkeypatch, capsys):
    def falhar():
        raise OSError("conexão interrompida")

    monkeypatch.setattr(local, "iniciar", falhar)
    assert local.main() == 1
    mensagem = capsys.readouterr().out
    assert "conexão interrompida" in mensagem
    assert "servidor.log" in mensagem
    assert "execute novamente" in mensagem


@pytest.fixture
def casa(tmp_path, monkeypatch):
    raiz = tmp_path / "bancada"
    (raiz / "services/admin").mkdir(parents=True)
    (raiz / "services/admin/requirements.txt").write_text("Django==5.1.4")
    planos = tmp_path / "sitesdoreino-docs/administracao-local"
    planos.mkdir(parents=True)
    (planos / "00-SINTESE-desenho-final.md").write_text("# Plano")
    monkeypatch.setattr(local, "RAIZ", raiz)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "dados"))
    return tmp_path


def test_porta_alheia_nao_encerra_processo(casa, monkeypatch):
    monkeypatch.setattr(local, "porta_ocupada", lambda: True)
    monkeypatch.setattr(
        local.subprocess, "Popen", lambda *a, **k: pytest.fail("não deve iniciar")
    )
    with pytest.raises(local.FalhaLocal, match="porta 8000 está ocupada"):
        local.iniciar()


@pytest.mark.parametrize("raiz_anterior", ["atual", "outra-bancada"])
def test_reexecucao_verifica_paginas_sem_iniciar(casa, monkeypatch, raiz_anterior):
    dados = casa / "dados/SitesDoReino/administracao-local"
    dados.mkdir(parents=True)
    (dados / "servidor.json").write_text(
        json.dumps(
            {
                "raiz": str(local.RAIZ) if raiz_anterior == "atual" else raiz_anterior,
                "token": "teste",
            }
        )
    )
    monkeypatch.setattr(local, "porta_ocupada", lambda: True)
    monkeypatch.setattr(local, "verificar_paginas", lambda token: [("Plano", token)])
    if raiz_anterior == "atual":
        assert local.iniciar()[0] == [("Plano", "teste")]
    else:
        with pytest.raises(local.FalhaLocal, match="outra bancada"):
            local.iniciar()


def test_pasta_errada_diz_o_que_fazer(casa):
    (
        casa / "sitesdoreino-docs/administracao-local/00-SINTESE-desenho-final.md"
    ).unlink()
    with pytest.raises(local.FalhaLocal, match="Restaure essa pasta"):
        local.iniciar()


def test_instalacao_falha_nao_anuncia_pronto(casa, monkeypatch):
    monkeypatch.setattr(
        local.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 1)
    )
    with pytest.raises(local.FalhaLocal, match="preparação falhou"):
        local.executar(["python"], casa / "log")


def test_redirecionamento_externo_e_recusado():
    with pytest.raises(local.FalhaLocal, match="sair do PC"):
        local.SomenteLocal().redirect_request(
            None, None, 302, "", {}, "https://meshcraft.top/entrar"
        )


def test_http_200_no_login_nao_e_pagina_pronta(monkeypatch):
    class Resposta(io.BytesIO):
        status = 200
        url = local.ORIGEM + "/entrar/"

    class Cliente:
        def open(self, *args, **kwargs):
            return Resposta(b"login")

    monkeypatch.setattr(local.urllib.request, "build_opener", lambda *a: Cliente())
    with pytest.raises(local.FalhaLocal, match="página esperada"):
        local.verificar_paginas("token")


def test_servidor_morto_informa_log(casa, monkeypatch):
    monkeypatch.setattr(local, "porta_ocupada", lambda: False)
    monkeypatch.setattr(local, "executar", lambda *a: None)

    class Processo:
        def poll(self):
            return 1

    monkeypatch.setattr(local.subprocess, "Popen", lambda *a, **k: Processo())
    with pytest.raises(local.FalhaLocal, match="servidor encerrou"):
        local.iniciar()
