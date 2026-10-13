"""Prévia restrita ao admin autenticado da própria conta; nenhum acesso público."""
import httpx
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from .clients import CatalogoClient, IdentidadeClient, MensageriaClient, http
from .porta import _emails_autorizados

TEMPLATE = "admin/acesso_sem_senha.html"
COOKIE = "meshcraft_sessao"

class Indisponivel(Exception):
    pass

def _pedir(cliente, caminho, *, cookie="", dados=None, params=None):
    config = cliente._configuracao()
    if not config:
        raise Indisponivel("A integração ainda não está configurada.")
    base, token = config
    headers = {"Authorization": "Bearer " + token}
    if cookie:
        headers["Cookie"] = COOKIE + "=" + cookie
    try:
        resposta = http().request("POST" if dados is not None else "GET", base+caminho,
            headers=headers, json=dados, params=params, timeout=40)
        payload = resposta.json()
    except (httpx.HTTPError, ValueError):
        raise Indisponivel("Não foi possível confirmar a resposta. Não repita o envio imediatamente.") from None
    if resposta.status_code != 200:
        # Só mensagens fixas da identidade; nunca ecoar resposta SMTP ou corpo.
        if cliente.__class__ is IdentidadeClient and resposta.status_code in {400,403,422,429}:
            raise Indisponivel(payload.get("detail", "Pedido recusado."))
        raise Indisponivel("A integração recusou o pedido ou ainda não está disponível.")
    return payload

@require_http_methods(["GET", "POST"])
def previa(request):
    admin = getattr(request, "admin", {})
    email_admin = str(admin.get("email") or "").strip().lower()
    # A porta aceita alguns crachás de robôs/equipe. Esta prévia exige pessoa
    # administradora e sua sessão real, revalidada pela identidade.
    if not email_admin or email_admin not in _emails_autorizados() or admin.get("equipe_apenas"):
        return HttpResponse(status=404)
    contexto = {"admin": admin}
    cookie = request.COOKIES.get(COOKIE, "")
    if not cookie:
        contexto["erro"] = "Entre na sua conta do site com Google ou senha antes de testar esta prévia."
        return render(request, TEMPLATE, contexto)
    nova_sessao = None
    try:
        site = CatalogoClient().site_por_host(request.get_host().split(":")[0].lower())
        if not site:
            raise Indisponivel("Não foi possível identificar este site.")
        site_id = str(site["id"])
        estado = _pedir(IdentidadeClient(), "/acesso-previa/estado", cookie=cookie, params={"site_id": site_id})
        if estado.get("email", "").strip().lower() != email_admin:
            return HttpResponse(status=403)
        contexto.update(email=estado["email"], pronto=True, desafio=estado.get("desafio"))
        if request.method == "POST":
            acao = request.POST.get("acao")
            if acao == "enviar":
                canal = request.POST.get("canal", "")
                if request.POST.get("autorizado") != "sim":
                    raise Indisponivel("Confirme que o contato é seu e autorize este envio de teste.")
                pedido = _pedir(IdentidadeClient(), "/acesso-previa/preparar", cookie=cookie, dados={
                    "site_id": site_id, "canal": canal, "destino": request.POST.get("destino", "")})
                contexto["desafio"] = {k:v for k,v in pedido.items() if k not in {"codigo", "destino"}}
                resultado = _pedir(MensageriaClient(), "/acesso-previa/enviar", dados={
                    "site_id": site_id, "desafio": pedido["desafio"], "canal": canal,
                    "destino": pedido["destino"], "codigo": pedido["codigo"]})
                estado_envio = resultado.get("estado")
                if estado_envio in {"aceito", "enviado", "entregue", "lido"}:
                    contexto["aviso"] = "O provedor aceitou o envio. Confira a mensagem recebida e digite o código abaixo."
                elif estado_envio in {"nao_configurado", "bloqueado", "aguarde"}:
                    contexto["erro"] = {"nao_configurado": "O SMTP ainda não está configurado para enviar e-mail.",
                        "bloqueado": "O provedor bloqueou envios para este e-mail.",
                        "aguarde": "O canal de e-mail precisa aguardar antes de enviar."}[estado_envio]
                else:
                    contexto["erro"] = "O envio não foi confirmado. Se a mensagem chegar, você pode usar o código; aguarde antes de pedir outro."
            elif acao == "confirmar":
                resultado = _pedir(IdentidadeClient(), "/acesso-previa/confirmar", cookie=cookie, dados={
                    "site_id": site_id, "desafio": request.POST.get("desafio", ""),
                    "codigo": request.POST.get("codigo", "").strip()})
                if resultado.get("id") != estado["id"]:
                    raise Indisponivel("A identidade retornada não corresponde à sua conta.")
                nova_sessao = resultado
                contexto["sucesso"] = True
                contexto["desafio"] = None
                contexto["canal_confirmado"] = resultado["canal"]
                contexto["destino_confirmado"] = resultado["destino_mascarado"]
            else:
                raise Indisponivel("Ação não reconhecida.")
    except Indisponivel as erro:
        contexto["erro"] = str(erro)
    resposta = render(request, TEMPLATE, contexto)
    resposta["Cache-Control"] = "no-store"
    resposta["Referrer-Policy"] = "same-origin"
    if nova_sessao:
        resposta.set_cookie(COOKIE, nova_sessao["sessao"], max_age=nova_sessao["max_age"],
            httponly=True, secure=True, samesite="Lax", path="/")
    return resposta
