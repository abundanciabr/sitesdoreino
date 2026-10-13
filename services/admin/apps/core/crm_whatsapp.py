"""Conversa de WhatsApp ao lado do perfil, usando a mensageria existente."""
import re
import uuid
from pathlib import Path

from django.http import Http404, HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods

import httpx

from .clients import LeadsClient, AlunosClient, http
from . import crm_conversas as caixa


def telefone_whatsapp(valor):
    texto = str(valor or "").strip()
    if not texto or re.search(r"[^0-9+().\s-]", texto):
        return ""
    numero = re.sub(r"\D", "", texto)
    if numero.startswith("00"):
        numero = numero[2:]
    elif texto.startswith("+"):
        return numero if 10 <= len(numero) <= 15 and not numero.startswith("0") else ""
    elif len(numero) in (10, 11):
        numero = "55" + numero
    return numero if 10 <= len(numero) <= 15 and not numero.startswith("0") else ""


def contato_da_pesquisa(site_id, avaliacao):
    """A pesquisa e o CRM têm IDs distintos; só um e-mail exato no mesmo site liga os dois."""
    aluno = (avaliacao or {}).get("aluno") or {}
    email = str(aluno.get("email") or "").strip().lower()
    if not site_id or not email:
        return None
    estado, dados = LeadsClient().listar(q=email, site_id=site_id, por_pagina=100, testes="mostrar")
    if estado != LeadsClient.OK or not isinstance(dados, dict) or dados.get("tem_mais"):
        return None
    encontrados = [c for c in dados.get("itens", []) if isinstance(c, dict)
                   and str(c.get("email") or "").strip().lower() == email
                   and str(c.get("site_id")) == str(site_id)]
    return encontrados[0] if len(encontrados) == 1 else None


def _json(dados, status=200):
    resposta = JsonResponse(dados, status=status)
    resposta["Cache-Control"] = "no-store"
    return resposta


def _erro(texto, status=503):
    return _json({"erro": texto}, status)


def _pertence(conversa, site_id, lead_id):
    return (isinstance(conversa, dict) and str(conversa.get("site_id")) == str(site_id)
            and str(conversa.get("lead_id")) == str(lead_id)
            and conversa.get("canal") == "whatsapp" and not conversa.get("ambigua"))


@require_GET
def javascript(request):
    arquivo = Path(__file__).resolve().parents[2] / "static" / "admin" / "crm_whatsapp.js"
    return HttpResponse(arquivo.read_text(encoding="utf-8"), content_type="application/javascript; charset=utf-8")


@require_http_methods(["GET", "POST"])
def conversa(request, lead_id):
    site_id = caixa.site_do_pedido(request)
    if not site_id:
        return _erro("Não foi possível identificar o site.")
    estado, contato = LeadsClient().ficha(lead_id)
    if estado == LeadsClient.NAO_EXISTE:
        raise Http404("Contato não encontrado")
    if estado != LeadsClient.OK or not contato:
        return _erro("Não foi possível consultar o contato agora.")
    if str(contato.get("site_id")) != str(site_id) or str(contato.get("id")) != str(lead_id):
        raise Http404("Contato não encontrado neste site")
    numero = telefone_whatsapp(contato.get("telefone"))
    if not numero:
        return _erro("Este contato não tem um número de WhatsApp válido cadastrado.", 422)
    cliente = caixa.ConversasClient()
    acao = request.POST.get("acao") if request.method == "POST" else ""
    if request.method == "POST":
        if acao not in ("abrir", "enviar", "devolver"):
            return _erro("Ação não reconhecida.", 422)
        if acao == "enviar":
            try:
                uuid.UUID(request.POST.get("referencia", ""))
            except ValueError:
                return _erro("Reabra a conversa antes de enviar.", 422)
            texto = request.POST.get("texto", "").strip()
            modelo = request.POST.get("modelo", "").strip()
            if (not texto and not modelo) or len(texto) > 4000 or len(modelo) > 200:
                return _erro("Escreva uma mensagem de até 4.000 caracteres.", 422)
        # O telefone e o destinatário vêm da ficha, nunca do formulário.
        estado, aberta = cliente.pedir("POST", "", corpo={
            "site_id": site_id, "canal": "whatsapp", "lead_id": str(lead_id), "endereco": "+" + numero})
        if estado != caixa.OK:
            return _erro("Não foi possível abrir a conversa. " + (
                "Este número pode estar vinculado a outro contato; confira a ficha."
                if estado == caixa.RECUSADO else caixa.erro_da_fonte(estado)),
                409 if estado == caixa.RECUSADO else 503)
        if not _pertence(aberta, site_id, lead_id):
            return _erro("A conversa não corresponde a este contato.", 409)
        conversa_id = aberta.get("id")
    else:
        conversa_id = request.GET.get("conversa_id", "")
    try:
        conversa_id = str(uuid.UUID(str(conversa_id)))
    except ValueError:
        return _erro("Reabra a conversa para consultar as mensagens.", 422)
    antes_de = request.GET.get("antes_de", "").strip()
    if antes_de and not caixa.cursor_valido(antes_de):
        return _erro("A referência das mensagens anteriores é inválida.", 422)
    estado, dados = cliente.mensagens(site_id, conversa_id, antes_de=antes_de)
    if estado != caixa.OK:
        return _erro("Não foi possível consultar o histórico agora.")
    if not _pertence(dados["conversa"], site_id, lead_id):
        raise Http404("Conversa não encontrada para este contato")
    resultado, recado = None, ""
    if acao in ("enviar", "devolver"):
        autor = str(request.admin.get("id") or request.admin.get("email") or "mantenedor")[:100]
        if acao == "enviar":
            resultado, recado = caixa.responder(request, cliente, site_id, conversa_id, autor)
            if resultado in (caixa.OK, caixa.INCERTO):
                campos = {"atendido_por": caixa.pessoa_atende(request)}
                if resultado == caixa.OK:
                    campos.update(ultimo_contato_em=timezone.now().isoformat(), aguardando_resposta=False)
                caixa.acompanhar_no_crm(request, cliente, site_id, conversa_id, "responder",
                    caixa.referencia_do_pedido(request), campos, lead_id=str(lead_id))
        else:
            resultado, _ = cliente.gesto(conversa_id, "devolver", {"site_id": site_id})
            caixa.registrar(request, conversa_id, "devolver", resultado)
            recado = "Conversa devolvida ao assistente." if resultado == caixa.OK else "Não foi possível devolver a conversa."
            if resultado == caixa.OK:
                caixa.acompanhar_no_crm(request, cliente, site_id, conversa_id, "devolver",
                    caixa.referencia_do_pedido(request),
                    {"atendido_por": {"tipo": "agente", "nome": caixa.NOME_DO_AGENTE}}, lead_id=str(lead_id))
        # Resultado do envio não depende de uma segunda leitura bem-sucedida.
        return _json({"resultado": resultado, "recado": recado, "conversa_id": conversa_id,
                      "referencia": str(uuid.uuid4()) if resultado == caixa.OK else request.POST.get("referencia", "")})
    conv = dados["conversa"]
    mensagens = [caixa.preparar_mensagem(m) for m in dados["mensagens"] if isinstance(m, dict)]
    return _json({
        "conversa_id": conversa_id, "nome": contato.get("nome") or "Contato",
        "telefone": contato.get("telefone"), "aplicativo_url": "https://wa.me/" + numero,
        "estado": caixa.ESTADOS.get(conv.get("estado"), ""),
        "com_pessoa": conv.get("estado") == "pessoa",
        "descadastrado": bool(conv.get("descadastrado")),
        "texto_livre": bool(conv.get("janela_aberta") or conv.get("texto_livre_pessoa")),
        "referencia": str(uuid.uuid4()),
        "mensagens": [{"id": m.get("id"), "texto": m["resumo"], "direcao": m.get("direcao"),
                       "estado": m["envio_nome"], "data": m["momento"].strftime("%d/%m/%Y %H:%M") if m["momento"] else ""}
                      for m in mensagens],
        "antes_de": dados.get("proxima_antes_de") if len(mensagens) >= caixa.MENSAGENS_POR_PAGINA else "",
    })


@require_http_methods(["GET", "POST"])
def conversa_aluno(request, tipo, aluno_id):
    site_id = caixa.site_do_pedido(request)
    if not site_id:
        return _erro("Não foi possível identificar o site.")
    if tipo not in ("fila", "aluno"):
        raise Http404("Aluno não encontrado")
    alunos = AlunosClient()
    pessoas = alunos.fila("aguardando") if tipo == "fila" else alunos.alunos()
    if pessoas is None:
        return _erro("Não foi possível consultar o cadastro do aluno agora.")
    pessoa = next((p for p in pessoas if str(p.get("id")) == str(aluno_id)
                   and str(p.get("site_id")) == str(site_id)), None)
    if pessoa is None:
        raise Http404("Aluno não encontrado neste site")
    numero = telefone_whatsapp(pessoa.get("whatsapp"))
    email = str(pessoa.get("email") or "").strip().lower()
    if not numero or not email:
        return _erro("O aluno precisa ter e-mail e WhatsApp válidos no cadastro.", 422)
    cliente = LeadsClient()
    estado, dados = cliente.listar(q=email, site_id=site_id, por_pagina=100, testes="mostrar")
    if estado != cliente.OK or not isinstance(dados, dict) or dados.get("tem_mais"):
        return _erro("Não foi possível consultar o contato do aluno agora.")
    contatos = [c for c in dados.get("itens", []) if isinstance(c, dict)
                and str(c.get("email") or "").strip().lower() == email
                and str(c.get("site_id")) == str(site_id)]
    if len(contatos) > 1:
        return _erro("Há mais de um contato para este aluno. Confira os contatos no CRM.", 409)
    contato = contatos[0] if contatos else None
    lead_id = contato.get("id") if contato else None
    if not contato or telefone_whatsapp(contato.get("telefone")) != numero:
        if request.method != "POST" or request.POST.get("acao") != "abrir":
            return _erro("O cadastro mudou. Feche e reabra a conversa.", 409)
        config = cliente._configuracao()
        if config is None:
            return _erro("Não foi possível conectar o cadastro à conversa.")
        base, token = config
        corpo = {"site_id": site_id, "email": contato.get("email") if contato else email,
                 "phone": "+" + numero}
        if not contato:
            corpo.update(name=pessoa.get("nome_completo") or "", source="escola")
        try:
            resposta = http().post(base + "/leads", json=corpo,
                headers={"Authorization": "Bearer " + token}, timeout=cliente.TIMEOUT)
            resposta.raise_for_status()
            lead_id = str(uuid.UUID(resposta.json()["lead_id"]))
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return _erro("Não foi possível conectar o aluno à conversa. Tente novamente.")
    if not lead_id:
        return _erro("Não foi possível identificar o contato do aluno.")
    return conversa(request, lead_id)
