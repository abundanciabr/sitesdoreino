"""Orquestração: eventos recentes -> adaptadores configurados -> IntegracaoEnvio."""

from __future__ import annotations

import os
from datetime import timedelta

from django.utils import timezone

from ..models import Submission, TelemetryEvent
from . import activecampaign, ga4, klaviyo, meta, tiktok
from .models import IntegracaoEnvio
from .nucleo import ErroEnvio, Evento, configurado, limpar, mascarar, transporte_urllib

ADAPTADORES = {
    modulo.SERVICO: modulo for modulo in (ga4, meta, tiktok, klaviyo, activecampaign)
}
MAX_TENTATIVAS = 5
# Chaves de `Submission.context` aceitas como flag de consentimento de marketing.
# Ausente = consentiu (o formulário atual não coleta); presente e falsa = não.
CHAVES_CONSENTIMENTO = ("consent", "consentimento", "mkt")
_FALSOS = {"0", "false", "nao", "não", "no", "off", "negado", "denied"}


def consentiu(contexto: dict) -> bool:
    for chave in CHAVES_CONSENTIMENTO:
        if chave in (contexto or {}):
            valor = contexto[chave]
            if isinstance(valor, str):
                return valor.strip().lower() not in _FALSOS
            return bool(valor)
    return True


def _oferta(submissao: Submission) -> str:
    dados = submissao.version.experience or {}
    return str((dados.get("band_offers") or {}).get(submissao.result_key) or "")


def evento_da_submissao(submissao: Submission) -> Evento:
    contexto = submissao.context or {}
    return Evento(
        tipo="quiz_complete",
        chave=f"sub:{submissao.id}",
        event_id=str(submissao.id),
        email=submissao.lead_email,
        nome=submissao.lead_name,
        quiz_slug=submissao.quiz.slug,
        version_key=submissao.version.key,
        result_key=submissao.result_key,
        score=submissao.score,
        oferta=_oferta(submissao),
        contexto=contexto,
        utm=submissao.utm or {},
        ocorreu=submissao.created_at,
        semente_cliente=str(submissao.session_id or submissao.id),
        consentiu=consentiu(contexto),
    )


def evento_da_saida(telemetria: TelemetryEvent) -> Evento:
    submissao = (
        Submission.objects.select_related("quiz", "version")
        .filter(session_id=telemetria.session_id, quiz__slug=telemetria.quiz_slug)
        .first()
    )
    meta_ev = telemetria.metadata or {}
    contexto = (submissao.context if submissao else meta_ev.get("context")) or {}
    return Evento(
        tipo="quiz_offer_exit",
        chave=f"exit:{telemetria.pk}",
        event_id=str(submissao.id) if submissao else f"exit-{telemetria.pk}",
        email=submissao.lead_email if submissao else "",
        nome="",
        quiz_slug=telemetria.quiz_slug,
        version_key=telemetria.version_key,
        result_key=submissao.result_key if submissao else telemetria.element_id,
        score=submissao.score if submissao else 0,
        oferta=_oferta(submissao) if submissao else "",
        contexto=contexto,
        utm=(submissao.utm if submissao else meta_ev.get("utm")) or {},
        ocorreu=telemetria.occurred_at,
        semente_cliente=str(telemetria.session_id),
        consentiu=consentiu(contexto),
        demonstracao=bool(meta_ev.get("demonstracao")),
    )


def eventos_recentes(dias: int = 7) -> list[Evento]:
    desde = timezone.now() - timedelta(days=dias)
    subs = (
        Submission.objects.select_related("quiz", "version")
        .filter(created_at__gte=desde)
        .order_by("created_at")
    )
    saidas = TelemetryEvent.objects.filter(
        event_type="checkout_exit", occurred_at__gte=desde
    ).order_by("occurred_at")
    return [evento_da_submissao(s) for s in subs] + [
        evento_da_saida(t) for t in saidas
    ]


def servicos_configurados(env=None, so=None) -> dict:
    env = os.environ if env is None else env
    nomes = [so] if so else list(ADAPTADORES)
    return {
        nome: configurado(env, *ADAPTADORES[nome].VARIAVEIS) for nome in nomes
    }


def payloads_mascarados(evento: Evento, env=None, so=None) -> list[dict]:
    """O que seria enviado, sem segredo e sem e-mail em claro. Para --dry-run.
    Serviços sem variável saem com placeholders para o payload ser visível."""
    env = os.environ if env is None else env
    saida = []
    for nome, adaptador in ADAPTADORES.items():
        if (so and nome != so) or evento.tipo not in adaptador.TIPOS:
            continue
        ambiente = {v: env.get(v) or f"<{v}>" for v in adaptador.VARIAVEIS}
        ambiente.update({k: v for k, v in env.items() if k.startswith(("META_TEST", "TIKTOK_TEST", "KLAVIYO_LIST", "AC_LIST"))})
        for req in adaptador.requisicoes(evento, ambiente):
            saida.append(
                {
                    "servico": nome,
                    "chave": evento.chave,
                    "metodo": req.metodo,
                    "url": mascarar(req.url, ambiente),
                    "headers": {k: "***" for k in req.headers},
                    "corpo": mascarar(req.corpo, ambiente),
                }
            )
    return saida


def enviar_evento(evento, env, transporte, so=None) -> list[tuple[str, str]]:
    resultados = []
    for nome, adaptador in ADAPTADORES.items():
        if (so and nome != so) or evento.tipo not in adaptador.TIPOS:
            continue
        registro, _ = IntegracaoEnvio.objects.get_or_create(
            servico=nome, chave_evento=evento.chave
        )
        if registro.status == "aceito":
            continue
        if registro.status == "falhou" and registro.tentativas >= MAX_TENTATIVAS:
            continue
        if not configurado(env, *adaptador.VARIAVEIS):
            registro.status = "nao_configurado"
            registro.ultimo_erro = ""
            registro.save(update_fields=["status", "ultimo_erro", "atualizado_em"])
            resultados.append((nome, "nao_configurado"))
            continue
        if adaptador.USA_DADO_PESSOAL and (not evento.consentiu or not evento.email):
            registro.status = "sem_consentimento"
            registro.save(update_fields=["status", "atualizado_em"])
            resultados.append((nome, "sem_consentimento"))
            continue
        registro.tentativas += 1
        try:
            resumo = adaptador.enviar(evento, env, transporte)
        except ErroEnvio as erro:
            registro.status, registro.ultimo_erro = "falhou", limpar(erro, env)
        except Exception as erro:  # noqa: BLE001 - nunca deixa a mensagem vazar token
            registro.status = "falhou"
            registro.ultimo_erro = f"{type(erro).__name__}: {limpar(erro, env)}"
        else:
            registro.status, registro.ultimo_erro = "aceito", ""
            registro.enviado_em = timezone.now()
            registro.resposta = {
                k: v for k, v in (resumo or {}).items() if isinstance(v, (int, str, bool, type(None)))
            }
        registro.save()
        resultados.append((nome, registro.status))
    return resultados


def enviar_pendentes(env=None, transporte=None, dias=7, so=None) -> dict:
    """Contagem por (serviço, status) desta rodada."""
    env = os.environ if env is None else env
    transporte = transporte or transporte_urllib
    contagem: dict[str, int] = {}
    for evento in eventos_recentes(dias):
        for nome, status in enviar_evento(evento, env, transporte, so):
            contagem[f"{nome}:{status}"] = contagem.get(f"{nome}:{status}", 0) + 1
    return contagem


def estado_integracoes(env=None) -> dict:
    """Por serviço: configurado, último aceito e última falha (para o painel)."""
    env = os.environ if env is None else env
    saida = {}
    for nome, adaptador in ADAPTADORES.items():
        registros = IntegracaoEnvio.objects.filter(servico=nome)
        aceito = registros.filter(status="aceito").order_by("-enviado_em").first()
        falha = registros.filter(status="falhou").order_by("-atualizado_em").first()
        saida[nome] = {
            "configurado": configurado(env, *adaptador.VARIAVEIS),
            "variaveis": list(adaptador.VARIAVEIS),
            "ultimo_aceito": aceito.enviado_em if aceito else None,
            "ultima_falha": (
                {"em": falha.atualizado_em, "erro": falha.ultimo_erro} if falha else None
            ),
        }
    return saida


# ------------------------------------------------------ público (Q36)


def publico_retargeting(versao_key, compradores=(), quiz_slug=None, dias=None):
    """E-mails de quem concluiu a versão `versao_key` (ex. "B2") e não comprou.

    `compradores`: iterável de e-mails, ou função sem argumentos que o devolve
    (a integração de pedidos ainda não existe; quem a tiver injeta aqui).
    Exclui quem tem consentimento explicitamente falso no `context`
    (chaves em CHAVES_CONSENTIMENTO). Um item por e-mail, o mais recente.
    """
    if callable(compradores):
        compradores = compradores()
    excluidos = {(e or "").strip().lower() for e in compradores}
    consulta = Submission.objects.select_related("quiz", "version").filter(
        version__key=versao_key
    )
    if quiz_slug:
        consulta = consulta.filter(quiz__slug=quiz_slug)
    if dias:
        consulta = consulta.filter(created_at__gte=timezone.now() - timedelta(days=dias))
    publico = {}
    for sub in consulta.order_by("created_at"):
        email = sub.lead_email.strip().lower()
        if not email or email in excluidos:
            continue
        if not consentiu(sub.context):  # a tentativa mais recente manda
            publico.pop(email, None)
            continue
        publico[email] = {
            "email": email,
            "submission_id": str(sub.id),
            "resultado": sub.result_key,
            "oferta": _oferta(sub),
            "concluiu_em": sub.created_at,
        }
    return list(publico.values())
