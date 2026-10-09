"""Despacho dos passos, com intenção durável para WhatsApp."""

from __future__ import annotations

import logging
import os
from urllib.parse import quote

import httpx
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from . import condicoes, crm, eventos, regua, tasks
from .motor import CanalNaoSuportado
from .models import Entrega, EstadoDoAluno, Inscricao, Passo

logger = logging.getLogger(__name__)
CANAIS_QUE_SEI_ENTREGAR = frozenset({"sino", "whatsapp"})
TIMEOUT = 5.0


def despachar(inscricao: Inscricao, passo: Passo, canal: str) -> bool:
    """O motor grava Entrega na mesma transação; a rede só é tocada após commit."""
    if canal not in CANAIS_QUE_SEI_ENTREGAR:
        raise CanalNaoSuportado(
            f"a plataforma ainda nao entrega pelo canal {canal}; "
            f"hoje sai por {', '.join(sorted(CANAIS_QUE_SEI_ENTREGAR))}"
        )
    if canal == "whatsapp":
        inscricao_id, passo_id = inscricao.pk, passo.pk
        transaction.on_commit(lambda: _processar_apos_commit(inscricao_id, passo_id))
        return True
    if inscricao.origem_event_id is None:
        logger.warning(
            "inscricao %s sem origem_event_id; carta nao publicada", inscricao.pk
        )
        return False
    eventos.passo_de_jornada_devido(
        site_id=inscricao.site_id,
        destinatario_id=inscricao.destinatario_id,
        jornada_slug=inscricao.jornada.slug,
        passo_id=str(passo.pk),
        ordem=passo.ordem,
        origem_event_id=str(inscricao.origem_event_id),
    )
    transaction.on_commit(tasks.relay_apos_commit)
    return True


def _config(nome: str) -> str:
    return (os.environ.get(nome) or "").strip()


def _processar_apos_commit(inscricao_id, passo_id) -> None:
    try:
        tasks.processar_whatsapp_da_jornada(str(inscricao_id), str(passo_id))
    except Exception:  # noqa: BLE001 - o job periódico retoma a intenção persistida
        logger.exception("entrega WhatsApp da jornada ficou pendente para retomada")


def _telefone_da_pessoa(
    *, pessoa_id: str, site_id: str
) -> tuple[str | None, str | None, str]:
    """Resolve ID na identidade e telefone na passagem mais recente deste site."""
    identidade = _config("IDENTIDADE_API_URL").rstrip("/")
    token_identidade = _config("IDENTIDADE_API_TOKEN")
    alunos = _config("ALUNOS_API_URL").rstrip("/")
    token_alunos = _config("ALUNOS_API_TOKEN")
    if not all((identidade, token_identidade, alunos, token_alunos)):
        return None, None, "consulta de telefone nao configurada"
    try:
        resposta = httpx.post(
            f"{identidade}/pessoas/por-id",
            json={"id": pessoa_id},
            headers={"Authorization": f"Bearer {token_identidade}"},
            timeout=TIMEOUT,
        )
        if resposta.status_code != 200:
            return None, None, f"identidade indisponivel (HTTP {resposta.status_code})"
        pessoa = resposta.json()
        if not isinstance(pessoa, dict):
            return None, None, "resposta invalida da identidade"
        email, idioma = pessoa.get("email"), pessoa.get("idioma")
        if not isinstance(email, str) or not email:
            return None, None, "pessoa sem endereco na identidade"
        resposta = httpx.get(
            f"{alunos}/alunos/{quote(email, safe='')}/prontuario",
            headers={"Authorization": f"Bearer {token_alunos}"},
            timeout=TIMEOUT,
        )
        if resposta.status_code != 200:
            return None, None, f"prontuario indisponivel (HTTP {resposta.status_code})"
        prontuario = resposta.json()
        if not isinstance(prontuario, dict) or not isinstance(
            prontuario.get("passagens"), list
        ):
            return None, None, "resposta invalida do prontuario"
        # O WhatsApp do topo mistura sites; cada jornada só usa sua passagem.
        passagens = [
            p
            for p in prontuario["passagens"]
            if isinstance(p, dict) and p.get("site_id") == site_id
        ]
        if not passagens:
            return None, None, "pessoa sem passagem neste site"
        telefone = passagens[-1].get("whatsapp")
        if not isinstance(telefone, str) or not telefone.strip():
            return None, None, "telefone ausente neste site"
        return telefone.strip(), idioma if isinstance(idioma, str) else None, ""
    except (httpx.HTTPError, ValueError) as erro:
        logger.warning("consulta de contato da jornada falhou: %s", type(erro).__name__)
        return None, None, "consulta de telefone indisponivel"


def _texto(passo: Passo, idioma: str | None) -> str | None:
    textos = {t.idioma.lower(): t for t in passo.textos.all()}
    idioma = (idioma or "pt-br").lower()
    texto = (
        textos.get(idioma) or textos.get(idioma.split("-")[0]) or textos.get("pt-br")
    )
    return texto.corpo if texto is not None else None


def _referencia(entrega: Entrega) -> str:
    return f"{entrega.inscricao_id}:{entrega.passo_id}:whatsapp"


def _atualizar(entrega: Entrega, status: str, erro: str = "") -> None:
    mapa = {
        "aceito": "aceita_pelo_gateway",
        "desconhecido": "resultado_desconhecido",
        "falhou": "falhou",
        "enviado": "enviada",
        "entregue": "entregue",
        "lido": "lida",
    }
    resultado = mapa.get(status, "resultado_desconhecido")
    entrega.resultado = resultado
    entrega.motivo = (erro or "")[:200]
    if resultado in {"enviada", "entregue", "lida"} and entrega.enviado_em is None:
        entrega.enviado_em = timezone.now()
    entrega.save(update_fields=["resultado", "motivo", "enviado_em"])


def processar_entrega(*, inscricao_id, passo_id) -> None:
    """Envia ou sincroniza intenção confirmada, sem repetir resultado incerto."""
    from apps.whatsapp.service import consultar_mensagem, enviar_mensagem

    entrega = (
        Entrega.objects.select_related("inscricao", "passo")
        .filter(
            inscricao_id=inscricao_id,
            passo_id=passo_id,
            canal="whatsapp",
            whatsapp_intencao=True,
        )
        .first()
    )
    if entrega is None or entrega.resultado not in {
        "pendente",
        "falhou",
        "aceita_pelo_gateway",
        "resultado_desconhecido",
        "enviada",
    }:
        return
    referencia = _referencia(entrega)
    existente = consultar_mensagem(
        site_id=entrega.inscricao.site_id,
        origem="jornada",
        referencia=referencia,
    )
    if existente is not None and existente.status != "falhou":
        _atualizar(entrega, existente.status, getattr(existente, "erro", ""))
        from apps.links import servico as links_servico

        # Retomada: o texto guardado já tem os links individuais.
        links_ret = links_servico.links_do_texto(
            getattr(existente, "corpo", ""), site_id=entrega.inscricao.site_id)
        if existente.status in {"aceito", "enviado", "entregue", "lido"}:
            links_servico.marcar_enviados(links_ret)
        if entrega.inscricao.oportunidade_id:
            try:
                crm.registrar_na_conversa(
                    entrega, telefone=existente.destinatario, corpo=existente.corpo,
                    mensagem_whatsapp=existente, links=links_ret,
                )
            except Exception:  # noqa: BLE001 - histórico; o envio já aconteceu
                logger.exception("jornada: mensagem enviada não entrou na conversa")
            crm.registrar_contato(entrega)
        return
    if entrega.inscricao.estado in {"cancelada", "saiu"}:
        entrega.resultado, entrega.motivo = "pulada", "jornada encerrada antes do envio"
        entrega.save(update_fields=["resultado", "motivo"])
        return
    projecao = EstadoDoAluno.objects.filter(
        destinatario_id=entrega.inscricao.destinatario_id,
        site_id=entrega.inscricao.site_id,
    ).first()
    try:
        vale = condicoes.avaliar(entrega.passo.condicao_slug, projecao, timezone.now())
    except condicoes.CondicaoDesconhecida:
        vale = False
    if not vale:
        entrega.resultado, entrega.motivo = (
            "pulada",
            "condicao deixou de valer antes do envio",
        )
        entrega.save(update_fields=["resultado", "motivo"])
        return
    veredito = regua.avaliar(
        destinatario_id=entrega.inscricao.destinatario_id,
        site_id=entrega.inscricao.site_id,
        canal="whatsapp",
        classe=entrega.passo.classe,
        momento=timezone.now(),
        mensagem=(entrega.inscricao_id, entrega.passo_id),
    )
    if veredito.barrada:
        if veredito.resultado == "barrada_por_preferencia":
            entrega.resultado, entrega.motivo = (
                veredito.resultado,
                veredito.motivo[:200],
            )
            entrega.save(update_fields=["resultado", "motivo"])
        return
    # A oportunidade pode ter mudado entre a varredura e este envio (compra
    # aprovada, pessoa da equipe assumiu, lead respondeu): confere de novo.
    conferencia = crm.conferir(entrega.inscricao, entrega.passo, timezone.now())
    if conferencia.decisao == crm.INDISPONIVEL:
        entrega.motivo = conferencia.motivo[:200]
        entrega.save(update_fields=["motivo"])
        return  # fica pendente; a retomada periódica tenta de novo
    if conferencia.decisao in (crm.ENCERRA, crm.NAO_SAI):
        entrega.resultado, entrega.motivo = "pulada", f"CRM: {conferencia.motivo}"[:200]
        entrega.save(update_fields=["resultado", "motivo"])
        if conferencia.decisao == crm.ENCERRA:
            crm.encerrar_oportunidade(entrega.inscricao, conferencia.motivo)
        return
    if "whatsapp" in conferencia.canais_barrados:
        entrega.resultado = "barrada_por_preferencia"
        entrega.motivo = conferencia.canais_barrados["whatsapp"][:200]
        entrega.save(update_fields=["resultado", "motivo"])
        return
    if entrega.inscricao.oportunidade_id:
        # Lead do quiz: o telefone é o que ele deixou no quiz, pelo CRM.
        telefone, idioma = conferencia.telefone or None, None
        motivo = "" if telefone else "lead sem telefone no CRM"
    else:
        telefone, idioma, motivo = _telefone_da_pessoa(
            pessoa_id=entrega.inscricao.destinatario_id,
            site_id=entrega.inscricao.site_id,
        )
    if not telefone:
        _atualizar(entrega, "falhou", motivo)
        return
    if entrega.passo.classe not in regua.CLASSES_FORA_DA_REGUA:
        from apps.consentimentos.servico import permite_whatsapp_proativo

        if not permite_whatsapp_proativo(
            entrega.inscricao.site_id,
            telefone,
            destinatario_id=entrega.inscricao.destinatario_id,
            classe=entrega.passo.classe,
        ):
            entrega.resultado = "barrada_por_preferencia"
            entrega.motivo = "a pessoa nao autorizou contato pelo WhatsApp"
            entrega.save(update_fields=["resultado", "motivo"])
            return
    corpo = _texto(entrega.passo, idioma)
    if not corpo:
        _atualizar(entrega, "falhou", "texto do passo ausente")
        return
    from apps.links import servico as links_servico

    corpo, links = links_servico.reescrever(
        corpo, site_id=entrega.inscricao.site_id, origem="jornada", referencia=referencia,
        jornada_slug=entrega.inscricao.jornada.slug, inscricao_id=entrega.inscricao_id,
        passo_id=entrega.passo_id)
    mensagem = enviar_mensagem(
        site_id=entrega.inscricao.site_id,
        destinatario=telefone,
        corpo=corpo,
        origem="jornada",
        referencia=referencia,
    )
    _atualizar(entrega, mensagem.status, getattr(mensagem, "erro", ""))
    if links and mensagem.status in {"aceito", "enviado", "entregue", "lido"}:
        links_servico.marcar_enviados(links)
    if entrega.inscricao.oportunidade_id:
        try:
            crm.registrar_na_conversa(
                entrega, telefone=telefone, corpo=corpo, mensagem_whatsapp=mensagem, links=links
            )
        except Exception:  # noqa: BLE001 - o envio já aconteceu; não reenviar
            logger.exception("jornada: mensagem enviada não entrou na conversa")
        crm.registrar_contato(entrega)


def processar_pendentes(lote: int = 200) -> int:
    """Retoma falhas explícitas e acompanha confirmações posteriores do gateway."""
    linhas = list(
        Entrega.objects.filter(
            canal="whatsapp",
            whatsapp_intencao=True,
            resultado__in=(
                "pendente",
                "falhou",
                "aceita_pelo_gateway",
                "resultado_desconhecido",
                "enviada",
            ),
        )
        .order_by(F("whatsapp_verificado_em").asc(nulls_first=True), "decidida_em")[
            :lote
        ]
        .values_list("inscricao_id", "passo_id")
    )
    for inscricao_id, passo_id in linhas:
        try:
            Entrega.objects.filter(
                inscricao_id=inscricao_id,
                passo_id=passo_id,
                canal="whatsapp",
            ).update(whatsapp_verificado_em=timezone.now())
            processar_entrega(inscricao_id=inscricao_id, passo_id=passo_id)
        except Exception:  # noqa: BLE001 - intenção fica durável para próxima passada
            logger.exception("falha ao processar entrega WhatsApp de jornada")
    return len(linhas)
