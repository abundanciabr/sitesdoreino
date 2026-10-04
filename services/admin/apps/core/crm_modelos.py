"""Modelos aprovados do WhatsApp oficial no CRM: /admin/crm/modelos/.

Os modelos e os envios são dados da mensageria; esta tela só os consulta pela
porta de máquina (`/api/mensageria/whatsapp-modelos/`) e nunca guarda cópia.
"""
import uuid
from urllib.parse import quote

import httpx
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .clients import CatalogoClient, MensageriaClient, http
from .crm import instante

ESTADOS_DO_MODELO = {
    "aprovado": "Aprovado — pode iniciar conversa",
    "pendente": "Em análise na Meta",
    "rejeitado": "Rejeitado pela Meta",
    "pausado": "Pausado pela Meta",
    "desativado": "Desativado",
    "outro": "Estado desconhecido",
}

ESTADOS_DO_ENVIO = {
    "reservado": "Preparando o envio",
    "aceito": "Aceito pela Meta — entrega ainda não confirmada",
    "enviado": "Enviado — entrega ainda não confirmada",
    "entregue": "Entrega confirmada",
    "lido": "Leitura confirmada",
    "falhou": "Não enviado",
    "desconhecido": "Resultado desconhecido — não reenviar às cegas",
}

CATEGORIAS = {"MARKETING": "Marketing", "UTILITY": "Utilidade", "AUTHENTICATION": "Autenticação"}

SEM_MENSAGERIA = "A comunicação com a mensageria ainda não está configurada."
SEM_RESPOSTA = "A mensageria não respondeu agora. Tente novamente em alguns instantes."


def _pedir(metodo, caminho, payload=None):
    config = MensageriaClient()._configuracao()
    if config is None:
        return None, SEM_MENSAGERIA
    base, token = config
    try:
        resposta = http().request(metodo, base + "/whatsapp-modelos/" + caminho, json=payload,
                                  headers={"Authorization": "Bearer " + token}, timeout=30.0)
        dados = resposta.json()
    except (httpx.HTTPError, ValueError):
        return None, SEM_RESPOSTA
    if resposta.status_code == 403:
        return None, "A mensageria só deu acesso de leitura a esta tela; a alteração não foi feita."
    if resposta.status_code != 200 or not isinstance(dados, dict):
        detalhe = dados.get("detail") if isinstance(dados, dict) else ""
        return None, "A mensageria recusou o pedido" + (f": {detalhe}" if isinstance(detalhe, str) and detalhe else ".")
    return dados, ""


def _preparar_modelo(modelo, variaveis_do_lead):
    modelo = dict(modelo)
    modelo["estado_visivel"] = ESTADOS_DO_MODELO.get(modelo.get("estado"), modelo.get("estado", ""))
    modelo["categoria_visivel"] = CATEGORIAS.get(modelo.get("categoria"), modelo.get("categoria", ""))
    mapa = modelo.get("mapeamento") or {}
    modelo["lugares"] = [{
        "chave": v.get("chave"),
        "nome": ("Botão: final do link" if str(v.get("componente", "")).startswith("button.")
                 else ("Cabeçalho " if v.get("componente") == "header" else "Texto ") + "{{" + str(v.get("parametro")) + "}}"),
        "dado": mapa.get(v.get("chave")) or "",
        "dado_visivel": variaveis_do_lead.get(mapa.get(v.get("chave")) or "", "Sem dado escolhido"),
    } for v in modelo.get("variaveis") or [] if isinstance(v, dict)]
    modelo["pronto"] = (modelo.get("estado") == "aprovado" and modelo.get("suportado")
                        and modelo.get("presente_no_provedor") and not modelo.get("faltando"))
    # Botão de URL com parte variável pede `link`, e o primeiro contato do agente não manda link.
    modelo["botao_dinamico"] = any(
        isinstance(v, dict) and str(v.get("componente", "")).startswith("button.")
        for v in modelo.get("variaveis") or [])
    return modelo


@require_http_methods(["GET", "POST"])
def crm_modelos(request):
    contexto = {"admin": request.admin, "erro": "", "recado": "", "modelos": [], "envios": [],
                "canal_oficial": "", "variaveis_do_lead": {}, "chave": "manual:" + uuid.uuid4().hex}
    site = CatalogoClient().site_por_host(request.get_host().split(":")[0].lower())
    if not site:
        contexto["erro"] = "Não consegui identificar este site."
        return render(request, "admin/crm_modelos.html", contexto, status=503)
    site_id = str(site["id"])
    if request.method == "POST":
        acao = request.POST.get("acao", "")
        if acao == "sincronizar":
            dados, erro = _pedir("POST", "sincronizar")
            if dados is not None:
                if dados.get("canal_oficial") == "nao_ligado":
                    erro = "O canal oficial do WhatsApp ainda não está ligado; não há modelos para buscar."
                elif dados.get("erro"):
                    erro = "A Meta não entregou os modelos agora (" + str(dados["erro"]) + ")."
                else:
                    contexto["recado"] = f"Modelos atualizados: {dados.get('modelos', 0)}."
            contexto["erro"] = erro
        elif acao == "mapear":
            modelo_id = request.POST.get("modelo_id", "")
            mapa = {k[len("lugar:"):]: v for k, v in request.POST.items() if k.startswith("lugar:")}
            if not (modelo_id.isascii() and modelo_id.isdigit() and len(modelo_id) <= 12):
                contexto["erro"] = "Este modelo não foi reconhecido."
            else:
                dados, erro = _pedir("POST", "modelos/mapeamento", {"modelo_id": int(modelo_id), "mapeamento": mapa})
                contexto["erro"] = erro
                contexto["recado"] = "" if erro else "Dados do lead ligados ao modelo."
        elif acao == "testar":
            if request.POST.get("autorizado") != "sim":
                contexto["erro"] = "Confirme que este destinatário autorizou a mensagem de teste."
            else:
                variaveis = {k: request.POST.get(k, "").strip() for k in ("nome", "quiz", "oferta", "link")}
                dados, erro = _pedir("POST", quote(site_id, safe="") + "/enviar", {
                    "chave_idempotencia": request.POST.get("chave", "")[:200] or "manual:" + uuid.uuid4().hex,
                    "destinatario": request.POST.get("destinatario", "").strip(),
                    "modelo": request.POST.get("modelo", "").strip(),
                    "variaveis": {k: v for k, v in variaveis.items() if v},
                    "origem": "manual"})
                contexto["erro"] = erro
                if dados is not None:
                    estado = ESTADOS_DO_ENVIO.get(dados.get("estado"), dados.get("estado", ""))
                    contexto["recado"] = estado + (f" — {dados['erro']}" if dados.get("erro") else "")
        else:
            contexto["erro"] = "Esta ação não foi reconhecida."
    dados, erro = _pedir("GET", quote(site_id, safe=""))
    if dados is None:
        contexto["erro"] = contexto["erro"] or erro
        return render(request, "admin/crm_modelos.html", contexto, status=200 if contexto["recado"] else 503)
    variaveis_do_lead = dados.get("variaveis_do_lead") or {}
    contexto["canal_oficial"] = dados.get("canal_oficial", "")
    contexto["variaveis_do_lead"] = variaveis_do_lead
    contexto["modelos"] = [_preparar_modelo(m, variaveis_do_lead) for m in dados.get("modelos") or []]
    contexto["aprovados"] = [m for m in contexto["modelos"] if m["pronto"]]
    contexto["para_o_primeiro_contato"] = [m for m in contexto["aprovados"] if not m["botao_dinamico"]]
    contexto["envios"] = [dict(e, estado_visivel=ESTADOS_DO_ENVIO.get(e.get("estado"), e.get("estado", "")),
                               quando=instante(e.get("criado_em")))
                          for e in dados.get("envios") or []]
    resposta = render(request, "admin/crm_modelos.html", contexto)
    resposta["Cache-Control"] = "no-store"
    return resposta
