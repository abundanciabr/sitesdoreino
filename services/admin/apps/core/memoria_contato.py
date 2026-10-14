"""Prévia administrativa e consulta comum aos agentes; somente leitura."""
import json
from urllib.parse import quote

from django.http import Http404
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .clients import LeadsClient, MedicaoClient


def consultar_memoria(lead_id, site_id):
    if not lead_id or not site_id:
        return LeadsClient.NAO_RESPONDEU, None
    estado, dados = LeadsClient()._pedir(
        "/leads/" + quote(str(lead_id), safe="") + "/memoria",
        {"site_id": str(site_id)}, aceita_404=True,
    )
    if estado != LeadsClient.OK:
        return estado, None
    if (not isinstance(dados, dict) or dados.get("lead_id") != str(lead_id)
            or dados.get("site_id") != str(site_id)
            or not all(isinstance(dados.get(k), list) for k in ("eventos", "vinculos", "quizzes", "lacunas"))):
        return LeadsClient.NAO_RESPONDEU, None
    medicao_estado, fatos = MedicaoClient()._pedir(
        "/contatos/" + quote(str(lead_id), safe="") + "/memoria", {"site_id": str(site_id)})
    if (medicao_estado == MedicaoClient.OK and isinstance(fatos, dict)
            and fatos.get("lead_id") == str(lead_id) and fatos.get("site_id") == str(site_id)
            and isinstance(fatos.get("eventos"), list) and isinstance(fatos.get("vinculos"), list)):
        dados["metricas"] = fatos
        dados["vinculos"].extend(fatos["vinculos"])
        if fatos["vinculos"]:
            dados["lacunas"] = [l for l in dados["lacunas"] if not l.startswith("Nenhum identificador de visitante")]
        if fatos.get("total", 0) > fatos.get("exibidos", 0):
            dados["lacunas"].append("Métricas: somente os 200 fatos mais recentes com referência explícita ao contato.")
    else:
        dados["metricas"] = None
        dados["lacunas"].append("A fonte de métricas não respondeu à consulta. Não foi contado zero nem inferida ausência de eventos.")
    return estado, dados


@require_GET
def previa(request, lead_id):
    estado, ficha = LeadsClient().ficha(lead_id)
    if estado == LeadsClient.NAO_EXISTE:
        raise Http404("Contato inexistente")
    memoria = None
    if estado == LeadsClient.OK and isinstance(ficha, dict):
        estado, memoria = consultar_memoria(lead_id, ficha.get("site_id"))
    contexto = {"admin": request.admin, "lead_id": lead_id,
                "nome": (ficha or {}).get("nome") or "Contato",
                "memoria": memoria,
                "contexto_json": json.dumps(memoria, ensure_ascii=False, indent=2) if memoria else "",
                "erro": "" if memoria is not None else "A fonte não respondeu à consulta da memória. Isso não significa ausência de histórico."}
    resposta = render(request, "admin/memoria_contato.html", contexto,
                      status=200 if memoria is not None else 503)
    resposta["Cache-Control"] = "private, no-store"
    return resposta
