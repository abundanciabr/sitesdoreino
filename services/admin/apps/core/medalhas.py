"""Medalhas dadas pelo administrador, com prévia sem concessão."""
from urllib.parse import quote, urlencode

import httpx
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import Http404, HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from .acompanhamento_fontes import _pedir
from .clients import AlunosClient, GamificacaoClient, IdentidadeClient, http
from .nps_client import NPSClient
from .nps_painel import preparar_painel

MENSAGEM = "Sua presença faz a diferença na nossa comunidade. Esta medalha é um reconhecimento da equipe Meshcraft para você!"
MENSAGEM_EMBAIXADOR = "Sua nota 10 e sua confiança na Meshcraft merecem ser celebradas. Obrigado por fazer parte da nossa história!"


def _identidade(email):
    config = IdentidadeClient()._configuracao()
    estado, dados = _pedir(*config, "/pessoas/por-email", metodo="POST", corpo={"email": email}) if config else ("indisponivel", None)
    return str(dados.get("id") or "") if estado == "ok" and isinstance(dados, dict) else ""


def _medalhas(site, pessoa, dados=None):
    config = GamificacaoClient()._configuracao()
    if not config:
        return None
    base, token = config
    try:
        resposta = http().request(
            "POST" if dados is not None else "GET",
            base.rstrip("/") + "/medalhas-painel/" + quote(site, safe="") + "/" + quote(pessoa, safe=""),
            json=dados, headers={"Authorization": "Bearer " + token}, timeout=10,
        )
        corpo = resposta.json()
        if resposta.status_code == 409 and isinstance(corpo, dict):
            return {"erro": corpo.get("detail", "Não foi possível conceder esta medalha.")}
        if resposta.status_code != 200 or not isinstance(corpo, dict):
            return None
        return corpo
    except (httpx.HTTPError, ValueError):
        return None


@never_cache
@require_http_methods(["GET", "POST"])
def painel(request):
    if request.admin.get("equipe_apenas"):
        return HttpResponseForbidden()
    dados = request.POST if request.method == "POST" else request.GET
    site, email = dados.get("site_id", "").strip()[:64], dados.get("email", "").strip().lower()[:254]
    try:
        validate_email(email)
    except ValidationError:
        raise Http404("Aluno não encontrado")
    if not site:
        raise Http404("Escola não encontrada")
    ficha = AlunosClient().prontuario(email)
    erro = ""
    if ficha is None:
        erro = "Não foi possível consultar a ficha do aluno agora. Tente novamente."
    elif not any(p.get("site_id") == site for p in ficha.get("passagens", [])):
        raise Http404("Aluno não encontrado nesta escola")
    avaliacao_id = dados.get("avaliacao", "").strip()[:100]
    avaliacao = None
    if avaliacao_id and not erro:
        estado, historico = NPSClient().historico(site, email=email)
        if estado == NPSClient.OK and isinstance(historico, dict):
            avaliacao = next((a for a in historico.get("avaliacoes", [])
                              if a.get("id") == avaliacao_id and
                              (a.get("aluno") or {}).get("email", "").lower() == email), None)
        if not avaliacao:
            erro = "Não foi possível conferir esta avaliação. Volte à pesquisa e selecione o aluno novamente."
    nota = preparar_painel(avaliacao).get("nota") if avaliacao else None
    nome = dados.get("nome", "Embaixador").strip()
    mensagem = dados.get("mensagem", MENSAGEM_EMBAIXADOR if nota == 10 else MENSAGEM).strip()
    pessoa = _identidade(email) if not erro else ""
    if not pessoa and not erro:
        erro = "Este aluno ainda não tem uma conta identificada na plataforma, ou a consulta está indisponível. A medalha precisa de uma conta para aparecer ao aluno."
    resultado = None
    if request.method == "POST" and not erro:
        if request.admin.get("robo") or not request.admin.get("id"):
            return HttpResponseForbidden("A concessão deve ser feita pelo administrador no painel.")
        if not nome or len(nome) > 120 or not mensagem or len(mensagem) > 1000:
            erro = "Preencha o nome (até 120 caracteres) e a mensagem (até 1.000 caracteres)."
        else:
            resultado = _medalhas(site, pessoa, {
                "nome": nome, "mensagem": mensagem, "quem_id": request.admin["id"],
                "referencia": "satisfacao:" + avaliacao_id if avaliacao_id else "painel-do-aluno",
            })
            if resultado and isinstance(resultado.get("medalha"), dict) and type(resultado.get("nova")) is bool:
                params = {"site_id": site, "email": email, "avaliacao": avaliacao_id,
                          "concedida": str(resultado["medalha"].get("id", ""))}
                return HttpResponseRedirect(reverse("escola_medalhas") + "?" + urlencode(params))
            erro = (resultado or {}).get("erro") or "Não foi possível confirmar a concessão. Consulte a lista abaixo ou tente novamente; repetir a mesma medalha não a duplica."
    resposta = _medalhas(site, pessoa) if pessoa else None
    medalhas = resposta.get("medalhas") if isinstance(resposta, dict) else None
    medalhas = medalhas if isinstance(medalhas, list) else None
    concedida = next((m for m in medalhas or [] if str(m.get("id")) == request.GET.get("concedida")), None)
    voltar = reverse("crm_satisfacao") + "?" + urlencode({"site_id": site, "email": email, "avaliacao": avaliacao_id})
    if not avaliacao_id:
        voltar = reverse("escola_prontuario") + "?" + urlencode({"email": email})
    return render(request, "admin/medalhas.html", {
        "admin": request.admin, "site_id": site, "email": email, "ficha": ficha or {},
        "avaliacao": avaliacao_id, "nota": nota, "nome": nome, "mensagem": mensagem,
        "erro": erro, "pode_conceder": bool(pessoa and not erro), "medalhas": medalhas,
        "concedida": concedida, "voltar": voltar,
        "previa_url": reverse("escola_medalhas_previa") + "?" + urlencode({"nome": nome, "mensagem": mensagem}),
    })


@never_cache
@require_GET
def previa(request):
    if request.admin.get("equipe_apenas"):
        return HttpResponseForbidden()
    return render(request, "admin/medalhas_previa.html", {"previa": {
        "nome": request.GET.get("nome", "Embaixador").strip()[:120] or "Embaixador",
        "mensagem": request.GET.get("mensagem", MENSAGEM_EMBAIXADOR).strip()[:1000],
        "previa": True,
    }})
