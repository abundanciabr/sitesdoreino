"""Texto privado, histórico e autorização atômica do pedido da Reunião.

A auditoria identifica o gesto; Documento e VersaoDoDocumento guardam o texto.
Nenhuma função deste módulo executa o pedido ou escreve fora do banco da admin.
"""

from __future__ import annotations

import hashlib
import json
import time
from uuid import UUID

from django.db import (
    IntegrityError,
    OperationalError,
    connection,
    connections,
    transaction,
)

from apps.auditoria.models import Registro
from .models import Documento, VersaoDoDocumento

PREFIXO = "pedido-reuniao-"
CAMPOS = (
    "compromisso1",
    "compromisso2",
    "confirmar_restricao",
    "decisoes",
    "aprendemos",
    "tirar_foto",
)


class ConflitoDoPedido(ValueError):
    pass


def _pode_repetir_lock(erro, tentativa):
    return (
        connection.vendor == "sqlite"
        and "locked" in str(erro).lower()
        and tentativa < 4
    )


def nome_do_pedido(identidade):
    return PREFIXO + str(UUID(str(identidade)))


def _hash(valor):
    return hashlib.sha256(
        json.dumps(
            valor, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _auditar(doc, versao, admin, acao, **gesto):
    return Registro.objects.create(
        quem_email=admin["email"],
        quem_id=admin.get("id") or "",
        acao=acao,
        alvo=doc.nome,
        desfecho=Registro.OK,
        detalhe=json.dumps(
            {
                "documento": doc.pk,
                "versao": versao.pk,
                "texto_sha256": _hash(versao.corpo),
                "autor": versao.salvo_por,
                **gesto,
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
    )


def _registros(doc, acao):
    for registro in Registro.objects.filter(
        alvo=doc.nome, acao=acao, desfecho=Registro.OK
    ).order_by("pk"):
        try:
            dado = json.loads(registro.detalhe)
        except (ValueError, TypeError):
            continue
        if isinstance(dado, dict) and dado.get("documento") == doc.pk:
            yield registro, dado


def _versao(doc, admin, gesto):
    return VersaoDoDocumento.objects.create(
        documento=doc,
        titulo=doc.titulo,
        publico=False,
        ordem=doc.ordem,
        corpo=doc.corpo,
        salvo_por=admin["email"],
        gesto=gesto,
    )


def vigente(doc, versao):
    atual = Documento.objects.get(pk=doc.pk)
    ultima = atual.versoes.order_by("-pk").first()
    return (
        ultima is not None
        and ultima.pk == versao.pk
        and versao.documento_id == atual.pk
        and not atual.publico
        and not atual.arquivado
        and not versao.publico
        and atual.corpo == versao.corpo == ultima.corpo
        and atual.titulo == versao.titulo == ultima.titulo
        and versao.salvo_por == ultima.salvo_por
    )


def _repeticao_inicial(doc, impressao, admin):
    for registro, gesto in _registros(doc, Registro.CRIAR_DOCUMENTO):
        if (
            gesto.get("formulario") == impressao
            and registro.quem_email == admin["email"]
            and registro.quem_id == (admin.get("id") or "")
        ):
            versao = doc.versoes.filter(pk=gesto.get("versao")).first()
            if (
                versao
                and gesto.get("texto_sha256") == _hash(versao.corpo)
                and gesto.get("autor") == versao.salvo_por
            ):
                return doc, versao
    raise ConflitoDoPedido(
        "Este pedido já foi salvo com outro conteúdo. Reabra o pedido original e confira antes de editar."
    )


def salvar_inicial(identidade, campos, hoje, foto, admin):
    from .reuniao import montar_o_pedido

    nome = nome_do_pedido(identidade)
    formulario = {campo: campos.get(campo, "") for campo in CAMPOS}
    limites = {
        "compromisso1": 200,
        "compromisso2": 200,
        "confirmar_restricao": 120,
        "decisoes": 1000,
        "aprendemos": 600,
        "tirar_foto": 3,
    }
    if any(
        not isinstance(valor, str) or len(valor) > limites[campo] or "\x00" in valor
        for campo, valor in formulario.items()
    ) or formulario["tirar_foto"] not in ("", "sim"):
        raise ConflitoDoPedido(
            "Um campo excedeu o limite ou contém um valor inválido. Confira os campos da pauta e salve novamente."
        )
    impressao = _hash(formulario)
    # A chave única decide a primeira corrida. A perdedora relê só após o rollback.
    for tentativa in range(5):
        try:
            with transaction.atomic():
                existente = (
                    Documento.objects.select_for_update().filter(nome=nome).first()
                )
                if existente:
                    return _repeticao_inicial(existente, impressao, admin)
                texto = montar_o_pedido(formulario, hoje, foto)
                if not texto:
                    raise ConflitoDoPedido(
                        "Nada para pedir. Preencha um item ou marque a foto da semana."
                    )
                doc = Documento.objects.create(
                    nome=nome,
                    titulo=f"Pedido da Reunião de {hoje:%d/%m/%Y}",
                    corpo=texto,
                    publico=False,
                )
                versao = _versao(doc, admin, "criou na Reunião")
                _auditar(
                    doc, versao, admin, Registro.CRIAR_DOCUMENTO, formulario=impressao
                )
                return doc, versao
        except IntegrityError:
            with transaction.atomic():
                existente = (
                    Documento.objects.select_for_update().filter(nome=nome).first()
                )
                if existente is None:
                    raise
                return _repeticao_inicial(existente, impressao, admin)
        except OperationalError as erro:
            if not _pode_repetir_lock(erro, tentativa):
                raise
            connections.close_all()
            time.sleep(0.01)


def editar(nome, esperada, texto, admin):
    if not isinstance(texto, str) or not texto.strip() or len(texto) > 50000:
        raise ConflitoDoPedido(
            "O texto precisa conter o pedido e ter até 50 mil caracteres. Corrija o campo e salve novamente."
        )
    for tentativa in range(5):
        try:
            with transaction.atomic():
                doc = Documento.objects.select_for_update().get(nome=nome)
                ultima = doc.versoes.order_by("-pk").first()
                if not ultima or not vigente(doc, ultima):
                    raise ConflitoDoPedido(
                        "O documento mudou fora da Reunião. Confira o histórico antes de continuar."
                    )
                for registro, gesto in _registros(doc, Registro.EDITAR_DOCUMENTO):
                    if (
                        gesto.get("anterior") == esperada
                        and gesto.get("versao") == ultima.pk
                        and gesto.get("texto_sha256") == _hash(texto)
                        and texto == ultima.corpo
                        and registro.quem_email == admin["email"]
                        and registro.quem_id == (admin.get("id") or "")
                    ):
                        return ultima
                if ultima.pk != esperada:
                    raise ConflitoDoPedido(
                        "Outra edição já foi salva. Seu texto continua abaixo; reabra o pedido para comparar as versões."
                    )
                if texto == ultima.corpo:
                    return ultima
                doc.corpo = texto
                doc.save(update_fields=["corpo", "atualizado_em"])
                nova = _versao(doc, admin, "editou na Reunião")
                _auditar(doc, nova, admin, Registro.EDITAR_DOCUMENTO, anterior=esperada)
                return nova
        except OperationalError as erro:
            if not _pode_repetir_lock(erro, tentativa):
                raise
            connections.close_all()
            time.sleep(0.01)


def envelope(doc, versao):
    dados = {
        "pedido": {
            "id": doc.nome.removeprefix(PREFIXO),
            "documento": doc.pk,
            "versao": versao.pk,
        },
        "tarefa": {
            "titulo": doc.titulo,
            "toca": ["painel"],
            "move": ["manutencao"],
            "cria": [],
            "depende_de": [],
            "evidencia_exigida": "Conferir cada item do texto autorizado contra os registros do livro e os cartões citados, com vínculo à mesma TAR, evidência e data da verificação; confirmar a publicação desses artefatos no painel.",
            "despacho": versao.corpo,
            "origem": f"Reunião: Documento privado {doc.pk}, versão {versao.pk}",
        },
        "explicacao": {
            "o_que_e": "O pedido revisado da Reunião para registrar os compromissos, as decisões e o aprendizado no livro da plataforma.",
            "o_que_muda": "Os itens autorizados ganham registros verificáveis no livro, acompanhados pela mesma tarefa mesmo depois de uma interrupção.",
            "exemplo": "Ao retomar uma reunião, o compromisso continua ligado ao pedido original e seu recibo mostra a mesma tarefa.",
            "importancia": 80,
        },
    }
    dados["pedido"]["sha256"] = _hash(dados)
    return dados


def envelope_autorizado(doc, versao):
    if not vigente(doc, versao):
        return None
    dados = envelope(doc, versao)
    for registro, gesto in _registros(doc, Registro.AUTORIZAR_PEDIDO):
        if (
            gesto.get("versao") == versao.pk
            and gesto.get("texto_sha256") == _hash(versao.corpo)
            and gesto.get("autor") == versao.salvo_por
            and registro.quem_email
            and gesto.get("pedido") == dados["pedido"]
        ):
            return dados
    return None


def autorizar(nome, esperada, admin, *, texto_exibido):
    with transaction.atomic():
        doc = Documento.objects.select_for_update().get(nome=nome)
        versao = doc.versoes.filter(pk=esperada).first()
        if versao is None or not vigente(doc, versao):
            raise ConflitoDoPedido(
                "A versão mudou. Leia o texto atual e autorize novamente a versão que deseja enviar."
            )
        if not isinstance(texto_exibido, str) or texto_exibido.replace(
            "\r\n", "\n"
        ) != versao.corpo.replace("\r\n", "\n"):
            raise ConflitoDoPedido(
                "O texto enviado não corresponde à versão salva. Seu rascunho continua abaixo; salve a revisão ou reabra a versão salva antes de autorizar."
            )
        dados = envelope(doc, versao)
        if envelope_autorizado(doc, versao):
            return next(
                registro
                for registro, gesto in _registros(doc, Registro.AUTORIZAR_PEDIDO)
                if gesto.get("pedido") == dados["pedido"]
            )
        return _auditar(
            doc, versao, admin, Registro.AUTORIZAR_PEDIDO, pedido=dados["pedido"]
        )
