"""`ci/cofre.py`: guarda no Gerenciador de Credenciais do Windows, entrega só ao
processo filho, e nenhum valor sai em stdout ou stderr.

Valores fictícios, sorteados aqui; cada teste apaga o que criou.
"""

from __future__ import annotations

import hashlib
import secrets
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform != "win32", reason="o cofre é o Gerenciador de Credenciais do Windows"
)

COFRE = str(Path(__file__).resolve().parents[1] / "cofre.py")


def cofre(*args: str, entrada: str | None = None) -> subprocess.CompletedProcess:
    # Um processo NOVO por chamada: prova que o segredo persiste fora dele.
    return subprocess.run(
        [sys.executable, COFRE, *args],
        input=entrada,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )


@pytest.fixture
def nome():
    nome = f"teste-{secrets.token_hex(6)}"
    yield nome
    cofre("revogar", nome)


def test_guardar_usar_conferir_listar_revogar_sem_vazar(nome):
    valor = secrets.token_urlsafe(32)
    saidas: list[str] = []

    guardou = cofre("guardar", nome, entrada=valor + "\r\n")
    saidas += [guardou.stdout, guardou.stderr]
    assert guardou.returncode == 0, guardou.stderr

    variavel = nome.upper().replace("-", "_")
    usou = cofre(
        "usar",
        nome,
        "--",
        sys.executable,
        "-c",
        f"import os,hashlib;print(hashlib.sha256(os.environ['{variavel}'].encode()).hexdigest())",
    )
    saidas += [usou.stdout, usou.stderr]
    assert usou.returncode == 0, usou.stderr
    # O filho recebeu exatamente o valor (sem o \r\n do cano), e só a
    # impressão dele aparece.
    assert usou.stdout.strip() == hashlib.sha256(valor.encode()).hexdigest()

    conferiu = cofre("conferir", nome)
    saidas += [conferiu.stdout, conferiu.stderr]
    assert conferiu.returncode == 0
    assert f"presente, {len(valor)} caracteres" in conferiu.stdout

    listou = cofre("listar")
    saidas += [listou.stdout, listou.stderr]
    assert nome in listou.stdout.split()

    revogou = cofre("revogar", nome)
    saidas += [revogou.stdout, revogou.stderr]
    assert revogou.returncode == 0
    assert cofre("conferir", nome).returncode == 1

    for texto in saidas:
        assert valor not in texto


def test_o_filho_so_recebe_os_nomes_pedidos(nome):
    outro = f"{nome}-outro"
    try:
        assert cofre("guardar", nome, entrada="valor-a").returncode == 0
        assert cofre("guardar", outro, entrada="valor-b").returncode == 0
        usou = cofre(
            "usar",
            nome,
            "--",
            sys.executable,
            "-c",
            f"import os;print('{outro.upper().replace('-', '_')}' in os.environ)",
        )
        assert usou.stdout.strip() == "False"
    finally:
        cofre("revogar", outro)


def test_ausente_nao_executa_o_comando(nome):
    usou = cofre("usar", nome, "--", sys.executable, "-c", "print('rodou')")
    assert usou.returncode == 2
    assert "rodou" not in usou.stdout
    assert f"ausente: {nome}" in usou.stderr


def test_valor_vazio_nao_e_guardado(nome):
    guardou = cofre("guardar", nome, entrada="")
    assert guardou.returncode == 2
    assert cofre("conferir", nome).returncode == 1


def test_nome_invalido_e_recusado():
    assert cofre("conferir", "../fora").returncode == 2
