"""GitHub controlado persiste os efeitos antes de simular respostas perdidas."""

import base64
import hashlib
import json
from datetime import datetime, timezone

import httpx
import pytest

from apps.core import fila_no_github as fila

MAIN = "0123456789abcdef0123456789abcdef01234567"
RAMO = "agent/fila/cancelar-TAR-102"
MOTIVO = "Pedido repetido, conservar esta frase."
AGORA = datetime(2026, 9, 9, 12, 30, tzinfo=timezone.utc)


class GitHubControlado:
    def __init__(self):
        self.ramo = None
        self.arquivos = {}
        self.arvores = {MAIN: {}}
        self.commits = {MAIN: {"tree": {"sha": MAIN}, "parents": []}}
        self.prs = []
        self.chamadas = []
        self.falhar = None
        self.resposta_perdida = False
        self.corrida = None
        self.falhar_na_chamada = None

    def pedido(self, numero=1270, estado="open", merged=False):
        return {
            "number": numero,
            "state": estado,
            "merged": merged,
            "html_url": f"https://github.com/{fila.REPOSITORIO}/pull/{numero}",
            "head": {
                "ref": RAMO,
                "sha": self.ramo,
                "repo": {"full_name": fila.REPOSITORIO},
            },
            "base": {
                "ref": "main",
                "sha": MAIN,
                "repo": {"full_name": fila.REPOSITORIO},
            },
        }

    def cliente(self):
        return httpx.Client(transport=httpx.MockTransport(self.responder))

    def responder(self, req):
        assert req.url.host == "api.github.com", "credencial enviada a outra origem"
        path = req.url.path.removeprefix(f"/repos/{fila.REPOSITORIO}")
        chave = (req.method, path)
        self.chamadas.append((chave, req))
        falha = self.falhar == chave or self.falhar_na_chamada == len(self.chamadas) - 1
        if falha:
            self.falhar_na_chamada = None
        if falha and not self.resposta_perdida:
            self.falhar = None
            raise httpx.ReadTimeout("rede fictícia interrompida", request=req)
        code, data = self.executar(req, path)
        if falha:
            self.falhar = None
            raise httpx.ReadTimeout("resposta perdida depois de persistir", request=req)
        return httpx.Response(code, json=data)

    def executar(self, req, path):
        data = json.loads(req.content) if req.content else {}
        if req.method == "GET" and path.startswith("/git/ref/heads/"):
            ref = path.removeprefix("/git/ref/heads/")
            sha = MAIN if ref == "main" else self.ramo
            return (
                (
                    200,
                    {
                        "ref": "refs/heads/" + ref,
                        "object": {"type": "commit", "sha": sha},
                    },
                )
                if sha
                else (404, {})
            )
        if req.method == "GET" and path == "/pulls":
            return 200, self.prs
        if req.method == "GET" and path.startswith("/pulls/"):
            bits = path.split("/")
            pr = next(p for p in self.prs if str(p["number"]) == bits[2])
            if len(bits) == 4:
                return 200, self.mudancas(pr["head"]["sha"])
            return 200, pr
        if req.method == "GET" and path.startswith("/compare/"):
            head = path.split("...")[1]
            files = self.mudancas(head)
            return 200, {
                "status": "ahead" if files else "identical",
                "total_commits": 1 if files else 0,
                "merge_base_commit": {"sha": MAIN},
                "files": files,
            }
        if req.method == "GET" and path.startswith("/contents/"):
            filename = path.removeprefix("/contents/")
            sha = req.url.params["ref"]
            content = self.arvores[self.commits[sha]["tree"]["sha"]][filename]
            return 200, {
                "type": "file",
                "path": filename,
                "encoding": "base64",
                "content": base64.b64encode(content).decode(),
            }
        if req.method == "GET" and path.startswith("/git/commits/"):
            return 200, self.commits[path.rsplit("/", 1)[1]]
        if req.method == "POST" and path == "/git/trees":
            tree = dict(self.arvores[data["base_tree"]])
            for entry in data["tree"]:
                tree[entry["path"]] = entry["content"].encode()
            sha = hashlib.sha1(repr(tree).encode()).hexdigest()
            self.arvores[sha] = tree
            return 201, {"sha": sha}
        if req.method == "POST" and path == "/git/commits":
            sha = hashlib.sha1(json.dumps(data, sort_keys=True).encode()).hexdigest()
            self.commits[sha] = {
                "tree": {"sha": data["tree"]},
                "parents": [{"sha": p} for p in data["parents"]],
            }
            return 201, {"sha": sha}
        if req.method in ("POST", "PATCH") and path.startswith("/git/refs"):
            if self.corrida:
                callback, self.corrida = self.corrida, None
                callback()
            if req.method == "POST":
                if self.ramo:
                    return 422, {}
                assert data["ref"] == "refs/heads/" + RAMO
            else:
                if not data["force"] and self.commits[data["sha"]]["parents"] != [
                    {"sha": self.ramo}
                ]:
                    return 422, {}
            self.ramo = data["sha"]
            self.arquivos = self.arvores[self.commits[self.ramo]["tree"]["sha"]]
            return 201 if req.method == "POST" else 200, {}
        if req.method == "POST" and path == "/pulls":
            if self.prs:
                return 422, {}
            self.prs.append(self.pedido())
            return 201, self.prs[0]
        raise AssertionError((req.method, path, data))

    def mudancas(self, sha):
        return [
            {"filename": path, "status": "added"}
            for path in self.arvores[self.commits[sha]["tree"]["sha"]]
        ]


@pytest.fixture
def github(monkeypatch):
    remoto = GitHubControlado()
    monkeypatch.setenv(fila.VARIAVEL_DO_TOKEN, "token-ficticio-sem-valor")
    monkeypatch.setattr(fila, "http", remoto.cliente)
    return remoto


def enviar(motivo=MOTIVO, agora=AGORA):
    return fila.abrir_pr_de_cancelamento(
        "TAR-102", "Tarefa fictícia", motivo, agora=agora
    )


def test_ramo_vazio_de_tentativa_antiga_e_retomado(github):
    github.ramo = MAIN
    resultado = enviar()
    assert resultado.estado == "revisao"
    assert len(github.prs) == len(github.arquivos) == 1
    assert json.loads(next(iter(github.arquivos.values())))["detalhe"] == MOTIVO


@pytest.mark.parametrize("etapa", ["/git/trees", "/git/commits", "/git/refs", "/pulls"])
@pytest.mark.parametrize("persistiu", [False, True])
def test_repetir_depois_de_timeout_completa_so_o_que_falta(github, etapa, persistiu):
    github.falhar = ("POST", etapa)
    github.resposta_perdida = persistiu
    primeiro = enviar()
    assert primeiro.estado in {"incerto", "recebido"}
    antes = dict(github.arquivos)
    segundo = enviar(agora=datetime(2026, 9, 10, tzinfo=timezone.utc))
    assert segundo.estado == "revisao"
    assert len(github.prs) == len(github.arquivos) == 1
    if antes:
        assert github.arquivos == antes
    terceiro = enviar()
    assert terceiro.estado == "revisao"
    assert len(github.prs) == len(github.arquivos) == 1


def test_consulta_posterior_reconstroi_evento_e_pr_sem_escrever(github):
    enviar()
    antes = len(github.chamadas)
    resultado = fila.consultar_pedido_de_cancelamento("TAR-102")
    assert resultado.estado == "revisao"
    assert resultado.numero == 1270
    assert resultado.motivo == MOTIVO
    assert all(chave[0] == "GET" for chave, _ in github.chamadas[antes:])


def test_motivo_diferente_nao_sobrescreve_tentativa_gravada(github):
    enviar()
    antes = dict(github.arquivos)
    assert enviar("Outra decisão").estado == "conflito"
    assert github.arquivos == antes
    assert len(github.prs) == 1


def test_pr_fechado_sem_merge_nao_abre_duplicado(github):
    enviar()
    github.prs[0]["state"] = "closed"
    assert enviar().estado == "conflito"
    assert len(github.prs) == 1


def test_pr_integrado_nao_e_aplicacao_comprovada(github):
    enviar()
    github.prs[0].update(state="closed", merged=True)
    assert enviar().estado == "integrado"


@pytest.mark.parametrize("numero", [True, 0, -1, "1270", "1270/../evil"])
def test_numero_externo_invalido_nao_vira_confirmacao(github, numero):
    enviar()
    github.prs[0]["number"] = numero
    github.prs[0]["html_url"] = f"https://github.com/{fila.REPOSITORIO}/pull/{numero}"
    assert enviar().estado == "conflito"


@pytest.mark.parametrize("campo", ["html_url", "head", "base"])
def test_origem_divergente_nao_e_pedido_desta_tar(github, campo):
    enviar()
    if campo == "html_url":
        github.prs[0][campo] = "https://evil.example/pull/1270"
    else:
        github.prs[0][campo]["repo"]["full_name"] = "outra/origem"
    assert enviar().estado == "conflito"


@pytest.mark.parametrize("ramo_antigo", [False, True])
def test_corrida_no_ramo_preserva_o_evento_vencedor(github, ramo_antigo):
    if ramo_antigo:
        github.ramo = MAIN
    github.corrida = lambda: enviar(agora=datetime(2026, 9, 10, tzinfo=timezone.utc))
    assert enviar().estado == "revisao"
    assert len(github.prs) == len(github.arquivos) == 1
    assert json.loads(next(iter(github.arquivos.values())))["quando"].startswith(
        "2026-09-10"
    )


@pytest.mark.parametrize("indice", [0, 1, 2, 3, 7, 8, 9, 10, 11, 13, 14, 15])
def test_timeout_em_cada_leitura_pode_ser_retomado(github, indice):
    github.falhar_na_chamada = indice
    primeiro = enviar()
    assert primeiro.estado in {"incerto", "recebido"}
    antes = dict(github.arquivos)
    assert enviar().estado == "revisao"
    assert len(github.prs) == len(github.arquivos) == 1
    if antes:
        assert github.arquivos == antes


@pytest.mark.parametrize("persistiu", [False, True])
def test_avanco_de_ramo_antigo_interrompido_e_retomado(github, persistiu):
    github.ramo = MAIN
    github.falhar = ("PATCH", "/git/refs/heads/" + RAMO)
    github.resposta_perdida = persistiu
    assert enviar().estado == "incerto"
    antes = dict(github.arquivos)
    assert enviar().estado == "revisao"
    if antes:
        assert github.arquivos == antes
    assert len(github.prs) == len(github.arquivos) == 1


@pytest.mark.parametrize(
    "mudanca",
    [
        "arquivo",
        "tipo",
        "quem",
        "tarefa",
        "quando",
        "vazio",
        "comprido",
        "segundo_arquivo",
    ],
)
def test_evento_divergente_e_preservado_sem_abrir_pr(github, mudanca):
    github.falhar = ("POST", "/pulls")
    enviar()
    path, conteudo = next(iter(github.arquivos.items()))
    evento = json.loads(conteudo)
    if mudanca == "arquivo":
        evento["arquivo"] = "outro"
    elif mudanca == "tipo":
        evento["evento"] = "concluida"
    elif mudanca == "quem":
        evento["quem"] = "outra-origem"
    elif mudanca == "tarefa":
        evento["tarefa"] = "TAR-999"
    elif mudanca == "quando":
        evento["quando"] = "2026-09-10T00:00:00"
    elif mudanca == "vazio":
        evento["detalhe"] = " "
    elif mudanca == "comprido":
        evento["detalhe"] = "x" * 501
    else:
        github.arquivos["services/admin/outro.py"] = b"mudanca alheia"
    github.arquivos[path] = json.dumps(evento).encode()
    antes = dict(github.arquivos)
    assert enviar().estado == "conflito"
    assert github.arquivos == antes and not github.prs


@pytest.mark.parametrize(
    "tarefa", ["TAR-102\n", "TAR-١٠٢", "TAR-102/evil", "TAR-" + "9" * 13, None]
)
def test_id_invalido_nao_chega_ao_transporte(github, tarefa):
    resultado = fila.abrir_pr_de_cancelamento(tarefa, "fictícia", MOTIVO)
    assert resultado.estado == "conflito"
    assert not github.chamadas


def test_pagina_incompleta_nao_confirma_pedido_nem_continua(github, monkeypatch):
    responder = github.responder

    def com_proxima_pagina(request):
        resposta = responder(request)
        resposta.headers["Link"] = (
            '<https://api.github.com/repos/abundanciabr/sitesdoreino/pulls?page=2>; rel="next"'
        )
        return resposta

    monkeypatch.setattr(github, "responder", com_proxima_pagina)
    resultado = enviar()
    assert resultado.estado == "conflito"
    assert "mais de uma página" in resultado.detalhe
    assert [chave[0] for chave, _ in github.chamadas] == ["GET"]
    assert github.ramo is None and not github.prs and not github.arquivos


def test_encoding_incompativel_recusa_antes_de_continuar(github, monkeypatch):
    github.falhar = ("POST", "/pulls")
    assert enviar().estado == "recebido"
    antes = dict(github.arquivos)
    chamadas_antes = len(github.chamadas)
    responder = github.responder

    def encoding_divergente(request):
        resposta = responder(request)
        if "/contents/" in request.url.path:
            dado = resposta.json()
            dado["encoding"] = "none"
            return httpx.Response(200, json=dado)
        return resposta

    monkeypatch.setattr(github, "responder", encoding_divergente)
    resultado = enviar()
    assert resultado.estado == "conflito"
    assert "arquivo esperado" in resultado.detalhe
    assert all(chave[0] == "GET" for chave, _ in github.chamadas[chamadas_antes:])
    assert github.arquivos == antes and not github.prs


def test_ref_de_outro_ramo_com_sha_valido_recusa_sem_escrever(github, monkeypatch):
    github.ramo = MAIN
    responder = github.responder

    def ref_divergente(request):
        resposta = responder(request)
        if request.url.path.endswith("/git/ref/heads/" + RAMO):
            dado = resposta.json()
            dado["ref"] = "refs/heads/outro-ramo"
            return httpx.Response(200, json=dado)
        return resposta

    monkeypatch.setattr(github, "responder", ref_divergente)
    resultado = enviar()
    assert resultado.estado == "conflito"
    assert "não pertence ao ramo" in resultado.detalhe
    assert all(chave[0] == "GET" for chave, _ in github.chamadas)
    assert github.ramo == MAIN and not github.prs and not github.arquivos
