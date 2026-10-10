"""Regressões nas fronteiras entre ensaio, congelamento e retomada por célula."""
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
from types import SimpleNamespace
import xml.etree.ElementTree as ET

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import ensaio_entregas as ensaio
import mercadopago_congelado as mp
import protecao_publicacao as protecao
import ponte_entregas as ponte
from integrador_servico import Estados, Servico
from testes_ensaio_entregas import _tar_imagem, _imagem_de_teste
from testes_integrador_servico import I1, I2, C1, C2, BASE, entrega, PonteFalsa, IntegradorFalso

FERRAMENTAS = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def ferramentas_instaladas(tmp_path, monkeypatch):
    fonte = Path(__file__).resolve().parents[1]
    runtime = tmp_path / "ferramentas"
    (runtime / "infra").mkdir(parents=True)
    for nome in ("protecao_publicacao.py", "execucao-celulas.py"):
        shutil.copy2(fonte / "infra" / nome, runtime / "infra" / nome)
    shutil.copy2(fonte / "services/aplicacao/preparar.py", runtime / "preparar-aplicacao.py")
    shutil.copytree(fonte / "services/aplicacao/tests/e2e", runtime / "provas-aplicacao/e2e")
    shutil.copytree(fonte / "services/funil/tests", runtime / "provas-funil")
    monkeypatch.setattr(protecao, "__file__", str(runtime / "infra/protecao_publicacao.py"))
    monkeypatch.setattr(sys.modules[__name__], "FERRAMENTAS", runtime)


def git(*args):
    p = subprocess.run(["git", *map(str, args)], capture_output=True, text=True, check=True)
    return p.stdout.strip()


def rota(nome):
    return '\n  services:\n    funil:\n      loadBalancer:\n        servers: [ { url: "http://' + nome + ':8000" } ]\n'


def ambiente(tmp_path):
    (tmp_path / "traefik/dynamic").mkdir(parents=True)
    (tmp_path / "docker-compose.yml").write_text("services: {}", encoding="utf-8")
    (tmp_path / "traefik/dynamic/plataforma.yml").write_text(rota("aplicacao"), encoding="utf-8")
    trabalho = tmp_path / "git-trabalho"
    git("init", trabalho)
    (trabalho / "exemplo.py").write_text("valor = 1", encoding="utf-8")
    git("-C", trabalho, "add", ".")
    git("-C", trabalho, "-c", "user.name=Teste", "-c", "user.email=teste@localhost",
        "commit", "-m", "base")
    sha = git("-C", trabalho, "rev-parse", "HEAD")
    (tmp_path / "codigo").mkdir()
    git("clone", "--bare", trabalho, tmp_path / "codigo/repo.git")
    return sha


def resultado_real(raiz, sha):
    base, codigo, imagem = ensaio._caminhos(raiz, sha, "funil")
    bundle = base / "bundle"
    for nome in ("config/settings.py", "entrypoint.py", "workers.py", "internal.py",
                 "modules/__init__.py", "modules/funil/app.py"):
        arquivo = bundle / nome
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        arquivo.write_text("valor = 1\n", encoding="utf-8")
    modulo = ensaio._modulo_funil(FERRAMENTAS)
    modulo.projetar(bundle, codigo, "funil")
    membros, _ = _imagem_de_teste("docker")
    _tar_imagem(imagem, membros)
    ensaio._snapshot_rota(raiz, base, ensaio._nome_funil(sha, base.name), FERRAMENTAS)
    evidencias = base / "evidencias"
    evidencias.mkdir()
    suite = ET.Element("testsuite")
    for nome in sorted(protecao.casos_esperados()):
        caso = ET.SubElement(suite, "testcase", name=nome)
        if nome == "test_20_conversa_do_contato_de_teste_liga_sozinha":
            ET.SubElement(caso, "skipped", type="pytest.xfail")
    ET.ElementTree(suite).write(evidencias / "comercial.xml", encoding="utf-8")
    (evidencias / "funil.xml").write_text('<testsuite><testcase name="rota"/></testsuite>')
    identidade = ensaio.identidade_atual(raiz, sha, FERRAMENTAS, "funil")
    comercial = protecao.conferir_relatorio(evidencias / "comercial.xml", registrar_falha_conhecida=True)
    resultado = {"estado": "comprovado", "celula": "funil", "casos": comercial["casos"],
        "relatorio_sha256": comercial["relatorio_sha256"], "identidade_execucao": identidade,
        "identidade": ensaio._json_hash(identidade),
        "funil": protecao.conferir_relatorio(evidencias / "funil.xml")}
    (base / "resultado.json").write_text(json.dumps(resultado), encoding="utf-8")
    return resultado


def test_destino_gerado_passa_no_verificador_congelado_sem_mudar_a_politica(tmp_path):
    sha = ambiente(tmp_path)
    politica = {"rotas_sha256": mp.capturar_rotas(tmp_path)}
    antes = dict(politica)
    resultado = resultado_real(tmp_path, sha)
    final = Path(resultado["identidade_execucao"]["artefato"]["configuracao_final"])
    mp.conferir_rotas(final, politica)
    assert politica == antes
    assert "-ensaio" not in resultado["identidade_execucao"]["nome_funil"]
    # O contrato mantém a recusa de qualquer alteração nas outras rotas.
    arquivo = final / "traefik/dynamic/plataforma.yml"
    arquivo.write_text(arquivo.read_text() + "  routers: adulterado\n")
    with pytest.raises(mp.IntegridadeMercadoPagoErro):
        mp.conferir_rotas(final, politica)


@pytest.mark.parametrize("alteracao", ["codigo", "imagem", "relatorio", "snapshot"])
def test_ativacao_e_upgrade_nao_apagam_historia_mas_adulteracao_e_recusada(tmp_path, monkeypatch, alteracao):
    sha = ambiente(tmp_path)
    prova = ensaio.registrar_prova(tmp_path, sha, resultado_real(tmp_path, sha), FERRAMENTAS, "funil")
    final = Path(prova["artefato"]["configuracao_final"])
    (tmp_path / "traefik/dynamic/plataforma.yml").write_bytes((final / "traefik/dynamic/plataforma.yml").read_bytes())
    monkeypatch.setattr(ensaio, "_ferramentas", lambda _: ("a" * 64, "b" * 64))
    with pytest.raises(ensaio.RecusaEnsaio):
        ensaio.verificar_prova(tmp_path, sha, FERRAMENTAS, "funil")
    assert ensaio.verificar_prova_historica(tmp_path, sha, FERRAMENTAS, "funil", prova["identidade"]) == prova
    alvos = {"codigo": Path(prova["artefato"]["codigo"]) / "entrypoint.py",
             "imagem": Path(prova["artefato"]["imagem_tar"]),
             "relatorio": Path(prova["artefato"]["funil_xml"]),
             "snapshot": final / "docker-compose.yml"}
    with alvos[alteracao].open("ab") as arquivo:
        arquivo.write(b"alteracao")
    with pytest.raises((ensaio.RecusaEnsaio, ET.ParseError)):
        ensaio.verificar_prova_historica(tmp_path, sha, FERRAMENTAS, "funil", prova["identidade"])


def test_repeticao_preserva_diretorio_antigo_e_prova_selada(tmp_path):
    sha = ambiente(tmp_path)
    antiga = ensaio.registrar_prova(tmp_path, sha, resultado_real(tmp_path, sha), FERRAMENTAS, "funil")
    codigo_antigo = Path(antiga["artefato"]["codigo"])
    antes = protecao.arvore(codigo_antigo)
    ensaio._nova_tentativa(tmp_path, sha, "funil")
    nova = ensaio.registrar_prova(tmp_path, sha, resultado_real(tmp_path, sha), FERRAMENTAS, "funil")
    assert nova["artefato"]["codigo"] != antiga["artefato"]["codigo"]
    assert nova["nome_funil"] != antiga["nome_funil"]
    assert protecao.arvore(codigo_antigo) == antes
    assert ensaio.verificar_prova_historica(tmp_path, sha, FERRAMENTAS, "funil", antiga["identidade"]) == antiga
    assert ensaio.verificar_prova(tmp_path, sha, FERRAMENTAS, "funil") == nova


def test_worker_retoma_funil_na_main_nova_apos_entrega_apenas_da_aplicacao(tmp_path):
    antiga = entrega(I1, C1)
    antiga.update(estado="integrada na main", promovida_candidata=C1,
                  promocao={"estado": "remota", "candidata": C1})
    nova = entrega(I2, C2)
    nova["base_da_candidata"] = C1
    integrador = IntegradorFalso([antiga, nova], diff={C1: "services/funil/app.py", C2: "services/admin/app.py"})
    autoridade = PonteFalsa(conciliacao={(I1, "funil"): {"situacao": "aguardando"}})
    estados = Estados(tmp_path / "fases")
    estados.salvar({"id": I1, "candidata": C1, "fase": "ativação pendente", "celulas": ["funil"]})
    worker = Servico(integrador, autoridade, estados)
    worker.rodada()
    assert ("reconciliar", I2, C2, "funil") in autoridade.chamadas
    assert ("publicar", I1) not in autoridade.chamadas
    assert estados.ler(I2)["reconciliacao_celulas"]["funil"]["estado"] == "ativa"
    # Um reinício e uma perda de resposta não dependem de nova entrega humana.
    salvo = estados.ler(I2)
    salvo["reconciliacao_celulas"]["funil"] = {"estado": "pendente", "candidata": C2}
    estados.salvar(salvo)
    Servico(integrador, autoridade, estados).rodada()
    assert autoridade.chamadas.count(("reconciliar", I2, C2, "funil")) == 2


def test_ponte_nao_renova_prova_nem_publica_candidata_que_saiu_da_main(tmp_path, monkeypatch):
    autoridade = ponte.Autoridade(tmp_path / "origem", tmp_path)
    monkeypatch.setattr(autoridade, "espelhar", lambda *_: None)
    monkeypatch.setattr(autoridade, "_conferir_espelho", lambda *_: {})
    monkeypatch.setattr(autoridade, "conferir_preservacao", lambda *_: {"situacao": "aguardando"})
    monkeypatch.setattr(autoridade, "preparar", lambda *_: pytest.fail("não deve ensaiar candidata antiga"))
    monkeypatch.setattr(autoridade, "publicar", lambda *_: pytest.fail("não deve publicar candidata antiga"))
    with pytest.raises(ponte.ErroPonte, match="main mudou"):
        autoridade.reconciliar(I1, C1, "funil")


def test_ponte_reensaia_pendencia_na_main_nova_com_git_artefatos_e_recibo_reais(tmp_path, monkeypatch):
    import publicar
    base = ambiente(tmp_path)
    trabalho = tmp_path / "git-trabalho"
    for nome in ("services/funil/pagina.py", "services/admin/painel.py"):
        arquivo = trabalho / nome
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        arquivo.write_text("valor = 2", encoding="utf-8")
        git("-C", trabalho, "add", ".")
        git("-C", trabalho, "-c", "user.name=Teste", "-c", "user.email=teste@localhost", "commit", "-m", nome)
    candidata = git("-C", trabalho, "rev-parse", "HEAD")
    git("--git-dir", tmp_path / "codigo/repo.git", "fetch", trabalho, "HEAD")
    publicacoes = tmp_path / "publicacoes"
    publicacoes.mkdir()
    journal = publicacoes / "funil.json"
    journal.write_text(json.dumps({"atual": base, "aprovada": {"sha": base}}))
    # A promoção mais recente era somente da aplicação; não havia prova funil.
    reg = {"id": I2, "promocao": {"estado": "remota", "candidata": candidata,
                                  "prova_identidade": "a" * 64}}
    original = json.dumps(reg, sort_keys=True)
    autoridade = ponte.Autoridade(tmp_path / "origem", tmp_path, FERRAMENTAS)
    monkeypatch.setattr(autoridade, "espelhar", lambda *_: None)
    monkeypatch.setattr(autoridade, "_conferir_espelho", lambda *_: reg)
    monkeypatch.setattr(autoridade, "conferir_preservacao", lambda *_: {"situacao": "publicavel"})
    monkeypatch.setattr(autoridade, "_ensaio", lambda: ensaio)
    monkeypatch.setattr(autoridade, "_container_da_tentativa_existe", lambda _: False)
    preparadas = []

    def preparar(id_, sha, celula):
        preparadas.append((id_, sha, celula))
        resultado_real(tmp_path, sha)

    monkeypatch.setattr(autoridade, "preparar", preparar)
    monkeypatch.setattr(publicar, "PUBLICACOES", publicacoes)
    publicadas = []

    def ativar(id_, sha, celula):
        if json.loads(journal.read_text())["atual"] == sha:
            return {"ok": True, "estado": "ativa"}
        prova = ensaio.verificar_prova(tmp_path, sha, FERRAMENTAS, celula)
        publicar._conferir_prova_promovida(id_, sha, celula, reg["promocao"], prova)
        final = Path(prova["artefato"]["configuracao_final"])
        (tmp_path / "traefik/dynamic/plataforma.yml").write_bytes((final / "traefik/dynamic/plataforma.yml").read_bytes())
        journal.write_text(json.dumps({"atual": sha, "aprovada": {"sha": sha, "pacote": prova["pacote_publicador"]}}))
        publicadas.append(sha)
        raise ponte.ErroPonte("resposta perdida")

    monkeypatch.setattr(autoridade, "publicar", ativar)
    with pytest.raises(ponte.ErroPonte, match="resposta perdida"):
        autoridade.reconciliar(I2, candidata, "funil")
    assert autoridade.reconciliar(I2, candidata, "funil")["estado"] == "ativa"
    assert preparadas == [(I2, candidata, "funil")]
    assert publicadas == [candidata]
    assert json.dumps(reg, sort_keys=True) == original
    recibo = json.loads((publicacoes / "reconciliacoes" / (candidata + "-funil.json")).read_text())
    assert recibo["origem_aprovada"] == base
    assert recibo["prova_promocao"] is None
    assert ensaio.verificar_prova_historica(tmp_path, candidata, FERRAMENTAS, "funil")["identidade"] == recibo["identidade"]
