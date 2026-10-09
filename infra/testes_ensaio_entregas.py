"""Casos C09, C10, C15, C17 e C18 do executor de entregas."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ensaio_entregas as modulo
import protecao_publicacao

A = "a" * 40
B = "b" * 40
AB = "c" * 40
C = "d" * 40


def test_C09_falha_individual_nao_trava_independente_e_dependente_espera():
    promovidas = []
    registros = [{"id": "A", "candidata": A},
                 {"id": "B", "candidata": B},
                 {"id": "C", "candidata": C, "dependencias": ["A"]}]
    resultado = modulo.separar_lote(
        registros, lambda sha: sha != A,
        lambda aceitas, reg: reg["candidata"],
        lambda reg, sha: promovidas.append((reg["id"], sha)))
    assert resultado["A"]["estado"] == "falha no ensaio"
    assert resultado["B"]["estado"] == "promovida"
    assert resultado["C"] == {"estado": "aguardando dependência", "dependencias": ["A"]}
    assert promovidas == [("B", B)]


def test_C10_duas_individuais_aprovadas_combinacao_falha_sem_culpa_unica():
    chamadas, promovidas = [], []
    def ensaio(sha):
        chamadas.append(sha)
        return sha != AB
    resultado = modulo.separar_lote(
        [{"id": "A", "candidata": A}, {"id": "B", "candidata": B}], ensaio,
        lambda aceitas, reg: AB if aceitas else reg["candidata"],
        lambda reg, sha: promovidas.append(sha))
    assert chamadas == [A, B, AB]
    assert resultado["B"] == {"estado": "incompatibilidade", "com": ["A"],
                                "candidata_final": AB}
    assert promovidas == [A]


def test_C15_executor_recusa_docker_remoto_ou_contexto_alternativo(monkeypatch):
    monkeypatch.setenv("DOCKER_HOST", "tcp://host-externo:2375")
    with pytest.raises(modulo.RecusaEnsaio):
        modulo._conferir_lancador()
    # Mesmo um marcador fictício não chega ao código candidato: preflight falha.
    marcador = []
    monkeypatch.setattr(modulo, "_conferir_lancador", lambda: (_ for _ in ()).throw(
        modulo.RecusaEnsaio("lançador proibido")))
    with pytest.raises(modulo.RecusaEnsaio):
        modulo.executar(Path("/tmp/ficticio"), A)
    assert marcador == []


def test_C15_marcador_real_do_host_e_parametros_do_container(monkeypatch):
    monkeypatch.setattr(modulo, "_conferir_lancador", lambda: None)
    chamadas = []
    class Retorno:
        returncode = 0
        stdout = ""
    def rodar(args, **_kwargs):
        chamadas.append(args)
        retorno = Retorno()
        if args[:2] == ["docker", "run"]:
            retorno.stdout = json.dumps({"leu_pacote": True, "gravou_pacote": False,
                                         "leu_controle": False, "gravou_controle": False,
                                         "socket_docker": False, "interfaces": ["lo"],
                                         "rota_default": False, "rede_errno": 101,
                                         "uid": 65532, "no_new_privs": "1",
                                         "cap_eff": "0000000000000000"})
        return retorno
    monkeypatch.setattr(modulo.subprocess, "run", rodar)
    assert modulo.provar_isolamento("sha256:" + "1" * 64)["estado"] == "isolado"
    comando = chamadas[1]
    assert comando[:3] == ["docker", "run", "--rm"]
    for parte in ("--network", "none", "--read-only", "--cap-drop", "ALL",
                  "no-new-privileges", "65532:65532", "/pacote:ro"):
        assert any(parte in arg for arg in comando)
    script = comando[-1]
    compile(script, "<marcadores>", "exec")
    assert "__CONTROLE__" not in script
    assert "MARCADOR-FICTICIO.txt" in script and "controle.read_text()" in script


def test_collectstatic_usa_uid_sem_privilegio_e_pacote_somente_leitura(tmp_path, monkeypatch):
    bundle = tmp_path / "pacote"
    bundle.mkdir()
    donos, comandos = [], []
    monkeypatch.setattr(modulo.os, "chown", lambda *args: donos.append(args), raising=False)
    class Retorno:
        returncode = 0
    def rodar(comando, **_kwargs):
        comandos.append(comando)
        saida = next(parte.split(":/app/staticfiles:")[0] for parte in comando
                     if ":/app/staticfiles:rw" in parte)
        (Path(saida) / "app.css").write_text("estilo", encoding="utf-8")
        return Retorno()
    monkeypatch.setattr(modulo.subprocess, "run", rodar)
    modulo._coletar_estaticos(bundle, tmp_path, "sha256:" + "1" * 64, io.StringIO())
    comando = comandos[0]
    assert donos[0][1:] == (65532, 65532)
    assert "65532:65532" in comando
    assert "--read-only" in comando and "no-new-privileges" in comando
    assert f"{bundle}:/app:ro" in comando
    assert f"{bundle}:/app:rw" not in comando
    assert "none" in comando and "--network" in comando
    assert (bundle / "staticfiles/app.css").read_text() == "estilo"


def test_celula_sem_ensaio_e_recusada_explicitamente(tmp_path):
    with pytest.raises(modulo.RecusaEnsaio, match="célula sem ensaio"):
        modulo.executar(tmp_path, A, celula="outra")


def test_funil_snapshot_privado_aponta_rota_sem_mudar_origem(tmp_path):
    plataforma = tmp_path / "plataforma"
    (plataforma / "traefik/dynamic").mkdir(parents=True)
    (plataforma / "env").mkdir()
    (plataforma / "docker-compose.yml").write_text("services: {}", encoding="utf-8")
    (plataforma / ".env").write_text("MARCADOR_FICTICIO=valor", encoding="utf-8")
    (plataforma / "env/app.env").write_text("MARCADOR_FICTICIO=valor", encoding="utf-8")
    rota = (plataforma / "traefik/dynamic/plataforma.yml")
    rota.write_text('\n  services:\n    funil:\n      loadBalancer:\n        servers: [ { url: "http://antigo:8000" } ]\n', encoding="utf-8")
    base = tmp_path / "saida"
    base.mkdir()
    destino = modulo._snapshot_rota(plataforma, base, "meshcraft-funil-candidato",
                                    Path(__file__).resolve().parents[1])
    assert "meshcraft-funil-candidato:8000" in (destino / "traefik/dynamic/plataforma.yml").read_text()
    assert "http://antigo:8000" in rota.read_text()
    assert (destino / ".env").read_text() == (plataforma / ".env").read_text()
    with pytest.raises(modulo.RecusaEnsaio, match="snapshot privado anterior"):
        modulo._snapshot_rota(plataforma, base, "outro", Path(__file__).resolve().parents[1])


def test_funil_prova_separada_exige_dois_relatorios(tmp_path, monkeypatch):
    pasta = tmp_path / "entregas/provas"
    pasta.mkdir(parents=True)
    comercial = tmp_path / "comercial.xml"
    funil = tmp_path / "funil.xml"
    comercial.write_text("comercial", encoding="utf-8")
    funil.write_text("funil", encoding="utf-8")
    identidade = {"candidata": A, "celula": "funil", "codigo": "projecao",
                  "configuracao_base": "anterior", "configuracao": "final",
                  "artefato": {"comercial_xml": str(comercial), "funil_xml": str(funil)}}
    monkeypatch.setattr(modulo, "identidade_atual", lambda *_a, **_k: identidade.copy())
    def conferir(arquivo, **_kwargs):
        return {"estado": "comprovado", "casos": 1,
                "relatorio_sha256": "f" if Path(arquivo) == funil else "c"}
    monkeypatch.setattr(protecao_publicacao, "conferir_relatorio", conferir)
    prova = {"versao": modulo.VERSAO, **identidade,
             "identidade": modulo._json_hash(identidade), "resultado": "aprovado",
             "cobertura": conferir(comercial), "cobertura_funil": conferir(funil)}
    (pasta / (A + "-funil.json")).write_text(json.dumps(prova), encoding="utf-8")
    assert modulo.verificar_prova(tmp_path, A, celula="funil")["celula"] == "funil"
    monkeypatch.setattr(protecao_publicacao, "conferir_relatorio", lambda *_a, **_k:
                        {"estado": "comprovado", "casos": 1, "relatorio_sha256": "outro"})
    with pytest.raises(modulo.RecusaEnsaio, match="relatório"):
        modulo.verificar_prova(tmp_path, A, celula="funil")


def test_C17_prova_invalida_se_codigo_config_imagem_executor_ou_ensaio_mudar(tmp_path, monkeypatch):
    pasta = tmp_path / "entregas/provas"
    pasta.mkdir(parents=True)
    xml = tmp_path / "comercial.xml"
    xml.write_text("<testsuite/>")
    identidade = {"candidata": A, "codigo": "codigo-1", "imagem": "imagem-1",
                  "configuracao": "config-1", "executor": "executor-1", "ensaio": "ensaio-1",
                  "artefato": {"comercial_xml": str(xml)}}
    monkeypatch.setattr(modulo, "identidade_atual", lambda *_: identidade.copy())
    monkeypatch.setattr(protecao_publicacao, "conferir_relatorio", lambda *_a, **_k:
                        {"estado": "comprovado", "casos": 1, "relatorio_sha256": "xml-1"})
    prova = {"versao": modulo.VERSAO, **identidade, "identidade": modulo._json_hash(identidade),
             "resultado": "aprovado", "cobertura": {"estado": "comprovado", "casos": 1,
                                                   "relatorio_sha256": "xml-1"}}
    (pasta / (A + ".json")).write_text(json.dumps(prova), encoding="utf-8")
    assert modulo.verificar_prova(tmp_path, A)["resultado"] == "aprovado"
    for campo in ("codigo", "imagem", "configuracao", "executor", "ensaio"):
        anterior = identidade[campo]
        identidade[campo] = anterior + "-mudou"
        with pytest.raises(modulo.RecusaEnsaio):
            modulo.verificar_prova(tmp_path, A)
        identidade[campo] = anterior
    xml.write_text("alterado")
    monkeypatch.setattr(protecao_publicacao, "conferir_relatorio", lambda *_a, **_k:
                        {"estado": "comprovado", "casos": 1, "relatorio_sha256": "xml-2"})
    with pytest.raises(modulo.RecusaEnsaio):
        modulo.verificar_prova(tmp_path, A)


def test_registro_exige_identidade_capturada_e_resultado_persistido(tmp_path, monkeypatch):
    base = tmp_path / "ensaios/saida" / A
    base.mkdir(parents=True)
    xml = base / "comercial.xml"
    xml.write_text("<testsuite/>", encoding="utf-8")
    identidade = {"candidata": A, "celula": "aplicacao", "configuracao": "antes",
                  "artefato": {"comercial_xml": str(xml)}}
    atual = identidade.copy()
    monkeypatch.setattr(modulo, "identidade_atual", lambda *_a, **_k: atual.copy())
    cobertura = {"estado": "comprovado", "casos": 1, "relatorio_sha256": "xml-1"}
    monkeypatch.setattr(protecao_publicacao, "conferir_relatorio", lambda *_a, **_k: cobertura)
    resultado = {"estado": "comprovado", "celula": "aplicacao", "casos": 1,
                 "relatorio_sha256": "xml-1", "identidade_execucao": identidade,
                 "identidade": modulo._json_hash(identidade)}
    arquivo = base / "resultado.json"
    arquivo.write_text(json.dumps(resultado), encoding="utf-8")

    prova = modulo.registrar_prova(tmp_path, A, resultado)
    assert prova["identidade"] == resultado["identidade"]

    atual = {**identidade, "configuracao": "depois"}
    with pytest.raises(modulo.RecusaEnsaio, match="insumos mudaram desde o ensaio"):
        modulo.registrar_prova(tmp_path, A, resultado)
    atual = identidade.copy()
    alterado = {**resultado, "segundos": 42}
    with pytest.raises(modulo.RecusaEnsaio, match="resultado não corresponde"):
        modulo.registrar_prova(tmp_path, A, alterado)
    arquivo.unlink()
    with pytest.raises(modulo.RecusaEnsaio, match="resultado do ensaio indisponível"):
        modulo.registrar_prova(tmp_path, A, resultado)


def test_C18_infra_indisponivel_preserva_demais_e_sem_prova_falha_fechado(tmp_path):
    def ensaio(sha):
        if sha == A:
            raise modulo.InfraIndisponivel("daemon Docker indisponível")
        return True
    promovidas = []
    estado = modulo.separar_lote(
        [{"id": "A", "candidata": A}, {"id": "B", "candidata": B}], ensaio,
        lambda aceitas, reg: reg["candidata"],
        lambda reg, sha: promovidas.append(sha))
    assert estado["A"]["estado"] == "infraestrutura indisponível"
    assert estado["B"]["estado"] == "promovida" and promovidas == [B]
    with pytest.raises(modulo.RecusaEnsaio, match="sem prova"):
        modulo.verificar_prova(tmp_path, A)


@pytest.mark.parametrize("formato", ["docker", "oci"])
def test_imagem_exportada_tem_config_digest_verificado(tmp_path, formato):
    config = b'{"architecture":"amd64","os":"linux"}'
    digest = hashlib.sha256(config).hexdigest()
    arquivo = tmp_path / "imagem.tar"
    with tarfile.open(arquivo, "w") as tar:
        def acrescentar(nome, dados):
            item = tarfile.TarInfo(nome)
            item.size = len(dados)
            tar.addfile(item, io.BytesIO(dados))
        if formato == "docker":
            acrescentar("manifest.json", json.dumps([{"Config": digest + ".json"}]).encode())
            acrescentar(digest + ".json", config)
        else:
            manifest = json.dumps({"config": {"digest": "sha256:" + digest}}).encode()
            md = hashlib.sha256(manifest).hexdigest()
            acrescentar("index.json", json.dumps({"manifests": [{"digest": "sha256:" + md}]}).encode())
            acrescentar("blobs/sha256/" + md, manifest)
            acrescentar("blobs/sha256/" + digest, config)
    assert modulo._imagem_id_tar(arquivo) == "sha256:" + digest
