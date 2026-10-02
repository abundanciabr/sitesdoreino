"""Transições reais do journal usando runtime e HTTP simulados, sem VPS."""
import importlib.util
import json
from pathlib import Path
import pytest
from conftest import BASH

ROOT = Path(__file__).resolve().parents[2]
A = "a" * 40
B = "b" * 40
C = "c" * 40

@pytest.fixture
def runtime(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("publicacao_local", ROOT / "infra/publicacao-local.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    modulo.RAIZ = tmp_path
    modulo.PASTA = tmp_path / "publicacoes"
    modulo.CELULA = "admin"
    for chave, valor in {"TAG": A, "ENDERECO_PROVA": "https://exemplo.test/healthz"}.items():
        monkeypatch.setenv(chave, valor)
    chamadas = []
    def comando(*args):
        chamadas.append(args)
        if args[:3] == ("docker", "compose", "config"):
            return "admin\nadmin-worker\npostgres"
        if args[:3] == ("docker", "compose", "ps"):
            return args[-1]
        if args[:2] == ("docker", "inspect") and args[3] == "{{json .State}}":
            return json.dumps({"Status": "running", "Running": True})
        if args[0] == "curl":
            return "200"
        return "sha256:imagem"
    monkeypatch.setattr(modulo, "comando", comando)
    publicar_e_aprovar(modulo, monkeypatch, A)
    (modulo.PASTA / "medicoes.jsonl").unlink()
    return modulo, chamadas

def ler(m):
    return json.loads((m.PASTA / "admin.json").read_text())

def preparar(m, monkeypatch):
    monkeypatch.setenv("TAG", B)
    m.executar("preparar")

def publicar_e_aprovar(m, monkeypatch, sha):
    monkeypatch.setenv("TAG", sha)
    for acao in ("preparar", "aplicar", "aprovar"):
        m.executar(acao)

def voltar(m, monkeypatch, de, para):
    monkeypatch.setenv("TAG", para)
    monkeypatch.setenv("ATUAL_ESPERADA", de)
    m.executar("recuperar")

def test_aprova_so_apos_mesma_imagem_e_http(runtime, monkeypatch):
    m, chamadas = runtime
    preparar(m, monkeypatch)
    assert ler(m)["aprovada"]["sha"] == A
    m.executar("aplicar")
    assert ler(m)["aprovada"]["sha"] == A
    m.executar("aprovar")
    assert ler(m)["aprovada"]["sha"] == B
    assert ler(m)["anterior_aprovada"]["sha"] == A
    assert any(c[0] == "curl" for c in chamadas)

def test_prova_falha_recupera_aprovada_e_prova_novamente(runtime, monkeypatch):
    m, chamadas = runtime
    preparar(m, monkeypatch)
    m.executar("aplicar")
    original = m.comando
    monkeypatch.setattr(m, "comando", lambda *a: "503" if a[0] == "curl" else original(*a))
    with pytest.raises(ValueError, match="HTTP 503"):
        m.executar("aprovar")
    assert ler(m)["aprovada"]["sha"] == A
    monkeypatch.setattr(m, "comando", original)
    monkeypatch.setenv("TAG", A)
    monkeypatch.setenv("ATUAL_ESPERADA", B)
    m.executar("recuperar")
    assert ler(m)["recuperacao"]["estado"] == "concluida"
    assert ler(m)["atual"] == A
    assert all("pg_restore" not in c for c in chamadas)
    assert ler(m)["aprovada"]["sha"] == A

def test_recuperacao_que_falhou_nao_tranca_a_proxima_publicacao(runtime, monkeypatch):
    m, chamadas = runtime
    preparar(m, monkeypatch)
    m.executar("aplicar")
    monkeypatch.setenv("TAG", A)
    monkeypatch.setenv("ATUAL_ESPERADA", B)
    original = m.comando
    monkeypatch.setattr(m, "comando", lambda *a: "500" if a[0] == "curl" else original(*a))
    with pytest.raises(ValueError, match="HTTP 500"):
        m.executar("recuperar")
    assert ler(m)["recuperacao"]["estado"] == "falhou"
    monkeypatch.setattr(m, "comando", original)
    publicar_e_aprovar(m, monkeypatch, C)
    assert ler(m)["aprovada"]["sha"] == C and "recuperacao" not in ler(m)

def test_vigia_usa_aprovada_anterior_distinta(runtime, monkeypatch):
    m, chamadas = runtime
    preparar(m, monkeypatch)
    m.executar("aplicar")
    m.executar("aprovar")
    monkeypatch.setenv("TAG", A)
    monkeypatch.setenv("ATUAL_ESPERADA", B)
    m.executar("recuperar")
    assert ler(m)["atual"] == A
    assert ler(m)["aprovada"]["sha"] == A and ler(m)["anterior_aprovada"] is None
    assert json.loads((m.PASTA / "imagens.json").read_text())["services"]["admin"]["image"].endswith(A)

def test_volta_guarda_a_aprovada_de_antes_para_a_proxima_volta(runtime, monkeypatch):
    m, chamadas = runtime
    publicar_e_aprovar(m, monkeypatch, B)
    publicar_e_aprovar(m, monkeypatch, C)
    voltar(m, monkeypatch, C, B)
    assert (ler(m)["aprovada"]["sha"], ler(m)["anterior_aprovada"]["sha"]) == (B, A)
    voltar(m, monkeypatch, B, A)
    assert ler(m)["atual"] == A and ler(m)["aprovada"]["sha"] == A

def test_backup_recusado_cancela_candidata_sem_trocar_pin(runtime, monkeypatch):
    m, chamadas = runtime
    preparar(m, monkeypatch)
    m.executar("abortar")
    assert ler(m)["candidata"] is None
    assert ler(m)["atual"] == A
    assert json.loads((m.PASTA / "imagens.json").read_text())["services"]["admin"]["image"].endswith(A)

def test_sem_journal_a_primeira_que_abre_o_endereco_vira_aprovada(runtime, monkeypatch):
    m, chamadas = runtime
    (m.PASTA / "admin.json").unlink()
    original = m.comando
    monkeypatch.setattr(m, "comando", lambda *a: "503" if a[0] == "curl" else original(*a))
    with pytest.raises(ValueError, match="HTTP 503"):
        publicar_e_aprovar(m, monkeypatch, B)
    assert ler(m)["aprovada"] is None
    monkeypatch.setattr(m, "comando", original)
    publicar_e_aprovar(m, monkeypatch, C)
    assert ler(m)["aprovada"]["sha"] == C and ler(m)["anterior_aprovada"] is None


def test_medicao_uma_linha_entrega_recuperada(runtime, monkeypatch):
    m, chamadas = runtime
    preparar(m, monkeypatch)
    m.executar("aplicar")
    original = m.comando
    monkeypatch.setattr(m, "comando", lambda *a: "503" if a[0] == "curl" else original(*a))
    with pytest.raises(ValueError):
        m.executar("aprovar")
    monkeypatch.setattr(m, "comando", original)
    monkeypatch.setenv("TAG", A)
    monkeypatch.setenv("ATUAL_ESPERADA", B)
    m.executar("recuperar")
    linhas = (m.PASTA / "medicoes.jsonl").read_text().splitlines()
    assert len(linhas) == 1
    dado = json.loads(linhas[0])
    assert dado["prova_falhou"] is True and dado["reversao"] is True
    assert dado["recuperacao_segundos"] >= 0


def test_aprovacao_inicial_tem_horario_com_fuso(runtime):
    from datetime import datetime
    m, chamadas = runtime
    assert datetime.fromisoformat(ler(m)["publicada_em"]).tzinfo is not None


def test_auxiliar_morto_recusa_promocao_mesmo_http_200(runtime, monkeypatch):
    m, chamadas = runtime
    preparar(m, monkeypatch)
    m.executar("aplicar")
    original = m.comando
    def comando(*args):
        if args[:2] == ("docker", "inspect") and args[3] == "{{json .State}}" and args[-1] == "admin-worker":
            return json.dumps({"Status": "exited", "Running": False})
        return original(*args)
    monkeypatch.setattr(m, "comando", comando)
    with pytest.raises(ValueError, match="serviço parado.*admin-worker"):
        m.executar("aprovar")
    assert ler(m)["aprovada"]["sha"] == A


def test_auxiliar_morto_recusa_recuperacao(runtime, monkeypatch):
    m, chamadas = runtime
    preparar(m, monkeypatch)
    m.executar("aplicar")
    monkeypatch.setenv("TAG", A)
    monkeypatch.setenv("ATUAL_ESPERADA", B)
    original = m.comando
    def comando(*args):
        if args[:2] == ("docker", "inspect") and args[3] == "{{json .State}}" and args[-1] == "admin-worker":
            return json.dumps({"Status": "running", "Running": True, "Health": {"Status": "unhealthy"}})
        return original(*args)
    monkeypatch.setattr(m, "comando", comando)
    with pytest.raises(ValueError, match="serviço sem saúde.*admin-worker"):
        m.executar("recuperar")
    assert ler(m)["recuperacao"]["estado"] == "falhou"


@pytest.mark.parametrize("resultado", ["backup_recusado", "aprovada", "recuperacao_falhou", "recuperada"])
def test_hora_publicacao_so_existe_com_prova_concluida(runtime, monkeypatch, resultado):
    from datetime import datetime
    m, chamadas = runtime
    preparar(m, monkeypatch)
    if resultado == "backup_recusado":
        m.executar("abortar")
    else:
        m.executar("aplicar")
        if resultado == "aprovada":
            m.executar("aprovar")
        else:
            monkeypatch.setenv("TAG", A)
            monkeypatch.setenv("ATUAL_ESPERADA", B)
            if resultado == "recuperacao_falhou":
                original = m.comando
                monkeypatch.setattr(m, "comando", lambda *a: "503" if a[0] == "curl" else original(*a))
                with pytest.raises(ValueError, match="HTTP 503"):
                    m.executar("recuperar")
            else:
                m.executar("recuperar")
    linhas = (m.PASTA / "medicoes.jsonl").read_text().splitlines()
    assert len(linhas) == 1
    dado = json.loads(linhas[0])
    if resultado in {"backup_recusado", "recuperacao_falhou"}:
        assert dado["publicado_em"] is None
    else:
        assert datetime.fromisoformat(dado["publicado_em"]).tzinfo is not None
    assert dado["pedido_em"] == ler(m)["pedido_em"]
