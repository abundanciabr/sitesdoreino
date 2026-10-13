"""Avisos privados da prévia; não publica eventos em sistemas da comunidade."""
import asyncio
import hashlib
import json
import time

from asgiref.sync import sync_to_async
from django.db import close_old_connections
from django.http import HttpResponseNotFound, StreamingHttpResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.core.feed_previa import _permitido
from .models import FeedPreviaNotificacao as Aviso, FeedPreviaPerfil as Perfil, FeedPreviaPost as Post

TIPOS = {"like": "curtiu sua criação", "follow": "começou a seguir você",
         "comment": "comentou na sua publicação", "mention": "mencionou você em um comentário"}


def emitir(destinatario, autor, tipo, chave, post=None, comentario=None, demonstracao=False):
    if destinatario.pk == autor.pk:
        return
    if destinatario.site_host != autor.site_host or (post and post.site_host != destinatario.site_host):
        raise ValueError("O aviso pertence a outra prévia.")
    Aviso.objects.get_or_create(chave_evento=chave, defaults={"destinatario": destinatario,
        "autor": autor, "tipo": tipo, "post": post, "comentario": comentario,
        "demonstracao": demonstracao})


def retrato(eu):
    meus = Aviso.objects.filter(destinatario=eu, destinatario__site_host=eu.site_host)
    itens = [{"id": a.pk, "kind": a.tipo, "actor": a.autor.chave, "name": a.autor.nome,
        "initials": a.autor.detalhes.get("initials", "MC"), "color": a.autor.detalhes.get("color", "mine"),
        "message": TIPOS[a.tipo], "post": a.post.chave if a.post else None,
        "title": a.post.titulo if a.post else None,
        "excerpt": a.comentario.texto[:240] if a.comentario else "",
        "read": a.lida_em is not None, "read_at": a.lida_em.isoformat() if a.lida_em else None,
        "demo": a.demonstracao, "created": a.criado_em.isoformat(),
        "time": timezone.localtime(a.criado_em).strftime("%d/%m · %H:%M")}
        for a in meus.select_related("autor", "post", "comentario").order_by("-pk")[:50]]
    return {"items": itens, "unread": meus.filter(lida_em__isnull=True).count(),
            "latest": itens[0]["id"] if itens else 0}


def pulso(eu):
    close_old_connections()
    try:
        return retrato(eu)
    finally:
        close_old_connections()


@require_GET
def lista(request):
    if not _permitido(request):
        return HttpResponseNotFound()
    from apps.core.feed_previa_social import contexto, resposta
    try:
        _, eu = contexto(request)
        return resposta(retrato(eu))
    except ValueError as erro:
        return resposta({"error": str(erro)}, 400)


async def eventos(eu):
    # A conexão curta é renovada pelo EventSource, conferindo a sessão novamente.
    anterior = None
    yield "retry: 2000\n\n"
    inicio = time.monotonic()
    rodada = 0
    while time.monotonic() - inicio < 45:
        dados = await sync_to_async(pulso, thread_sensitive=True)(eu)
        serializado = json.dumps(dados, ensure_ascii=False, separators=(",", ":"))
        assinatura = hashlib.sha256(serializado.encode()).hexdigest()
        if assinatura != anterior:
            yield f"event: notifications\ndata: {serializado}\n\n"
            anterior = assinatura
        elif rodada % 10 == 0:
            yield ": conectado\n\n"
        rodada += 1
        await asyncio.sleep(1)


@require_GET
def stream(request):
    if not _permitido(request):
        return HttpResponseNotFound()
    from apps.core.feed_previa_social import contexto, resposta
    try:
        _, eu = contexto(request)
    except ValueError as erro:
        return resposta({"error": str(erro)}, 400)
    r = StreamingHttpResponse(eventos(eu), content_type="text/event-stream; charset=utf-8")
    r["Cache-Control"] = "no-store, no-cache"
    r["X-Accel-Buffering"] = "no"
    r["X-Robots-Tag"] = "noindex, nofollow"
    return r


@require_POST
def ler(request):
    if not _permitido(request):
        return HttpResponseNotFound()
    from apps.core.feed_previa_social import contexto, resposta
    try:
        _, eu = contexto(request)
        if len(request.body) > 2048:
            raise ValueError("Pedido muito grande.")
        d = json.loads(request.body)
        if not isinstance(d, dict):
            raise ValueError("Pedido inválido.")
        meus = Aviso.objects.filter(destinatario=eu, lida_em__isnull=True)
        if type(d.get("id")) is int and d["id"] > 0:
            meus = meus.filter(pk=d["id"])
        elif type(d.get("before")) is int and d["before"] >= 0:
            meus = meus.filter(pk__lte=d["before"])
        else:
            raise ValueError("Escolha a notificação.")
        meus.update(lida_em=timezone.now())
        return resposta(retrato(eu))
    except (ValueError, TypeError, json.JSONDecodeError) as erro:
        return resposta({"error": str(erro)}, 400)


@require_POST
def simular(request):
    if not _permitido(request):
        return HttpResponseNotFound()
    from apps.core.feed_previa_social import contexto, resposta, pedido, semear
    try:
        host, eu = contexto(request)
        if len(request.body) > 2048:
            raise ValueError("Pedido muito grande.")
        d = json.loads(request.body)
        if not isinstance(d, dict) or d.get("kind") not in TIPOS:
            raise ValueError("Escolha o tipo de aviso.")
        chave = pedido(d.get("request_key"))
        semear(host)
        autor = Perfil.objects.get(site_host=host, chave={"like": "lia", "follow": "davi", "comment": "caio", "mention": "nina"}[d["kind"]])
        post = Post.objects.filter(autor=eu).order_by("-pk").first() if d["kind"] != "follow" else None
        emitir(eu, autor, d["kind"], f"demo:{eu.pk}:{d['kind']}:{chave}", post=post, demonstracao=True)
        return resposta(retrato(eu))
    except (ValueError, TypeError, json.JSONDecodeError) as erro:
        return resposta({"error": str(erro)}, 400)
