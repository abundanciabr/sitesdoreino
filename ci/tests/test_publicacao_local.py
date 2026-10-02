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
    for chave, valor in {"TAG": A, "PROVA_IMAGEM_SHA": A, "COMPATIBILIDADE_DADOS": "expand-v1",
                         "COMPATIBILIDADE_CONFIGURACAO": "env-v1", "ENDERECO_PROVA": "https://exemplo.test/healthz"}.items():
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
    modulo.executar("inicializar")
    return modulo, chamadas

def ler(m):
    return json.loads((m.PASTA / "admin.json").read_text())

def preparar(m, monkeypatch):
    monkeypatch.setenv("TAG", B)
    monkeypatch.setenv("PROVA_IMAGEM_SHA", B)
    m.executar("preparar")

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
    with pytest.raises(ValueError, match="já executada"):
        m.executar("recuperar")

def test_recuperacao_falha_uma_vez(runtime, monkeypatch):
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
    with pytest.raises(ValueError, match="já executada"):
        m.executar("recuperar")

def test_vigia_usa_aprovada_anterior_distinta(runtime, monkeypatch):
    m, chamadas = runtime
    preparar(m, monkeypatch)
    m.executar("aplicar")
    m.executar("aprovar")
    monkeypatch.setenv("TAG", A)
    monkeypatch.setenv("ATUAL_ESPERADA", B)
    m.executar("recuperar")
    assert ler(m)["atual"] == A
    assert json.loads((m.PASTA / "imagens.json").read_text())["services"]["admin"]["image"].endswith(A)

def test_backup_recusado_cancela_candidata_sem_trocar_pin(runtime, monkeypatch):
    m, chamadas = runtime
    preparar(m, monkeypatch)
    m.executar("abortar")
    assert ler(m)["candidata"] is None
    assert ler(m)["atual"] == A
    assert json.loads((m.PASTA / "imagens.json").read_text())["services"]["admin"]["image"].endswith(A)

def test_recusa_compatibilidade_diferente_sem_exigir_suites(runtime, monkeypatch):
    m, chamadas = runtime
    monkeypatch.setenv("TAG", B)
    monkeypatch.setenv("COMPATIBILIDADE_CONFIGURACAO", "coord-removida")
    with pytest.raises(ValueError, match="incompatível"):
        m.executar("preparar")


def test_infra_prova_pin_recuperado_e_preserva_aprovacao(runtime, monkeypatch):
    m, chamadas = runtime
    preparar(m, monkeypatch)
    m.executar("aplicar")
    monkeypatch.setenv("TAG", A)
    monkeypatch.setenv("ATUAL_ESPERADA", B)
    m.executar("recuperar")
    antes = ler(m)
    chamadas.clear()
    m.executar("conferir-infra")
    assert ler(m) == antes
    assert any(c[0] == "curl" for c in chamadas)
    assert any(c[:3] == ("docker", "image", "inspect") and c[-1].endswith(A) for c in chamadas)


def test_recusa_imagem_divergente_antes_da_aprovacao(runtime, monkeypatch):
    m, chamadas = runtime
    preparar(m, monkeypatch)
    m.executar("aplicar")
    original = m.comando
    monkeypatch.setattr(m, "comando", lambda *a: "outra-imagem" if a[:2] == ("docker", "inspect") and a[3] == "{{.Image}}" else original(*a))
    with pytest.raises(ValueError, match="imagem aplicada diverge"):
        m.executar("aprovar")
    assert ler(m)["aprovada"]["sha"] == A


def test_inicializacao_recusa_http_sem_escrever_aprovacao(runtime, monkeypatch):
    m, chamadas = runtime
    (m.PASTA / "admin.json").unlink()
    original = m.comando
    monkeypatch.setattr(m, "comando", lambda *a: "503" if a[0] == "curl" else original(*a))
    with pytest.raises(ValueError, match="HTTP 503"):
        m.executar("inicializar")
    assert not (m.PASTA / "admin.json").exists()


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


@pytest.mark.parametrize("falha_prova", [False, True])
def test_retorno_infra_prova_uma_vez_e_para(tmp_path, falha_prova):
    import os
    import subprocess
    bash = BASH
    assert bash
    fonte = (ROOT / "infra/sincronizar-infra-na-vps.sh").read_text(encoding="utf-8")
    funcao = fonte[fonte.index("restaurar_o_que_estava_no_ar() {"):fonte.index("# O trap cobre")]
    trap = next(linha for linha in fonte.splitlines() if linha.startswith("trap "))
    script = tmp_path / "infra-retorno.sh"
    script.write_text("""set -e
RAIZ=$PWD
STAMP=teste
TROCADO=1
cp() { :; }
rm() { :; }
docker() { :; }
python3() { echo PROVA-RETORNO; return "$FALHA_PROVA"; }
""" + funcao + trap + "\nexit 1\n", encoding="utf-8", newline="\n")
    resultado = subprocess.run([bash, "infra-retorno.sh"], cwd=tmp_path,
                               env=dict(os.environ, FALHA_PROVA=str(int(falha_prova))),
                               capture_output=True, text=True)
    assert resultado.returncode == (2 if falha_prova else 1)
    assert resultado.stdout.count("PROVA-RETORNO") == 1
    assert ("RECUPERACAO-TERMINAL" in resultado.stderr) == falha_prova
    assert ("VOLTA ATRAS CONCLUIDA" in resultado.stdout) != falha_prova


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


def test_recuperacao_falha_registrada_sem_bloquear_publicacao_nova(runtime, monkeypatch):
    m, chamadas = runtime
    monkeypatch.delenv("TAG")
    monkeypatch.setenv("ATUAL_ESPERADA", A)
    m.executar("encerrar-recuperacao")
    estado = ler(m)
    assert estado["recuperacao"]["estado"] == "falhou"
    m.executar("encerrar-recuperacao")
    assert ler(m) == estado
    monkeypatch.setenv("TAG", B)
    monkeypatch.setenv("PROVA_IMAGEM_SHA", B)
    m.executar("preparar")
    assert ler(m)["candidata"] == B
    assert not any("up" in c for c in chamadas)


def test_latch_global_nao_adivinha_celula_e_so_aprovacao_limpa(runtime, monkeypatch):
    m, chamadas = runtime
    m.CELULA = ""
    monkeypatch.delenv("TAG")
    m.executar("encerrar-recuperacao")
    terminal = m.PASTA / "recuperacao-terminal.json"
    antes = terminal.read_text()
    m.executar("encerrar-recuperacao")
    assert terminal.read_text() == antes
    assert ler(m)["atual"] == A
    m.CELULA = "admin"
    preparar(m, monkeypatch)
    assert terminal.exists()
    m.executar("aplicar")
    assert terminal.exists()
    m.executar("aprovar")
    assert not terminal.exists()


@pytest.mark.parametrize("http", ["200", "503"])
def test_bootstrap_tag_main_exige_pull_sha_e_prova_sem_troca(tmp_path, http):
    import os
    import subprocess
    import sys
    bash = BASH
    assert bash
    fonte = (ROOT / "infra/deploy-celula-na-vps.sh").read_text(encoding="utf-8")
    inicio = fonte.index('if [ "${MODO:-publicar}" = "inicializar" ]; then')
    ramo = fonte[inicio:fonte.index("\nfi\n", inicio) + len("\nfi\n")]
    adapter = tmp_path / "adapter.py"
    adapter.write_text("""import importlib.util
import json
import os
from pathlib import Path
import sys
spec = importlib.util.spec_from_file_location('publicacao_local', os.environ['MODULO_PUBLICACAO'])
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
def comando(*args):
    if args[:3] == ('docker', 'compose', 'config'):
        return 'admin'
    if args[:3] == ('docker', 'compose', 'ps'):
        return 'container-em-main'
    if args[:2] == ('docker', 'inspect'):
        if args[3] == '{{json .State}}':
            return json.dumps({'Status': 'running', 'Running': True})
        return 'sha256:imagem-em-main'
    if args[:3] == ('docker', 'image', 'inspect'):
        assert (m.RAIZ / '.tag-sha').exists(), 'SHA indisponível sem pull'
        return 'sha256:imagem-em-main'
    if args[0] == 'curl':
        return os.environ['HTTP_PROVA']
    raise AssertionError(args)
m.comando = comando
m.executar(sys.argv[-1])
""", encoding="utf-8")
    script = tmp_path / "bootstrap.sh"
    script.write_text("""set -eu
RAIZ=$PWD
docker() {
  if [ "$1" != pull ]; then echo TROCA-INDEVIDA >&2; return 2; fi
  printf '%s' "$2" > .tag-sha
}
python3() { "$PYTHON_TESTE" "$RAIZ/adapter.py" "$@"; }
""" + ramo, encoding="utf-8", newline="\n")
    ambiente = dict(os.environ, CELULA="admin", TAG=A, PROVA_IMAGEM_SHA=A, MODO="inicializar",
                    COMPATIBILIDADE_DADOS="expand-v1", COMPATIBILIDADE_CONFIGURACAO="env-v1",
                    ENDERECO_PROVA="https://exemplo.test/healthz", PLATAFORMA_DIR=tmp_path.as_posix(),
                    HTTP_PROVA=http, PYTHON_TESTE=Path(sys.executable).as_posix(),
                    MODULO_PUBLICACAO=(ROOT / "infra/publicacao-local.py").as_posix())
    resultado = subprocess.run([bash, "bootstrap.sh"], cwd=tmp_path, env=ambiente,
                               capture_output=True, text=True)
    assert (tmp_path / ".tag-sha").read_text().endswith(A)
    assert (resultado.returncode == 0) == (http == "200"), resultado.stdout + resultado.stderr
    assert (tmp_path / "publicacoes/admin.json").exists() == (http == "200")
    assert "TROCA-INDEVIDA" not in resultado.stderr
    assert ("INICIALIZACAO-CONCLUIDA" in resultado.stdout) == (http == "200")


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
