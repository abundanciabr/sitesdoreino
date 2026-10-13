"""Conversas entre participantes da prévia privada, sem eventos de alunos ou XP."""
import asyncio
import json
import time

from asgiref.sync import sync_to_async
from django.db import close_old_connections, transaction
from django.db.models import Count, OuterRef, Q, Subquery
from django.http import HttpResponseNotFound, StreamingHttpResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.core.feed_previa import _permitido
from apps.core.feed_previa_social import contexto, pedido, resposta, texto
from .models import FeedPreviaConversa as Conversa, FeedPreviaMensagem as Mensagem, FeedPreviaPerfil as Perfil


def minhas(eu):
    return Conversa.objects.filter(site_host=eu.site_host,
        participante_a__site_host=eu.site_host, participante_b__site_host=eu.site_host).filter(
        Q(participante_a=eu) | Q(participante_b=eu))


def encontrar(eu, chave):
    return minhas(eu).get(pk=pedido(chave))


def outro(c, eu):
    return c.participante_b if c.participante_a_id == eu.pk else c.participante_a


def pessoa(p):
    return {"key": p.chave, "name": p.nome, "handle": p.handle, "demo": p.demonstracao,
        "initials": p.detalhes.get("initials", "MC"), "color": p.detalhes.get("color", "mine")}


def mensagem(m, eu):
    return {"id": m.pk, "text": m.texto, "mine": m.autor_id == eu.pk,
        "demo": m.demonstracao, "read": m.lida_em is not None,
        "created": m.criado_em.isoformat(), "time": timezone.localtime(m.criado_em).strftime("%d/%m · %H:%M")}


def historico(c, eu, antes=None):
    registros = c.mensagens.all()
    if antes is not None:
        registros = registros.filter(pk__lt=antes)
    ultimas = list(registros.order_by("-pk")[:51])
    return {"id": str(c.pk), "peer": pessoa(outro(c, eu)),
        "messages": [mensagem(m, eu) for m in reversed(ultimas[:50])], "has_more": len(ultimas) > 50}


def retrato(eu, selecionada=None):
    ultima = Mensagem.objects.filter(conversa=OuterRef("pk")).order_by("-pk")
    conversas = minhas(eu).select_related("participante_a", "participante_b").annotate(
        ultimo_id=Subquery(ultima.values("id")[:1]), ultimo_texto=Subquery(ultima.values("texto")[:1]),
        ultimo_demo=Subquery(ultima.values("demonstracao")[:1]),
        ultimo_autor=Subquery(ultima.values("autor_id")[:1]),
        nao_lidas=Count("mensagens", filter=Q(mensagens__lida_em__isnull=True) & ~Q(mensagens__autor=eu)),
    ).order_by("-ultimo_id", "-criado_em")
    itens = [{"id": str(c.pk), "peer": pessoa(outro(c, eu)), "unread": c.nao_lidas,
        "last": (c.ultimo_texto or "Sua conversa começa aqui.")[:160],
        "last_id": c.ultimo_id or 0, "last_demo": bool(c.ultimo_demo), "last_mine": c.ultimo_autor == eu.pk} for c in conversas]
    dados = {"conversations": itens, "unread": sum(c["unread"] for c in itens),
        "latest": max((c["last_id"] for c in itens), default=0)}
    if selecionada:
        dados["chat"] = historico(encontrar(eu, selecionada), eu)
    return dados


def corpo(request):
    if len(request.body) > 24000:
        raise ValueError("A mensagem está muito grande.")
    d = json.loads(request.body)
    if not isinstance(d, dict):
        raise ValueError("Pedido inválido.")
    return d


@require_GET
def lista(request):
    if not _permitido(request):
        return HttpResponseNotFound()
    try:
        _, eu = contexto(request)
        return resposta(retrato(eu))
    except ValueError as erro:
        return resposta({"error": str(erro)}, 400)


@require_POST
@transaction.atomic
def iniciar(request):
    if not _permitido(request):
        return HttpResponseNotFound()
    try:
        host, eu = contexto(request)
        d = corpo(request)
        chave = texto(d.get("profile"), 80, "o destinatário")
        par = Perfil.objects.get(site_host=host, chave=chave)
        if par.pk == eu.pk:
            raise ValueError("Escolha outro participante.")
        a, b = sorted([eu.pk, par.pk])
        c, _ = Conversa.objects.get_or_create(participante_a_id=a, participante_b_id=b, defaults={"site_host": host})
        return resposta(retrato(eu, c.pk))
    except Perfil.DoesNotExist:
        transaction.set_rollback(True)
        return HttpResponseNotFound()
    except (ValueError, TypeError, json.JSONDecodeError) as erro:
        transaction.set_rollback(True)
        return resposta({"error": str(erro)}, 400)


@require_GET
def conversa(request, conversa_id):
    if not _permitido(request):
        return HttpResponseNotFound()
    try:
        _, eu = contexto(request)
        antes = request.GET.get("before")
        if antes is not None:
            antes = int(antes)
            if antes <= 0:
                raise ValueError("Histórico inválido.")
        return resposta(historico(encontrar(eu, conversa_id), eu, antes))
    except Conversa.DoesNotExist:
        return HttpResponseNotFound()
    except (ValueError, TypeError) as erro:
        return resposta({"error": str(erro)}, 400)


@require_POST
@transaction.atomic
def enviar(request):
    if not _permitido(request):
        return HttpResponseNotFound()
    try:
        _, eu = contexto(request)
        d = corpo(request)
        c = encontrar(eu, d.get("conversation"))
        c = Conversa.objects.select_for_update().get(pk=c.pk)
        t = texto(d.get("text"), 4000, "a mensagem")
        m, criada = Mensagem.objects.get_or_create(conversa=c, chave_pedido=pedido(d.get("request_key")),
            defaults={"autor": eu, "texto": t})
        if not criada and (m.autor_id != eu.pk or m.texto != t or m.demonstracao):
            raise ValueError("Este envio já identifica outra mensagem.")
        return resposta(retrato(eu, c.pk))
    except Conversa.DoesNotExist:
        transaction.set_rollback(True)
        return HttpResponseNotFound()
    except (ValueError, TypeError, json.JSONDecodeError) as erro:
        transaction.set_rollback(True)
        return resposta({"error": str(erro)}, 400)


@require_POST
def ler(request):
    if not _permitido(request):
        return HttpResponseNotFound()
    try:
        _, eu = contexto(request)
        d = corpo(request)
        c = encontrar(eu, d.get("conversation"))
        corte = d.get("before")
        if type(corte) is not int or corte < 0:
            raise ValueError("Escolha as mensagens recebidas.")
        c.mensagens.filter(pk__lte=corte, lida_em__isnull=True).exclude(autor=eu).update(lida_em=timezone.now())
        return resposta(retrato(eu, c.pk))
    except Conversa.DoesNotExist:
        return HttpResponseNotFound()
    except (ValueError, TypeError, json.JSONDecodeError) as erro:
        return resposta({"error": str(erro)}, 400)


@require_POST
@transaction.atomic
def simular(request):
    if not _permitido(request):
        return HttpResponseNotFound()
    try:
        _, eu = contexto(request)
        d = corpo(request)
        c = encontrar(eu, d.get("conversation"))
        c = Conversa.objects.select_for_update().get(pk=c.pk)
        par = outro(c, eu)
        if not par.demonstracao:
            raise ValueError("A simulação está disponível apenas com um perfil fictício.")
        t = "Resposta simulada para testar a conversa privada: recebi sua mensagem! Podemos trocar ideias sobre a criação e o portfólio. 🚀"
        m, criada = Mensagem.objects.get_or_create(conversa=c, chave_pedido=pedido(d.get("request_key")),
            defaults={"autor": par, "texto": t, "demonstracao": True})
        if not criada and (m.autor_id != par.pk or not m.demonstracao):
            raise ValueError("Este envio já identifica outra mensagem.")
        return resposta(retrato(eu, c.pk))
    except Conversa.DoesNotExist:
        transaction.set_rollback(True)
        return HttpResponseNotFound()
    except (ValueError, TypeError, json.JSONDecodeError) as erro:
        transaction.set_rollback(True)
        return resposta({"error": str(erro)}, 400)


def pulso(eu, selecionada):
    close_old_connections()
    try:
        return retrato(eu, selecionada)
    finally:
        close_old_connections()


async def eventos(eu, selecionada):
    anterior = None
    yield "retry: 2000\n\n"
    inicio = time.monotonic()
    rodada = 0
    while time.monotonic() - inicio < 45:
        try:
            dados = await sync_to_async(pulso, thread_sensitive=True)(eu, selecionada)
        except Conversa.DoesNotExist:
            return
        serializado = json.dumps(dados, ensure_ascii=False, separators=(",", ":"))
        if serializado != anterior:
            yield f"event: messages\ndata: {serializado}\n\n"
            anterior = serializado
        elif rodada % 10 == 0:
            yield ": conectado\n\n"
        rodada += 1
        await asyncio.sleep(1)


@require_GET
def stream(request):
    if not _permitido(request):
        return HttpResponseNotFound()
    try:
        _, eu = contexto(request)
        selecionada = request.GET.get("conversation")
        if selecionada:
            selecionada = encontrar(eu, selecionada).pk
    except Conversa.DoesNotExist:
        return HttpResponseNotFound()
    except ValueError as erro:
        return resposta({"error": str(erro)}, 400)
    r = StreamingHttpResponse(eventos(eu, selecionada), content_type="text/event-stream; charset=utf-8")
    r["Cache-Control"] = "no-store, no-cache"
    r["X-Accel-Buffering"] = "no"
    r["X-Robots-Tag"] = "noindex, nofollow"
    return r
