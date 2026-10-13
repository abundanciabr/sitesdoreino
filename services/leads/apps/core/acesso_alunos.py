import re
from django.db.models import Q
from ninja import Router, Schema
from .crm import _admin
from .models import ContatoDeAcesso

router = Router()
class Consulta(Schema):
    site_id: str
    canal: str
    contato: str

def telefone(valor):
    valor = re.sub(r"[^0-9]", "", valor)
    if len(valor) in (10, 11): valor = "55" + valor
    return valor if re.fullmatch(r"[1-9][0-9]{9,14}", valor) else ""

@router.post("/acesso-alunos/resolver")
def resolver(request, dados: Consulta):
    _admin(request)
    valor = dados.contato.strip().lower()
    if dados.canal == "whatsapp": valor = telefone(valor)
    if not valor or dados.canal not in {"email", "whatsapp"}: return {"encontrado":False}
    filtro = {"email__iexact":valor} if dados.canal == "email" else {"telefone":valor}
    site = Q(site_id=dados.site_id)
    # As matrículas antigas da Meshcraft usavam o nome no lugar do UUID.
    if dados.site_id == "cc06b8c3-043b-4c06-92c5-5ea624e00586":
        site |= Q(site_id__iexact="Meshcraft")
    registros = ContatoDeAcesso.objects.filter(site, **filtro)
    emails = list(registros.values_list("email", flat=True).distinct()[:2])
    if len(emails) != 1: return {"encontrado":False}
    return {"encontrado":True, "email":emails[0], "destino":valor}
