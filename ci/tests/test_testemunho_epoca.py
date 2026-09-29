"""Ensaios de autoridade externa e falha fechada do testemunho de época."""

import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import testemunho_epoca as epoca


class FonteMemoria:
    def __init__(self):
        self.tags = {}
        self.protegida = True
        self.particao = False
        self.perder_resposta = False
        self.ponteiro = None
        self.proximo_oid = 1

    def protecao_ativa(self, coorte):
        if self.particao:
            raise epoca.ErroTestemunho("ERROR: partição")
        return self.protegida

    def listar(self, coorte):
        if self.particao:
            raise epoca.ErroTestemunho("ERROR: partição")
        prefixo = f"{epoca.PREFIXO}/{coorte}/"
        return {
            nome: oid
            for nome, (oid, _) in self.tags.items()
            if nome.startswith(prefixo)
        }

    def ler(self, oid):
        for _, (atual, assinado) in self.tags.items():
            if atual == oid:
                return copy.deepcopy(assinado), "a" * 40
        raise epoca.ErroTestemunho("ERROR: tag ausente")

    def verificar_assinatura(self, assinado, revisao=None):
        if self.particao or assinado["bundle"].get("falsa"):
            raise epoca.ErroTestemunho("ERROR: assinatura indisponível")
        return "a" * 40

    def criar(self, nome, assinado, revisao):
        if nome in self.tags:
            raise epoca.ErroTestemunho("ERROR: conflito")
        oid = f"{self.proximo_oid:040x}"
        self.proximo_oid += 1
        self.tags[nome] = (oid, copy.deepcopy(assinado))
        if self.perder_resposta:
            self.perder_resposta = False
            raise epoca.ErroTestemunho("ERROR: resposta perdida")

    def cas_ponteiro(self, coorte, nome, oid):
        self.ponteiro = oid


def registro(epoca_numero, fase, anterior, transicao="troca-1"):
    return {
        "registro": {
            "versao": 1,
            "coorte": "piloto",
            "epoca": epoca_numero,
            "transicao": transicao,
            "estado": fase,
            "anterior": anterior,
            "watermark_sha256": "b" * 64,
            "autoridade_sha256": "c" * 64,
        },
        "bundle": {"prova": "oficial"},
    }


def prova_pg():
    return {
        "coorte": "piloto",
        "epoca": 1,
        "transicao": "troca-1",
        "pausada": True,
        "concessoes_invalidas": True,
        "watermark_sha256": "b" * 64,
        "autoridade_sha256": "c" * 64,
        "hmac_valido": True,
    }


@pytest.fixture
def protocolo():
    fonte = FonteMemoria()
    return (
        epoca.TestemunhoEpoca(
            Path.cwd(), lambda prova: prova.get("hmac_valido") is True, fonte
        ),
        fonte,
    )


def preparar_primeira(protocolo):
    testemunho, _ = protocolo
    vazio = testemunho.consultar("piloto")
    preparada = testemunho.preparar(registro(1, "preparada", None), vazio)
    return preparada


def test_listagem_consulta_api_oficial_e_exige_tags_anotadas(monkeypatch):
    fonte = epoca.FonteGitHub(Path.cwd())
    referencia = epoca.nome_tag("piloto", 1, "preparada")
    resposta = [
        {
            "ref": f"refs/tags/{referencia}",
            "object": {"type": "tag", "sha": "a" * 40},
        }
    ]
    caminhos = []

    def api(caminho):
        caminhos.append(caminho)
        return resposta

    monkeypatch.setattr(fonte, "_api", api)
    assert fonte.listar("piloto") == {referencia: "a" * 40}
    assert caminhos == [
        "repos/abundanciabr/sitesdoreino/git/matching-refs/tags/coordenacao-epoca/piloto/"
    ]
    resposta[0]["object"]["type"] = "commit"
    with pytest.raises(epoca.ErroTestemunho, match="referência remota inválida"):
        fonte.listar("piloto")


def test_preparada_mais_nova_bloqueia_ativa_antiga_e_rewind(protocolo):
    testemunho, fonte = protocolo
    preparada = preparar_primeira(protocolo)
    ativa = testemunho.ativar(
        registro(
            1, "ativa", {"epoca": 1, "registro_sha256": preparada["registro_sha256"]}
        ),
        preparada,
        prova_pg(),
    )
    ponteiro_antigo = fonte.ponteiro
    segunda = testemunho.preparar(
        registro(
            2,
            "preparada",
            {"epoca": 1, "registro_sha256": ativa["registro_sha256"]},
            "troca-2",
        ),
        ativa,
    )
    fonte.ponteiro = ponteiro_antigo
    assert testemunho.consultar("piloto") == segunda
    assert segunda["max_epoca"] == 2
    assert segunda["estado"] == "preparada"
    with pytest.raises(epoca.ErroTestemunho, match="estado remoto mudou"):
        testemunho.preparar(registro(2, "preparada", None, "outra"), ativa)
    with pytest.raises(epoca.ErroTestemunho, match="preparada não sucede"):
        testemunho.preparar(
            registro(
                3,
                "preparada",
                {"epoca": 2, "registro_sha256": segunda["registro_sha256"]},
                "troca-3",
            ),
            segunda,
        )


def test_restauro_antigo_nao_gera_ativa_nem_nova_epoca(protocolo):
    testemunho, _ = protocolo
    preparada = preparar_primeira(protocolo)
    backup_antigo = {
        "max_epoca": 0,
        "estado": "vazia",
        "transicao": None,
        "registro_sha256": None,
        "watermark_sha256": None,
    }
    with pytest.raises(epoca.ErroTestemunho, match="estado remoto mudou"):
        testemunho.preparar(registro(2, "preparada", None), backup_antigo)
    with pytest.raises(epoca.ErroTestemunho, match="prova PG"):
        testemunho.ativar(
            registro(
                1,
                "ativa",
                {"epoca": 1, "registro_sha256": preparada["registro_sha256"]},
            ),
            preparada,
            {**prova_pg(), "epoca": 0},
        )


def test_resposta_perdida_confirma_apenas_mesmo_conteudo(protocolo):
    testemunho, fonte = protocolo
    vazio = testemunho.consultar("piloto")
    primeiro = registro(1, "preparada", None)
    fonte.perder_resposta = True
    preparado = testemunho.preparar(primeiro, vazio)
    assert preparado["registro_sha256"] == epoca.digest(primeiro)
    assert testemunho.preparar(primeiro, vazio) == preparado
    outro = registro(1, "preparada", None, "concorrente")
    with pytest.raises(epoca.ErroTestemunho, match="estado remoto mudou"):
        testemunho.preparar(outro, vazio)


def test_particao_protecao_e_assinatura_fecham(protocolo):
    testemunho, fonte = protocolo
    fonte.particao = True
    with pytest.raises(epoca.ErroTestemunho, match="partição"):
        testemunho.consultar("piloto")
    fonte.particao = False
    fonte.protegida = False
    with pytest.raises(epoca.ErroTestemunho, match="proteção nativa"):
        testemunho.consultar("piloto")
    fonte.protegida = True
    preparar_primeira(protocolo)
    nome = epoca.nome_tag("piloto", 1, "preparada")
    fonte.tags[nome][1]["bundle"]["falsa"] = True
    with pytest.raises(epoca.ErroTestemunho, match="assinatura"):
        testemunho.consultar("piloto")


def test_tag_ausente_e_cadeia_lacunosa_fecham(protocolo):
    testemunho, fonte = protocolo
    preparada = preparar_primeira(protocolo)
    ativa = testemunho.ativar(
        registro(
            1, "ativa", {"epoca": 1, "registro_sha256": preparada["registro_sha256"]}
        ),
        preparada,
        prova_pg(),
    )
    testemunho.preparar(
        registro(
            2,
            "preparada",
            {"epoca": 1, "registro_sha256": ativa["registro_sha256"]},
            "troca-2",
        ),
        ativa,
    )
    fonte.tags.pop(epoca.nome_tag("piloto", 1, "preparada"))
    with pytest.raises(epoca.ErroTestemunho, match="tag preparada ausente"):
        testemunho.consultar("piloto")


def test_ativa_exige_prova_pg_autenticada_e_concessoes_invalidas(protocolo):
    testemunho, _ = protocolo
    preparada = preparar_primeira(protocolo)
    assinada = registro(
        1, "ativa", {"epoca": 1, "registro_sha256": preparada["registro_sha256"]}
    )
    for adulteracao in (
        {"hmac_valido": False},
        {"concessoes_invalidas": False},
        {"watermark_sha256": "d" * 64},
    ):
        with pytest.raises(epoca.ErroTestemunho, match="prova PG"):
            testemunho.ativar(assinada, preparada, {**prova_pg(), **adulteracao})
    assert testemunho.ativar(assinada, preparada, prova_pg())["estado"] == "ativa"


def test_ruleset_exige_tag_update_delete_ativo_sem_bypass(tmp_path, monkeypatch):
    fonte = epoca.FonteGitHub(tmp_path)
    regra = {
        "target": "tag",
        "enforcement": "active",
        "bypass_actors": [],
        "conditions": {
            "ref_name": {
                "include": ["refs/tags/coordenacao-epoca/*/*/*"],
                "exclude": [],
            }
        },
        "rules": [{"type": "update"}, {"type": "deletion"}],
    }
    monkeypatch.setattr(
        fonte,
        "_api",
        lambda caminho: [{"id": 1, "target": "tag"}] if "?" in caminho else regra,
    )
    assert fonte.protecao_ativa("piloto")
    regra["bypass_actors"] = [{"actor_id": 1}]
    assert not fonte.protecao_ativa("piloto")
    regra["bypass_actors"] = []
    regra["rules"].pop()
    assert not fonte.protecao_ativa("piloto")


def test_ruleset_nao_aceita_glob_que_nao_cobre_barras(tmp_path, monkeypatch):
    fonte = epoca.FonteGitHub(tmp_path)
    regra = {
        "target": "tag",
        "enforcement": "active",
        "bypass_actors": [],
        "conditions": {
            "ref_name": {"include": ["refs/tags/coordenacao-epoca/*"], "exclude": []}
        },
        "rules": [{"type": "update"}, {"type": "deletion"}],
    }
    monkeypatch.setattr(
        fonte,
        "_api",
        lambda caminho: [{"id": 1, "target": "tag"}] if "?" in caminho else regra,
    )
    assert not fonte.protecao_ativa("piloto")


def test_origem_dispatch_exige_main_e_run_concluido(tmp_path, monkeypatch):
    fonte = epoca.FonteGitHub(tmp_path)
    assinado = registro(1, "preparada", None)
    revisao = "a" * 40
    run = {
        "status": "completed",
        "conclusion": "success",
        "head_sha": revisao,
        "head_branch": "main",
        "event": "workflow_dispatch",
        "path": ".github/workflows/coordenacao-epoca.yml",
    }
    provas = [
        {
            "verificationResult": {
                "signature": {
                    "certificate": {
                        "sourceRepositoryDigest": revisao,
                        "runInvocationURI": (
                            "https://github.com/abundanciabr/sitesdoreino/actions/runs/11/attempts/1"
                        ),
                        "buildTrigger": "workflow_dispatch",
                    }
                },
                "verifiedTimestamps": [{"type": "Tlog"}],
                "statement": {
                    "subject": [
                        {"digest": {"sha256": epoca.digest(assinado["registro"])}}
                    ]
                },
            }
        }
    ]
    monkeypatch.setattr(fonte, "_executar", lambda comando: json.dumps(provas).encode())
    monkeypatch.setattr(fonte, "_api", lambda caminho: run)
    assert fonte.verificar_assinatura(assinado, revisao) == revisao
    run["status"] = "in_progress"
    with pytest.raises(epoca.ErroTestemunho, match="ainda não concluída"):
        fonte.verificar_assinatura(assinado, revisao)
    run["status"] = "completed"
    run["event"] = "push"
    with pytest.raises(epoca.ErroTestemunho, match="divergente"):
        fonte.verificar_assinatura(assinado, revisao)
    run["event"] = "workflow_dispatch"
    run["path"] += "@main"
    with pytest.raises(epoca.ErroTestemunho, match="divergente"):
        fonte.verificar_assinatura(assinado, revisao)


def resposta_pg(fase, epoca_atual, epoca_numero, nonce="a" * 32):
    return {
        "coorte": "piloto",
        "epoca_atual": epoca_atual,
        "epoca": epoca_numero,
        "transicao": "troca-1",
        "pausada": True,
        "concessoes_invalidas": True,
        "watermark_sha256": "b" * 64,
        "autoridade_sha256": "c" * 64,
        "fase": fase,
        "nonce": nonce,
    }


def test_consulta_pg_preparada_exige_nonce_schema_e_epoca_externa(protocolo):
    testemunho, _ = protocolo
    vazio = testemunho.consultar("piloto")
    resposta = resposta_pg("preparada", 0, 1)
    registro = epoca.registro_da_consulta_pg(
        resposta, vazio, "piloto", "troca-1", "preparada", "a" * 32
    )
    assert registro["epoca"] == 1
    assert registro["anterior"] is None
    for adulterada in (
        {**resposta, "extra": True},
        {"estado": "PASS", "resultado": resposta},
        {**resposta, "nonce": "0" * 32},
        {**resposta, "epoca": 2},
        {**resposta, "pausada": False},
    ):
        with pytest.raises(epoca.ErroTestemunho):
            epoca.registro_da_consulta_pg(
                adulterada, vazio, "piloto", "troca-1", "preparada", "a" * 32
            )


def test_consulta_pg_ativa_preserva_watermark_e_pina_oid(protocolo):
    testemunho, fonte = protocolo
    preparada = preparar_primeira(protocolo)
    with pytest.raises(epoca.ErroTestemunho, match="preparação PG"):
        epoca.registro_da_consulta_pg(
            resposta_pg("preparada", 1, 2),
            preparada,
            "piloto",
            "troca-1",
            "preparada",
            "a" * 32,
        )
    resposta = resposta_pg("ativa", 1, 1)
    registro_pg = epoca.registro_da_consulta_pg(
        resposta, preparada, "piloto", "troca-1", "ativa", "a" * 32
    )
    assert registro_pg["anterior"] == {
        "epoca": 1,
        "registro_sha256": preparada["registro_sha256"],
    }
    with pytest.raises(epoca.ErroTestemunho, match="ativação PG"):
        epoca.registro_da_consulta_pg(
            resposta_pg("ativa", 0, 1),
            preparada,
            "piloto",
            "troca-1",
            "ativa",
            "a" * 32,
        )
    resposta["watermark_sha256"] = "d" * 64
    with pytest.raises(epoca.ErroTestemunho, match="ativação PG"):
        epoca.registro_da_consulta_pg(
            resposta, preparada, "piloto", "troca-1", "ativa", "a" * 32
        )
    preparada_oid = fonte.tags[epoca.nome_tag("piloto", 1, "preparada")][0]
    assert testemunho.referencia_confirmada("piloto", preparada) == preparada_oid
    assinada = registro(
        1, "ativa", {"epoca": 1, "registro_sha256": preparada["registro_sha256"]}
    )
    ativa = testemunho.ativar(assinada, preparada, prova_pg())
    nome = epoca.nome_tag("piloto", 1, "ativa")
    assert testemunho.referencia_confirmada("piloto", ativa) == fonte.tags[nome][0]
    with pytest.raises(epoca.ErroTestemunho, match="aprovada"):
        testemunho.referencia_confirmada("piloto", preparada)


def test_preparar_consulta_escreve_script_fixo_e_nonce(tmp_path, monkeypatch):
    saida = tmp_path / "github-output"
    for chave, valor in {
        "COORTE": "piloto",
        "TRANSICAO": "troca-1",
        "FASE": "preparada",
        "RUNNER_TEMP": str(tmp_path),
        "GITHUB_OUTPUT": str(saida),
    }.items():
        monkeypatch.setenv(chave, valor)
    assert epoca.main(["preparar-consulta"]) == 0
    linhas = dict(linha.split("=", 1) for linha in saida.read_text().splitlines())
    assert len(linhas["nonce"]) == 32
    assert epoca.re.fullmatch("[0-9a-f]{32}", linhas["nonce"])
    script = Path(linhas["script"]).read_text()
    assert "/opt/plataforma/infra/trava-de-publicacao.sh" in script
    assert "/opt/plataforma/infra/consultar-transicao-coordenacao-na-vps.sh" in script
    assert "piloto" not in script
    monkeypatch.setenv("COORTE", "piloto;echo PWN")
    assert epoca.main(["preparar-consulta"]) == 2


def test_workflow_main_assina_artefato_sem_poder_de_criar_tag():
    import yaml

    caminho = (
        Path(__file__).resolve().parents[2] / ".github/workflows/coordenacao-epoca.yml"
    )
    workflow = yaml.safe_load(caminho.read_text(encoding="utf-8-sig"))
    disparo = workflow.get("on", workflow.get(True))
    assert set(disparo) == {"workflow_dispatch"}
    assert set(disparo["workflow_dispatch"]["inputs"]) == {
        "coorte",
        "transicao",
        "fase",
    }
    assert workflow["permissions"]["contents"] == "read"
    assert workflow["permissions"]["id-token"] == "write"
    passos = workflow["jobs"]["assinar"]["steps"]
    assert "github.ref != 'refs/heads/main'" in passos[0]["if"]
    remoto = next(p for p in passos if p.get("id") == "remoto")
    assert remoto["with"]["fingerprint"].startswith("SHA256:")
    assert remoto["with"]["script_path"] == "${{ steps.preparar.outputs.script }}"
    assert remoto["with"]["envs"] == "COORTE,TRANSICAO,FASE,NONCE"
    assert any("actions/attest@" in p.get("uses", "") for p in passos)
    assert any("actions/upload-artifact@" in p.get("uses", "") for p in passos)
    assert "contents: write" not in caminho.read_text(encoding="utf-8-sig")


def test_construir_registro_no_job_recusa_stdout_extra(tmp_path, monkeypatch):
    vazio = {
        "max_epoca": 0,
        "estado": "vazia",
        "transicao": None,
        "registro_sha256": None,
        "watermark_sha256": None,
    }
    monkeypatch.setattr(epoca.TestemunhoEpoca, "consultar", lambda self, coorte: vazio)
    ambiente = {
        "COORTE": "piloto",
        "TRANSICAO": "troca-1",
        "FASE": "preparada",
        "NONCE": "a" * 32,
        "RUNNER_TEMP": str(tmp_path),
        "SAIDA_PG": json.dumps(resposta_pg("preparada", 0, 1)),
    }
    for chave, valor in ambiente.items():
        monkeypatch.setenv(chave, valor)
    assert epoca.main(["construir-registro"]) == 0
    registro_lido = json.loads((tmp_path / "registro.json").read_bytes())
    assert registro_lido["epoca"] == 1
    assert (tmp_path / "registro.json").read_bytes() == epoca.canonico(registro_lido)
    monkeypatch.setenv("SAIDA_PG", ambiente["SAIDA_PG"] + "\nlog inesperado")
    assert epoca.main(["construir-registro"]) == 2
