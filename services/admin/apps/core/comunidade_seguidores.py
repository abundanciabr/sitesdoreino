"""Pedidos reais para seguir, confirmados somente pelo destinatário."""
from pathlib import Path

from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from . import comunidade_entrada as comunidade
from .comunidade_modelos import PerfilDaComunidade
from .comunidade_seguidores_modelo import PedidoSeguidor

BASE = "/galeria-publica/seguidores"
CAMINHOS = {BASE, BASE + "/solicitar", BASE + "/responder", BASE + "/interface.js", BASE + "/interface.css"}
ROTULOS = {"pendente": "Solicitação enviada", "aceito": "Seguindo", "recusado": "Solicitação recusada"}


def chave(host, email):
    # Identificador opaco: nenhum endereço de contato vai para o HTML ou JSON.
    return salted_hmac("comunidade-seguidor-v1", host + "\n" + email.strip().lower(), algorithm="sha256").hexdigest()


def pessoa(request):
    from .galeria_comunidade import aluno
    return comunidade.reconhecer_admin(request) or aluno(request)


def resposta(dados, status=200):
    return comunidade._resposta(JsonResponse(dados, status=status))


def decorar(alunos, perfil):
    estados = dict(PedidoSeguidor.objects.filter(site_host=perfil.site_host, autor=perfil).values_list("destinatario", "estado"))
    minha = chave(perfil.site_host, perfil.email)
    for item in alunos or []:
        alvo = item.get("seguir_chave", "")
        item["sou_eu"] = alvo == minha
        item["seguir_estado"] = estados.get(alvo, "")
        item["seguir_rotulo"] = ROTULOS.get(item["seguir_estado"], "Seguir")


def caixa(host, dono):
    alvo = chave(host, dono["email"])
    recebidos = PedidoSeguidor.objects.filter(site_host=host, destinatario=alvo)
    # Prioriza pedidos que ainda precisam de resposta, mantendo o histórico recente.
    pedidos = list(recebidos.filter(estado="pendente").select_related("autor").order_by("-criado_em")[:100])
    pedidos += list(recebidos.exclude(estado="pendente").select_related("autor").order_by("-respondido_em")[:20])
    enviados = PedidoSeguidor.objects.filter(site_host=host, autor__site_host=host, autor__identidade_id=str(dono["id"]))
    return {"pendentes": recebidos.filter(estado="pendente").count(),
            "recebidos": [{"id": str(p.pk), "nome": p.autor.nome, "usuario": p.autor.usuario, "estado": p.estado} for p in pedidos],
            "enviados": [{"alvo": p.destinatario, "estado": p.estado, "rotulo": ROTULOS[p.estado]} for p in enviados]}


@require_GET
@never_cache
def dados(request):
    dono = pessoa(request)
    if not dono:
        return resposta({"erro": "Entre com sua conta de aluno para ver seus seguidores."}, 403)
    get_token(request)
    return resposta(caixa(comunidade._host(request), dono))


@require_POST
@never_cache
def solicitar(request):
    dono = pessoa(request)
    if not dono:
        return resposta({"erro": "Entre com sua conta para seguir uma pessoa."}, 403)
    host = comunidade._host(request)
    perfil = PerfilDaComunidade.objects.filter(site_host=host, identidade_id=str(dono["id"])).first()
    if not perfil:
        return resposta({"erro": "Complete seu perfil na comunidade antes de seguir uma pessoa."}, 400)
    alvo = str(request.POST.get("alvo") or "")
    if alvo == chave(host, dono["email"]):
        return resposta({"erro": "Você não pode seguir seu próprio perfil."}, 400)
    alunos = comunidade._alunos(request)
    if alunos is None:
        return resposta({"erro": "Não foi possível conferir essa pessoa agora. Tente novamente."}, 503)
    if not any(item.get("seguir_chave") == alvo for item in alunos):
        return resposta({"erro": "Essa pessoa não está disponível nesta comunidade."}, 404)
    # A restrição única também impede duplicação entre requisições simultâneas.
    pedido, criado = PedidoSeguidor.objects.get_or_create(site_host=host, autor=perfil, destinatario=alvo)
    return resposta({"alvo": alvo, "estado": pedido.estado, "rotulo": ROTULOS[pedido.estado], "criado": criado})


@require_POST
@never_cache
def responder(request):
    dono = pessoa(request)
    if not dono:
        return resposta({"erro": "Entre com sua conta para responder."}, 403)
    acao = request.POST.get("acao")
    if acao not in {"aceitar", "recusar"}:
        return resposta({"erro": "Escolha aceitar ou recusar."}, 400)
    import uuid
    try:
        pedido_id = uuid.UUID(str(request.POST.get("pedido") or ""))
    except ValueError:
        return resposta({"erro": "Solicitação não encontrada."}, 404)
    host = comunidade._host(request)
    estado = "aceito" if acao == "aceitar" else "recusado"
    with transaction.atomic():
        pedido = PedidoSeguidor.objects.select_for_update().filter(pk=pedido_id, site_host=host, destinatario=chave(host, dono["email"])).first()
        if pedido is None:
            return resposta({"erro": "Solicitação não encontrada."}, 404)
        if pedido.estado not in {"pendente", estado}:
            return resposta({"erro": "Essa solicitação já foi respondida. Atualize os avisos."}, 409)
        if pedido.estado == "pendente":
            pedido.estado = estado
            pedido.respondido_em = timezone.now()
            pedido.save(update_fields=["estado", "respondido_em"])
    return resposta(caixa(host, dono))


@require_GET
@never_cache
def interface(request, nome):
    if nome not in {"interface.js", "interface.css"}:
        return resposta({"erro": "Recurso não encontrado."}, 404)
    arquivo = Path(__file__).with_name("comunidade_assets") / ("seguidores." + nome.rsplit(".", 1)[1])
    return comunidade._resposta(HttpResponse(arquivo.read_bytes(), content_type="text/javascript" if nome.endswith(".js") else "text/css"))
