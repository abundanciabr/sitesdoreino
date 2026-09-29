"""Prova que o produtor mede entradas reais e recusa prova anterior ao merge."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import candidato
import preparar_candidato as preparo

BASE = "docker.io/library/python@sha256:" + "a" * 64
IMAGEM = "ghcr.io/abundanciabr/plataforma-admin@sha256:" + "b" * 64
AMBIENTE = {
    "runner": "ubuntu-24.04",
    "arquitetura": "amd64",
    "docker": "28.0",
    "python": "3.12",
}
PACOTES = [
    {"name": "Django", "version": "5.1.4"},
    {"name": "asgiref", "version": "3.8.1"},
]


def git(raiz, *args):
    return subprocess.run(
        ["git", *args], cwd=raiz, text=True, capture_output=True, check=True
    ).stdout.strip()


def escrever(raiz, nome, texto):
    caminho = raiz / nome
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(texto, encoding="utf-8")


@pytest.fixture
def bancada(tmp_path):
    for nome in (
        *preparo.POLITICAS,
        *(caminho for grupo in preparo.VERIFICADORES.values() for caminho in grupo),
        "celulas.yml",
        "infra/docker-compose.yml",
        "contracts/admin.openapi.yaml",
        "services/admin/config/settings.py",
        "services/admin/migrations/0001.py",
    ):
        if nome == "ci":
            nome = "ci/verificador.py"
        escrever(tmp_path, nome, nome)
    escrever(tmp_path, "services/admin/Dockerfile", "FROM python:3.12-slim\nCOPY . .\n")
    escrever(tmp_path, "services/admin/requirements.txt", "Django==5.1.4\n")
    escrever(tmp_path, "services/admin/apps.py", "valor = 1\n")
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.name", "Teste")
    git(tmp_path, "config", "user.email", "teste@example.invalid")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "base")
    base = git(tmp_path, "rev-parse", "HEAD")
    escrever(tmp_path, "services/admin/apps.py", "valor = 2\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "fonte")
    fonte = git(tmp_path, "rev-parse", "HEAD")
    return tmp_path, base, fonte


def provas(atual, revisao, execucao):
    return [
        {
            "nome": nome,
            "resultado": "PASS",
            "run_id": execucao["run_id"] if nome == "build" else 100 + indice,
            "tentativa": 1,
            "job_id": execucao["job_id"] if nome == "build" else 200 + indice,
            "revisao": revisao,
        }
        for indice, nome in enumerate(sorted(atual["verificadores"]), 1)
    ]


def montar(raiz, base, fonte, integracao, atual, revisao_provas):
    execucao = {"run_id": 10, "tentativa": 1, "job_id": 20}
    lista = provas(atual, revisao_provas, execucao)
    next(p for p in lista if p["nome"] == "build")["revisao"] = integracao
    return preparo.criar(
        raiz,
        "admin",
        "TAR-980",
        1,
        fonte,
        base,
        integracao,
        atual,
        lista,
        execucao,
        IMAGEM,
        candidato.assinatura_build(atual),
    )


def test_snapshot_mede_dependencias_transitivas_e_dockerfile_pinado(bancada):
    raiz, _, _ = bancada
    atual = preparo.snapshot(raiz, "admin", BASE, PACOTES, AMBIENTE)
    assert set(atual["entradas"]) == candidato.GRUPOS
    assert atual["entradas"]["dependencias"]["pacote:asgiref"] == candidato.digest(
        "3.8.1"
    )
    assert atual["entradas"]["imagem_base"]["docker.io/library/python"] == "a" * 64
    assert preparo.dockerfile_pinado(raiz, "admin", BASE).startswith(
        b"FROM docker.io/library/python@sha256:"
    )
    assert atual["entradas"]["build"]["dockerfile_pinado"]


def test_mudanca_de_dependencia_invalida_prova_e_imagem(bancada):
    raiz, _, _ = bancada
    anterior = preparo.snapshot(raiz, "admin", BASE, PACOTES, AMBIENTE)
    pacotes_novos = [PACOTES[0], {"name": "asgiref", "version": "3.9.0"}]
    transitiva_nova = preparo.snapshot(raiz, "admin", BASE, pacotes_novos, AMBIENTE)
    assert candidato.assinatura_build(anterior) != candidato.assinatura_build(
        transitiva_nova
    )
    escrever(raiz, "services/admin/requirements.txt", "Django==5.2.0\n")
    novo = preparo.snapshot(raiz, "admin", BASE, PACOTES, AMBIENTE)
    assert anterior["entradas"]["dependencias"] != novo["entradas"]["dependencias"]
    assert candidato.assinatura_build(anterior) != candidato.assinatura_build(novo)
    assert candidato.assinatura_prova(
        anterior, "muralhas", sorted(candidato.GRUPOS)
    ) != candidato.assinatura_prova(novo, "muralhas", sorted(candidato.GRUPOS))


def test_merge_que_muda_codigo_exige_nova_prova(bancada):
    raiz, base, fonte = bancada
    escrever(raiz, "README.md", "mudança independente\n")
    git(raiz, "add", ".")
    git(raiz, "commit", "-qm", "merge independente")
    integracao_sem_mudanca = git(raiz, "rev-parse", "HEAD")
    atual = preparo.snapshot(raiz, "admin", BASE, PACOTES, AMBIENTE)
    assert (
        candidato.validar(
            montar(raiz, base, fonte, integracao_sem_mudanca, atual, fonte)
        )["estado"]
        == "PASS"
    )
    escrever(raiz, "services/admin/apps.py", "valor = 3\n")
    git(raiz, "add", ".")
    git(raiz, "commit", "-qm", "merge alterou candidato")
    integracao = git(raiz, "rev-parse", "HEAD")
    atual = preparo.snapshot(raiz, "admin", BASE, PACOTES, AMBIENTE)
    with pytest.raises(preparo.PreparoInvalido, match="novas provas"):
        montar(raiz, base, fonte, integracao, atual, fonte)
    manifesto = montar(raiz, base, fonte, integracao, atual, integracao)
    assert candidato.validar(manifesto)["estado"] == "PASS"
    assert (
        candidato.validar(
            manifesto,
            preparo.snapshot(raiz, "admin", BASE, PACOTES, AMBIENTE),
        )["estado"]
        == "PASS"
    )


def test_label_divergente_e_base_mutavel_sao_recusados(bancada):
    raiz, base, fonte = bancada
    atual = preparo.snapshot(raiz, "admin", BASE, PACOTES, AMBIENTE)
    with pytest.raises(preparo.PreparoInvalido, match="label"):
        preparo.criar(
            raiz,
            "admin",
            "TAR-980",
            1,
            fonte,
            base,
            fonte,
            atual,
            provas(atual, fonte, {"run_id": 10, "tentativa": 1, "job_id": 20}),
            {"run_id": 10, "tentativa": 1, "job_id": 20},
            IMAGEM,
            "0" * 64,
        )
    with pytest.raises(preparo.PreparoInvalido, match="sem digest"):
        preparo.snapshot(raiz, "admin", "python:3.12-slim", PACOTES, AMBIENTE)


def test_imagem_local_exige_digest_e_label_exatos(monkeypatch, bancada):
    raiz, _, _ = bancada

    def inspecionar(args, **_):
        assert args == ["docker", "image", "inspect", IMAGEM]
        return subprocess.CompletedProcess(
            args,
            0,
            json.dumps(
                [
                    {
                        "RepoDigests": [IMAGEM],
                        "Config": {"Labels": {preparo.LABEL: "c" * 64}},
                    }
                ]
            ),
            "",
        )

    monkeypatch.setattr(preparo.subprocess, "run", inspecionar)
    assert preparo.label_da_imagem(raiz, IMAGEM) == "c" * 64

    def digest_errado(args, **_):
        return subprocess.CompletedProcess(
            args,
            0,
            json.dumps(
                [
                    {
                        "RepoDigests": [IMAGEM[:-64] + "d" * 64],
                        "Config": {"Labels": {preparo.LABEL: "c" * 64}},
                    }
                ]
            ),
            "",
        )

    monkeypatch.setattr(preparo.subprocess, "run", digest_errado)
    with pytest.raises(preparo.PreparoInvalido, match="digest local"):
        preparo.label_da_imagem(raiz, IMAGEM)


def test_checkout_modificado_nao_gera_snapshot_oficial(bancada):
    raiz, _, fonte = bancada
    preparo.conferir_checkout(raiz, fonte)
    escrever(raiz, "services/admin/apps.py", "valor = alterado\n")
    with pytest.raises(preparo.PreparoInvalido, match="arquivos versionados"):
        preparo.conferir_checkout(raiz, fonte)
    with pytest.raises(preparo.PreparoInvalido, match="revisão integrada"):
        preparo.conferir_checkout(raiz, "f" * 40)
