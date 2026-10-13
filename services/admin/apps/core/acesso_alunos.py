"""Recuperação pública, por solicitação do aluno, sem sessão administrativa."""
import hashlib
import hmac
import secrets
import uuid
import redis
from django.conf import settings
from django.core import signing
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods
from .clients import CatalogoClient, IdentidadeClient, LeadsClient, MensageriaClient
from .acesso_sem_senha import _pedir, Indisponivel, COOKIE
from .porta import _emails_autorizados

PEDIDO_COOKIE = "meshcraft_acesso_pedido"
SALT = "recuperacao-aluno-v1"
TEMPLATE = "admin/acesso_alunos.html"

def _pedido(request):
    try:
        p = signing.loads(request.COOKIES.get(PEDIDO_COOKIE, ""), salt=SALT, max_age=600)
        return p if isinstance(p,dict) and set(p)=={"site_id","desafio","vinculo","canal"} else None
    except signing.BadSignature: return None

def _limitar(request, contato):
    url = settings.SITE_ERRORS_REDIS_URL
    if not url: raise Indisponivel("O envio está temporariamente indisponível. Tente novamente em alguns minutos.")
    try:
        r = redis.Redis.from_url(url,socket_timeout=2,socket_connect_timeout=2)
        for tipo,valor,limite in (("ip",request.META.get("REMOTE_ADDR", ""),20),("contato",contato,5)):
            digest = hmac.new(settings.SECRET_KEY.encode(),valor.encode(),hashlib.sha256).hexdigest()
            n = r.eval("local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],3600) end; return n",1,"acesso-aluno:"+tipo+":"+digest)
            if n>limite: raise Indisponivel("Muitas solicitações. Aguarde antes de pedir outro código.")
    except redis.RedisError:
        raise Indisponivel("O envio está temporariamente indisponível. Tente novamente em alguns minutos.") from None

@sensitive_post_parameters("codigo", "contato")
@require_http_methods(["GET", "POST"])
def recuperar(request):
    if request.get_host().split(":")[0].lower() not in {"meshcraft.top","www.meshcraft.top"}: raise Http404
    pedido = _pedido(request)
    contexto = {"pedido":pedido}
    try:
        if request.method == "POST":
            acao = request.POST.get("acao")
            if acao == "enviar":
                canal = request.POST.get("canal", "")
                contato = request.POST.get("contato", "").strip().lower()
                if canal not in {"email","whatsapp"} or not contato or len(contato)>254:
                    raise Indisponivel("Informe o e-mail ou WhatsApp usado no seu cadastro.")
                _limitar(request, contato)
                site = CatalogoClient().site_por_host(request.get_host().split(":")[0].lower())
                if not site: raise Indisponivel("Não foi possível conferir o site. Tente novamente em alguns minutos.")
                site_id = str(site["id"])
                ficha = _pedir(LeadsClient(),"/acesso-alunos/resolver",dados={"site_id":site_id,"canal":canal,"contato":contato})
                # O navegador recebe o mesmo estado para contatos ausentes ou ambíguos.
                pedido = {"site_id":site_id,"desafio":str(uuid.uuid4()),"vinculo":secrets.token_urlsafe(32),"canal":canal}
                elegivel = ficha.get("encontrado") and not (canal=="whatsapp" and ficha.get("email","").lower() in _emails_autorizados())
                if elegivel:
                    d = _pedir(IdentidadeClient(),"/acesso-alunos/preparar",dados={"site_id":site_id,"email":ficha["email"],"canal":canal,"destino":ficha["destino"],"vinculo":pedido["vinculo"]})
                    if d.get("encontrado"):
                        pedido["desafio"] = d["desafio"]
                        resultado = _pedir(MensageriaClient(),"/acesso-previa/enviar",dados={"site_id":site_id,"desafio":d["desafio"],"canal":canal,"destino":d["destino"],"codigo":d["codigo"],"finalidade":"aluno"})
                        if resultado.get("estado") not in {"aceito","enviado","entregue","lido"}:
                            raise Indisponivel("Não foi possível confirmar o envio. Se o código não chegar, tente por e-mail ou procure o suporte.")
                resposta = HttpResponseRedirect(reverse("recuperar_acesso_aluno"))
                resposta.set_cookie(PEDIDO_COOKIE,signing.dumps(pedido,salt=SALT),max_age=600,secure=True,httponly=True,samesite="Lax",path="/admin/recuperar-acesso/")
                return resposta
            if acao == "confirmar":
                if not pedido: raise Indisponivel("Seu pedido expirou. Solicite um novo código.")
                resultado = _pedir(IdentidadeClient(),"/acesso-alunos/confirmar",dados={"site_id":pedido["site_id"],"desafio":pedido["desafio"],"vinculo":pedido["vinculo"],"codigo":request.POST.get("codigo","").strip()})
                resposta = HttpResponseRedirect("/cursos/")
                resposta.set_cookie(COOKIE,resultado["sessao"],max_age=resultado["max_age"],httponly=True,secure=True,samesite="Lax",path="/")
                resposta.delete_cookie(PEDIDO_COOKIE,path="/admin/recuperar-acesso/",samesite="Lax")
                return resposta
            raise Indisponivel("Ação não reconhecida.")
    except Indisponivel as erro:
        contexto["erro"] = str(erro)
    return render(request,TEMPLATE,contexto)
