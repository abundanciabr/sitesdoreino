"""Gestão reservada ao par autenticado do Admin."""
from django.http import HttpResponse
from ninja import Router, Schema
from ninja.errors import HttpError
from .ganhos_admin_api import autorizar
from apps.gamificacao.jornada import situacao
from apps.gamificacao.models import JornadaPessoal, RegistroDaJornada
from apps.gamificacao.gestao_trilha import remover
router = Router()

class Retirada(Schema):
    ordem: int
    tipo: str
    ator: str
    revisao: int

def leitura(pessoa_id, site_id):
    j = JornadaPessoal.objects.filter(pessoa_id=pessoa_id, site_id=site_id).first()
    estado = situacao(pessoa_id, site_id)
    return {"atual": estado["atual"]["nome"], "revisao": j.revisao if j else 0,
            "etapas": [{"ordem": p["ordem"], "nome": p["nome"], "alcancada": p["alcancada"]}
                       for p in estado["lista"]],
            "historico": [{"id": h.pk, "quando": h.criado_em.isoformat(),
                           "ordem": h.dados.get("ordem"), "tipo": h.dados.get("tipo")}
                          for h in RegistroDaJornada.objects.filter(pessoa_id=pessoa_id,
                          site_id=site_id, acao="admin_remover")[:20]]}

@router.get("/gestao-trilha/{site_id}/{pessoa_id}")
def consultar(request, response: HttpResponse, site_id: str, pessoa_id: str):
    autorizar(request, site_id)
    response["Cache-Control"] = "private, no-store"
    return leitura(pessoa_id, site_id)

@router.post("/gestao-trilha/{site_id}/{pessoa_id}")
def retirar(request, response: HttpResponse, site_id: str, pessoa_id: str, dados: Retirada):
    autorizar(request, site_id)
    try:
        remover(pessoa_id, site_id, dados.ordem, dados.tipo, dados.ator, dados.revisao)
    except ValueError as erro:
        raise HttpError(409, str(erro)) from None
    response["Cache-Control"] = "private, no-store"
    return leitura(pessoa_id, site_id)
