"""Contraprovas da TAR-310 no portão normal da fila."""

import copy
import json
import subprocess
import sys

import pytest

import fila
import responsabilidades
from test_fila import montar, tarefa
from test_responsabilidades import escrever_registro, registro_completo


def git(raiz, *args):
    subprocess.run(["git", "-C", str(raiz), *args], check=True, capture_output=True)


@pytest.fixture
def bancada(tmp_path):
    montar(tmp_path)
    escrever_registro(tmp_path, registro_completo())
    git(tmp_path, "init", "-b", "main")
    git(tmp_path, "config", "user.name", "Teste")
    git(tmp_path, "config", "user.email", "teste@example.com")
    git(tmp_path, "add", "painel")
    git(tmp_path, "commit", "-m", "cadastro válido")
    git(tmp_path, "checkout", "-b", "correcao")
    return tmp_path


def acrescentar_tarefa(raiz, **campos):
    dados = tarefa("9999", responsabilidade="curso", responsabilidade_obrigatoria=True)
    dados.update(campos)
    dados = {chave: valor for chave, valor in dados.items() if valor is not None}
    caminho = raiz / "fila/tarefas/9999-exemplo.json"
    caminho.write_text(json.dumps(dados), encoding="utf-8")
    git(raiz, "add", "fila/tarefas/9999-exemplo.json")
    git(raiz, "commit", "-m", "tarefa nova")


@pytest.mark.parametrize("campos", [
    {"responsabilidade": None, "responsabilidade_obrigatoria": None},
    {"responsabilidade": "curso", "responsabilidade_obrigatoria": False},
    {"responsabilidade": "inexistente"},
])
def test_portao_recusa_tarefa_nova_sem_vinculo_valido(bancada, campos):
    # guarda: ci/fila.py:2619
    # guarda: ci/fila.py:2625
    acrescentar_tarefa(bancada, **campos)
    problemas = fila.conferir_imutabilidade(bancada, "main")
    assert problemas, "o portão aceitou tarefa nova sem vínculo válido"
    assert "responsabilidade" in " ".join(problemas)
    assert "Corrija" in " ".join(problemas)


@pytest.mark.parametrize("defeito", ["vazio", "duplicado", "json", "ausente"])
def test_validar_recusa_cadastro_invalido(bancada, defeito, capsys):
    # guarda: ci/fila.py:2465
    # guarda: ci/responsabilidades.py:208
    registro = registro_completo()
    if defeito == "vazio":
        registro["unidades"] = []
    elif defeito == "duplicado":
        outra = copy.deepcopy(registro["unidades"][0])
        outra["titular_funcao"] = "comercial-relacionamento"
        registro["unidades"].append(outra)
    texto = "{" if defeito == "json" else json.dumps(registro)
    (bancada / "painel/responsabilidades.json").write_text(texto, encoding="utf-8")
    if defeito == "ausente":
        acrescentar_tarefa(bancada)
        (bancada / "painel/responsabilidades.json").unlink()
    assert fila.cmd_validar(bancada) == 1
    saida = capsys.readouterr().out
    assert "Corrija painel/responsabilidades.json" in saida
    assert "Traceback" not in saida


def test_resolucao_recusa_identificador_duplicado():
    # guarda: ci/responsabilidades.py:56
    registro = registro_completo()
    registro["unidades"].append(copy.deepcopy(registro["unidades"][0]))
    unidade, problemas = responsabilidades.resolver_unidade(registro, "curso")
    assert unidade is None
    assert any("duplicado" in erro for erro in problemas)


def test_portao_aceita_cadastro_e_tarefa_validos(bancada):
    acrescentar_tarefa(bancada)
    assert fila.cmd_validar(bancada) == 0
    assert fila.conferir_imutabilidade(bancada, "main") == []


def test_cli_recusa_json_ilegivel_sem_traceback(bancada):
    # guarda: ci/responsabilidades.py:205
    (bancada / "painel/responsabilidades.json").write_text("{", encoding="utf-8")
    resultado = subprocess.run(
        [sys.executable, responsabilidades.__file__, "--raiz", str(bancada), "--auditar"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert resultado.returncode == 1
    assert "Corrija painel/responsabilidades.json" in resultado.stdout
    assert "Traceback" not in resultado.stderr
