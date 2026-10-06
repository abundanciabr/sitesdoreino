"""Consulta e configuração da satisfação, separada das oportunidades de venda."""

import json
from urllib.parse import urlencode

from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_GET, require_POST

from .clients import CatalogoClient
from .nps_client import NPSClient


def _texto(valor, limite=128):
    return valor.strip()[:limite] if isinstance(valor, str) else ""


def _site(request):
    informado = _texto(request.GET.get("site_id"), 100)
    if informado:
        return informado
    site = CatalogoClient().site_por_host(request.get_host().split(":")[0].lower())
    return str(site.get("id", "")) if isinstance(site, dict) else ""


def _linhas_legiveis(avaliacao):
    prontas = avaliacao.get("respostas_legiveis")
    if isinstance(prontas, list):
        return [
            {"pergunta": _texto(item.get("pergunta") or item.get("texto"), 500),
             "resposta": item.get("resposta") or item.get("valor") or "Não respondido"}
            for item in prontas if isinstance(item, dict)
        ]
    if isinstance(prontas, dict):
        return [{"pergunta": chave, "resposta": valor} for chave, valor in prontas.items()]
    documento = avaliacao.get("config_documento") or avaliacao.get("config_snapshot") or {}
    perguntas = documento.get("perguntas", {}) if isinstance(documento, dict) else {}
    respostas = avaliacao.get("respostas", {})
    if not isinstance(respostas, dict):
        return []
    linhas = []
    for chave, valor in respostas.items():
        pergunta = perguntas.get(chave, {}) if isinstance(perguntas, dict) else {}
        opcoes = pergunta.get("opcoes", []) if isinstance(pergunta, dict) else []
        legenda = next((o.get("texto") for o in opcoes if isinstance(o, dict) and o.get("valor") == valor), None)
        linhas.append({"pergunta": pergunta.get("texto", chave) if isinstance(pergunta, dict) else chave,
                       "resposta": legenda or valor})
    return linhas


def preparar_avaliacoes(historico):
    acoes = {"exibida": "Pergunta exibida", "respondida": "Resposta enviada", "voltar": "Voltou à pergunta", "ramo_abandonado": "Caminho anterior abandonado", "concluida": "Avaliação concluída"}
    for avaliacao in historico.get("avaliacoes", []):
        if isinstance(avaliacao, dict):
            curso = avaliacao.get("curso") or avaliacao.get("produto")
            avaliacao["curso_nome"] = (
                curso.get("nome") or curso.get("name") or "Curso não identificado"
                if isinstance(curso, dict) else str(curso or "Curso não identificado")
            )
            aluno = avaliacao.get("aluno") or {}
            avaliacao["aluno_nome"] = (aluno.get("nome") or aluno.get("email") or "Aluno") if isinstance(aluno, dict) else "Aluno"
            avaliacao["respostas_tela"] = _linhas_legiveis(avaliacao)
            documento = avaliacao.get("config_documento") or {}
            perguntas = documento.get("perguntas", {}) if isinstance(documento, dict) else {}
            registros = avaliacao.get("respostas_registro") or []
            avaliacao["registros_tela"] = []
            for registro in registros if isinstance(registros, list) else []:
                if not isinstance(registro, dict):
                    continue
                chave = registro.get("pergunta_id")
                pergunta = perguntas.get(chave, {}) if isinstance(perguntas, dict) else {}
                opcoes = pergunta.get("opcoes", []) if isinstance(pergunta, dict) else []
                valor = registro.get("valor")
                resposta = next((opcao.get("texto") for opcao in opcoes if isinstance(opcao, dict) and opcao.get("valor") == valor), valor)
                avaliacao["registros_tela"].append({
                    "quando": registro.get("registrado_em"),
                    "pergunta": pergunta.get("texto", chave) if isinstance(pergunta, dict) else chave,
                    "resposta": resposta,
                    "editada": registro.get("valor_anterior") is not None,
                })
            qualidade = avaliacao.get("qualidade") or {}
            evidencias = qualidade.get("evidencias", {}) if isinstance(qualidade, dict) else {}
            registros_locais = evidencias.get("registros_locais", {}) if isinstance(evidencias, dict) else {}
            rotulos = (
                ("aulas_concluidas", "Aulas concluídas neste site"),
                ("entregas", "Entregas neste site"),
                ("comentarios", "Comentários neste site"),
                ("ultima_entrega", "Última entrega neste site"),
            )
            avaliacao["evidencias_tela"] = [
                {"rotulo": rotulo, "valor": registros_locais.get(chave) if registros_locais.get(chave) is not None else "Não disponível"}
                for chave, rotulo in rotulos
            ] if isinstance(registros_locais, dict) else []
            avaliacao["evidencias_observacao"] = evidencias.get("observacao", "") if isinstance(evidencias, dict) else ""
            avaliacao["eventos_tela"] = []
            for evento in qualidade.get("eventos", []) if isinstance(qualidade, dict) else []:
                if not isinstance(evento, dict):
                    continue
                chave = evento.get("pergunta_id")
                pergunta = perguntas.get(chave, {}) if isinstance(perguntas, dict) else {}
                avaliacao["eventos_tela"].append({
                    "quando": evento.get("registrado_em"),
                    "acao": acoes.get(evento.get("acao"), evento.get("acao")),
                    "pergunta": pergunta.get("texto") if isinstance(pergunta, dict) else "",
                })
            resultado = avaliacao.get("resultado") or {}
            motivos = resultado.get("motivos") if isinstance(resultado, dict) else None
            avaliacao["motivos_tela"] = (
                [str(item) for item in motivos] if isinstance(motivos, list)
                else [f"{k}: {v}" for k, v in motivos.items()] if isinstance(motivos, dict)
                else [motivos] if isinstance(motivos, str) and motivos else []
            )
    return historico


@require_GET
def crm_satisfacao(request):
    site_id = _site(request)
    aluno_id = _texto(request.GET.get("aluno_id"))
    email = _texto(request.GET.get("email"), 254).lower()
    cliente = NPSClient()
    estado_config, config = (cliente.configuracao(site_id) if site_id else ("sem-site", None))
    estado_historico, historico = (
        cliente.historico(site_id, aluno_id=aluno_id, email=email)
        if site_id and (aluno_id or email) else ("sem-aluno", None)
    )
    if estado_historico == cliente.OK and (
        not isinstance(historico.get("avaliacoes"), list)
        or not isinstance(historico.get("atendimentos"), list)
    ):
        estado_historico, historico = cliente.INDISPONIVEL, None
    if historico:
        historico = preparar_avaliacoes(historico)
    documento = config.get("documento") if estado_config == cliente.OK else None
    if historico and not aluno_id:
        aluno_id = _texto(historico.get("aluno_id"))
        if not aluno_id and historico.get("avaliacoes"):
            aluno_id = _texto(historico["avaliacoes"][0].get("aluno_id"))
    config_json = json.dumps(documento, ensure_ascii=False, indent=2) if isinstance(documento, dict) else ""
    return render(request, "admin/crm_satisfacao.html", {
        "admin": request.admin,
        "site_id": site_id,
        "aluno_id": aluno_id,
        "email": email,
        "estado_config": estado_config,
        "config": config or {},
        "config_json": config_json,
        "estado_historico": estado_historico,
        "historico": historico or {},
        "salvo": request.GET.get("salvo") == "1",
        "atendido": request.GET.get("atendido") == "1",
    })


@require_POST
def crm_satisfacao_config_salvar(request):
    site_id = _texto(request.POST.get("site_id"), 100)
    if not site_id:
        return _erro(request, "Informe o site antes de salvar a configuração.")
    texto = request.POST.get("documento") or ""
    try:
        documento = json.loads(texto)
    except (ValueError, TypeError):
        return _erro(request, "O documento precisa ser JSON válido.", site_id=site_id, documento=texto)
    if not isinstance(documento, dict):
        return _erro(request, "O documento precisa ser um objeto JSON.", site_id=site_id, documento=texto)
    estado, detalhe = NPSClient().salvar_configuracao(site_id, documento)
    if estado != NPSClient.OK:
        return _erro(request, detalhe if isinstance(detalhe, str) else "Não foi possível salvar a configuração.", site_id=site_id, documento=texto)
    return HttpResponseRedirect(reverse("crm_satisfacao") + "?" + urlencode({"site_id": site_id, "salvo": "1"}))


@require_POST
def crm_satisfacao_atendimento_salvar(request):
    site_id = _texto(request.POST.get("site_id"), 100)
    aluno_id = _texto(request.POST.get("aluno_id"))
    if not site_id or not aluno_id:
        return _erro(request, "Informe o site e o ID do aluno para registrar o atendimento.")
    corpo = {
        "site_id": site_id,
        "aluno_id": aluno_id,
        "tentativa_id": _texto(request.POST.get("tentativa_id"), 100) or None,
        "responsavel": _texto(request.POST.get("responsavel"), 120),
        "proximo_passo": _texto(request.POST.get("proximo_passo"), 2000),
        "prazo": None,
        "solucao": _texto(request.POST.get("solucao"), 2000),
        "status": _texto(request.POST.get("status"), 40),
    }
    prazo_texto = _texto(request.POST.get("prazo"), 40)
    if prazo_texto:
        prazo = parse_datetime(prazo_texto)
        if prazo is None:
            return _erro(request, "O prazo informado não é uma data válida.", site_id=site_id, aluno_id=aluno_id)
        if timezone.is_naive(prazo):
            prazo = timezone.make_aware(prazo, timezone.get_default_timezone())
        corpo["prazo"] = prazo.isoformat()
    atendimento_id = _texto(request.POST.get("atendimento_id"), 100)
    if atendimento_id:
        corpo["id"] = atendimento_id
    estado, detalhe = NPSClient().salvar_atendimento(corpo)
    if estado != NPSClient.OK:
        return _erro(request, detalhe if isinstance(detalhe, str) else "Não foi possível registrar o atendimento.", site_id=site_id, aluno_id=aluno_id)
    return HttpResponseRedirect(reverse("crm_satisfacao") + "?" + urlencode({"site_id": site_id, "aluno_id": aluno_id, "atendido": "1"}))


def _erro(request, mensagem, *, site_id="", aluno_id="", documento=""):
    return render(request, "admin/crm_satisfacao.html", {
        "admin": request.admin, "site_id": site_id, "aluno_id": aluno_id,
        "erro": mensagem, "config_json": documento,
        "estado_config": "indisponivel", "estado_historico": "indisponivel",
        "config": {}, "historico": {},
    }, status=400)
