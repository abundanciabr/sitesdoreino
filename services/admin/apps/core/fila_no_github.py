"""Um pedido por TAR, recuperado do GitHub antes de qualquer continuação.

O evento entra no ramo em um único avanço de referência, sem force. Duas
requisições podem preparar commits, mas só uma avança; a outra lê o vencedor.
Um ramo, um evento e um PR são provas diferentes. Nenhuma delas prova que o
snapshot servido pelo admin já aplicou o cancelamento.
"""

from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from .clients import http

REPOSITORIO = "abundanciabr/sitesdoreino"
VARIAVEL_DO_TOKEN = "GITHUB_TOKEN_FILA"
API = "https://api.github.com"
RAMO_BASE = "main"
TIMEOUT = 10.0
QUEM = "mantenedor-pela-tela-dos-robos"
SEM_TOKEN = "sem_token"
_ID = re.compile(r"TAR-[0-9]{3,12}")
_SHA = re.compile(r"[0-9a-f]{40}")


@dataclass(frozen=True)
class PedidoCancelamento:
    estado: str
    detalhe: str = ""
    numero: int | None = None
    arquivo: str = ""
    conteudo: bytes = b""
    motivo: str = ""


def token() -> str:
    return (os.environ.get(VARIAVEL_DO_TOKEN) or "").strip()


def esta_ligado() -> bool:
    return bool(token())


def montar_evento(tarefa: str, motivo: str, agora: datetime) -> tuple[str, dict]:
    arquivo = f"{agora.strftime('%Y%m%d-%H%M%S')}-{tarefa}-cancelada"
    return arquivo, {
        "arquivo": arquivo,
        "tarefa": tarefa,
        "evento": "cancelada",
        "quando": agora.isoformat(timespec="seconds"),
        "quem": QUEM,
        "detalhe": motivo,
    }


class _Conflito(ValueError):
    pass


class _SemConfirmacao(Exception):
    pass


def _sha(valor):
    if not isinstance(valor, str) or not _SHA.fullmatch(valor):
        raise _Conflito("O GitHub respondeu com uma revisão inválida.")
    return valor


class _Cancelamento:
    """Confere o protocolo de uma TAR sem aceitar URLs de respostas externas."""

    def __init__(self, tarefa, motivo, senha):
        self.tarefa = tarefa
        self.motivo = motivo
        self.ramo = f"agent/fila/cancelar-{tarefa}"
        self.cliente = http()
        self.headers = {
            "Authorization": f"Bearer {senha}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        self.prova = PedidoCancelamento("incerto")
        self.main = self.head = ""

    def chamar(self, metodo, caminho, *, aceita=(200,), **kwargs):
        resposta = self.cliente.request(
            metodo,
            f"{API}/repos/{REPOSITORIO}{caminho}",
            headers=self.headers,
            timeout=TIMEOUT,
            **kwargs,
        )
        if resposta.status_code not in aceita:
            raise _SemConfirmacao(
                f"O GitHub recusou a etapa (código {resposta.status_code})."
            )
        if resposta.status_code in (404, 409, 422):
            return None
        if 'rel="next"' in resposta.headers.get("link", ""):
            raise _Conflito(
                "A consulta trouxe mais de uma página e não confirma um pedido único."
            )
        return resposta.json()

    def evento(self, files, sha):
        if not isinstance(files, list) or len(files) != 1:
            raise _Conflito("O ramo não contém somente o evento esperado desta tarefa.")
        arquivo = files[0]
        path = arquivo["filename"]
        padrao = rf"fila/eventos/[0-9]{{8}}-[0-9]{{6}}-{self.tarefa}-cancelada\.json"
        if (
            arquivo.get("status") != "added"
            or not isinstance(path, str)
            or not re.fullmatch(padrao, path)
        ):
            raise _Conflito("O conteúdo do ramo diverge do pedido de cancelamento.")
        dado = self.chamar("GET", f"/contents/{path}", params={"ref": _sha(sha)})
        if (
            dado.get("type") != "file"
            or dado.get("path") != path
            or dado.get("encoding") != "base64"
        ):
            raise _Conflito("O GitHub não confirmou o arquivo esperado.")
        conteudo = base64.b64decode("".join(dado["content"].split()), validate=True)
        if len(conteudo) > 10000:
            raise _Conflito(
                "O evento recebido excede o tamanho de um pedido desta tela."
            )
        evento = json.loads(conteudo)
        if not isinstance(evento, dict) or set(evento) != {
            "arquivo",
            "tarefa",
            "evento",
            "quando",
            "quem",
            "detalhe",
        }:
            raise _Conflito("O evento recebido tem um formato diferente do esperado.")
        quando = datetime.fromisoformat(evento["quando"])
        motivo = evento["detalhe"]
        if (
            quando.tzinfo is None
            or evento["tarefa"] != self.tarefa
            or evento["evento"] != "cancelada"
            or evento["quem"] != QUEM
            or not isinstance(motivo, str)
            or not motivo.strip()
            or len(motivo) > 500
            or path
            != "fila/eventos/" + montar_evento(self.tarefa, motivo, quando)[0] + ".json"
            or evento["arquivo"] + ".json" != path.rsplit("/", 1)[1]
        ):
            raise _Conflito(
                "A origem, a data ou o conteúdo do evento diverge desta tarefa."
            )
        self.prova = PedidoCancelamento(
            "recebido", arquivo=path, conteudo=conteudo, motivo=motivo
        )
        if self.motivo is not None and motivo != self.motivo:
            raise _Conflito(
                "Já existe um motivo diferente gravado. Consulte o pedido original e peça a continuação a um robô."
            )
        return self.prova

    def conferir_pr(self, numero):
        if type(numero) is not int or numero <= 0:
            raise _Conflito("O GitHub não confirmou um número válido de pedido.")
        pr = self.chamar("GET", f"/pulls/{numero}")
        if (
            pr.get("number") != numero
            or type(pr.get("number")) is not int
            or pr.get("html_url") != f"https://github.com/{REPOSITORIO}/pull/{numero}"
            or pr["head"]["ref"] != self.ramo
            or pr["base"]["ref"] != RAMO_BASE
            or pr["head"]["repo"]["full_name"] != REPOSITORIO
            or pr["base"]["repo"]["full_name"] != REPOSITORIO
            or pr.get("state") not in ("open", "closed")
            or type(pr.get("merged")) is not bool
        ):
            raise _Conflito("A identidade ou a origem do pedido diverge desta tarefa.")
        files = self.chamar("GET", f"/pulls/{numero}/files", params={"per_page": 100})
        evento = self.evento(files, pr["head"]["sha"])
        if pr["state"] == "closed" and not pr["merged"]:
            raise _Conflito(
                "O pedido foi fechado sem integração. Peça a um robô para conferir e continuar este mesmo pedido."
            )
        if pr["state"] == "open" and pr["merged"]:
            raise _Conflito(
                "O GitHub respondeu com estados incompatíveis para o pedido."
            )
        self.prova = PedidoCancelamento(
            "integrado" if pr["merged"] else "revisao",
            numero=numero,
            arquivo=evento.arquivo,
            conteudo=evento.conteudo,
            motivo=evento.motivo,
        )
        return self.prova

    def conferir(self):
        prs = self.chamar(
            "GET",
            "/pulls",
            params={
                "state": "all",
                "head": f"{REPOSITORIO.split('/')[0]}:{self.ramo}",
                "base": RAMO_BASE,
                "per_page": 100,
            },
        )
        if not isinstance(prs, list) or len(prs) > 1:
            raise _Conflito(
                "A consulta não confirmou um único pedido para esta tarefa."
            )
        if prs:
            candidato = prs[0]
            if (
                candidato["head"]["ref"] != self.ramo
                or candidato["head"]["repo"]["full_name"] != REPOSITORIO
                or candidato["base"]["ref"] != RAMO_BASE
                or candidato["base"]["repo"]["full_name"] != REPOSITORIO
                or _numero_e_url_do_pr(candidato) is False
            ):
                raise _Conflito("A consulta devolveu um pedido de outra origem.")
            return self.conferir_pr(candidato["number"])
        base = self.chamar("GET", f"/git/ref/heads/{RAMO_BASE}")
        if (
            base.get("ref") != f"refs/heads/{RAMO_BASE}"
            or base["object"].get("type") != "commit"
        ):
            raise _Conflito("O GitHub não confirmou a origem principal do pedido.")
        self.main = _sha(base["object"]["sha"])
        ref = self.chamar("GET", f"/git/ref/heads/{self.ramo}", aceita=(200, 404))
        if ref is None:
            self.head = ""
            return PedidoCancelamento("sem_pedido")
        if (
            ref.get("ref") != f"refs/heads/{self.ramo}"
            or ref["object"].get("type") != "commit"
        ):
            raise _Conflito("A referência recebida não pertence ao ramo desta tarefa.")
        self.head = _sha(ref["object"]["sha"])
        comparacao = self.chamar("GET", f"/compare/{self.main}...{self.head}")
        commits = comparacao["total_commits"]
        if type(commits) is not int:
            raise _Conflito("O GitHub não confirmou o histórico do ramo.")
        if (
            commits == 0
            and comparacao["status"] in ("identical", "behind")
            and comparacao["files"] == []
            and comparacao["merge_base_commit"]["sha"] == self.head
        ):
            return PedidoCancelamento(
                "sem_pedido",
                "Existe um ramo sem evento. Repetir o pedido pode completar a etapa faltante.",
            )
        if commits != 1 or comparacao["status"] not in ("ahead", "diverged"):
            raise _Conflito(
                "O ramo contém um histórico diferente do pedido desta tela."
            )
        return self.evento(comparacao["files"], self.head)

    def gravar_evento(self, motivo, agora):
        origem = self.head or self.main
        commit = self.chamar("GET", f"/git/commits/{origem}")
        nome, evento = montar_evento(self.tarefa, motivo, agora)
        arvore = self.chamar(
            "POST",
            "/git/trees",
            aceita=(201,),
            json={
                "base_tree": _sha(commit["tree"]["sha"]),
                "tree": [
                    {
                        "path": f"fila/eventos/{nome}.json",
                        "mode": "100644",
                        "type": "blob",
                        "content": json.dumps(evento, ensure_ascii=False, indent=2)
                        + "\n",
                    }
                ],
            },
        )
        novo = self.chamar(
            "POST",
            "/git/commits",
            aceita=(201,),
            json={
                "message": f"fila: pedido de cancelamento da {self.tarefa}",
                "tree": _sha(arvore["sha"]),
                "parents": [origem],
            },
        )
        sha = _sha(novo["sha"])
        if self.head:
            self.chamar(
                "PATCH",
                f"/git/refs/heads/{self.ramo}",
                aceita=(200, 409, 422),
                json={"sha": sha, "force": False},
            )
        else:
            self.chamar(
                "POST",
                "/git/refs",
                aceita=(201, 409, 422),
                json={"ref": f"refs/heads/{self.ramo}", "sha": sha},
            )


def _numero_e_url_do_pr(pr):
    numero = pr.get("number")
    return (
        type(numero) is int
        and numero > 0
        and pr.get("html_url") == f"https://github.com/{REPOSITORIO}/pull/{numero}"
    )


def _operar(tarefa, titulo="", motivo=None, agora=None, *, escrever=False):
    if not isinstance(tarefa, str) or not _ID.fullmatch(tarefa):
        return PedidoCancelamento(
            "conflito", "A tarefa não tem um identificador válido. Recarregue a fila."
        )
    if escrever and (
        not isinstance(motivo, str) or not motivo.strip() or len(motivo) > 500
    ):
        return PedidoCancelamento(
            "conflito", "Escreva um motivo de até 500 caracteres e tente de novo."
        )
    senha = token()
    if not senha:
        return PedidoCancelamento(SEM_TOKEN)
    pedido = _Cancelamento(tarefa, motivo, senha)
    try:
        atual = pedido.conferir()
        if not escrever or atual.estado in ("revisao", "integrado"):
            return atual
        if atual.estado == "sem_pedido":
            instante = agora or datetime.now(timezone.utc)
            if not isinstance(instante, datetime) or instante.tzinfo is None:
                raise _Conflito("A data do pedido não informa o fuso horário.")
            pedido.gravar_evento(motivo, instante)
            atual = pedido.conferir()
            if atual.estado in ("revisao", "integrado"):
                return atual
            if atual.estado != "recebido":
                raise _SemConfirmacao("Não recebi confirmação do evento no ramo.")
        resposta = pedido.chamar(
            "POST",
            "/pulls",
            aceita=(201, 409, 422),
            json={
                "title": f"fila: pedido de cancelamento da {tarefa}",
                "head": pedido.ramo,
                "base": RAMO_BASE,
                "body": f"Pedido do mantenedor pela tela dos robôs.\n\nTarefa: **{tarefa}**, {titulo}.\n\nMotivo gravado no evento:\n\n{atual.motivo}\n\nEste PR contém somente o evento da fila. A integração e a aplicação ainda precisam ser conferidas.",
            },
        )
        if resposta is not None:
            return pedido.conferir_pr(resposta["number"])
        atual = pedido.conferir()
        if atual.estado not in ("revisao", "integrado"):
            raise _SemConfirmacao(
                "O evento foi recebido, mas não recebi confirmação do PR."
            )
        return atual
    except (httpx.HTTPError, _SemConfirmacao) as erro:
        explicacao = (
            str(erro)
            if isinstance(erro, _SemConfirmacao)
            else f"A comunicação foi interrompida ({type(erro).__name__})."
        )
        prova = pedido.prova
        return PedidoCancelamento(
            "recebido" if prova.arquivo else "incerto",
            explicacao
            + " Não foi possível confirmar todas as etapas. Consulte ou repita o mesmo pedido para continuar.",
            numero=prova.numero,
            arquivo=prova.arquivo,
            conteudo=prova.conteudo,
            motivo=prova.motivo,
        )
    except (ValueError, TypeError, KeyError, AttributeError) as erro:
        explicacao = (
            str(erro)
            if isinstance(erro, _Conflito)
            else "O GitHub respondeu com dados incompatíveis com este pedido. Peça a um robô para conferir a continuação."
        )
        return PedidoCancelamento(
            "conflito",
            explicacao,
            arquivo=pedido.prova.arquivo,
            conteudo=pedido.prova.conteudo,
            motivo=pedido.prova.motivo,
        )


def consultar_pedido_de_cancelamento(tarefa: str) -> PedidoCancelamento:
    return _operar(tarefa)


def abrir_pr_de_cancelamento(
    tarefa: str, titulo: str, motivo: str, agora: datetime | None = None
) -> PedidoCancelamento:
    return _operar(tarefa, titulo, motivo, agora, escrever=True)
