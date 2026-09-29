"""Provas de candidato: conteúdo, equivalência, fonte quebrada e CAS durável."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import candidato


@pytest.fixture
def entrada():
    atual = {
        "entradas": {
            grupo: (
                {"resolvido": "a" * 64}
                if grupo
                in {"codigo", "dependencias", "imagem_base", "build", "politicas"}
                else {}
            )
            for grupo in candidato.GRUPOS
        },
        "ambiente": "b" * 64,
        "verificadores": {nome: "c" * 64 for nome in candidato.OBRIGATORIOS},
    }
    provas = []
    for indice, nome in enumerate(sorted(candidato.OBRIGATORIOS), 1):
        escopo = sorted(candidato.BUILD if nome == "build" else candidato.GRUPOS)
        provas.append(
            {
                "nome": nome,
                "resultado": "PASS",
                "escopo": escopo,
                "entradas": candidato.assinatura_prova(atual, nome, escopo),
                "run_id": 10 if nome == "build" else 20 + indice,
                "tentativa": 1,
                "job_id": indice,
                "revisao": "d" * 40 if nome == "build" else "e" * 40,
            }
        )
    return {
        "versao": 1,
        "tarefa": "TAR-966",
        "tentativa": 1,
        "celula": "admin",
        "fonte": {"revisao": "e" * 40, "arvore": "f" * 40, "base": "6" * 40},
        "integracao": {"revisao": "d" * 40, "arvore": "f" * 40},
        **atual,
        "provas": provas,
        "execucao": {"run_id": 10, "tentativa": 1, "job_id": 1},
        "imagem": {
            "referencia": "ghcr.io/abundanciabr/plataforma-admin@sha256:" + "1" * 64,
            "entradas": candidato.assinatura_build(atual),
        },
    }


def assinado(manifesto):
    return [
        {
            "verificationResult": {
                "signature": {
                    "certificate": {
                        "runInvocationURI": "https://github.com/abundanciabr/sitesdoreino/actions/runs/10/attempts/1",
                        "buildTrigger": "push",
                        "sourceRepositoryDigest": "d" * 40,
                    }
                },
                "verifiedTimestamps": [{"type": "Tlog"}],
                "statement": {
                    "subject": [
                        {
                            "digest": {
                                "sha256": candidato.hashlib.sha256(
                                    candidato.canonico(manifesto)
                                ).hexdigest()
                            }
                        }
                    ]
                },
            }
        }
    ]


def fonte_oficial(monkeypatch, manifesto):
    comandos = []
    execucao = {"nome": "build", "revisao": "d" * 40, **manifesto["execucao"]}
    provas = {p["run_id"]: p for p in [execucao, *manifesto["provas"]]}

    def medir(args, raiz):
        comandos.append(args)
        if "attestation" in args:
            assert "--bundle" in args
            assert args[args.index("--cert-identity") + 1] == candidato.IDENTIDADE
            assert args[args.index("--source-digest") + 1] == "d" * 40
            assert "--deny-self-hosted-runners" in args
            return assinado(manifesto)
        endpoint = args[-1]
        if "/git/commits/" in endpoint:
            return {"sha": endpoint.rsplit("/", 1)[1], "tree": {"sha": "f" * 40}}
        if "/compare/" in endpoint:
            return {
                "status": "ahead",
                "merge_base_commit": {
                    "sha": endpoint.split("/compare/")[1].split("...")[0]
                },
            }
        run_id = int(endpoint.split("/runs/")[1].split("/")[0])
        prova = provas[run_id]
        nome = prova["nome"]
        if "/jobs?" in endpoint:
            return [
                {
                    "jobs": [
                        {
                            "id": prova["job_id"],
                            "name": "preparar (admin)" if nome == "build" else nome,
                            "status": "completed",
                            "conclusion": "success",
                        }
                    ]
                }
            ]
        return {
            "head_sha": prova["revisao"],
            "path": (
                candidato.WORKFLOW
                if nome == "build"
                else (
                    ".github/workflows/muralhas.yml"
                    if nome == "muralhas"
                    else ".github/workflows/ci-celula.yml"
                )
            ),
            "head_repository": {"full_name": candidato.REPO},
            "run_attempt": 1,
            "event": "push" if nome == "build" else "pull_request",
            "head_branch": "main",
            "status": "completed",
            "conclusion": "success",
        }

    monkeypatch.setattr(candidato, "_json_comando", medir)
    return comandos, medir


def test_cadeia_fonte_provas_imagem_deterministica(entrada):
    manifesto = candidato.criar(entrada)
    relatorio = candidato.validar(manifesto)
    assert relatorio["estado"] == "PASS"
    assert relatorio["digest"] == "sha256:" + "1" * 64
    assert candidato.criar(dict(reversed(list(entrada.items())))) == manifesto
    assert manifesto["fonte"]["base"] == "6" * 40
    assert manifesto["integracao"]["arvore"] == "f" * 40


@pytest.mark.parametrize("grupo", sorted(candidato.GRUPOS))
def test_alteracao_relevante_invalida_prova_e_build_conforme_propriedade(
    entrada, grupo
):
    manifesto = candidato.criar(entrada)
    atual = copy.deepcopy(candidato.snapshot(manifesto))
    atual["entradas"][grupo]["mudanca"] = "2" * 64
    relatorio = candidato.validar(manifesto, atual)
    assert relatorio["estado"] == "FAIL"
    assert {"muralhas", "ci-celula-gate"} <= set(relatorio["provas_invalidas"])
    assert relatorio["reconstruir"] == (grupo != "politicas")
    assert ("build" in relatorio["provas_invalidas"]) == (grupo != "politicas")


def test_verificador_novo_invalida_so_prova_sem_rebuild(entrada):
    manifesto = candidato.criar(entrada)
    atual = copy.deepcopy(candidato.snapshot(manifesto))
    atual["verificadores"]["muralhas"] = "2" * 64
    relatorio = candidato.validar(manifesto, atual)
    assert relatorio["provas_invalidas"] == ["muralhas"]
    assert relatorio["reconstruir"] is False


def test_ambiente_diferente_invalida_provas_e_build(entrada):
    manifesto = candidato.criar(entrada)
    atual = copy.deepcopy(candidato.snapshot(manifesto))
    atual["ambiente"] = "2" * 64
    assert candidato.validar(manifesto, atual)["reconstruir"] is True


def test_entradas_equivalentes_reutilizam_sem_nome_de_celula(entrada):
    manifesto = candidato.criar(entrada)
    assert (
        candidato.validar(manifesto, copy.deepcopy(candidato.snapshot(manifesto)))[
            "estado"
        ]
        == "PASS"
    )


@pytest.mark.parametrize("resultado", ["FAIL", "ERROR", "SKIP", "cancelled", None])
def test_resultado_nao_aprovado_recusado(entrada, resultado):
    # guarda: ci/candidato.py:210
    entrada["provas"][0]["resultado"] = resultado
    with pytest.raises(candidato.CandidatoInvalido, match="não aprovam"):
        candidato.criar(entrada)


def test_prova_ausente_nao_vira_verde(entrada):
    entrada["provas"].pop()
    with pytest.raises(candidato.CandidatoInvalido, match="sem prova"):
        candidato.criar(entrada)


def test_merge_alterou_entrada_prova_antiga_nao_vira_verde(entrada):
    entrada["entradas"]["contratos"]["pagamentos.v1"] = "2" * 64
    with pytest.raises(candidato.CandidatoInvalido, match="não mediu"):
        candidato.criar(entrada)


@pytest.mark.parametrize("campo", ["segredo", "official", "lease", "autor"])
def test_campos_autodeclarados_ou_segretos_recusados(entrada, campo):
    entrada[campo] = "token"
    with pytest.raises(candidato.CandidatoInvalido, match="desconhecidos"):
        candidato.criar(entrada)


def test_valor_de_dependencia_sem_resolucao_recusado(entrada):
    entrada["entradas"]["dependencias"]["python"] = ">=3.12"
    with pytest.raises(candidato.CandidatoInvalido, match="digest inválido"):
        candidato.criar(entrada)


def test_candidato_imutavel(entrada):
    manifesto = candidato.criar(entrada)
    manifesto["imagem"]["referencia"] = (
        "ghcr.io/abundanciabr/plataforma-admin@sha256:" + "2" * 64
    )
    with pytest.raises(candidato.CandidatoInvalido, match="alterado"):
        candidato.validar(manifesto)


def test_origem_confere_certificado_e_jobs_sem_artifact(entrada, monkeypatch, tmp_path):
    manifesto = candidato.criar(entrada)
    comandos, _ = fonte_oficial(monkeypatch, manifesto)
    candidato.conferir_origem(manifesto, {"dsseEnvelope": {}}, tmp_path)
    assert len([c for c in comandos if "attestation" in c]) == 1
    assert all("artifacts" not in c[-1] for c in comandos)


@pytest.mark.parametrize(
    "falha",
    [
        "assinatura",
        "tentativa",
        "revisao",
        "workflow",
        "fork",
        "cancelled",
        "skipped",
        "ausente",
        "json",
    ],
)
def test_origem_falsa_ou_instrumento_quebrado_nunca_aprova(
    entrada, monkeypatch, tmp_path, falha
):
    manifesto = candidato.criar(entrada)
    _, medir = fonte_oficial(monkeypatch, manifesto)

    def sabotado(args, raiz):
        if falha == "json":
            raise candidato.InstrumentoIndisponivel("GitHub indisponível")
        resposta = medir(args, raiz)
        if "attestation" in args:
            if falha == "assinatura":
                return []
            if falha == "tentativa":
                resposta[0]["verificationResult"]["signature"]["certificate"][
                    "runInvocationURI"
                ] = "https://github.com/abundanciabr/sitesdoreino/actions/runs/10/attempts/2"
        elif "/jobs?" in args[-1]:
            if falha == "ausente":
                return [{"jobs": []}]
            if falha == "skipped":
                resposta[0]["jobs"][0]["conclusion"] = "skipped"
        elif "/runs/" in args[-1]:
            if falha == "revisao":
                resposta["head_sha"] = "0" * 40
            if falha == "workflow":
                resposta["path"] = ".github/workflows/evil.yml"
            if falha == "fork":
                resposta["head_repository"]["full_name"] = "invasor/fork"
            if falha == "cancelled":
                resposta["conclusion"] = "cancelled"
        return resposta

    monkeypatch.setattr(candidato, "_json_comando", sabotado)
    with pytest.raises(
        (candidato.CandidatoInvalido, candidato.InstrumentoIndisponivel)
    ):
        candidato.conferir_origem(manifesto, {}, tmp_path)


def repo_local(tmp_path):
    bare = tmp_path / "remoto.git"
    trabalho = tmp_path / "bancada"
    subprocess.run(
        ["git", "init", "--bare", str(bare)], check=True, capture_output=True
    )
    subprocess.run(["git", "init", str(trabalho)], check=True, capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "origin", str(bare)], cwd=trabalho, check=True
    )
    return trabalho


def test_duravel_cas_idempotente_leitura_independente_do_lease(
    entrada, monkeypatch, tmp_path
):
    raiz = repo_local(tmp_path)
    manifesto = candidato.criar(entrada)
    fonte_oficial(monkeypatch, manifesto)
    identificador = candidato.aceitar(raiz, manifesto, {"assinatura": "bundle-ensaio"})
    assert (
        candidato.aceitar(raiz, manifesto, {"assinatura": "bundle-ensaio"})
        == identificador
    )
    assert candidato.carregar(raiz, identificador) == manifesto
    with pytest.raises(candidato.CandidatoInvalido, match="conteúdo diferente"):
        candidato.aceitar(raiz, manifesto, {"assinatura": "outro-bundle"})
    refs = subprocess.run(
        ["git", "ls-remote", "origin"],
        cwd=raiz,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "refs/candidatos/" + identificador in refs
    assert "refs/reservas" not in refs


def test_escrita_incerta_reconcilia_antes_de_repetir(entrada, monkeypatch, tmp_path):
    raiz = repo_local(tmp_path)
    manifesto = candidato.criar(entrada)
    fonte_oficial(monkeypatch, manifesto)
    real = candidato._comando
    pushes = []

    def rede_sem_resposta(args, pasta, entrada=None):
        resultado = real(args, pasta, entrada)
        if args[:2] == ["git", "push"]:
            pushes.append(args)
            raise candidato.InstrumentoIndisponivel(
                "Resposta perdida depois da escrita"
            )
        return resultado

    monkeypatch.setattr(candidato, "_comando", rede_sem_resposta)
    assert candidato.aceitar(raiz, manifesto, {}) == manifesto["id"]
    assert len(pushes) == 1


def test_leitura_duravel_rejeita_ref_forjada(entrada, monkeypatch, tmp_path):
    # guarda: ci/candidato.py:614
    raiz = repo_local(tmp_path)
    manifesto = candidato.criar(entrada)
    fonte_oficial(monkeypatch, manifesto)
    candidato.aceitar(raiz, manifesto, {})
    monkeypatch.setattr(candidato, "_json_comando", lambda *args: [])
    with pytest.raises(candidato.CandidatoInvalido, match="assinatura"):
        candidato.carregar(raiz, manifesto["id"])


def test_cli_real_criar_validar_e_instrumento_ausente(entrada, tmp_path):
    script = Path(candidato.__file__).resolve()
    arquivo = tmp_path / "entrada.json"
    saida = tmp_path / "candidato.json"
    arquivo.write_text(json.dumps(entrada), encoding="utf-8")
    criado = subprocess.run(
        [
            sys.executable,
            str(script),
            "criar",
            "--entrada",
            str(arquivo),
            "--saida",
            str(saida),
        ],
        capture_output=True,
        text=True,
    )
    assert criado.returncode == 0, criado.stdout
    assert json.loads(criado.stdout)["estado"] == "PASS"
    medido = subprocess.run(
        [sys.executable, str(script), "validar", "--arquivo", str(saida)],
        capture_output=True,
        text=True,
    )
    assert medido.returncode == 0
    assert json.loads(medido.stdout)["id"] == json.loads(criado.stdout)["id"]
    ausente = subprocess.run(
        [
            sys.executable,
            str(script),
            "validar",
            "--arquivo",
            str(tmp_path / "ausente"),
        ],
        capture_output=True,
        text=True,
    )
    assert ausente.returncode == 2
    assert json.loads(ausente.stdout)["estado"] == "ERROR"


def test_verificador_obrigatorio_adicionado_exige_prova(entrada):
    manifesto = candidato.criar(entrada)
    atual = copy.deepcopy(candidato.snapshot(manifesto))
    atual["verificadores"]["jornada"] = "2" * 64
    assert candidato.validar(manifesto, atual)["provas_invalidas"] == ["jornada"]


def test_captura_git_inclui_dependencia_fora_da_celula_e_modo(tmp_path):
    raiz = repo_local(tmp_path)
    subprocess.run(["git", "config", "user.name", "Ensaio"], cwd=raiz, check=True)
    subprocess.run(
        ["git", "config", "user.email", "ensaio@example.test"], cwd=raiz, check=True
    )
    (raiz / "services").mkdir()
    (raiz / "services" / "admin.py").write_text("codigo", encoding="utf-8")
    (raiz / "contrato.yaml").write_text("v1", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=raiz, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Fonte"], cwd=raiz, check=True, capture_output=True
    )
    fonte = candidato.identidade_git(raiz, "HEAD", "HEAD")
    antes = candidato.fotografar_arquivos(
        raiz, fonte["revisao"], ["services", "contrato.yaml"]
    )
    (raiz / "contrato.yaml").write_text("v2", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=raiz, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Contrato"], cwd=raiz, check=True, capture_output=True
    )
    integrado = candidato.identidade_git(raiz, "HEAD")
    depois = candidato.fotografar_arquivos(
        raiz, integrado["revisao"], ["services", "contrato.yaml"]
    )
    assert antes["services/admin.py"] == depois["services/admin.py"]
    assert antes["contrato.yaml"] != depois["contrato.yaml"]
    assert fonte["arvore"] != integrado["arvore"]
    with pytest.raises(candidato.CandidatoInvalido, match="fora da árvore"):
        candidato.fotografar_arquivos(raiz, fonte["revisao"], ["../segredo"])


@pytest.mark.parametrize("sabotagem", ["arvore", "ancestral"])
def test_arvore_e_base_medidas_na_fonte_externa(
    entrada, monkeypatch, tmp_path, sabotagem
):
    manifesto = candidato.criar(entrada)
    _, medir = fonte_oficial(monkeypatch, manifesto)

    def falso(args, raiz):
        resposta = medir(args, raiz)
        if sabotagem == "arvore" and "/git/commits/" in args[-1]:
            resposta["tree"]["sha"] = "2" * 40
        if sabotagem == "ancestral" and "/compare/" in args[-1]:
            resposta["status"] = "diverged"
        return resposta

    monkeypatch.setattr(candidato, "_json_comando", falso)
    with pytest.raises(candidato.CandidatoInvalido):
        candidato.conferir_origem(manifesto, {}, tmp_path)
