"""A recusa inicial vira um atendimento único, com decisão feita pelo suporte."""
import uuid
import httpx
from django.db import transaction
from django.utils import timezone
from apps.core.clients import AlunosClient, IdentidadeClient
from .models import Assunto, Conversa, Mensagem

def _alunos(caminho, params=None, dados=None):
    config = AlunosClient()._configuracao()
    if not config: raise ValueError("A escola não respondeu. O pedido continua pendente.")
    base, token = config
    try:
        r = httpx.request("POST" if dados is not None else "GET", base+caminho,
            headers={"Authorization": "Bearer "+token}, params=params, json=dados, timeout=8)
    except httpx.HTTPError:
        raise ValueError("A escola não respondeu. Confira novamente antes de repetir.") from None
    if r.status_code == 404: return None
    if r.status_code != 200: raise ValueError("A escola não concluiu a operação. Confira o pedido e o curso escolhido.")
    return r.json()

def encaminhar(envelope):
    data=envelope["data"]
    d=_alunos("/avisos-acesso/suporte", params={"site_id":data["site_id"], "event_id":envelope["event_id"]})
    if not d or d["resolvido"]: return
    cid=uuid.uuid5(uuid.NAMESPACE_URL, "meshcraft:pedido-escola:"+data["site_id"]+":"+envelope["event_id"])
    assunto,_=Assunto.objects.get_or_create(site_id=data["site_id"],nome="Pedido de acesso à escola",defaults={"modo":"assistido"})
    pessoa="pedido-escola:"+d["matricula_id"]
    config=IdentidadeClient()._configuracao()
    if config:
        base,token=config
        r=httpx.post(base+"/pessoas/por-email", json={"email":d["email"]},headers={"Authorization":"Bearer "+token},timeout=8)
        if r.status_code != 200: raise ValueError("A identidade não respondeu ao encaminhamento.")
        pessoa=r.json().get("id") or pessoa
    conversa,_=Conversa.objects.get_or_create(pk=cid,defaults={"site_id":data["site_id"],"pessoa_id":pessoa,
        "nome":d["nome"],"assunto":assunto,"estado":"aguardando","processar":False,
        "pedido_escola_id":d["matricula_id"],"pedido_escola_event_id":envelope["event_id"]})
    Mensagem.objects.get_or_create(conversa=conversa,referencia="encaminhamento:"+envelope["event_id"],
        defaults={"autor":"sistema","nome":"Escola","texto":"Pedido de acesso encaminhado para resolução pelo suporte. Motivo da análise inicial: "+d["motivo"]})
    return conversa

def resolver(conversa, *, decisao, quem, nome, motivo="", product_id=""):
    if not conversa.pedido_escola_id or not conversa.pedido_escola_event_id:
        raise ValueError("Este atendimento não é um pedido de acesso à escola.")
    if decisao == "recusar" and not motivo.strip():
        raise ValueError("Escreva a explicação que será enviada ao aluno.")
    resultado=_alunos(f"/pre-matriculas/{conversa.pedido_escola_id}/suporte", dados={
        "site_id":conversa.site_id,"event_id":str(conversa.pedido_escola_event_id),
        "decisao":decisao,"decidido_por":quem,"motivo":motivo,"product_id":product_id})
    if not resultado or not resultado.get("resolvido"):
        raise ValueError("O pedido mudou; confira a situação atual na escola.")
    with transaction.atomic():
        c=Conversa.objects.select_for_update().get(pk=conversa.pk)
        Mensagem.objects.get_or_create(conversa=c,referencia="decisao-escola:"+str(c.pedido_escola_event_id),
            defaults={"autor":"equipe","nome":nome,"texto":("Seu acesso foi liberado. O link de entrada será enviado ao seu e-mail e ao WhatsApp confirmado." if decisao == "liberar" else motivo)})
        c.estado="encerrado";c.encerrada_em=timezone.now();c.arquivada_em=timezone.now()
        c.resolvida_em=timezone.now();c.resolucao="suporte";c.processar=False;c.save()
