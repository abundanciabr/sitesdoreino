from django import template
from django.urls import reverse
from apps.core.crm_whatsapp import telefone_whatsapp

register = template.Library()


@register.inclusion_tag("admin/_whatsapp_botao.html")
def chamar_whatsapp(lead_id, telefone, nome="Contato"):
    numero = telefone_whatsapp(telefone)
    return {"whatsapp_url": reverse("crm_whatsapp", args=[lead_id]) if lead_id and numero else "",
            "whatsapp_nome": nome or "Contato"}


@register.inclusion_tag("admin/_whatsapp_botao.html")
def chamar_whatsapp_aluno(pessoa):
    numero = telefone_whatsapp(pessoa.get("whatsapp"))
    origem = pessoa.get("origem_identificada") or {}
    dados = chamar_whatsapp(origem.get("contato_crm_id"), pessoa.get("whatsapp"), pessoa.get("nome_completo"))
    dados["whatsapp_aplicativo"] = "https://wa.me/" + numero if numero else ""
    return dados
