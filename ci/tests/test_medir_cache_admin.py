import json
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest
import yaml


SCRIPT = Path(__file__).resolve().parents[1] / "medir_cache_admin.py"
WORKFLOW = (
    Path(__file__).resolve().parents[2] / ".github/workflows/medir-cache-admin.yml"
)
IDENTIDADE = {
    "revisao": "a" * 40,
    "base": "python@sha256:" + "b" * 64,
    "manifesto_sha256": "c" * 64,
}


def executar(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "comparar", *map(str, args)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def amostra(modo, *, digest="sha256:" + "d" * 64, identidade=IDENTIDADE):
    resultado = {
        "modo": modo,
        "identidade": identidade,
        "bootstrap_s": 2.0,
        "build_com_export_s": 10.0 if modo != "importar" else 4.0,
        "imagem_oci_bytes": 1000,
        "digest_oci": digest,
        "acertos_cache": 4 if modo == "importar" else 0,
    }
    if modo in ("exportar", "importar"):
        resultado.update(cache_tar_sha256="e" * 64, cache_tar_bytes=2000)
    if modo == "importar":
        resultado["cache_extracao_s"] = 0.5
    if modo == "exportar":
        resultado["cache_empacotar_s"] = 0.5
    return resultado


def parametros(tmp_path, trio):
    caminhos = []
    for nome, conteudo in zip(("frio", "exportar", "importar"), trio):
        caminho = tmp_path / f"{nome}.json"
        caminho.write_text(json.dumps(conteudo), encoding="utf-8")
        caminhos += [f"--{nome}", caminho]
    return [
        *caminhos,
        "--saida",
        tmp_path / "resultado.json",
        "--preparar-total-s",
        "5",
        "--frio-total-s",
        "15",
        "--exportar-total-s",
        "22",
        "--importar-total-s",
        "16",
        "--contexto-upload-s",
        "1",
        "--frio-download-s",
        "1",
        "--exportar-download-s",
        "1",
        "--cache-upload-s",
        "5",
        "--importar-contexto-download-s",
        "1",
        "--cache-download-s",
        "6",
        "--cache-artifact-bytes",
        "2000",
        "--contexto-artifact-bytes",
        "1000",
    ]


def test_compara_custo_incluindo_transporte_e_nao_confunde_seed_com_reuso(tmp_path):
    processo = executar(
        *parametros(tmp_path, [amostra(x) for x in ("frio", "exportar", "importar")])
    )
    assert processo.returncode == 0, processo.stdout + processo.stderr
    resultado = json.loads((tmp_path / "resultado.json").read_text())
    assert resultado["frio_total_s"] == 20
    assert resultado["cache_inicial_total_s"] == 27
    assert resultado["importado_total_s"] == 21
    assert resultado["diferenca_importado_menos_frio_s"] == 1


@pytest.mark.parametrize(
    "alteracao, trecho",
    [
        (
            lambda trio: trio[2].update(identidade={**IDENTIDADE, "revisao": "f" * 40}),
            "contexto ou base",
        ),
        (
            lambda trio: trio[2].update(digest_oci="sha256:" + "f" * 64),
            "imagens OCI diferentes",
        ),
        (lambda trio: trio[2].update(acertos_cache=0), "cache importado"),
        (lambda trio: [r.pop("cache_tar_sha256") for r in trio[1:]], "cache importado"),
        (lambda trio: trio[1].update(cache_tar_bytes=0), "cache importado"),
        (lambda trio: trio[1].pop("build_com_export_s"), "sem build_com_export_s"),
    ],
)
def test_resultado_incompleto_ou_diferente_e_nao_medido(tmp_path, alteracao, trecho):
    trio = [amostra(x) for x in ("frio", "exportar", "importar")]
    alteracao(trio)
    processo = executar(*parametros(tmp_path, trio))
    assert processo.returncode != 0
    assert processo.stderr.startswith("N" + chr(195) + "O MEDIDO:")
    assert trecho in processo.stderr
    assert not (tmp_path / "resultado.json").exists()


def test_workflow_so_main_sem_runtime_e_com_contexto_real():
    bruto = WORKFLOW.read_text(encoding="utf-8")
    workflow = yaml.safe_load(bruto)
    assert workflow.get("on", workflow.get(True)) == {"workflow_dispatch": None}
    assert workflow["permissions"] == {"contents": "read", "actions": "read"}
    assert "preparar" in workflow["jobs"]
    checkout_preparo = next(
        passo for passo in workflow["jobs"]["preparar"]["steps"]
        if passo.get("uses", "").startswith("actions/checkout@")
    )
    assert checkout_preparo["with"]["fetch-depth"] == 0
    assert "workflow_dispatch" in bruto
    assert "refs/heads/main" in bruto
    assert "workflow_dispatch:" in bruto
    assert "environment:" not in bruto
    assert "DEPLOY_SSH_KEY" not in bruto
    assert "docker push" not in bruto
    assert "type=local" in (SCRIPT.read_text(encoding="utf-8"))
    for trecho in (
        "ci/preparar_dados_admin.py painel",
        "ci/preparar_dados_admin.py fila",
        "cp -R documentos",
        "cp -R docs/decisoes",
        "permissions:",
        "contents: read",
        "actions: read",
    ):
        assert trecho in bruto


def test_cache_transportado_aceita_diretorios_e_recusa_link(tmp_path):
    sys.path.insert(0, str(SCRIPT.parent))
    from medir_cache_admin import extrair_tar

    pacote = tmp_path / "cache.tar"
    origem = tmp_path / "origem"
    (origem / "blobs").mkdir(parents=True)
    (origem / "blobs" / "camada").write_bytes(b"cache")
    with tarfile.open(pacote, "w") as tar:
        tar.add(origem, arcname=".")
    destino = tmp_path / "destino"
    destino.mkdir()
    extrair_tar(pacote, destino)
    assert (destino / "blobs" / "camada").read_bytes() == b"cache"

    with tarfile.open(pacote, "w") as tar:
        link = tarfile.TarInfo("fora")
        link.type = tarfile.SYMTYPE
        link.linkname = "../fora"
        tar.addfile(link)
    with pytest.raises(SystemExit, match="caminho inv"):
        extrair_tar(pacote, destino)


def test_acertos_buildkit_aceita_linha_real_e_recusa_falso_positivo():
    sys.path.insert(0, str(SCRIPT.parent))
    from medir_cache_admin import contar_acertos_cache

    assert contar_acertos_cache("#8 CACHED\n#11 CACHED\n#13 DONE 0.2s\n") == 2
    assert (
        contar_acertos_cache("#8 FETCHED\n#11 CACHED extra\n#13 [7/7] RUN pip CACHED\n")
        == 0
    )
