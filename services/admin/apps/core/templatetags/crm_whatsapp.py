from django import template
from django.urls import reverse
from apps.core.crm_whatsapp import telefone_whatsapp

register = template.Library()


@register.inclusion_tag("admin/_whatsapp_botao.html")
def chamar_whatsapp(lead_id, telefone, nome="Contato"):
    numero = telefone_whatsapp(telefone)
    return {"whatsapp_url": reverse("crm_whatsapp", args=[lead_id]) if lead_id and numero else "",
            "whatsapp_nome": nome or "Contato"}
