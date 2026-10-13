"""Operações da rede social privada de demonstração, sem eventos da comunidade real."""
import hashlib
import io
import json
import re
import uuid
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.db import transaction
from django.db.models import Count, Prefetch
from django.http import HttpResponse, HttpResponseNotFound, JsonResponse
from django.urls import reverse
from django.utils.text import slugify
from django.views.decorators.http import require_GET, require_POST

from .feed_previa import _permitido
from apps.feed_previa.models import (FeedPreviaPerfil as Perfil, FeedPreviaPost as Post,
    FeedPreviaInteracao as Interacao, FeedPreviaComentario as Comentario,
    FeedPreviaPreferencia as Preferencia, FeedPreviaArquivo as Arquivo)

SEMENTE = json.loads(Path(__file__).with_name("feed_previa_seed.json").read_text(encoding="utf-8"))
JOBS = {"props", "team", "ugcjob"}
CATEGORIAS = {"creation", "evolution", "result", "help"}


def resposta(dados, status=200):
    r = JsonResponse(dados, status=status)
    r["Cache-Control"] = "no-store"
    r["X-Robots-Tag"] = "noindex, nofollow"
    return r


def contexto(request):
    host = request.get_host().split(":")[0].lower()
    identidade = str(request.admin.get("id") or "")
    if not identidade:
        raise ValueError("A sessão administrativa não foi reconhecida.")
    chave = "admin-" + hashlib.sha256(identidade.encode()).hexdigest()[:20]
    nome = str(request.admin.get("nome") or "Admin").strip()
    if "@" in nome:
        nome = "Admin"
    perfil, _ = Perfil.objects.get_or_create(site_host=host, chave=chave, defaults={
        "handle": (slugify(nome)[:50] or "admin") + "-" + chave[-6:],
        "nome": nome[:100] + " · prévia", "detalhes": {
            "initials": "".join(p[0] for p in nome.split()[:2]).upper() or "EU",
            "color": "mine", "focus": "Construindo minha história", "city": "Perfil administrativo da prévia",
            "tools": ["Blender", "Roblox"], "quote": "Minha próxima conquista começa com uma criação.",
            "badge": "Dev Aprendiz", "path": "Prévia"}})
    return host, perfil


def semear(host):
    # Idempotente e restrito às tabelas admin_feed_previa_*.
    for pessoa in SEMENTE["people"]:
        Perfil.objects.get_or_create(site_host=host, chave=pessoa["id"], defaults={
            "nome": pessoa["name"], "handle": slugify(pessoa["name"]),
            "demonstracao": True, "detalhes": {k: v for k, v in pessoa.items() if k not in {"id", "name"}}})
    for post in SEMENTE["posts"]:
        Post.objects.get_or_create(site_host=host, chave=post["id"], defaults={
            "autor": Perfil.objects.get(site_host=host, chave=post["author"]),
            "categoria": post["kind"], "titulo": post["title"], "texto": post["story"],
            "detalhes": {k: v for k, v in post.items() if k not in {"id", "author", "kind", "title", "story"}}})


def bootstrap(host, eu):
    perfis = list(Perfil.objects.filter(site_host=host).order_by("demonstracao", "pk"))
    interacoes = Interacao.objects.filter(autor__site_host=host, ativa=True)
    totais = {(r["tipo"], r["alvo"]): r["n"] for r in interacoes.values("tipo", "alvo").annotate(n=Count("id"))}
    minhas = list(interacoes.filter(autor=eu).values("tipo", "alvo", "quantidade"))
    preferencias = Preferencia.objects.filter(autor=eu).first()
    detalhes = preferencias.detalhes if preferencias else {}
    pessoas = [{**p.detalhes, "id": "me" if p.pk == eu.pk else p.chave, "key": p.chave,
        "name": p.nome, "handle": p.handle, "demo": p.demonstracao,
        "followers": totais.get(("follow", p.chave), 0),
        "following": interacoes.filter(autor=p, tipo="follow").count()} for p in perfis]
    aliases = {p.pk: "me" if p.pk == eu.pk else p.chave for p in perfis}
    posts = []
    for p in Post.objects.filter(site_host=host).select_related("autor").prefetch_related(
            "comentarios__autor", Prefetch("arquivos", queryset=Arquivo.objects.only("id", "post_id", "tipo"))).order_by("-criado_em", "-pk"):
        arquivos = [{"url": reverse("feed_previa_arquivo", args=[a.pk]), "tipo": a.tipo}
                    for a in p.arquivos.all()]
        comentarios = [*p.detalhes.get("comments", []), *[
            {"id": c.pk, "author": aliases[c.autor_id], "name": c.autor.nome,
             "text": c.texto, "mentions": c.mencoes} for c in p.comentarios.all()]]
        posts.append({"id": p.chave, "author": aliases[p.autor_id], "kind": p.categoria,
            "title": p.titulo, "story": p.texto, "art": p.detalhes.get("art", "sword"),
            "tags": p.detalhes.get("tags", []), "amount": p.detalhes.get("amount", 0),
            "time": p.detalhes.get("time") or p.criado_em.strftime("%d/%m/%Y · %H:%M · prévia"),
            "demo": p.autor.demonstracao, "images": [a["url"] for a in arquivos if a["tipo"].startswith("image/")],
            "video": next((a["url"] for a in arquivos if a["tipo"].startswith("video/")), None),
            "likes": p.detalhes.get("likes", 0) + totais.get(("like", p.chave), 0),
            "views": totais.get(("view", p.chave), 0), "saves": totais.get(("save", p.chave), 0),
            "comments": comentarios})
    return {"people": pessoas, "state": {"posts": posts,
        "likes": [r["alvo"] for r in minhas if r["tipo"] == "like"],
        "saved": [r["alvo"] for r in minhas if r["tipo"] == "save"],
        "follows": [r["alvo"] for r in minhas if r["tipo"] == "follow"],
        "viewed": [r["alvo"] for r in minhas if r["tipo"] == "view"],
        "shares": {r["alvo"]: r["quantidade"] for r in minhas if r["tipo"] == "share"},
        "comments": {}, "proposal": detalhes.get("proposal", 0),
        "applications": detalhes.get("applications", []), "applicationStories": detalhes.get("applicationStories", {})}}


@require_GET
def dados(request):
    if not _permitido(request):
        return HttpResponseNotFound()
    try:
        host, eu = contexto(request)
    except ValueError as erro:
        return resposta({"error": str(erro)}, 400)
    semear(host)
    return resposta(bootstrap(host, eu))


def texto(valor, maximo, nome):
    if not isinstance(valor, str) or not valor.strip() or len(valor) > maximo:
        raise ValueError(f"Confira {nome}.")
    return valor.strip()


def pedido(valor):
    try:
        return uuid.UUID(str(valor))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Não foi possível identificar este envio.") from None


@require_POST
@transaction.atomic
def acao(request):
    if not _permitido(request):
        return HttpResponseNotFound()
    try:
        host, eu = contexto(request)
        if len(request.body) > 65536:
            raise ValueError("O pedido está muito grande.")
        d = json.loads(request.body)
        if not isinstance(d, dict):
            raise ValueError("Pedido inválido.")
        op = d.get("op")
        if op == "view":
            ids = d.get("posts")
            if not isinstance(ids, list) or len(ids) > 100 or any(not isinstance(i, str) for i in ids):
                raise ValueError("Visualizações inválidas.")
            posts = list(Post.objects.filter(site_host=host, chave__in=ids))
            for post in posts:
                Interacao.objects.get_or_create(autor=eu, tipo="view", alvo=post.chave)
            contagens = {p.chave: Interacao.objects.filter(autor__site_host=host, tipo="view", alvo=p.chave, ativa=True).count() for p in posts}
            return resposta({"views": contagens})
        elif op in {"like", "save", "share", "comment"}:
            post = Post.objects.get(site_host=host, chave=d.get("post"))
            if op == "comment":
                corpo = texto(d.get("text"), 2400, "o comentário")
                handles = set(re.findall(r"(?<!\S)@([\w-]+)", corpo))
                mencoes = list(Perfil.objects.filter(site_host=host, handle__in=handles).values_list("handle", flat=True))
                comentario, criado = Comentario.objects.get_or_create(autor=eu, chave_pedido=pedido(d.get("request_key")),
                    defaults={"post": post, "texto": corpo, "mencoes": mencoes})
                if not criado and (comentario.post_id != post.pk or comentario.texto != corpo):
                    raise ValueError("Este envio já foi usado em outro comentário.")
            else:
                registro, _ = Interacao.objects.get_or_create(autor=eu, tipo=op, alvo=post.chave)
                registro = Interacao.objects.select_for_update().get(pk=registro.pk)
                if op == "share":
                    chave = pedido(d.get("request_key"))
                    if registro.ultima_chave != chave:
                        registro.quantidade += 1
                        registro.ultima_chave = chave
                        registro.save()
                else:
                    if type(d.get("active")) is not bool:
                        raise ValueError("Escolha o estado da interação.")
                    registro.ativa = d["active"]
                    registro.save()
        elif op == "follow":
            alvo = Perfil.objects.get(site_host=host, chave=d.get("profile"))
            if alvo.pk == eu.pk or type(d.get("active")) is not bool:
                raise ValueError("Escolha outro criador para seguir.")
            registro, _ = Interacao.objects.get_or_create(autor=eu, tipo="follow", alvo=alvo.chave)
            registro.ativa = d["active"]
            registro.save()
        elif op in {"proposal", "application"}:
            registro, _ = Preferencia.objects.get_or_create(autor=eu)
            registro = Preferencia.objects.select_for_update().get(pk=registro.pk)
            if op == "proposal":
                if type(d.get("level")) is not int or d["level"] not in range(4):
                    raise ValueError("Selo proposto inválido.")
                registro.detalhes["proposal"] = d["level"]
            else:
                if d.get("job") not in JOBS:
                    raise ValueError("Oportunidade inválida.")
                story = texto(d.get("story"), 800, "a apresentação")
                registro.detalhes["applications"] = sorted(set([*registro.detalhes.get("applications", []), d["job"]]))
                registro.detalhes.setdefault("applicationStories", {})[d["job"]] = story
            registro.save()
        else:
            raise ValueError("Operação desconhecida.")
    except (ValueError, TypeError, json.JSONDecodeError, Post.DoesNotExist, Perfil.DoesNotExist) as erro:
        transaction.set_rollback(True)
        return resposta({"error": str(erro) if isinstance(erro, ValueError) else "Pedido inválido."}, 400)
    return resposta(bootstrap(host, eu))


def conferir_arquivo(f):
    limite = 15 * 1024 * 1024 if f.content_type.startswith("video/") else 2 * 1024 * 1024
    if f.size > limite or f.content_type not in {"image/png", "image/jpeg", "image/webp", "video/mp4", "video/webm"}:
        raise ValueError("Use imagens de até 2 MB ou vídeo de até 15 MB.")
    bruto = f.read()
    if f.content_type.startswith("image/"):
        from PIL import Image
        try:
            with Image.open(io.BytesIO(bruto)) as imagem:
                if imagem.width * imagem.height > 20000000 or imagem.format not in {"PNG", "JPEG", "WEBP"}:
                    raise ValueError()
                imagem.verify()
        except Exception:
            raise ValueError("Uma imagem não pôde ser aberta.") from None
    elif (f.content_type == "video/mp4" and bruto[4:8] != b"ftyp") or (f.content_type == "video/webm" and not bruto.startswith(b"\x1aE\xdf\xa3")):
        raise ValueError("O vídeo não corresponde ao formato informado.")
    return bruto


@require_POST
@transaction.atomic
def publicar(request):
    if not _permitido(request):
        return HttpResponseNotFound()
    try:
        host, eu = contexto(request)
        d = json.loads(request.POST.get("data", "{}"))
        if not isinstance(d, dict) or d.get("kind") not in CATEGORIAS:
            raise ValueError("Escolha o tipo de publicação.")
        titulo = texto(d.get("title"), 120, "o título")
        story = texto(d.get("story"), 2400, "a história")
        tags = d.get("tags", [])
        if not isinstance(tags, list) or len(tags) > 5 or any(not isinstance(t, str) or len(t) > 40 for t in tags):
            raise ValueError("Confira os temas da publicação.")
        valor = Decimal(str(d.get("amount") or 0))
        if not valor.is_finite() or not 0 <= valor <= 999999:
            raise ValueError("Confira o valor do exemplo.")
        imgs = request.FILES.getlist("images")
        vids = request.FILES.getlist("video")
        if len(imgs) > 4 or len(vids) > 1 or any(not f.content_type.startswith("image/") for f in imgs) or any(not f.content_type.startswith("video/") for f in vids):
            raise ValueError("Escolha até quatro imagens e um vídeo.")
        post, criado = Post.objects.get_or_create(autor=eu, chave_pedido=pedido(d.get("request_key")), defaults={
            "site_host": host, "chave": "post-" + uuid.uuid4().hex, "categoria": d["kind"],
            "titulo": titulo, "texto": story, "detalhes": {"tags": tags, "amount": float(valor),
                "art": "evolution" if d["kind"] == "evolution" else "sword"}})
        if criado:
            for f in [*imgs, *vids]:
                Arquivo.objects.create(post=post, tipo=f.content_type, dados=conferir_arquivo(f))
        elif (post.titulo, post.texto, post.categoria) != (titulo, story, d["kind"]):
            raise ValueError("Este envio já identifica outra publicação.")
    except (ValueError, TypeError, json.JSONDecodeError, InvalidOperation) as erro:
        transaction.set_rollback(True)
        return resposta({"error": str(erro) if isinstance(erro, ValueError) else "Publicação inválida."}, 400)
    return resposta({**bootstrap(host, eu), "published": post.chave})


@require_GET
def arquivo(request, arquivo_id):
    if not _permitido(request):
        return HttpResponseNotFound()
    host = request.get_host().split(":")[0].lower()
    registro = Arquivo.objects.filter(pk=arquivo_id, post__site_host=host).first()
    if not registro:
        return HttpResponseNotFound()
    bruto = bytes(registro.dados)
    r = HttpResponse(bruto, content_type=registro.tipo)
    r["X-Content-Type-Options"] = "nosniff"
    r["Cache-Control"] = "no-store"
    r["X-Robots-Tag"] = "noindex, nofollow"
    return r
