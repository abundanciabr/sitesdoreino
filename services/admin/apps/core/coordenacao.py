"""Autoridade, concessões e candidatos da coorte; origem do candidato pertence ao PME06."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from contextlib import contextmanager
from pathlib import Path

import psycopg
from django.http import JsonResponse
from typing import Literal, Union
from ninja import Router, Schema
from ninja.errors import HttpError
from ninja.security import HttpBearer
from pydantic import StrictInt, create_model

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

PAPEIS = {
    "listar": "leitor",
    "importar": "operador",
    "adquirir": "executor",
    "renovar": "executor",
    "checkpoint": "executor",
    "candidato": "executor",
    "adquirir_publicador": "publicador",
    "autorizar_publicacao": "publicador",
    "conferir_publicacao": "publicador",
    "confirmar_publicacao": "publicador",
    "reconciliar_publicacao": "reconciliador",
}
CAMPOS = {
    "listar": (),
    "importar": ("chave", "origem_sha", "tarefas", "historico"),
    "adquirir": ("chave", "tarefa", "epoca", "versao"),
    "renovar": ("chave", "tarefa", "epoca", "versao", "concessao"),
    "checkpoint": ("chave", "tarefa", "epoca", "versao", "concessao", "checkpoint"),
    "candidato": ("chave", "tarefa", "epoca", "versao", "concessao", "candidato"),
    "adquirir_publicador": ("chave", "celula", "epoca"),
    "autorizar_publicacao": (
        "chave",
        "celula",
        "epoca",
        "concessao",
        "candidato",
        "manifesto",
        "estado_anterior",
        "aceitacao",
    ),
    "conferir_publicacao": (
        "celula",
        "epoca",
        "concessao",
        "publicacao",
        "estado_anterior",
    ),
    "confirmar_publicacao": (
        "chave",
        "celula",
        "epoca",
        "concessao",
        "publicacao",
        "resultado",
        "prova",
        "recibo",
    ),
    "reconciliar_publicacao": (
        "chave",
        "celula",
        "epoca",
        "publicacao",
        "resultado",
        "prova",
        "recibo",
    ),
}


class Recusa(Exception):
    def __init__(self, mensagem, status=409):
        super().__init__(mensagem)
        self.status = status


def canonico(dados):
    try:
        return json.dumps(
            dados,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as erro:
        raise Recusa(
            "Conteúdo não é JSON finito. Corrija a entrada antes de repetir.", 422
        ) from erro


def hash_conteudo(dados):
    return hashlib.sha256(canonico(dados).encode()).hexdigest()


@contextmanager
def banco():
    dsn = os.environ.get("COORDENACAO_DATABASE_URL", "")
    if not dsn:
        raise Recusa(
            "Banco de coordenação ausente. Provisione pelo canal oficial antes de usar.",
            503,
        )
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=10) as conexao:
            identidade = conexao.execute(
                "SELECT current_database() AS banco, current_user AS papel"
            ).fetchone()
            if identidade != {"banco": "coordenacao_db", "papel": "coordenacao_user"}:
                raise Recusa(
                    "Banco ou papel incompatível. Corrija o DSN específico da coordenação.",
                    503,
                )
            yield conexao
    except psycopg.Error as erro:
        raise Recusa(
            "Banco indisponível ou esquema incompatível. Confira provisionamento e repita a mesma chave.",
            503,
        ) from erro


def preparar():
    with banco() as conexao:
        conexao.execute(
            Path(__file__).with_suffix(".sql").read_text(encoding="utf-8-sig")
        )
    return {"estado": "PASS", "banco": "coordenacao_db"}


@contextmanager
def capturar_snapshot():
    """Mantém a visão do pg_dump --snapshot e dos hashes até o receptor terminar."""
    with banco() as c:
        c.commit()
        c.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        c.execute("SET LOCAL TIME ZONE 'UTC'")
        snapshot = c.execute("SELECT pg_export_snapshot() AS id").fetchone()["id"]
        tabelas = {}
        for nome, ordem in (
            ("autoridade", "coorte"),
            ("tarefa", "id"),
            ("historico", "id"),
            ("operacao", "coorte,chave"),
            ("evento", "id"),
            ("outbox", "evento"),
            ("candidato", "id"),
            ("publicador", "celula"),
            ("publicacao", "id"),
        ):
            linhas = [
                item["linha"]
                for item in c.execute(
                    f"SELECT to_jsonb(t) AS linha FROM coordenacao.{nome} t ORDER BY {ordem}"
                ).fetchall()
            ]
            tabelas[nome] = {"linhas": len(linhas), "sha256": hash_conteudo(linhas)}
        autoridades = [
            item["linha"]
            for item in c.execute(
                "SELECT to_jsonb(a) AS linha FROM coordenacao.autoridade a ORDER BY coorte"
            ).fetchall()
        ]
        yield {"snapshot_id": snapshot, "autoridades": autoridades, "tabelas": tabelas}


def identificar(token):
    try:
        identidades = json.loads(os.environ.get("COORDENACAO_IDENTIDADES", "{}"))
    except ValueError as erro:
        raise Recusa(
            "Identidades técnicas ilegíveis. Corrija o provisionamento oficial.", 503
        ) from erro
    if not token or not isinstance(identidades, dict):
        raise Recusa(
            "Credencial técnica ausente ou recusada. Use a identidade da operação.", 401
        )
    identidade = identidades.get(hashlib.sha256(token.encode()).hexdigest())
    if (
        not isinstance(identidade, dict)
        or not isinstance(identidade.get("id"), str)
        or not identidade["id"]
        or any(
            not isinstance(identidade.get(campo), list)
            or not all(isinstance(v, str) for v in identidade[campo])
            for campo in ("papeis", "coortes", "celulas")
        )
    ):
        raise Recusa("Credencial técnica recusada. Use a identidade da operação.", 401)
    return identidade


def validar_pedido(pedido, identidade):
    if not isinstance(pedido, dict):
        raise Recusa("Corpo precisa ser objeto JSON. Corrija o pedido.", 422)
    operacao = pedido.get("operacao")
    if not isinstance(operacao, str) or operacao not in PAPEIS:
        raise Recusa("Operação desconhecida. Use o contrato da coordenação.", 422)
    exigidos = {"operacao", "coorte", *CAMPOS[operacao]}
    if set(pedido) != exigidos:
        raise Recusa(
            "Campos ausentes ou desconhecidos. Envie os campos exatos da operação.", 422
        )
    if PAPEIS[operacao] not in identidade.get("papeis", []) or pedido[
        "coorte"
    ] not in identidade.get("coortes", []):
        raise Recusa(
            "Identidade sem função ou coorte autorizada. Solicite o escopo oficial correto.",
            403,
        )
    if "celula" in pedido and pedido["celula"] not in identidade.get("celulas", []):
        raise Recusa(
            "Identidade sem autorização para esta célula. Use o publicador da célula.",
            403,
        )
    for nome in ("coorte", "chave", "tarefa", "celula", "candidato", "publicacao"):
        if nome in pedido and (
            not isinstance(pedido[nome], str)
            or not pedido[nome]
            or len(pedido[nome]) > 200
        ):
            raise Recusa(
                "Identificador inválido. Use texto não vazio de até 200 caracteres.",
                422,
            )
    for nome in ("epoca", "versao", "concessao"):
        if nome in pedido and (type(pedido[nome]) is not int or pedido[nome] < 1):
            raise Recusa(
                "Época, versão e concessão precisam ser inteiros positivos. Consulte o estado atual.",
                422,
            )


def _tarefa(c, p):
    tarefa = c.execute(
        "SELECT *, expira_em > clock_timestamp() AS vigente FROM coordenacao.tarefa WHERE id=%s AND coorte=%s FOR UPDATE",
        (p["tarefa"], p["coorte"]),
    ).fetchone()
    if not tarefa:
        raise Recusa(
            "Tarefa não importada nesta coorte. Reconcilie a importação antes de executar."
        )
    if tarefa["versao"] != p["versao"]:
        raise Recusa("Versão mudou. Consulte a tarefa e reavalie a operação.")
    return tarefa


def _concessao(tarefa, p, ator):
    if (
        tarefa["dono"] != ator
        or tarefa["concessao"] != p["concessao"]
        or not tarefa["vigente"]
    ):
        raise Recusa(
            "Executor perdeu a concessão. Preserve a bancada e adquira uma nova tentativa."
        )


def _publicador(c, p, ator):
    atual = c.execute(
        "SELECT *, expira_em > clock_timestamp() AS vigente FROM coordenacao.publicador WHERE celula=%s FOR UPDATE",
        (p["celula"],),
    ).fetchone()
    if (
        not atual
        or atual["coorte"] != p["coorte"]
        or atual["dono"] != ator
        or atual["concessao"] != p["concessao"]
        or not atual["vigente"]
    ):
        raise Recusa(
            "Publicador perdeu a concessão. Reconcilie a ativação antes de adquirir outra."
        )
    return atual


def _candidato(c, p):
    candidato = c.execute(
        "SELECT ca.*,t.coorte FROM coordenacao.candidato ca JOIN coordenacao.tarefa t ON t.id=ca.tarefa WHERE ca.id=%s",
        (p["candidato"],),
    ).fetchone()
    if (
        not candidato
        or candidato["coorte"] != p["coorte"]
        or candidato["epoca"] != p["epoca"]
        or candidato["revogado"]
    ):
        raise Recusa(
            "Candidato ausente, revogado ou de outra época. Consulte a aceitação vigente."
        )
    return candidato


def _publicacao(c, p, ator):
    _publicador(c, p, ator)
    registro = c.execute(
        "SELECT * FROM coordenacao.publicacao WHERE id=%s AND celula=%s FOR UPDATE",
        (p["publicacao"], p["celula"]),
    ).fetchone()
    if (
        not registro
        or registro["epoca"] != p["epoca"]
        or registro["concessao"] != p["concessao"]
    ):
        raise Recusa(
            "Autorização de publicação incompatível. Reconcilie o resultado da operação."
        )
    _candidato(c, dict(p, candidato=registro["candidato"]))
    return registro


def _verificar_recibo(recebido, esperado):
    chave = os.environ.get("COORDENACAO_RECIBOS_CHAVE", "")
    if not re.fullmatch("[0-9a-f]{64}", chave):
        raise Recusa(
            "Emissor de recibos ausente. Provisione a chave de par do receptor oficial.",
            503,
        )
    if (
        not isinstance(recebido, dict)
        or set(recebido) != {"conteudo", "assinatura"}
        or recebido["conteudo"] != esperado
        or not isinstance(recebido["assinatura"], str)
        or not re.fullmatch("[0-9a-f]{64}", recebido["assinatura"])
    ):
        raise Recusa(
            "Recibo não comprova esta operação. Peça a revalidação ao receptor oficial.",
            403,
        )
    assinatura = hmac.new(
        bytes.fromhex(chave), canonico(esperado).encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(assinatura, recebido["assinatura"]):
        raise Recusa(
            "Assinatura do recibo recusada. Revalide pelo receptor oficial antes do efeito.",
            403,
        )


def _conteudo_aceitacao(p, tarefa):
    return {
        "tipo": "aceitacao",
        "coorte": p["coorte"],
        "epoca": p["epoca"],
        "celula": p["celula"],
        "candidato": p["candidato"],
        "tarefa": tarefa,
        "referencia": "refs/candidatos/" + p["candidato"],
        "manifesto_sha256": hash_conteudo(p["manifesto"]),
    }


def _conteudo_resultado(p, registro, tipo):
    return {
        "tipo": tipo,
        "coorte": p["coorte"],
        "epoca": p["epoca"],
        "celula": p["celula"],
        "publicacao": registro["id"],
        "epoca_publicacao": registro["epoca"],
        "concessao": registro["concessao"],
        "resultado": p["resultado"],
        "prova_sha256": hash_conteudo(p["prova"]),
    }


def _validar_resultado(p, registro, manifesto, reconciliacao=False):
    prova = p["prova"]
    if (
        p["resultado"] not in ("publicada", "falhou", "incerta")
        or not isinstance(prova, dict)
        or not isinstance(prova.get("estado_observado"), dict)
    ):
        raise Recusa(
            "Resultado exige estado observado pelo receptor. Reconcilie o efeito real antes de confirmar.",
            422,
        )
    if reconciliacao and prova.get("mutadores_parados") is not True:
        raise Recusa(
            "Reconciliação exige parada comprovada sob a exclusão comum. Pare e observe os mutadores antes de retomar."
        )
    if p["resultado"] == "publicada":
        esperado = {
            "candidato": manifesto["id"],
            "digest": manifesto["imagem"]["referencia"].split("@", 1)[1],
            "revisao": manifesto["integracao"]["revisao"],
        }
        if prova["estado_observado"] != esperado:
            raise Recusa(
                "Estado observado não corresponde ao candidato autorizado. Preserve o resultado incerto e investigue."
            )
    elif (
        p["resultado"] == "falhou"
        and prova["estado_observado"] != registro["estado_anterior"]
    ):
        raise Recusa(
            "Falha não comprovou preservação do estado anterior. Registre resultado incerto e investigue."
        )


def _validar_snapshot(p):
    if (
        not re.fullmatch("[0-9a-f]{40}", str(p["origem_sha"]))
        or not isinstance(p["tarefas"], list)
        or not isinstance(p["historico"], list)
    ):
        raise Recusa(
            "Snapshot inválido. Reexporte tarefas, projeções e histórico do Git.", 422
        )
    ids = set()
    for item in p["tarefas"]:
        if (
            not isinstance(item, dict)
            or set(item) != {"id", "documento", "projecao"}
            or not isinstance(item["id"], str)
            or not re.fullmatch(r"TAR-\d+", item["id"])
            or not isinstance(item["documento"], dict)
            or item["documento"].get("id") != item["id"]
            or not isinstance(item["projecao"], dict)
            or not isinstance(item["projecao"].get("estado"), str)
            or item["id"] in ids
        ):
            raise Recusa(
                "Tarefa do snapshot incompatível. Reexporte IDs únicos, documentos e projeções.",
                422,
            )
        ids.add(item["id"])
    for item in p["historico"]:
        if (
            not isinstance(item, dict)
            or set(item) != {"id", "conteudo"}
            or not isinstance(item["id"], str)
            or not item["id"]
            or not isinstance(item["conteudo"], dict)
            or item["conteudo"].get("tarefa") not in ids
        ):
            raise Recusa(
                "Histórico incompatível com a coorte. Reexporte os eventos das tarefas importadas.",
                422,
            )


def executar(p, identidade):
    validar_pedido(p, identidade)
    ator, op, coorte = identidade["id"], p["operacao"], p["coorte"]
    with banco() as c:
        if op == "importar":
            _validar_snapshot(p)
            c.execute(
                "INSERT INTO coordenacao.autoridade(coorte,origem_sha,hash_historico) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING",
                (coorte, p["origem_sha"], hash_conteudo(p["historico"])),
            )
        autoridade = c.execute(
            "SELECT * FROM coordenacao.autoridade WHERE coorte=%s FOR UPDATE", (coorte,)
        ).fetchone()
        if not autoridade:
            raise Recusa(
                "Coorte desconhecida. Importe o histórico pelo operador autorizado."
            )
        if op == "listar":
            tarefas = c.execute(
                "SELECT id,documento,projecao,versao,dono,concessao,expira_em FROM coordenacao.tarefa WHERE coorte=%s ORDER BY id",
                (coorte,),
            ).fetchall()
            return {"autoridade": autoridade, "tarefas": tarefas}
        if "epoca" in p and autoridade["epoca"] != p["epoca"]:
            raise Recusa("Época obsoleta. Reconsulte a autoridade antes de operar.")
        if op != "importar" and autoridade["backend"] != "postgres":
            raise Recusa(
                "Git ainda é a autoridade. Use os comandos atuais até o corte oficial da coorte."
            )
        if op == "conferir_publicacao":
            registro = _publicacao(c, p, ator)
            if (
                registro["estado"] != "autorizada"
                or registro["estado_anterior"] != p["estado_anterior"]
            ):
                raise Recusa(
                    "Estado da publicação mudou. Reavalie sob a exclusão comum antes da ativação."
                )
            return registro
        fingerprint = hash_conteudo({"ator": ator, "pedido": p})
        anterior = c.execute(
            "SELECT * FROM coordenacao.operacao WHERE coorte=%s AND chave=%s",
            (coorte, p["chave"]),
        ).fetchone()
        if anterior:
            if anterior["sha256"] != fingerprint:
                raise Recusa(
                    "Chave reutilizada com conteúdo ou identidade diferente. Preserve a operação original."
                )
            return anterior["resultado"]
        resultado = _aplicar(c, p, ator, autoridade)
        evento = c.execute(
            "INSERT INTO coordenacao.evento(coorte,tarefa,ator,operacao,conteudo) VALUES(%s,%s,%s,%s,%s) RETURNING id",
            (
                coorte,
                p.get("tarefa"),
                ator,
                op,
                Jsonb(
                    {
                        "chave": p["chave"],
                        "resultado": resultado,
                        "recibo": p.get("aceitacao", p.get("recibo")),
                    }
                ),
            ),
        ).fetchone()["id"]
        c.execute("INSERT INTO coordenacao.outbox(evento) VALUES(%s)", (evento,))
        c.execute(
            "INSERT INTO coordenacao.operacao(coorte,chave,sha256,resultado) VALUES(%s,%s,%s,%s)",
            (coorte, p["chave"], fingerprint, Jsonb(resultado)),
        )
        return resultado


def _aplicar(c, p, ator, autoridade):
    op = p["operacao"]
    if op == "importar":
        anteriores = c.execute(
            "SELECT id,projecao FROM coordenacao.tarefa WHERE coorte=%s", (p["coorte"],)
        ).fetchall()
        novas = {item["id"]: item for item in p["tarefas"]}
        ids_historicos = {item["id"] for item in p["historico"]}
        preservados = c.execute(
            "SELECT h.id FROM coordenacao.historico h JOIN coordenacao.tarefa t ON t.id=h.tarefa WHERE t.coorte=%s",
            (p["coorte"],),
        ).fetchall()
        if any(t["id"] not in novas for t in anteriores) or any(
            h["id"] not in ids_historicos for h in preservados
        ):
            raise Recusa(
                "Snapshot omite tarefas ou eventos já importados. Reexporte o histórico completo antes de retomar."
            )
        if any(
            t["projecao"].get("estado") in ("concluída", "cancelada")
            and novas[t["id"]]["projecao"].get("estado") != t["projecao"]["estado"]
            for t in anteriores
        ):
            raise Recusa(
                "Snapshot tenta reabrir estado terminal. Preserve a projeção e reconcilie a origem."
            )
        if autoridade["backend"] != "git":
            raise Recusa(
                "Importação recusada após transferência. Exporte e reconcilie as novas escritas."
            )
        for item in p["tarefas"]:
            existente = c.execute(
                "SELECT coorte FROM coordenacao.tarefa WHERE id=%s", (item["id"],)
            ).fetchone()
            if existente and existente["coorte"] != p["coorte"]:
                raise Recusa(
                    "Tarefa pertence a outra coorte. Preserve sua autoridade original."
                )
            gravada = c.execute(
                "INSERT INTO coordenacao.tarefa(id,coorte,documento,projecao) VALUES(%s,%s,%s,%s) ON CONFLICT(id) DO UPDATE SET documento=EXCLUDED.documento,projecao=EXCLUDED.projecao WHERE coordenacao.tarefa.coorte=EXCLUDED.coorte RETURNING id",
                (
                    item["id"],
                    p["coorte"],
                    Jsonb(item["documento"]),
                    Jsonb(item["projecao"]),
                ),
            ).fetchone()
            if not gravada:
                raise Recusa(
                    "Tarefa disputada por outra coorte. Preserve sua autoridade original."
                )
        for item in p["historico"]:
            digest = hash_conteudo(item["conteudo"])
            anterior = c.execute(
                "SELECT sha256 FROM coordenacao.historico WHERE id=%s", (item["id"],)
            ).fetchone()
            if anterior and anterior["sha256"] != digest:
                raise Recusa(
                    "Histórico divergiu para o mesmo ID. Confira os hashes antes da importação."
                )
            if not anterior:
                c.execute(
                    "INSERT INTO coordenacao.historico(id,tarefa,conteudo,sha256) VALUES(%s,%s,%s,%s)",
                    (
                        item["id"],
                        item["conteudo"]["tarefa"],
                        Jsonb(item["conteudo"]),
                        digest,
                    ),
                )
        c.execute(
            "UPDATE coordenacao.autoridade SET origem_sha=%s,hash_historico=%s,atualizado_em=clock_timestamp() WHERE coorte=%s",
            (p["origem_sha"], hash_conteudo(p["historico"]), p["coorte"]),
        )
        return {
            "tarefas": len(p["tarefas"]),
            "eventos": len(p["historico"]),
            "backend": "git",
            "hash_historico": hash_conteudo(p["historico"]),
        }
    if op in ("adquirir", "renovar", "checkpoint", "candidato"):
        tarefa = _tarefa(c, p)
        if op == "adquirir":
            if tarefa["projecao"].get("estado") not in (
                "na fila",
                "reivindicada",
                "em execução",
            ):
                raise Recusa(
                    "Estado da tarefa não permite aquisição. Reconcilie bloqueio ou preserve o estado terminal."
                )
            dependencias = tarefa["documento"].get("depende_de", [])
            if not isinstance(dependencias, list) or not all(
                isinstance(d, str) for d in dependencias
            ):
                raise Recusa(
                    "Dependências inválidas. Corrija o documento canônico antes de adquirir.",
                    422,
                )
            for dependencia in dependencias:
                estado = c.execute(
                    "SELECT projecao FROM coordenacao.tarefa WHERE id=%s",
                    (dependencia,),
                ).fetchone()
                if not estado or estado["projecao"].get("estado") != "concluída":
                    raise Recusa(
                        "Dependência ainda não concluída. Reconcilie sua projeção antes de adquirir a tarefa."
                    )
            if tarefa["dono"] and tarefa["vigente"]:
                raise Recusa(
                    "Tarefa ocupada. Escolha outra tarefa ou reconcilie a tentativa vigente."
                )
            return c.execute(
                "UPDATE coordenacao.tarefa SET dono=%s,concessao=concessao+1,versao=versao+1,expira_em=clock_timestamp()+interval '3 hours' WHERE id=%s RETURNING id,versao,concessao,expira_em::text AS expira_em",
                (ator, p["tarefa"]),
            ).fetchone() | {"epoca": p["epoca"]}
        _concessao(tarefa, p, ator)
        if op == "candidato":
            c.execute(
                "INSERT INTO coordenacao.candidato(id,tarefa,manifesto,epoca) VALUES(%s,%s,%s,%s)",
                (
                    p["candidato"],
                    p["tarefa"],
                    Jsonb({"referencia": "refs/candidatos/" + p["candidato"]}),
                    p["epoca"],
                ),
            )
        elif op == "checkpoint":
            if not isinstance(p["checkpoint"], dict):
                raise Recusa(
                    "Checkpoint precisa ser objeto JSON. Corrija a retomada.", 422
                )
            projecao = dict(tarefa["projecao"], checkpoint=p["checkpoint"])
            c.execute(
                "UPDATE coordenacao.tarefa SET projecao=%s WHERE id=%s",
                (Jsonb(projecao), p["tarefa"]),
            )
        return c.execute(
            "UPDATE coordenacao.tarefa SET versao=versao+1,expira_em=clock_timestamp()+interval '3 hours' WHERE id=%s RETURNING id,versao,concessao,expira_em::text AS expira_em",
            (p["tarefa"],),
        ).fetchone() | {"epoca": p["epoca"]}
    if op == "adquirir_publicador":
        c.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            ("coordenacao/publicador/" + p["celula"],),
        )
        atual = c.execute(
            "SELECT *,expira_em>clock_timestamp() AS vigente FROM coordenacao.publicador WHERE celula=%s FOR UPDATE",
            (p["celula"],),
        ).fetchone()
        incerta = c.execute(
            "SELECT id FROM coordenacao.publicacao WHERE celula=%s AND estado IN ('autorizada','incerta')",
            (p["celula"],),
        ).fetchone()
        if incerta or (atual and atual["vigente"]):
            raise Recusa(
                "Célula possui publicador ou operação pendente. Reconcilie e comprove a parada antes de assumir."
            )
        return c.execute(
            "INSERT INTO coordenacao.publicador(celula,coorte,dono,concessao,expira_em) VALUES(%s,%s,%s,1,clock_timestamp()+interval '30 minutes') ON CONFLICT(celula) DO UPDATE SET coorte=EXCLUDED.coorte,dono=EXCLUDED.dono,concessao=coordenacao.publicador.concessao+1,expira_em=EXCLUDED.expira_em RETURNING celula,concessao,expira_em::text AS expira_em",
            (p["celula"], p["coorte"], ator),
        ).fetchone() | {"epoca": p["epoca"]}
    if op == "autorizar_publicacao":
        _publicador(c, p, ator)
        candidato = _candidato(c, p)
        manifesto = p["manifesto"]
        _verificar_recibo(p["aceitacao"], _conteudo_aceitacao(p, candidato["tarefa"]))
        if "imagem" in candidato["manifesto"] and hash_conteudo(
            candidato["manifesto"]
        ) != hash_conteudo(manifesto):
            raise Recusa(
                "Aceitação já registrada com conteúdo diferente. Preserve o candidato durável e investigue a origem."
            )
        if (
            not isinstance(manifesto, dict)
            or manifesto.get("id") != p["candidato"]
            or manifesto.get("tarefa") != candidato["tarefa"]
            or manifesto.get("celula") != p["celula"]
        ):
            raise Recusa(
                "Manifesto não identifica o candidato e célula aceitos. Verifique a origem no PME06."
            )
        if not isinstance(manifesto.get("imagem"), dict) or not isinstance(
            manifesto.get("integracao"), dict
        ):
            raise Recusa(
                "Imagem ou integração inválida. Recarregue a aceitação assinada.", 422
            )
        digest = manifesto.get("imagem", {}).get("referencia", "")
        revisao = manifesto.get("integracao", {}).get("revisao", "")
        if not isinstance(digest, str) or not isinstance(revisao, str):
            raise Recusa(
                "Digest e revisão precisam ser texto. Recarregue a aceitação assinada.",
                422,
            )
        if not re.search(r"@sha256:[0-9a-f]{64}$", digest) or not re.fullmatch(
            "[0-9a-f]{40}", revisao
        ):
            raise Recusa(
                "Identidade de imagem ou integração ausente. Recarregue a aceitação assinada."
            )
        vigente = c.execute(
            "SELECT id FROM coordenacao.publicacao WHERE celula=%s AND estado IN ('autorizada','incerta')",
            (p["celula"],),
        ).fetchone()
        if vigente:
            raise Recusa(
                "Publicação ainda não reconciliada. Confira seu efeito antes de repetir."
            )
        c.execute(
            "UPDATE coordenacao.candidato SET manifesto=%s WHERE id=%s",
            (Jsonb(manifesto), p["candidato"]),
        )
        return c.execute(
            "INSERT INTO coordenacao.publicacao(id,candidato,celula,epoca,concessao,estado_anterior) VALUES(%s,%s,%s,%s,%s,%s) RETURNING id,candidato,celula,epoca,concessao,estado",
            (
                p["chave"],
                p["candidato"],
                p["celula"],
                p["epoca"],
                p["concessao"],
                Jsonb(p["estado_anterior"]),
            ),
        ).fetchone()

    if op == "reconciliar_publicacao":
        c.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            ("coordenacao/publicador/" + p["celula"],),
        )
        registro = c.execute(
            "SELECT pu.*,ca.manifesto FROM coordenacao.publicacao pu JOIN coordenacao.candidato ca ON ca.id=pu.candidato JOIN coordenacao.tarefa t ON t.id=ca.tarefa WHERE pu.id=%s AND pu.celula=%s AND t.coorte=%s FOR UPDATE OF pu",
            (p["publicacao"], p["celula"], p["coorte"]),
        ).fetchone()
        if not registro or registro["estado"] not in ("autorizada", "incerta"):
            raise Recusa(
                "Publicação sem pendência nesta coorte. Consulte o estado antes de reconciliar."
            )
        _validar_resultado(p, registro, registro["manifesto"], reconciliacao=True)
        _verificar_recibo(
            p["recibo"], _conteudo_resultado(p, registro, "reconciliacao")
        )
        resultado = c.execute(
            "UPDATE coordenacao.publicacao SET estado=%s,prova=%s WHERE id=%s RETURNING id,estado",
            (p["resultado"], Jsonb(p["prova"]), registro["id"]),
        ).fetchone()
        if p["resultado"] != "incerta":
            c.execute(
                "UPDATE coordenacao.publicador SET expira_em=clock_timestamp(),concessao=concessao+1 WHERE celula=%s",
                (p["celula"],),
            )
        return resultado
    registro = _publicacao(c, p, ator)
    if (
        registro["estado"] not in ("autorizada", "incerta")
        or p["resultado"] not in ("publicada", "falhou", "incerta")
        or not isinstance(p["prova"], dict)
        or not p["prova"]
    ):
        raise Recusa(
            "Resultado sem prova ou publicação já terminal. Consulte e reconcilie o efeito real."
        )
    candidato = _candidato(c, dict(p, candidato=registro["candidato"]))
    _validar_resultado(p, registro, candidato["manifesto"])
    _verificar_recibo(p["recibo"], _conteudo_resultado(p, registro, "confirmacao"))
    return c.execute(
        "UPDATE coordenacao.publicacao SET estado=%s,prova=%s WHERE id=%s RETURNING id,estado",
        (p["resultado"], Jsonb(p["prova"]), registro["id"]),
    ).fetchone()


class CoordenacaoAuth(HttpBearer):
    def authenticate(self, request, token):
        try:
            return identificar(token)
        except Recusa as erro:
            raise HttpError(erro.status, str(erro)) from erro


class PedidoFechado(Schema):
    model_config = {"extra": "forbid"}


class ReciboReceptor(PedidoFechado):
    conteudo: dict
    assinatura: str


TIPOS = {
    "epoca": StrictInt,
    "versao": StrictInt,
    "concessao": StrictInt,
    "tarefas": list[dict],
    "historico": list[dict],
    "checkpoint": dict,
    "manifesto": dict,
    "estado_anterior": dict,
    "prova": dict,
    "aceitacao": ReciboReceptor,
    "recibo": ReciboReceptor,
}
PEDIDOS = tuple(
    create_model(
        "Coordenacao_" + nome,
        __base__=PedidoFechado,
        operacao=(Literal[nome], ...),
        coorte=(str, ...),
        **{campo: (TIPOS.get(campo, str), ...) for campo in campos},
    )
    for nome, campos in CAMPOS.items()
)
PedidoCoordenacao = Union[PEDIDOS]
router = Router(tags=["Coordenação"], auth=CoordenacaoAuth())


@router.post(
    "/coordenacao",
    response={200: dict, 401: dict, 403: dict, 409: dict, 422: dict, 503: dict},
    operation_id="coordenarEntrega",
    summary="Coordenação durável por função e coorte",
    description="Importa snapshots enquanto Git governa. Operações PostgreSQL exigem época, versão e concessão vigentes. O publicador tem concessão própria. Autorizações e resultados exigem recibo do receptor oficial, que verifica a origem assinada e o efeito sob bloqueio de publicação.",
)
def operar(request, pedido: PedidoCoordenacao):
    try:
        return JsonResponse(
            {"estado": "PASS", "resultado": executar(pedido.model_dump(), request.auth)}
        )
    except Recusa as erro:
        return JsonResponse(
            {"estado": "ERROR" if erro.status == 503 else "FAIL", "erro": str(erro)},
            status=erro.status,
        )
