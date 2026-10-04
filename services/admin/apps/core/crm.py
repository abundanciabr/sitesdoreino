"""Contatos e recuperação de vendas no painel do mantenedor."""
import uuid
from urllib.parse import urlencode

from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_GET, require_POST

from apps.auditoria.models import Registro
from .crm_client import CRMClient

ETAPAS = (
    ("nova", "Nova"), ("qualificada", "Qualificada"), ("proposta", "Proposta"),
    ("negociacao", "Em negociação"), ("ganha", "Ganha"),
    ("perdida", "Perdida"), ("desqualificada", "Encerrada"),
)
ABERTAS = dict(ETAPAS[:4])
# Os dois filtros do acompanhamento, com os valores que a API de leads aceita.
QUEM_ATENDE = (("agente", "Agente"), ("pessoa", "Pessoa da equipe"), ("ninguem", "Ninguém ainda"))
AGUARDANDO = (("sim", "Aguardando resposta do contato"), ("nao", "Sem resposta pendente"))


def instante(texto):
    try:
        data = parse_datetime(texto) if isinstance(texto, str) else None
        return timezone.localtime(data) if data and timezone.is_aware(data) else data
    except (ValueError, TypeError):
        return None


def preparar(item):
    item = dict(item)
    item["etapa_nome"] = dict(ETAPAS).get(item.get("etapa"), item.get("etapa", ""))
    passo = item.get("proximo_passo") or {}
    item["prazo"] = instante(passo.get("executar_ate") or item.get("prazo"))
    item["atrasada"] = bool(item["prazo"] and timezone.is_aware(item["prazo"]) and item["prazo"] < timezone.now() and item.get("situacao") == "aberta")
    item["prazo_formulario"] = item["prazo"].strftime("%Y-%m-%dT%H:%M") if item["prazo"] else ""
    item["aberta"] = item.get("situacao") == "aberta"
    item["historico"] = [dict(r, data=instante(r.get("registrado_em"))) for r in item.get("historico", [])]
    item["ultimo_contato"] = instante(item.get("ultimo_contato_em"))
    item["aguardando"] = item["aberta"] and item.get("aguardando_resposta") is True
    item["objecao"] = item.get("objecao_principal") if isinstance(item.get("objecao_principal"), str) else ""
    item["atendimento"] = atendimento(item.get("atendido_por"))
    return item


def atendimento(atendido_por):
    """Quem atende agora, em palavras: "Agente · Nome" ou "Pessoa · Nome"."""
    if not isinstance(atendido_por, dict) or atendido_por.get("tipo") not in ("agente", "pessoa"):
        return None
    tipo = "Agente" if atendido_por["tipo"] == "agente" else "Pessoa"
    nome = atendido_por.get("nome") if isinstance(atendido_por.get("nome"), str) else ""
    return {"tipo": atendido_por["tipo"], "rotulo": f"{tipo} · {nome}" if nome.strip() else tipo}


def erro_da_fonte(estado):
    if estado == CRMClient.SEM_CONFIGURACAO:
        return "O CRM está aguardando a conexão com os contatos. Tente novamente em alguns instantes."
    return "Não foi possível consultar o CRM agora. Tente novamente em alguns instantes."


@require_GET
def crm(request):
    filtros = {k: request.GET.get(k, "").strip() for k in ("q", "etapa", "situacao", "lead_id", "testes", "atendido_por", "aguardando_resposta")}
    if filtros["testes"] not in ("ocultar", "mostrar", "somente"):
        filtros["testes"] = "ocultar"
    if filtros["atendido_por"] not in dict(QUEM_ATENDE):
        filtros["atendido_por"] = ""
    if filtros["aguardando_resposta"] not in dict(AGUARDANDO):
        filtros["aguardando_resposta"] = ""
    # Filtro que a API de leads recusaria (422) é ignorado aqui, e a tela diz isso;
    # senão o endereço mal digitado aparece como "o CRM não respondeu".
    ignorados = []
    if filtros["situacao"] not in ("", "aberta", "encerrada"):
        filtros["situacao"] = ""
        ignorados.append("situação")
    if filtros["lead_id"]:
        try:
            filtros["lead_id"] = str(uuid.UUID(filtros["lead_id"]))
        except ValueError:
            filtros["lead_id"] = ""
            ignorados.append("contato")
    try:
        pagina = min(10000, max(1, int(request.GET.get("pagina", 1))))
    except ValueError:
        pagina = 1
    estado, dados = CRMClient().quadro(**filtros, pagina=pagina, por_pagina=100)
    contexto = {"admin": request.admin, "filtros": filtros, "etapas": ETAPAS, "quem_atende": QUEM_ATENDE, "aguardando": AGUARDANDO, "colunas": [], "erro": "", "recado": "Alteração salva." if request.GET.get("salvo") == "1" else ""}
    if ignorados:
        contexto["recado"] = "O filtro de " + " e de ".join(ignorados) + " não foi reconhecido e foi ignorado."
    if estado != CRMClient.OK:
        contexto["erro"] = erro_da_fonte(estado)
        return render(request, "admin/crm.html", contexto, status=503)
    # O filtro "aguardando resposta" é da API de leads (só oportunidade aberta): refiltrar aqui,
    # depois da página que ela devolveu, deixaria o total e a paginação contando outra coisa.
    itens = [preparar(i) for i in dados["itens"]]
    contexto.update(dados)
    contexto["colunas"] = [{"chave": chave, "nome": nome, "itens": [i for i in itens if i.get("etapa") == chave]} for chave, nome in ETAPAS if any(i.get("etapa") == chave for i in itens) or chave in ABERTAS]
    contexto["hoje"] = sorted([i for i in itens if i["aberta"] and i["prazo"] and i["prazo"].date() <= timezone.localdate()], key=lambda i: i["prazo"])[:8]
    parametros = {k: v for k, v in filtros.items() if v}
    contexto["filtrado"] = any(filtros[k] for k in ("q", "etapa", "situacao", "lead_id", "atendido_por", "aguardando_resposta"))
    contexto["proxima"] = "?" + urlencode(dict(parametros, pagina=pagina + 1)) if dados.get("tem_mais") else ""
    contexto["anterior"] = "?" + urlencode(dict(parametros, pagina=pagina - 1)) if pagina > 1 else ""
    return render(request, "admin/crm.html", contexto)


def ficha_contexto(request, chave, *, erro=""):
    estado, item = CRMClient().oportunidade(chave)
    if estado == CRMClient.NAO_EXISTE:
        raise Http404("Oportunidade não encontrada")
    if estado != CRMClient.OK:
        return {"admin": request.admin, "erro": erro_da_fonte(estado)}, 503
    return {"admin": request.admin, "oportunidade": preparar(item), "etapas_abertas": tuple(ABERTAS.items()), "erro": erro, "recado": "Alteração salva." if request.GET.get("salvo") == "1" else ""}, 200


@require_GET
def crm_oportunidade(request, opportunity_id):
    contexto, status = ficha_contexto(request, opportunity_id)
    return render(request, "admin/crm_oportunidade.html", contexto, status=status)


@require_POST
def crm_salvar(request, opportunity_id):
    gesto = request.POST.get("gesto", "")
    autor = str(request.admin.get("id") or request.admin.get("email") or "mantenedor")
    corpo = {"autor_id": autor}
    erro = ""
    if gesto == "passo":
        etapa = request.POST.get("etapa", "")
        prazo = instante(request.POST.get("prazo", ""))
        descricao = request.POST.get("descricao", "").strip()
        if etapa not in ABERTAS or not prazo or not descricao:
            erro = "Escolha a etapa, escreva o próximo passo e informe o prazo."
        else:
            if timezone.is_naive(prazo):
                prazo = timezone.make_aware(prazo, timezone.get_default_timezone())
            corpo.update(etapa=etapa, proximo_passo={"descricao": descricao, "executar_ate": prazo.isoformat(), "evidencia_esperada": request.POST.get("evidencia_esperada", "").strip() or "Resposta do contato registrada no histórico."})
            responsavel = request.POST.get("responsavel", "").strip()
            if responsavel:
                corpo["titular_id"] = responsavel
        metodo, caminho = "PATCH", ""
    elif gesto == "nota":
        corpo["descricao"] = request.POST.get("nota", "").strip()
        if not corpo["descricao"]:
            erro = "Escreva o que aconteceu antes de registrar."
        metodo, caminho = "POST", "/history"
    elif gesto == "encerrar":
        corpo.update(resultado=request.POST.get("resultado", ""), motivo=request.POST.get("motivo", "").strip(), evidencia=request.POST.get("evidencia", "").strip())
        if corpo["resultado"] not in ("perdida", "desqualificada") or not corpo["motivo"] or not corpo["evidencia"]:
            erro = "Informe o resultado, o motivo e o que confirma o encerramento."
        metodo, caminho = "POST", "/close"
    else:
        erro = "Esta alteração não foi reconhecida."
    if erro:
        contexto, status = ficha_contexto(request, opportunity_id, erro=erro)
        contexto["formulario"] = request.POST
        return render(request, "admin/crm_oportunidade.html", contexto, status=422 if status == 200 else status)
    estado, resultado = CRMClient().alterar(opportunity_id, metodo, caminho, corpo)
    Registro.objects.create(quem_email=request.admin.get("email", ""), quem_id=autor[:64], acao=Registro.EDITAR, alvo=str(opportunity_id), desfecho=Registro.OK if estado == CRMClient.OK else Registro.RECUSADO_PELA_CELULA if estado == CRMClient.RECUSADO else Registro.NAO_RESPONDEU, detalhe="CRM: " + gesto)
    if estado == CRMClient.OK:
        return HttpResponseRedirect(reverse("crm_oportunidade", args=[opportunity_id]) + "?salvo=1")
    if estado == CRMClient.NAO_EXISTE:
        raise Http404("Oportunidade não encontrada")
    contexto, status = ficha_contexto(request, opportunity_id, erro=resultado if estado == CRMClient.RECUSADO else "Não conseguimos confirmar que a alteração foi salva. Reabra a ficha antes de tentar novamente.")
    contexto["formulario"] = request.POST
    return render(request, "admin/crm_oportunidade.html", contexto, status=422 if estado == CRMClient.RECUSADO and status == 200 else 503)
