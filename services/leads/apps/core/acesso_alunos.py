import re
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
    registros = ContatoDeAcesso.objects.filter(site_id=dados.site_id, **filtro)
    emails = list(registros.values_list("email", flat=True).distinct()[:2])
    if len(emails) != 1: return {"encontrado":False}
    return {"encontrado":True, "email":emails[0], "destino":valor}
