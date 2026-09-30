"""A revisão candidata nunca fornece a implementação que emite autoridade."""
from __future__ import annotations

import importlib.util
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[2]
URL_PR = "https://github.com/abundanciabr/sitesdoreino/pull/1"
RECIBO = "painel/registros/prova.js"
spec = importlib.util.spec_from_file_location("autoridade_das_fontes", RAIZ / "ci/autoridade_das_fontes.py")
autoridade = importlib.util.module_from_spec(spec)
spec.loader.exec_module(autoridade)


@pytest.fixture(autouse=True)
def fila_da_proposta(monkeypatch):
    def carregar(raiz):
        tarefas = list((raiz / "fila/tarefas").glob("*.json"))
        if not tarefas:
            return {}, []
        tid = json.loads(tarefas[0].read_text())["id"]
        evento = {"tarefa": tid, "evento": "submetida", "arquivo": "20260929-180003-" + tid + "-submetida",
                  "pr": URL_PR, "revisao": "a" * 40, "arvore": "b" * 40}
        return {tid: {}}, [evento]
    monkeypatch.setattr(autoridade.fila, "_carregar_ou_parar", carregar)


def _consulta(caminho="services/catalogo/models.py", autor="abundanciabr", mandato="", anterior=None):
    def consultar(rota):
        if rota == "pulls/1":
            return {"state": "open", "head": {"sha": "a" * 40},
                    "base": {"ref": "main"}, "html_url": URL_PR, "body": mandato,
                    "user": {"login": autor}, "labels": []}
        if rota.startswith("pulls/1/files?"):
            return [{"filename": caminho, "previous_filename": anterior}] if "page=1" in rota else []
        raise AssertionError(rota)
    return consultar


def test_caminho_relativo_da_candidata_e_resolvido_antes_de_mudar_cwd(monkeypatch, tmp_path):
    candidato = tmp_path / "candidate"
    candidato.mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(autoridade, "base_na_main",
                        lambda consulta, numero, sha: consulta(f"pulls/{numero}"))
    vistos = []
    monkeypatch.setattr(autoridade, "candidato_inerte",
                        lambda caminho, sha: vistos.append(caminho))

    def provar(caminho, numero, sha):
        vistos.append(caminho)
        return True, "PASS", "TAR-991", RECIBO

    monkeypatch.setattr(autoridade, "prova_da_base", provar)
    assert autoridade.analisar(1, "a" * 40, Path("candidate"), _consulta())[:2] == ("PASS", False)
    assert vistos == [candidato, candidato]


def test_entrega_comum_recebe_app_sem_revisao_humana(monkeypatch, tmp_path):
    monkeypatch.setattr(autoridade, "candidato_inerte", lambda *a: None)
    monkeypatch.setattr(autoridade, "base_na_main",
                        lambda consulta, numero, sha: consulta(f"pulls/{numero}"))
    monkeypatch.setattr(autoridade, "prova_da_base", lambda *a: (True, "PASS", "TAR-991", RECIBO))
    estado, protegido, _ = autoridade.analisar(1, "a" * 40, tmp_path, _consulta())
    assert (estado, protegido) == ("PASS", False)
    assert autoridade.conclusao(estado, protegido, "skipped") == "success"


def test_caminho_de_dono_exige_mandato_e_aprovacao_condicional(monkeypatch, tmp_path):
    monkeypatch.setattr(autoridade, "candidato_inerte", lambda *a: None)
    monkeypatch.setattr(autoridade, "base_na_main",
                        lambda consulta, numero, sha: consulta(f"pulls/{numero}"))
    monkeypatch.setattr(autoridade, "prova_da_base", lambda *a: (True, "PASS", "TAR-991", RECIBO))
    rota = "ci/guarda_dos_guardas.py"
    sem_mandato = autoridade.analisar(1, "a" * 40, tmp_path, _consulta(rota))
    assert sem_mandato[:2] == ("FAIL", True)
    com_mandato = autoridade.analisar(
        1, "a" * 40, tmp_path,
        _consulta(rota, mandato="Mandato-do-mantenedor: pedido autorizado para ci/ nesta sessão"),
    )
    assert com_mandato[:2] == ("PASS", True)
    assert autoridade.conclusao("PASS", True, "skipped") == "failure"
    assert autoridade.conclusao("PASS", True, "success") == "success"
    assert autoridade.conclusao("ERROR", True, "success") == "failure"
    assert autoridade.analisar(
        1, "a" * 40, tmp_path,
        _consulta(rota, autor="candidato", mandato="Mandato-do-mantenedor: pedido autorizado para ci/ nesta sessão"),
    )[:2] == ("FAIL", True)


def test_renomear_arquivo_protegido_nao_foge_da_revisao():
    assert autoridade.caminhos_protegidos_por_codeowners(
        RAIZ, [{"filename": "texto.txt", "previous_filename": "ci/guardas.py"}],
    )
    assert autoridade.caminhos_protegidos_por_codeowners(RAIZ, [{"filename": "AGENTS.md"}])
    assert autoridade.caminhos_protegidos_por_codeowners(RAIZ, [{"filename": ".claude/agents/revisor.md"}])
    assert not autoridade.caminhos_protegidos_por_codeowners(RAIZ, [{"filename": "services/catalogo/models.py"}])
    assert autoridade.caminhos_protegidos_por_codeowners(RAIZ, [
        {"filename": "texto.txt", "previous_filename": "infra/deploy.sh"}]) == ["texto.txt", "infra/deploy.sh"]




def test_renomear_protegido_exige_mandato_para_nome_antigo(monkeypatch, tmp_path):
    monkeypatch.setattr(autoridade, "candidato_inerte", lambda *a: None)
    monkeypatch.setattr(autoridade, "base_na_main",
                        lambda consulta, numero, sha: consulta(f"pulls/{numero}"))
    monkeypatch.setattr(autoridade, "prova_da_base", lambda *a: (True, "PASS", "TAR-991", RECIBO))
    consulta = _consulta("texto.txt", anterior="ci/guardas.py")
    assert autoridade.analisar(1, "a" * 40, tmp_path, consulta)[:2] == ("FAIL", True)


def test_lista_no_teto_da_api_recusa_antes_de_classificar():
    chamadas = []
    def consultar(rota):
        chamadas.append(rota)
        return [{"filename": f"arquivo-{len(chamadas)}-{i}"} for i in range(100)]
    with pytest.raises(ValueError, match="3000 ou mais"):
        autoridade.arquivos_do_pr(consultar, 1)
    assert len(chamadas) == 30


def test_base_executa_seu_verificador_e_recusa_autoaprovador(tmp_path):
    candidato = tmp_path / "candidate"
    (candidato / "ci").mkdir(parents=True)
    (candidato / "ci/padrao_de_trabalho.py").write_text("print('PASS')\n", encoding="utf-8")
    comandos = []
    def rodar(comando, **kwargs):
        comandos.append(comando)
        assert Path(comando[2]).is_relative_to(autoridade.BASE)
        assert not Path(comando[2]).is_relative_to(candidato)
        return subprocess.CompletedProcess(comando, 1 if "padrao_de_trabalho.py" in comando[2] else 0, "", "")
    assert autoridade.prova_da_base(candidato, 1, "a" * 40, rodar)[0] is False
    assert len(comandos) == 1


def test_sem_linhagem_da_base_check_falha_fechado(tmp_path):
    comandos = []
    def rodar(comando, **kwargs):
        comandos.append(comando)
        return subprocess.CompletedProcess(comando, 2 if "fila.py" in comando[2] else 0, "", "")
    assert autoridade.prova_da_base(tmp_path, 1, "a" * 40, rodar)[0] is False
    assert len(comandos) == 2
    assert Path(comandos[1][2]) == autoridade.BASE / "ci/fila.py"
    assert comandos[1][-2:] == ["--checkout", str(tmp_path)]


def test_import_malicioso_da_candidata_nao_executa(tmp_path):
    candidato = tmp_path / "candidate"
    for nome in autoridade.FONTES:
        destino = candidato / nome
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(RAIZ / nome, destino)
    marcador = tmp_path / "codigo-candidato-executou"
    fonte = candidato / "ci/padrao_de_trabalho.py"
    fonte.write_text(f"from pathlib import Path\nPath({str(marcador)!r}).write_text('executou')\n")
    resultado = subprocess.run(
        [sys.executable, "-I", str(RAIZ / "ci/padrao_de_trabalho.py"),
         "--candidato", str(candidato)], capture_output=True, text=True,
    )
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    assert not marcador.exists()


def test_candidato_com_head_ou_fonte_ilegivel_e_recusado(tmp_path):
    candidato = tmp_path / "candidate"
    candidato.mkdir()
    errado = lambda *a, **k: SimpleNamespace(returncode=0, stdout="b" * 40)
    with pytest.raises(ValueError, match="HEAD"):
        autoridade.candidato_inerte(candidato, "a" * 40, errado)
    correto = lambda *a, **k: SimpleNamespace(returncode=0, stdout="a" * 40)
    with pytest.raises(ValueError, match="fonte candidata"):
        autoridade.candidato_inerte(candidato, "a" * 40, correto)
    with pytest.raises(ValueError, match="fora da candidata"):
        autoridade.candidato_inerte(autoridade.BASE, "a" * 40, correto)


def _fontes_do_mandato(tmp_path, tarefa="TAR-991", nome=None, caminhos=None):
    base, candidato = tmp_path / "base", tmp_path / "candidate"
    nome = nome or "991-proteger-configuracoes.json"
    caminhos = caminhos or ["infra/deploy.sh"]
    for raiz in (base, candidato):
        (raiz / "fila/eventos").mkdir(parents=True)
        (raiz / "fila/tarefas").mkdir(parents=True)
        (raiz / "fila/tarefas" / nome).write_text(json.dumps({
            "id": tarefa, "origem": "Frente18 PME08 TAR958",
            "toca": ["infra", "ci"], "despacho": "Alterar " + ", ".join(caminhos)}))
    pasta = base / "fila/eventos"
    contrato = pasta / "20260929-142620-TAR-958-contrato_execucao.json"
    contrato.write_text(json.dumps({"evento": "contrato_execucao", "tarefa": "TAR-958"}))
    evento = pasta / "20260929-180000-TAR-958-checkpoint.json"
    evento.write_text(json.dumps({"evento": "checkpoint", "tarefa": "TAR-958", "contexto": {
        "mandato_reutilizavel": {"contrato": contrato.name,
            "contrato_sha256": hashlib.sha256(contrato.read_bytes()).hexdigest(),
            "valido_enquanto": "TAR-958-aberta",
            "tarefas": {tarefa: {"arquivo": nome,
                "sha256": hashlib.sha256((base / "fila/tarefas" / nome).read_bytes()).hexdigest(),
                "caminhos": caminhos}}}}}))
    return base, candidato, evento, hashlib.sha256(evento.read_bytes()).hexdigest()


def _arquivos(*caminhos):
    return [{"filename": caminho} for caminho in caminhos]


def test_pin_reusa_tarefa_do_programa_ja_integrada_e_expira(tmp_path):
    base, candidato, evento, pin = _fontes_do_mandato(tmp_path)
    assert autoridade.mandato_reutilizavel(base, candidato, _arquivos("infra/deploy.sh"), pin, "TAR-991", URL_PR, RECIBO)
    for caminhos, tid, codigo in [(_arquivos("infra/deploy.sh"), "TAR-990", pin),
                                  (_arquivos("infra/deploy.sh"), "TAR-991", ""),
                                  (_arquivos("infra/deploy.sh", "ci/fila.py"), "TAR-991", pin),
                                  (_arquivos("infra/deploy.sh", "texto.txt"), "TAR-991", pin)]:
        assert not autoridade.mandato_reutilizavel(base, candidato, caminhos, codigo, tid, URL_PR, RECIBO)
    evento.write_text(evento.read_text() + " ")
    assert not autoridade.mandato_reutilizavel(base, candidato, _arquivos("infra/deploy.sh"), pin, "TAR-991", URL_PR, RECIBO)
    evento.write_text(evento.read_text().rstrip())
    (base / "fila/eventos/20260929-180001-TAR-958-concluida.json").write_text(
        json.dumps({"evento": "concluida", "tarefa": "TAR-958"}))
    assert not autoridade.mandato_reutilizavel(base, candidato, _arquivos("infra/deploy.sh"), pin, "TAR-991", URL_PR, RECIBO)


def test_tarefa_nova_ou_alheia_nao_reusa(tmp_path):
    base, candidato, _, pin = _fontes_do_mandato(tmp_path)
    nome = "991-proteger-configuracoes.json"
    alvo = candidato / "fila/tarefas" / nome
    dados = json.loads(alvo.read_text())
    dados["origem"] = "Programa alheio"
    alvo.write_text(json.dumps(dados))
    assert not autoridade.mandato_reutilizavel(base, candidato, _arquivos("infra/deploy.sh"), pin, "TAR-991", URL_PR, RECIBO)
    alvo.write_text((base / "fila/tarefas" / nome).read_text())
    (candidato / "fila/tarefas/992-tarefa-nova.json").write_text(json.dumps({
        "id": "TAR-992", "origem": "TAR958", "toca": ["infra"]}))
    assert not autoridade.mandato_reutilizavel(base, candidato, _arquivos("infra/deploy.sh"), pin, "TAR-992", URL_PR, RECIBO)
    dados = json.loads((base / "fila/tarefas" / nome).read_text())
    dados["origem"] = "Programa alheio"
    (base / "fila/tarefas" / nome).write_text(json.dumps(dados))
    alvo.write_text(json.dumps(dados))
    assert not autoridade.mandato_reutilizavel(base, candidato, _arquivos("infra/deploy.sh"), pin, "TAR-991", URL_PR, RECIBO)


def test_tarefa_terminada_na_base_revoga_reuso(tmp_path):
    base, candidato, _, pin = _fontes_do_mandato(tmp_path)
    (base / "fila/eventos/20260929-180001-TAR-991-cancelada.json").write_text(
        json.dumps({"evento": "cancelada", "tarefa": "TAR-991"}))
    assert not autoridade.mandato_reutilizavel(base, candidato, _arquivos("infra/deploy.sh"), pin, "TAR-991", URL_PR, RECIBO)


def test_candidata_nao_injeta_escopo_no_checkpoint(tmp_path):
    base, candidato, evento, pin = _fontes_do_mandato(tmp_path)
    registro = json.loads(evento.read_text())
    registro["contexto"]["mandato_reutilizavel"]["tarefas"]["TAR-991"]["caminhos"] = ["ci/fila.py"]
    (candidato / "fila/eventos" / evento.name).write_text(json.dumps(registro))
    assert autoridade.mandato_reutilizavel(base, candidato, _arquivos("infra/deploy.sh"), pin, "TAR-991", URL_PR, RECIBO)
    assert not autoridade.mandato_reutilizavel(base, candidato, _arquivos("ci/fila.py"), pin, "TAR-991", URL_PR, RECIBO)


def test_identidade_da_tarefa_vem_da_linhagem_da_base(tmp_path):
    def rodar(comando, **kwargs):
        saida = ("PASS linhagem: TAR-991 PR 1 HEAD " + "a" * 40
                 + " recibo painel/registros/prova.js\n") if "fila.py" in comando[2] else ""
        return subprocess.CompletedProcess(comando, 0, saida, "")
    assert autoridade.prova_da_base(tmp_path, 1, "a" * 40, rodar)[2] == "TAR-991"
    def pr_alheio(comando, **kwargs):
        saida = "PASS linhagem: TAR-991 PR 2 HEAD " + "a" * 40 + " recibo recibo.js\n"
        return subprocess.CompletedProcess(comando, 0, saida if "fila.py" in comando[2] else "", "")
    assert autoridade.prova_da_base(tmp_path, 1, "a" * 40, pr_alheio)[0] is False

def test_escopo_exato_cobre_diff_inteiro_e_renomeacao(tmp_path):
    base, candidato, _, pin = _fontes_do_mandato(tmp_path)
    assert autoridade.mandato_reutilizavel(base, candidato, _arquivos("infra/deploy.sh"), pin, "TAR-991", URL_PR, RECIBO)
    for arquivos in (
        _arquivos("infra/deploy.sh", "infra/outro.sh"),
        _arquivos("infra/deploy.sh", "services/catalogo/models.py"),
        [{"filename": "infra/deploy.sh", "previous_filename": "infra/outro.sh"}],
        [{"filename": "services/catalogo/models.py", "previous_filename": "infra/deploy.sh"}],
    ):
        assert not autoridade.mandato_reutilizavel(base, candidato, arquivos, pin, "TAR-991", URL_PR, RECIBO)


def test_revogacao_versionada_na_base_recusa_pin_antigo(tmp_path):
    base, candidato, _, pin = _fontes_do_mandato(tmp_path)
    revogacao = base / "fila/eventos/20260929-180002-TAR-958-checkpoint.json"
    revogacao.write_text(json.dumps({"evento": "checkpoint", "tarefa": "TAR-958",
                                      "contexto": {"mandatos_revogados_sha256": [pin]}}))
    assert not autoridade.mandato_reutilizavel(
        base, candidato, _arquivos("infra/deploy.sh"), pin, "TAR-991", URL_PR, RECIBO)


def test_base_igual_ao_pr_e_main_antes_da_emissao():
    estado = {"base": "b" * 40, "main": "b" * 40}
    def consulta(rota):
        if rota == "pulls/1":
            return {"state": "open", "head": {"sha": "a" * 40},
                    "base": {"ref": "main", "sha": estado["base"]}}
        if rota == "git/ref/heads/main":
            return {"object": {"sha": estado["main"]}}
        raise AssertionError(rota)
    def rodar(*args, **kwargs):
        return subprocess.CompletedProcess(args, 0, estado["base"] + "\n", "")
    assert autoridade.base_na_main(consulta, 1, "a" * 40, rodar)["base"]["sha"] == "b" * 40
    estado["main"] = "c" * 40
    with pytest.raises(ValueError, match="main divergiram"):
        autoridade.base_na_main(consulta, 1, "a" * 40, rodar)


def test_main_avancou_durante_analise_impede_pass(monkeypatch, tmp_path):
    leituras = []
    def base(consulta, numero, sha):
        leituras.append(1)
        if len(leituras) > 1:
            raise ValueError("main divergiu")
        return consulta(f"pulls/{numero}")
    monkeypatch.setattr(autoridade, "base_na_main", base)
    monkeypatch.setattr(autoridade, "candidato_inerte", lambda *a: None)
    monkeypatch.setattr(autoridade, "prova_da_base", lambda *a: (True, "PASS", "TAR-991", RECIBO))
    with pytest.raises(ValueError, match="main divergiu"):
        autoridade.analisar(1, "a" * 40, tmp_path, _consulta())
    assert len(leituras) == 2


def test_diff_integral_do_pr_real_2355_cabe_no_grant_exato(monkeypatch, tmp_path):
    infra = [
        "infra/provisionar-par-da-caixa.sh",
        "infra/provisionar-par-da-economia.sh",
        "infra/provisionar-par-da-gamificacao-com-o-forum.sh",
        "infra/provisionar-par-da-gamificacao-com-os-alunos.sh",
        "infra/provisionar-par-da-medicao.sh",
        "infra/provisionar-par-do-forum-com-a-gamificacao.sh",
        "infra/provisionar-par-do-funil-com-a-gamificacao.sh",
        "infra/provisionar-par-do-menu.sh",
        "infra/provisionar-par-do-portfolio-com-a-admin.sh",
        "infra/provisionar-par-do-teste-de-aviso.sh",
        "infra/provisionar-par-dos-parametros.sh",
        "infra/provisionar-pares-da-prancheta.sh",
        "infra/provisionar-pares-da-sala-de-aula.sh",
        "infra/provisionar-pares-de-categorias.sh",
    ]
    teste = "ci/tests/test_exclusao_comum_da_publicacao.py"
    tarefa = "fila/tarefas/989-impedir-que-as-conexoes-entre-servicos-disputem-a-publicacao.json"
    eventos = [
        {"tarefa": "TAR-989", "evento": tipo, "arquivo": nome}
        for tipo, nome in (
            ("explicada", "20260929-184542-TAR-989-explicada"),
            ("reivindicada", "20260929-184902-TAR-989-reivindicada"),
            ("contrato_execucao", "20260929-184936-TAR-989-contrato_execucao"),
        )
    ]
    eventos.append({
        "tarefa": "TAR-989", "evento": "submetida",
        "arquivo": "20260929-185644-TAR-989-submetida",
        "pr": "https://github.com/abundanciabr/sitesdoreino/pull/2355",
        "revisao": "094f12d45300605428a7590a1b561f83847af260",
        "arvore": "f7d117d8f447c371c64a71d2181cffeaae01c35a",
    })
    recibo = "painel/registros/20260929-044-infra-serializar-quatorze-provisionadores-de-pares.js"
    paths = [teste, *(f"fila/eventos/{ev['arquivo']}.json" for ev in eventos),
             tarefa, *infra, recibo]
    assert len(paths) == 21
    base, candidato, _, pin = _fontes_do_mandato(
        tmp_path, "TAR-989", tarefa.rsplit("/", 1)[1], [teste, *infra])
    (base / tarefa).unlink()  # Como no PR real: tarefa embarca no primeiro diff; grant já está pinado na base.
    monkeypatch.setattr(autoridade.fila, "_carregar_ou_parar",
                        lambda _: ({"TAR-989": {}}, eventos))
    url = "https://github.com/abundanciabr/sitesdoreino/pull/2355"
    assert autoridade.mandato_reutilizavel(
        base, candidato, _arquivos(*paths), pin, "TAR-989", url, recibo)
    assert not autoridade.mandato_reutilizavel(
        base, candidato, _arquivos(*paths, "painel/registros/recibo-alheio.js"),
        pin, "TAR-989", url, recibo)
    assert not autoridade.mandato_reutilizavel(
        base, candidato, _arquivos(*paths, "fila/eventos/20260929-185644-TAR-990-submetida.json"),
        pin, "TAR-989", url, recibo)
    evento_tardio = {"tarefa": "TAR-989", "evento": "explicada",
                     "arquivo": "20260929-185700-TAR-989-explicada"}
    eventos.append(evento_tardio)
    try:
        assert not autoridade.mandato_reutilizavel(
            base, candidato,
            _arquivos(*paths, f"fila/eventos/{evento_tardio['arquivo']}.json"),
            pin, "TAR-989", url, recibo)
    finally:
        eventos.pop()
    for tipo in ("cancelada", "concluida", "checkpoint"):
        evento_indevido = {"tarefa": "TAR-989", "evento": tipo,
                           "arquivo": f"20260929-185700-TAR-989-{tipo}"}
        eventos.append(evento_indevido)
        try:
            nome = f"fila/eventos/{evento_indevido['arquivo']}.json"
            assert not autoridade.mandato_reutilizavel(
                base, candidato, _arquivos(*paths, nome), pin, "TAR-989", url, recibo)
        finally:
            eventos.pop()


def test_tentativa_anterior_precisa_estar_fechada_sem_merge(monkeypatch, tmp_path):
    base, candidato, _, pin = _fontes_do_mandato(tmp_path)
    anterior = {"tarefa": "TAR-991", "evento": "submetida",
                "arquivo": "20260929-170000-TAR-991-submetida",
                "pr": "https://github.com/abundanciabr/sitesdoreino/pull/2"}
    atual = {"tarefa": "TAR-991", "evento": "submetida",
             "arquivo": "20260929-180003-TAR-991-submetida", "pr": URL_PR,
             "revisao": "a" * 40, "arvore": "b" * 40}
    monkeypatch.setattr(autoridade.fila, "_carregar_ou_parar",
                        lambda _: ({"TAR-991": {}}, [anterior, atual]))
    estado = {"state": "OPEN", "mergeCommit": None}
    monkeypatch.setattr(autoridade.fila, "consultar_pr_submetido", lambda *a: estado)
    args = (base, candidato, _arquivos("infra/deploy.sh"), pin, "TAR-991", URL_PR, RECIBO)
    assert not autoridade.mandato_reutilizavel(*args)
    estado["state"] = "MERGED"
    assert not autoridade.mandato_reutilizavel(*args)
    estado.clear()
    estado["state"] = "CLOSED"
    assert not autoridade.mandato_reutilizavel(*args)
    estado["mergeCommit"] = {"oid": "a" * 40}
    assert not autoridade.mandato_reutilizavel(*args)
    estado["mergeCommit"] = None
    assert autoridade.mandato_reutilizavel(*args)
    def erro_api(*_):
        raise autoridade.ErroDeInstrumentacao("API indisponível", "Repetir a consulta.")
    monkeypatch.setattr(autoridade.fila, "consultar_pr_submetido", erro_api)
    assert not autoridade.mandato_reutilizavel(*args)


def test_workflow_priviligiado_so_tem_codigo_base_e_segredo_no_emissor():
    fluxo = yaml.safe_load((RAIZ / ".github/workflows/autoridade-das-fontes.yml").read_text(encoding="utf-8"))
    jobs = fluxo["jobs"]
    assert "pull_request_target" in fluxo[True]
    assert all(
        re.fullmatch(r"actions/[^@]+@[0-9a-f]{40}", passo["uses"])
        for job in jobs.values() for passo in job["steps"] if "uses" in passo
    )
    passos = jobs["analisar"]["steps"]
    assert all("secrets." not in str(p) for p in passos)
    assert any(p.get("with", {}).get("path") == "candidate" for p in passos)
    assert "mandato-protegido" == jobs["mandato"]["environment"]
    assert "autoridade-app" == jobs["emitir"]["environment"]
    assert "needs.analisar.outputs.revisao_necessaria == 'true'" in jobs["mandato"]["if"]
    assert "vars.AUTH_MANDATE_SHA256" in jobs["analisar"]["steps"][-1]["env"]["AUTH_MANDATE_SHA256"]
    assert not any(p.get("with", {}).get("path") == "candidate" for p in jobs["emitir"]["steps"])
    app = next(p for p in jobs["emitir"]["steps"] if p.get("id") == "app")
    assert app["with"]["permission-checks"] == "write"
    assert not any(chave.startswith("permission-") and chave != "permission-checks" for chave in app["with"])
    assert "secrets.AUTH_APP_PRIVATE_KEY" in app["with"]["private-key"]
    assert "pull-requests" in jobs["emitir"]["permissions"]
    assert "github.token" in jobs["emitir"]["steps"][-1]["env"]["READ_TOKEN"]


def test_emissor_falha_fechado_se_base_mudou(monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "abundanciabr/sitesdoreino")
    monkeypatch.setenv("GH_TOKEN", "token-app")
    monkeypatch.setenv("READ_TOKEN", "token-leitura")
    monkeypatch.setenv("ESTADO_ANALISE", "PASS")
    monkeypatch.setenv("REVISAO_NECESSARIA", "false")
    monkeypatch.setenv("RESULTADO_ANALISE", "success")
    monkeypatch.setattr(sys, "argv", ["autoridade_das_fontes.py", "emitir",
                                       "--pr", "1", "--head", "a" * 40])
    monkeypatch.setattr(autoridade, "base_na_main",
                        lambda *a: (_ for _ in ()).throw(ValueError("base mudou")))
    pedidos = []
    monkeypatch.setattr(autoridade, "consultar", lambda *args: pedidos.append(args))
    assert autoridade.main() == 1
    assert pedidos[0][3]["conclusion"] == "failure"


@pytest.mark.parametrize(
    ("analise", "protegido", "revisao", "esperado"),
    [("PASS", "false", "skipped", "success"),
     ("PASS", "true", "skipped", "failure"),
     ("PASS", "true", "success", "success"),
     ("ERROR", "false", "success", "failure")],
)
def test_app_emite_resultado_no_head_exato(monkeypatch, analise, protegido, revisao, esperado):
    env = {"GITHUB_REPOSITORY": "abundanciabr/sitesdoreino", "GH_TOKEN": "token-app",
           "ESTADO_ANALISE": analise, "REVISAO_NECESSARIA": protegido,
           "REVISAO_PROTEGIDA": revisao, "RESULTADO_ANALISE": "success"}
    for nome, valor in env.items():
        monkeypatch.setenv(nome, valor)
    monkeypatch.setattr(sys, "argv", ["autoridade_das_fontes.py", "emitir", "--pr", "1", "--head", "a" * 40])
    pedidos = []
    monkeypatch.setattr(autoridade, "consultar", lambda *args: pedidos.append(args))
    monkeypatch.setattr(autoridade, "base_na_main", lambda *a: None)
    assert autoridade.main() == (0 if esperado == "success" else 1)
    assert len(pedidos) == 1
    token, repo, rota, corpo = pedidos[0]
    assert (token, repo, rota) == ("token-app", "abundanciabr/sitesdoreino", "check-runs")
    assert (corpo["name"], corpo["head_sha"], corpo["conclusion"]) == (
        "autoridade-das-fontes", "a" * 40, esperado,
    )
