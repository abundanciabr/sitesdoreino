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


@dataclass(frozen=True)
class ReciboReuniao:
    estado: str
    detalhe: str
    tarefa: str = ""
    ramo: str = ""
    revisao: str = ""
    pr: int | None = None
    artefatos: tuple = ()
    inicio: str = ""


class _RecebimentoReuniao:
    """Leitura limitada de uma reserva e de dois artefatos no mesmo commit."""

    def __init__(self, envelope):
        import hashlib
        from time import monotonic

        self.envelope = envelope
        self.chave = hashlib.sha256(
            ("pedido:" + envelope["pedido"]["id"]).encode("utf-8")
        ).hexdigest()
        self.fim = monotonic() + TIMEOUT
        self.chamadas = 0
        self.tarefa = self.ramo = ""

    def get(self, caminho, *, params=None, ausente=False):
        from time import monotonic

        restante = self.fim - monotonic()
        self.chamadas += 1
        if restante <= 0 or self.chamadas > 32:
            raise _SemConfirmacao(
                "A consulta atingiu o limite. Tente conferir novamente."
            )
        with http().stream(
            "GET",
            f"{API}/repos/{REPOSITORIO}{caminho}",
            headers={
                "Authorization": f"Bearer {token()}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            params=params,
            timeout=restante,
            follow_redirects=False,
        ) as resposta:
            if ausente and resposta.status_code == 404:
                return None
            if resposta.status_code != 200:
                raise _SemConfirmacao(
                    f"O GitHub não confirmou a consulta (código {resposta.status_code}). Tente novamente."
                )
            if 'rel="next"' in resposta.headers.get("link", ""):
                raise _SemConfirmacao(
                    "A resposta ultrapassou uma página. Peça ao robô para conferir a mesma tarefa."
                )
            bruto = bytearray()
            for parte in resposta.iter_bytes():
                bruto.extend(parte)
                if len(bruto) > 2000000 or monotonic() > self.fim:
                    raise _SemConfirmacao(
                        "A resposta excedeu o limite de leitura. Tente conferir novamente."
                    )
            return json.loads(bruto.decode("utf-8"))

    def ref(self, nome, ausente=False):
        from urllib.parse import quote

        dado = self.get("/git/ref/" + quote(nome, safe="/"), ausente=ausente)
        if dado is None:
            return None
        if dado.get("ref") != "refs/" + nome or dado["object"].get("type") != "commit":
            raise _Conflito(
                "A referência não confirma a origem pedida. Confira a tarefa com o robô."
            )
        return _sha(dado["object"]["sha"])

    def arvore(self, sha):
        dado = self.get("/git/trees/" + _sha(sha))
        if dado.get("truncated") is not False or not isinstance(dado.get("tree"), list):
            raise _SemConfirmacao(
                "A árvore está incompleta. Não consegui confirmar o recebimento; tente novamente."
            )
        entradas = dado["tree"]
        nomes = [item["path"] for item in entradas]
        if len(set(nomes)) != len(nomes) or any(
            not isinstance(n, str) or "/" in n or n in (".", "..") for n in nomes
        ):
            raise _Conflito(
                "A árvore trouxe caminhos ambíguos. Confira o ramo original."
            )
        return entradas

    def subarvore(self, entradas, nome):
        item = next((e for e in entradas if e["path"] == nome), None)
        if not item or item.get("type") != "tree" or item.get("mode") != "040000":
            raise _SemConfirmacao(
                "Os artefatos da fila ainda não foram confirmados. Tente novamente após o envio do robô."
            )
        return self.arvore(item["sha"])

    def blob(self, item):
        if item.get("type") != "blob" or item.get("mode") != "100644":
            raise _Conflito(
                "O artefato não é um arquivo de dados regular. Confira o ramo original."
            )
        dado = self.get("/git/blobs/" + _sha(item["sha"]))
        if dado.get("encoding") != "base64" or dado.get("sha") != item["sha"]:
            raise _Conflito(
                "O arquivo não confirma os bytes solicitados. Confira o ramo original."
            )
        conteudo = base64.b64decode("".join(dado["content"].split()), validate=True)
        conteudo.decode("utf-8")
        if len(conteudo) > 100000:
            raise _Conflito(
                "O arquivo excede o tamanho de um pedido desta tela. Confira o ramo original."
            )
        return conteudo.replace(b"\r\n", b"\n")

    def conferir_integracao(self, pr, revisao, origem, artefatos):
        head = _sha(pr["head"]["sha"])
        merge = _sha(pr["merge_commit_sha"])
        if origem == "ramo" and head != revisao:
            raise _SemConfirmacao("O PR aponta para outra revisão do ramo.")
        for sha in dict.fromkeys((head, merge)):
            if sha == revisao:
                continue
            fila = self.subarvore(self.arvore(sha), "fila")
            for pasta in ("tarefas", "eventos"):
                entradas = self.subarvore(fila, pasta)
                for caminho, esperado in artefatos:
                    if not caminho.startswith("fila/" + pasta + "/"):
                        continue
                    nome = caminho.rsplit("/", 1)[1]
                    item = next((e for e in entradas if e["path"] == nome), None)
                    if item is None or self.blob(item) != esperado:
                        raise _SemConfirmacao(
                            "O commit do PR ou da integração não confirma os mesmos artefatos."
                        )
        main = revisao if origem == "main" else self.ref("heads/" + RAMO_BASE)
        if main != merge:
            comparacao = self.get(f"/compare/{main}...{merge}")
            if (
                comparacao.get("status") != "behind"
                or comparacao["base_commit"]["sha"] != main
                or comparacao["merge_base_commit"]["sha"] != merge
            ):
                raise _SemConfirmacao(
                    "O commit da integração não foi confirmado na história da main."
                )

    def conferir(self):
        import unicodedata

        reserva_sha = self.ref("chaves-numero/tarefa/" + self.chave, ausente=True)
        if reserva_sha is None:
            return ReciboReuniao(
                "incerto",
                "Não consegui confirmar recebimento. Salvar, autorizar ou copiar não envia o pedido; consulte novamente após a sessão do robô.",
            )
        commit = self.get("/git/commits/" + reserva_sha)
        if commit.get("sha") != reserva_sha:
            raise _Conflito("A revisão da reserva diverge. Confira o pedido original.")
        reserva = json.loads(commit["message"])
        numero, ramo = reserva.get("numero"), reserva.get("ramo")
        if (
            reserva.get("chave") != self.chave
            or reserva.get("superficie") != "tarefa"
            or not isinstance(numero, str)
            or not re.fullmatch(r"[0-9]{3,12}", numero)
            or not isinstance(ramo, str)
            or not re.fullmatch(r"agent/[a-zA-Z0-9/_-]+", ramo)
            or any(parte in ("", ".", "..") for parte in ramo.split("/"))
        ):
            raise _Conflito(
                "A reserva tem identidade ou ramo inválido. Confira o pedido com o robô."
            )
        self.tarefa, self.ramo = "TAR-" + numero, ramo
        if reserva.get("pedido") != self.envelope["pedido"] or any(
            type(reserva["pedido"][campo]) is not int
            for campo in ("documento", "versao")
        ):
            return ReciboReuniao(
                "divergente",
                "Esta identidade já está reservada com outra versão. Continue na mesma tarefa com o texto original; esta versão não tem recebimento confirmado.",
                self.tarefa,
                ramo,
            )
        instante = datetime.fromisoformat(reserva["criado_em"])
        if instante.tzinfo is None or instante.strftime("%Y%m%d") != reserva.get("dia"):
            raise _Conflito("A data da reserva não confere. Confira o pedido original.")
        sha = self.ref("heads/" + ramo, ausente=True)
        origem = "ramo"
        if sha is None:
            sha = self.ref("heads/" + RAMO_BASE)
            origem = "main"
        raiz = self.arvore(sha)
        fila = self.subarvore(raiz, "fila")
        tarefas = self.subarvore(fila, "tarefas")
        eventos = self.subarvore(fila, "eventos")
        tarefa = self.envelope["tarefa"]
        plano = (
            unicodedata.normalize("NFKD", tarefa["titulo"])
            .encode("ascii", "ignore")
            .decode()
        )
        slug = re.sub(r"[^a-z0-9]+", "-", plano.lower()).strip("-")[:60] or "tarefa"
        stem = numero + "-" + slug
        evento_stem = f"{instante:%Y%m%d-%H%M%S}-{self.tarefa}-explicada"
        candidatos = [e for e in tarefas if e["path"].startswith(numero + "-")]
        if len(candidatos) != 1 or candidatos[0]["path"] != stem + ".json":
            raise _Conflito(
                "Não encontrei um único arquivo da tarefa original. Confira o ramo com o robô."
            )
        explicada = next(
            (e for e in eventos if e["path"] == evento_stem + ".json"), None
        )
        if explicada is None:
            raise _SemConfirmacao(
                "Falta a explicação do pedido no mesmo ramo. Tente novamente após o envio completo."
            )
        esperados = (
            (
                "fila/tarefas/" + stem + ".json",
                candidatos[0],
                {
                    "arquivo": stem,
                    "id": self.tarefa,
                    **tarefa,
                    "pedido": self.envelope["pedido"],
                    "criada_em": instante.astimezone(timezone.utc).strftime("%Y-%m-%d"),
                },
            ),
            (
                "fila/eventos/" + evento_stem + ".json",
                explicada,
                {
                    "arquivo": evento_stem,
                    "tarefa": self.tarefa,
                    "evento": "explicada",
                    "quando": instante.isoformat(timespec="seconds"),
                    "quem": tarefa["origem"],
                    **self.envelope["explicacao"],
                },
            ),
        )
        artefatos = []
        for caminho, item, esperado in esperados:
            conteudo = self.blob(item)
            canonico = (
                json.dumps(esperado, ensure_ascii=False, sort_keys=True, indent=2)
                + "\n"
            ).encode("utf-8")
            if conteudo != canonico:
                raise _Conflito(
                    "Os bytes recebidos divergem do pedido autorizado. Continue na mesma tarefa e confira a versão original."
                )
            artefatos.append((caminho, conteudo))
        prs = self.get(
            "/pulls",
            params={"state": "all", "head": f"abundanciabr:{ramo}", "per_page": 100},
        )
        if not isinstance(prs, list) or len(prs) > 1:
            raise _Conflito(
                "Mais de um PR pode corresponder ao ramo. Confira o pedido original."
            )
        pr_numero, integrado = None, False
        detalhe_integracao = ""
        if prs:
            pr = prs[0]
            if (
                not _numero_e_url_do_pr(pr)
                or pr["head"]["ref"] != ramo
                or pr["head"]["repo"]["full_name"] != REPOSITORIO
                or pr["base"]["ref"] != RAMO_BASE
                or pr["base"]["repo"]["full_name"] != REPOSITORIO
                or pr.get("state") not in ("open", "closed")
            ):
                raise _Conflito(
                    "O PR não pertence à origem da tarefa. Confira o ramo original."
                )
            pr_numero = pr["number"]
            if pr.get("merged_at") and pr["state"] == "closed":
                try:
                    self.conferir_integracao(pr, sha, origem, artefatos)
                    integrado = True
                    detalhe_integracao = " Integração confirmada na história da main, com os mesmos artefatos no PR e no commit integrado."
                except (
                    _Conflito,
                    _SemConfirmacao,
                    httpx.HTTPError,
                    ValueError,
                    TypeError,
                    KeyError,
                    AttributeError,
                ):
                    detalhe_integracao = " A integração não foi confirmada. Consulte novamente ou peça ao robô para conferir o PR e a main."
        inicio = ""
        inicios = [
            e
            for e in eventos
            if re.fullmatch(
                rf"[0-9]{{8}}-[0-9]{{6}}-{self.tarefa}-iniciada\.json", e["path"]
            )
        ]
        if len(inicios) > 8:
            raise _SemConfirmacao(
                "O histórico de início excede esta consulta. Confira a tarefa com o robô."
            )
        for item in inicios:
            dado = json.loads(self.blob(item))
            data = datetime.fromisoformat(dado["quando"])
            if (
                dado.get("tarefa") != self.tarefa
                or dado.get("evento") != "iniciada"
                or not dado.get("quem")
                or data.tzinfo is None
                or dado.get("arquivo") + ".json" != item["path"]
                or item["path"] != f"{data:%Y%m%d-%H%M%S}-{self.tarefa}-iniciada.json"
            ):
                raise _Conflito(
                    "O registro de início diverge da tarefa. Confira o ramo original."
                )
            inicio = max(inicio, dado["quando"])
        return ReciboReuniao(
            "integrado" if integrado else "recebido",
            f"Pedido recebido na {origem}, com tarefa e explicação conferidas na mesma revisão. Integração não comprova publicação ou aplicação."
            + detalhe_integracao,
            self.tarefa,
            ramo,
            sha,
            pr_numero,
            tuple(artefatos),
            inicio,
        )


def consultar_recibo_reuniao(envelope):
    if not token():
        return ReciboReuniao(
            "incerto",
            "Não consegui confirmar recebimento: a consulta ao repositório está indisponível. O texto privado continua salvo; tente consultar novamente. Se você já levou o pedido à sessão e a consulta continuar indisponível, acione o robô para conferir a mesma tarefa.",
        )
    leitor = _RecebimentoReuniao(envelope)
    try:
        return leitor.conferir()
    except (
        _Conflito,
        _SemConfirmacao,
        httpx.HTTPError,
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
    ) as erro:
        return ReciboReuniao(
            "incerto",
            f"Não consegui confirmar recebimento. {erro} Consulte novamente. Se a consulta continuar indisponível, acione o robô para conferir a mesma tarefa.",
            leitor.tarefa,
            leitor.ramo,
        )
