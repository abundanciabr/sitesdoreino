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
AMBIENTE_FONTE = {**AMBIENTE, "pacotes": PACOTES}


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
    lista = [
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
    for prova in lista:
        nome = prova["nome"]
        escopo = sorted(candidato.BUILD if nome == "build" else candidato.FONTE)
        prova["emissao"] = {
            "versao": 1,
            **{
                campo: prova[campo]
                for campo in (
                    "nome",
                    "resultado",
                    "run_id",
                    "tentativa",
                    "job_id",
                    "revisao",
                )
            },
            "escopo": escopo,
            "entradas": candidato.assinatura_prova(atual, nome, escopo),
            "ambiente": atual["ambiente"],
            "verificador": atual["verificadores"][nome],
            "insumos": {grupo: atual["entradas"][grupo] for grupo in escopo},
        }
        if nome == "ci-celula-gate":
            prova["emissao"]["job_id"] += 1000
        prova["bundle"] = {"dsseEnvelope": {"payload": "assinada-pelo-job"}}
    return lista


def montar(raiz, base, fonte, integracao, atual, revisao_provas):
    execucao = {"run_id": 10, "tentativa": 1, "job_id": 20}
    lista = provas(atual, revisao_provas, execucao)
    build = next(p for p in lista if p["nome"] == "build")
    build["revisao"] = integracao
    build["emissao"]["revisao"] = integracao
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


def test_snapshot_fonte_nao_depende_da_imagem_futura(bancada):
    raiz, _, _ = bancada
    fonte = preparo.snapshot_fonte(raiz, "admin", AMBIENTE_FONTE)
    completo = preparo.snapshot(raiz, "admin", BASE, PACOTES, AMBIENTE)
    assert set(fonte["entradas"]) == candidato.FONTE
    assert fonte["entradas"] == {
        grupo: completo["entradas"][grupo] for grupo in candidato.FONTE
    }
    assert "services/admin/requirements.txt" in fonte["entradas"]["codigo"]
    assert "dependencias" not in fonte["entradas"]
    pacotes_novos = [PACOTES[0], {"name": "asgiref", "version": "3.9.0"}]
    assert (
        preparo.snapshot_fonte(raiz, "admin", {**AMBIENTE, "pacotes": pacotes_novos})[
            "ambiente"
        ]
        != fonte["ambiente"]
    )


def test_emissao_main_de_fonte_e_build_reutiliza_prova_equivalente(bancada):
    raiz, base, fonte = bancada
    atual = preparo.snapshot(raiz, "admin", BASE, PACOTES, AMBIENTE)
    medido_fonte = preparo.snapshot_fonte(raiz, "admin", AMBIENTE_FONTE)
    execucao = {"run_id": 10, "tentativa": 1, "job_id": 20}
    provas_fonte = [
        p for p in provas(medido_fonte, fonte, execucao) if p["nome"] != "build"
    ]
    prova_build = next(
        p for p in provas(atual, fonte, execucao) if p["nome"] == "build"
    )
    manifesto = preparo.criar(
        raiz,
        "admin",
        "TAR-980",
        1,
        fonte,
        base,
        fonte,
        atual,
        provas_fonte + [prova_build],
        execucao,
        IMAGEM,
        candidato.assinatura_build(atual),
    )
    assert candidato.validar(manifesto)["estado"] == "PASS"
    equivalente = {
        **atual,
        "ambientes": {p["nome"]: p["emissao"]["ambiente"] for p in manifesto["provas"]},
    }
    assert candidato.validar(manifesto, equivalente)["estado"] == "PASS"
    divergente = {
        **equivalente,
        "ambientes": {**equivalente["ambientes"], "muralhas": "0" * 64},
    }
    assert candidato.validar(manifesto, divergente)["provas_invalidas"] == ["muralhas"]


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


def test_prova_pr_nao_recebe_ambiente_main_retroativamente(bancada):
    raiz, base, fonte = bancada
    ambiente_pr = {**AMBIENTE, "runner": "ubuntu-22.04"}
    medido_no_pr = preparo.snapshot_fonte(
        raiz, "admin", {**ambiente_pr, "pacotes": PACOTES}
    )
    escrever(raiz, "README.md", "merge sem mudança relevante\n")
    git(raiz, "add", ".")
    git(raiz, "commit", "-qm", "integração")
    integracao = git(raiz, "rev-parse", "HEAD")
    medido_na_main = preparo.snapshot(raiz, "admin", BASE, PACOTES, AMBIENTE)
    assert candidato.assinatura_prova(
        medido_no_pr, "muralhas", sorted(candidato.FONTE)
    ) != candidato.assinatura_prova(medido_na_main, "muralhas", sorted(candidato.FONTE))
    emissao_pr = provas(
        medido_no_pr, fonte, {"run_id": 10, "tentativa": 1, "job_id": 20}
    )
    emissao_build = next(
        p
        for p in provas(
            medido_na_main, integracao, {"run_id": 10, "tentativa": 1, "job_id": 20}
        )
        if p["nome"] == "build"
    )
    emissao_pr = [p for p in emissao_pr if p["nome"] != "build"] + [emissao_build]
    with pytest.raises((preparo.PreparoInvalido, candidato.CandidatoInvalido)):
        preparo.criar(
            raiz,
            "admin",
            "TAR-980",
            1,
            fonte,
            base,
            integracao,
            medido_na_main,
            emissao_pr,
            {"run_id": 10, "tentativa": 1, "job_id": 20},
            IMAGEM,
            candidato.assinatura_build(medido_na_main),
        )


def test_emissao_usa_identidade_do_job_oficial(monkeypatch, bancada):
    raiz, _, fonte = bancada
    medido = preparo.snapshot(raiz, "admin", BASE, PACOTES, AMBIENTE)
    ambiente = {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": candidato.REPO,
        "GITHUB_WORKFLOW_REF": f"{candidato.REPO}/.github/workflows/ci-celula.yml@refs/heads/main",
        "GITHUB_JOB": "rodar",
        "GITHUB_SHA": fonte,
        "GITHUB_RUN_ID": "42",
        "GITHUB_RUN_ATTEMPT": "2",
        "GITHUB_EVENT_NAME": "push",
    }
    for chave, valor in ambiente.items():
        monkeypatch.setenv(chave, valor)

    def api(args, _):
        if "jobs?" in args[-1]:
            return [
                {"jobs": [{"id": 99, "name": "rodar (admin)", "status": "in_progress"}]}
            ]
        return {
            "head_sha": fonte,
            "path": ".github/workflows/ci-celula.yml",
            "head_repository": {"full_name": candidato.REPO},
            "run_attempt": 2,
            "event": "push",
        }

    monkeypatch.setattr(candidato, "_json_comando", api)
    emissao = preparo.emitir(raiz, "ci-celula-gate", "admin", medido)
    assert emissao["job_id"] == 99
    assert emissao["run_id"] == 42
    assert emissao["entradas"] == candidato.assinatura_prova(
        medido, "ci-celula-gate", emissao["escopo"]
    )
    monkeypatch.setenv("GITHUB_JOB", "ci-celula-gate")
    with pytest.raises(preparo.PreparoInvalido, match="job emissor"):
        preparo.emitir(raiz, "ci-celula-gate", "admin", medido)
