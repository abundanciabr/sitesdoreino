from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SHA_DA_PUBLICACAO = "a" * 40

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "ci"))
sys.path.insert(0, str(RAIZ / "services" / "admin"))

from preparar_dados_admin import escrever_manifesto, preparar_fila  # noqa: E402
from publicador_dados_admin import (  # noqa: E402
    PublicacaoInvalida,
    decidir_publicacao,
)
from apps.core.admin_dados import selecionar_dados  # noqa: E402


def _payload_fila(pasta: Path, *, sha=SHA_DA_PUBLICACAO, run_number=10) -> Path:
    (pasta / "tarefas").mkdir(parents=True)
    (pasta / "eventos").mkdir()
    (pasta / "tarefas" / "001.json").write_text("{}", encoding="utf-8")
    (pasta / "estados.json").write_text(
        json.dumps({"TAR-001": {"estado": "na fila"}}), encoding="utf-8"
    )
    (pasta / "regua.json").write_text(
        json.dumps({"esperas": {}, "medido_em": "2026-09-08"}), encoding="utf-8"
    )
    escrever_manifesto(pasta, tipo="fila", sha=sha, run_id="321", run_number=run_number)
    return pasta


def _payload_painel(pasta: Path, *, sha=SHA_DA_PUBLICACAO, run_number=10) -> Path:
    (pasta / "registros").mkdir(parents=True)
    (pasta / "registros" / "20260908-001-x.js").write_text(
        "export default {}", encoding="utf-8"
    )
    (pasta / "painel.html").write_text("<html></html>", encoding="utf-8")
    (pasta / "livro-202609.js").write_text("export default []", encoding="utf-8")
    escrever_manifesto(
        pasta, tipo="painel", sha=sha, run_id="321", run_number=run_number
    )
    return pasta


def test_preparar_fila_materializa_estados_regua_e_manifesto(tmp_path):
    raiz = tmp_path / "repo"
    (raiz / "ci").mkdir(parents=True)
    (raiz / "fila" / "tarefas").mkdir(parents=True)
    (raiz / "fila" / "tarefas" / "001.json").write_text("{}", encoding="utf-8")
    (raiz / "ci" / "tempos_esperados.json").write_text(
        json.dumps({"esperas": {}}), encoding="utf-8"
    )
    (raiz / "ci" / "fila.py").write_text(
        "import json; print(json.dumps({'TAR-001': {'estado': 'na fila'}}))",
        encoding="utf-8",
    )

    destino = tmp_path / "payload"
    preparar_fila(raiz, destino)
    manifesto = escrever_manifesto(
        destino, tipo="fila", sha=SHA_DA_PUBLICACAO, run_id="77", run_number=88
    )

    assert json.loads((destino / "estados.json").read_text(encoding="utf-8")) == {
        "TAR-001": {"estado": "na fila"}
    }
    assert (destino / "regua.json").is_file()
    assert manifesto["formato"] == "admin-dados.v1"
    assert manifesto["origem"]["sha"] == SHA_DA_PUBLICACAO
    assert "estados.json" in manifesto["integridade"]["arquivos"]


def test_publicador_recusa_arquivo_com_hash_quebrado(tmp_path):
    payload = _payload_fila(tmp_path / "payload")
    (payload / "estados.json").write_text("{}", encoding="utf-8")

    with pytest.raises(PublicacaoInvalida, match="integridade quebrada"):
        decidir_publicacao(
            payload,
            tmp_path / "ativo",
            tipo="fila",
            sha=SHA_DA_PUBLICACAO,
            run_number=10,
        )


def test_publicador_recusa_arquivo_fora_do_manifesto(tmp_path):
    payload = _payload_painel(tmp_path / "payload")
    (payload / "registros" / "20260908-999-extra.js").write_text(
        "export default {}", encoding="utf-8"
    )

    with pytest.raises(PublicacaoInvalida, match="arquivo fora do manifesto"):
        decidir_publicacao(
            payload,
            tmp_path / "ativo",
            tipo="painel",
            sha=SHA_DA_PUBLICACAO,
            run_number=10,
        )


def test_publicador_recusa_conteudo_incompleto_mesmo_com_manifesto(tmp_path):
    payload = tmp_path / "payload"
    payload.mkdir()
    (payload / "estados.json").write_text("{}", encoding="utf-8")
    (payload / "regua.json").write_text(json.dumps({"esperas": {}}), encoding="utf-8")
    escrever_manifesto(
        payload, tipo="fila", sha=SHA_DA_PUBLICACAO, run_id="321", run_number=10
    )

    with pytest.raises(PublicacaoInvalida, match="fila sem tarefas JSON"):
        decidir_publicacao(
            payload,
            tmp_path / "ativo",
            tipo="fila",
            sha=SHA_DA_PUBLICACAO,
            run_number=10,
        )


def test_publicador_recusa_painel_sem_livro_mensal(tmp_path):
    payload = _payload_painel(tmp_path / "payload")
    (payload / "livro-202609.js").unlink()
    escrever_manifesto(
        payload, tipo="painel", sha=SHA_DA_PUBLICACAO, run_id="321", run_number=10
    )

    with pytest.raises(PublicacaoInvalida, match="painel sem livro mensal JS"):
        decidir_publicacao(
            payload,
            tmp_path / "ativo",
            tipo="painel",
            sha=SHA_DA_PUBLICACAO,
            run_number=10,
        )


def test_publicador_nao_deixa_run_antigo_sobrescrever_run_novo(tmp_path):
    payload = _payload_fila(tmp_path / "payload", run_number=9)
    ativo = _payload_fila(tmp_path / "ativo", run_number=10)

    assert (
        decidir_publicacao(
            payload, ativo, tipo="fila", sha=SHA_DA_PUBLICACAO, run_number=9
        )
        == "ignorar"
    )


def test_publicador_trata_painel_e_fila_como_publicacoes_independentes(tmp_path):
    painel = _payload_painel(tmp_path / "painel")
    fila = _payload_fila(tmp_path / "fila")

    assert (
        decidir_publicacao(
            painel,
            tmp_path / "ativo-painel",
            tipo="painel",
            sha=SHA_DA_PUBLICACAO,
            run_number=10,
        )
        == "publicar"
    )
    assert (
        decidir_publicacao(
            fila,
            tmp_path / "ativo-fila",
            tipo="fila",
            sha=SHA_DA_PUBLICACAO,
            run_number=10,
        )
        == "publicar"
    )


def test_leitor_da_admin_pula_formato_incompativel(tmp_path):
    ruim = tmp_path / "ruim"
    bom = _payload_painel(tmp_path / "bom")
    ruim.mkdir()
    (ruim / "painel.html").write_text("<html></html>", encoding="utf-8")
    (ruim / "admin-dados.json").write_text(
        json.dumps({"formato": "admin-dados.v2"}), encoding="utf-8"
    )

    assert (
        selecionar_dados(
            (ruim, bom), tipo="painel", arquivos_obrigatorios=("painel.html",)
        ).pasta
        == bom.resolve()
    )


def test_leitor_da_admin_pula_payload_com_arquivo_fora_do_manifesto(tmp_path):
    ruim = _payload_fila(tmp_path / "ruim")
    bom = _payload_fila(tmp_path / "bom")
    (ruim / "eventos" / "extra.json").write_text("{}", encoding="utf-8")

    assert (
        selecionar_dados(
            (ruim, bom), tipo="fila", arquivos_obrigatorios=("estados.json",)
        ).pasta
        == bom.resolve()
    )


def test_script_de_vps_troca_ponteiro_e_nao_reinicia_admin():
    script = (RAIZ / "infra" / "publicar-dados-admin-na-vps.sh").read_text(
        encoding="utf-8"
    )
    assert "flock 9" in script
    assert script.index("flock 9") < script.index("ACAO=$(python3")
    assert 'mv -Tf "$LINK_NOVO" "$ATIVO"' in script
    assert "docker compose" not in script
    assert "docker build" not in script
    assert "ADMIN-DADOS-PUBLICADOS:" in script


def test_deploy_infra_prepara_admin_dados_antes_do_compose_up():
    script = (RAIZ / "infra" / "sincronizar-infra-na-vps.sh").read_text(
        encoding="utf-8"
    )
    preparo = script.index("mkdir -p admin-dados")
    assert preparo < script.index("docker compose up -d")
    assert "touch admin-dados/.permissao-deploy-teste" in script
