"""Prova pela borda: pytest real, isolamento e conteúdo original preservado."""
import json
import subprocess
import sys
from pathlib import Path

import pytest
import provar_guardas as guardas

SCRIPT = Path(__file__).resolve().parents[1] / "provar_guardas.py"


@pytest.fixture
def bancada(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "codigo.py").write_bytes(b"valor = 1\r\nvalor = 2\r\n")
    (tmp_path / "test_codigo.py").write_text(
        "import codigo\ndef test_valor():\n    # guarda: codigo.py:2\n    assert codigo.valor == 2\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.name=Teste", "-c", "user.email=teste@example.org",
                    "-c", "core.hooksPath=", "commit", "-qm", "baseline"], cwd=tmp_path, check=True)
    return tmp_path


def provar(bancada, *alvos):
    antes = (bancada / "codigo.py").read_bytes()
    proc = subprocess.run([sys.executable, str(SCRIPT), *(alvos or ["test_codigo.py"])],
                          cwd=bancada, capture_output=True, text=True, encoding="utf-8", timeout=90)
    assert (bancada / "codigo.py").read_bytes() == antes
    assert len(proc.stdout.encode()) < 500, proc.stdout
    resultado = json.loads(proc.stdout)
    evidencia = json.loads(Path(resultado["log"]).read_text(encoding="utf-8"))
    return proc.returncode, resultado, evidencia


def test_sabotagem_falha_restauracao_passa_e_preserva_crlf(bancada):
    codigo, resultado, evidencia = provar(bancada)
    assert codigo == 0, resultado
    guarda = evidencia["guardas"][0]
    assert guarda["reprovou"] is True
    assert guarda["baseline"] == "PASS"
    assert guarda["mutacao"] == "FAIL"
    assert guarda["restauracao"] == "PASS"
    assert guarda["teste"] == "test_codigo.py::test_valor"
    assert guarda["sha256"]


@pytest.mark.parametrize("corpo,estado", [
    ("import codigo\ndef test_valor():\n    # guarda: codigo.py:2\n    assert codigo.valor == 999", "FAIL"),
    ("def test_valor():\n    # guarda: codigo.py:2\n    assert True", "FAIL"),
    ("import pytest\n@pytest.mark.skip(reason='declarado')\ndef test_valor():\n    # guarda: codigo.py:2\n    assert True", "ERROR"),
    ("import ausente\ndef test_valor():\n    # guarda: codigo.py:2\n    assert True", "ERROR"),
    ("def test_valor(): assert True", "ERROR")])
def test_falso_verde_e_instrumento_quebrado_nao_provam(bancada, corpo, estado):
    (bancada / "test_codigo.py").write_text(corpo)
    codigo, resultado, evidencia = provar(bancada)
    assert codigo != 0
    assert resultado["estado"] == estado
    assert not any(g["reprovou"] for g in evidencia["guardas"])


@pytest.mark.parametrize("alvo", ["ausente.py", "sem_match_*.py"])
def test_entrada_inexistente_nao_prova(bancada, alvo):
    codigo, resultado, _ = provar(bancada, alvo)
    assert codigo == 2 and resultado["estado"] == "ERROR"


@pytest.mark.parametrize("protecao", ["../fora.py:1", "codigo.py:90", "codigo.py:0", "ausente.py:1", "codigo.py:abc"])
def test_marcador_invalido_nao_prova(bancada, protecao):
    (bancada / "test_codigo.py").write_text(
        f"def test_valor():\n    # guarda: {protecao}\n    assert True")
    codigo, resultado, _ = provar(bancada)
    assert codigo == 2 and resultado["estado"] == "ERROR"


@pytest.mark.parametrize("linha", [b"\r\n", b"# comentario\r\n", b"if True:\r\n    valor = 2\r\n"])
def test_linha_vazia_comentario_ou_sintaxe_quebrada_e_erro(bancada, linha):
    (bancada / "codigo.py").write_bytes(b"valor = 1\r\n" + linha)
    codigo, resultado, _ = provar(bancada)
    assert codigo == 2 and resultado["estado"] == "ERROR"


def test_mede_estado_nao_commitado_e_nao_roda_teste_vizinho(bancada):
    (bancada / "codigo.py").write_bytes(b"valor = 1\r\nvalor = 3\r\n")
    (bancada / "nao_rastreado.py").write_text("esperado = 3")
    (bancada / "test_codigo.py").write_text(
        "import codigo, nao_rastreado\ndef test_valor():\n    # guarda: codigo.py:2\n"
        "    assert codigo.valor == nao_rastreado.esperado\n\ndef test_vizinho(): assert False")
    codigo, resultado, _ = provar(bancada)
    assert codigo == 0, resultado
    assert (bancada / "nao_rastreado.py").read_text() == "esperado = 3"


def test_erro_de_setup_depois_da_mutacao_nao_e_prova(bancada):
    # guarda: ci/provar_guardas.py:207
    (bancada / "test_codigo.py").write_text(
        "import codigo, pytest\n@pytest.fixture\ndef valor():\n"
        "    if codigo.valor != 2: raise RuntimeError('setup quebrou')\n"
        "    return codigo.valor\ndef test_valor(valor):\n    # guarda: codigo.py:2\n    assert valor == 2")
    codigo, resultado, evidencia = provar(bancada)
    assert codigo == 2 and resultado["estado"] == "ERROR"
    assert evidencia["guardas"][0]["reprovou"] is False
    assert evidencia["guardas"][0]["restauracao"] == "PASS"


def test_excecao_restaura_bytes_do_arquivo_descartavel(tmp_path):
    # guarda: ci/provar_guardas.py:123
    alvo = tmp_path / "codigo.py"
    antes = b"valor = 1\r\nvalor = 2\r\n"
    alvo.write_bytes(antes)
    with pytest.raises(RuntimeError):
        with guardas.sabotar(alvo, 2):
            assert alvo.read_bytes() != antes
            raise RuntimeError("falha externa")
    assert alvo.read_bytes() == antes


def test_exclusao_staged_nao_reaparece_na_copia(bancada):
    # guarda: ci/provar_guardas.py:158
    (bancada / "antigo.py").write_text("valor = 99")
    subprocess.run(["git", "add", "antigo.py"], cwd=bancada, check=True)
    subprocess.run(["git", "-c", "user.name=Teste", "-c", "user.email=teste@example.org",
                    "-c", "core.hooksPath=", "commit", "-qm", "dependencia antiga"], cwd=bancada, check=True)
    subprocess.run(["git", "rm", "antigo.py"], cwd=bancada, check=True, capture_output=True)
    (bancada / "test_codigo.py").write_text(
        "import codigo\nfrom pathlib import Path\ndef test_valor():\n    # guarda: codigo.py:2\n"
        "    assert not Path('antigo.py').exists()\n    assert codigo.valor == 2")
    codigo, resultado, evidencia = provar(bancada)
    assert codigo == 0, resultado
    assert evidencia["bancada"]["ausentes"] == ["antigo.py"]
    assert not (bancada / "antigo.py").exists()


def test_manifesto_vincula_dependencia_nao_commitada(bancada):
    # guarda: ci/provar_guardas.py:155
    import hashlib
    (bancada / "dependencia.py").write_bytes(b"esperado = 2\n")
    (bancada / "test_codigo.py").write_text(
        "import codigo, dependencia\ndef test_valor():\n    # guarda: codigo.py:2\n"
        "    assert codigo.valor == dependencia.esperado")
    codigo, resultado, evidencia = provar(bancada)
    assert codigo == 0, resultado
    assert evidencia["bancada"]["arquivos"]["dependencia.py"] == hashlib.sha256(b"esperado = 2\n").hexdigest()
    assert evidencia["bancada_sha256"] == hashlib.sha256(
        json.dumps(evidencia["bancada"], sort_keys=True).encode("utf-8")).hexdigest()


def test_erro_de_coleta_apos_mutacao_nao_prova(bancada):
    (bancada / "codigo.py").write_text("valor = 1\nvalor = 2\nif valor == 1:\n    import inexistente")
    codigo, resultado, evidencia = provar(bancada)
    assert codigo == 2 and resultado["estado"] == "ERROR"
    assert evidencia["guardas"][0]["mutacao"] == "ERROR"
    assert evidencia["guardas"][0]["restauracao"] == "PASS"
    assert evidencia["guardas"][0]["reprovou"] is False


def test_caminho_fora_da_raiz_recusado_mesmo_existindo(tmp_path):
    # guarda: ci/provar_guardas.py:38
    raiz = tmp_path / "bancada"
    raiz.mkdir()
    (tmp_path / "fora.py").write_text("valor = 1")
    with pytest.raises(guardas.ProvaInvalida, match="fora da bancada"):
        guardas.dentro(raiz, "../fora.py")


def test_selecao_nao_aceita_falha_de_vizinho():
    assert not guardas.selecionados({"dados": {"tests": [
        {"nodeid": "test_a.py::test_vizinho", "outcome": "failed"}
    ]}}, "test_a.py::test_alvo")
    assert guardas.selecionados({"dados": {"tests": [
        {"nodeid": "test_a.py::test_alvo[caso]", "outcome": "failed"}
    ]}}, "test_a.py::test_alvo")
