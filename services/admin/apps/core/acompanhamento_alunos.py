"""Acompanhamento pedagógico, sem criar oportunidades comerciais.

Contrato de rotas para config/urls.py:
``path('escola/alunos/acompanhamento/', acompanhamento_alunos, name='acompanhamento_alunos')``
``path('escola/alunos/acompanhamento/ficha/', acompanhamento_aluno, name='acompanhamento_aluno')``
A ficha recebe ``email`` e ``site_id`` pela query string; POST vai à mesma rota.
O middleware PortaAdministrativa protege ambas sob a URL da administração.
"""

from __future__ import annotations

from urllib.parse import urlencode

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import Http404, HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_GET, require_http_methods

from .acompanhamento_modelo import RegistroAcompanhamentoAluno as Registro
from .clients import AlunosClient, CatalogoClient, LeadsClient
from .crm_client import CRMClient


def _texto(valor, limite=300):
    return valor.strip()[:limite] if isinstance(valor, str) else ""


def _chave(email, site_id):
    email, site_id = _texto(email, 254).lower(), _texto(site_id, 100)
    try:
        validate_email(email)
    except ValidationError:
        raise Http404("Aluno não encontrado")
    if not site_id:
        raise Http404("Aluno não encontrado")
    return site_id, email


def _matriculas(site_id, email, linhas):
    return [m for m in linhas if _texto(m.get("site_id"), 100) == site_id
            and _texto(m.get("email"), 254).lower() == email]


def _resumo_atual():
    """Um registro mais recente por pessoa e curso; o curso vazio é geral."""
    atual = {}
    for registro in Registro.objects.all():
        atual.setdefault((registro.site_id, registro.email, registro.product_id), registro)
    return atual


def _url_ficha(site_id, email):
    return reverse("acompanhamento_aluno") + "?" + urlencode({"site_id": site_id, "email": email})


@require_GET
def acompanhamento_alunos(request):
    if request.admin.get("equipe_apenas"):
        return HttpResponseForbidden()
    linhas = AlunosClient().alunos()
    grupos = {}
    if linhas is not None:
        for linha in linhas:
            site_id, email = _texto(linha.get("site_id"), 100), _texto(linha.get("email"), 254).lower()
            if not site_id or not email:
                continue
            grupo = grupos.setdefault((site_id, email), {
                "site_id": site_id, "email": email, "nome": "", "matriculas": [],
                "turmas": set(), "url": _url_ficha(site_id, email),
            })
            grupo["nome"] = grupo["nome"] or _texto(linha.get("nome_completo"), 200)
            grupo["matriculas"].append(linha)
            if linha.get("turma"):
                grupo["turmas"].add(str(linha["turma"]))
    atuais = _resumo_atual()
    q = _texto(request.GET.get("q"), 120).casefold()
    status = _texto(request.GET.get("status"), 24)
    situacao = _texto(request.GET.get("situacao_curso"), 24)
    site = _texto(request.GET.get("site_id"), 100)
    atraso = request.GET.get("atraso") == "sim"
    sem_registro = request.GET.get("sem_registro") == "sim"
    if status not in Registro.Status.values:
        status = ""
    if situacao not in Registro.SituacaoCurso.values:
        situacao = ""
    itens = []
    sites = sorted({g["site_id"] for g in grupos.values()})
    resumo = {"pessoas": len(grupos), "sem_registro": 0, "atrasados": 0,
              "esperando_resposta": 0, "em_andamento": 0, "resolvido": 0}
    hoje = timezone.localdate()
    for chave, grupo in grupos.items():
        casos = [r for (site_reg, email_reg, _), r in atuais.items()
                 if (site_reg, email_reg) == chave]
        casos.sort(key=lambda r: (r.criado_em, r.pk), reverse=True)
        ultimo = casos[0] if casos else None
        grupo["ultimo"] = ultimo
        grupo["acompanhamentos"] = casos
        grupo["atrasado"] = any(r.prazo and r.prazo < hoje
                                and r.status != Registro.Status.RESOLVIDO for r in casos)
        if any(r.status == Registro.Status.ESPERANDO_RESPOSTA for r in casos):
            resumo["esperando_resposta"] += 1
        elif any(r.status == Registro.Status.EM_ANDAMENTO for r in casos):
            resumo["em_andamento"] += 1
        elif casos:
            resumo["resolvido"] += 1
        else:
            resumo["sem_registro"] += 1
        if grupo["atrasado"]:
            resumo["atrasados"] += 1
        grupo["turmas"] = ", ".join(sorted(grupo["turmas"]))
        if q and q not in " ".join([grupo["nome"], grupo["email"], grupo["turmas"]]).casefold():
            continue
        if site and grupo["site_id"] != site:
            continue
        if status and not any(r.status == status for r in casos):
            continue
        if situacao and not any(r.situacao_curso == situacao for r in casos):
            continue
        if atraso and not grupo["atrasado"]:
            continue
        if sem_registro and ultimo:
            continue
        itens.append(grupo)
    itens.sort(key=lambda g: (g["nome"] or g["email"]).casefold())
    return render(request, "admin/acompanhamento_alunos.html", {
        "admin": request.admin, "itens": itens, "fonte_indisponivel": linhas is None,
        "q": q, "status": status, "situacao": situacao, "site_id": site,
        "atraso": atraso, "sem_registro": sem_registro, "resumo": resumo,
        "sites": sites,
        "status_opcoes": Registro.Status.choices, "situacao_opcoes": Registro.SituacaoCurso.choices,
    })


def _fontes_externas(site_id, email, matriculas):
    """Só consulta contatos já vinculados à matrícula e atendimentos existentes."""
    ids = list(dict.fromkeys(str(m.get("contato_crm_id")) for m in matriculas if m.get("contato_crm_id")))
    contatos, atendimentos = [], []
    contato_estado = "sem_vinculo"
    atendimento_estado = "sem_vinculo"
    if not ids:
        contato_estado, resposta = LeadsClient().listar(q=email, site_id=site_id, por_pagina=50)
        if contato_estado == LeadsClient.OK and isinstance(resposta, dict):
            ids = [str(i.get("id")) for i in resposta.get("itens", []) if isinstance(i, dict)
                   and _texto(i.get("email"), 254).lower() == email
                   and _texto(i.get("site_id"), 100) == site_id and i.get("id")]
            if not ids:
                contato_estado = "sem_vinculo"
    for lead_id in ids:
        estado, contato = LeadsClient().ficha(lead_id)
        contato_estado = estado
        if estado != LeadsClient.OK or not isinstance(contato, dict):
            continue
        # A referência é da matrícula, mas ainda conferimos a identidade devolvida.
        if _texto(contato.get("email"), 254).lower() != email or (
            contato.get("site_id") and _texto(contato.get("site_id"), 100) != site_id
        ):
            continue
        contatos.append(contato)
        estado_crm, quadro = CRMClient().quadro(lead_id=lead_id)
        atendimento_estado = estado_crm
        if estado_crm == CRMClient.OK:
            atendimentos.extend(i for i in quadro.get("itens", [])
                                 if str(i.get("lead_id") or (i.get("contato") or {}).get("id")) == lead_id)
    return contatos, contato_estado, atendimentos, atendimento_estado


def _contexto(request, site_id, email, matriculas, *, erro="", dados=None):
    historico = list(Registro.objects.filter(site_id=site_id, email=email))
    produtos = CatalogoClient().listar_produtos()
    nomes_produtos = {str(p.get("id")): p.get("name") or p.get("nome") for p in (produtos or []) if isinstance(p, dict)}
    for matricula in matriculas:
        matricula["curso_nome"] = nomes_produtos.get(str(matricula.get("product_id"))) or matricula.get("product_id") or "Curso não identificado"
    contatos, contato_estado, atendimentos, atendimento_estado = _fontes_externas(site_id, email, matriculas)
    from .acompanhamento_fontes import consultar_fontes
    fontes = consultar_fontes(site_id, email)
    return {
        "admin": request.admin, "site_id": site_id, "email": email,
        "nome": next((_texto(m.get("nome_completo"), 200) for m in matriculas if m.get("nome_completo")), email),
        "matriculas": matriculas, "historico": historico, "ultimo": historico[0] if historico else None,
        "contatos": contatos, "contato_estado": contato_estado,
        "atendimentos": atendimentos, "atendimento_estado": atendimento_estado,
        "fontes": fontes,
        "status_opcoes": Registro.Status.choices, "situacao_opcoes": Registro.SituacaoCurso.choices,
        "erro": erro, "dados": dados or {}, "salvo": request.GET.get("salvo") == "1",
    }


@require_http_methods(["GET", "POST"])
def acompanhamento_aluno(request):
    if request.admin.get("equipe_apenas"):
        return HttpResponseForbidden()
    origem = request.POST if request.method == "POST" else request.GET
    site_id, email = _chave(origem.get("email"), origem.get("site_id"))
    linhas = AlunosClient().alunos()
    if linhas is None:
        return render(request, "admin/acompanhamento_aluno.html", {
            "admin": request.admin, "fonte_indisponivel": True, "site_id": site_id, "email": email,
        }, status=503)
    matriculas = _matriculas(site_id, email, linhas)
    if not matriculas:
        raise Http404("Aluno não encontrado")
    erro = ""
    if request.method == "POST":
        dados = request.POST
        status = _texto(dados.get("status"), 24)
        situacao = _texto(dados.get("situacao_curso"), 24)
        product_id = _texto(dados.get("product_id"), 200)
        progresso = _texto(dados.get("progresso_externo"), 300)
        fonte = _texto(dados.get("fonte"), 300)
        prazo_texto = _texto(dados.get("prazo"), 10)
        try:
            prazo = parse_date(prazo_texto) if prazo_texto else None
        except ValueError:
            prazo = None
        if status not in Registro.Status.values or situacao not in Registro.SituacaoCurso.values:
            erro = "Escolha uma situação de acompanhamento e uma situação do curso."
        elif product_id and product_id not in {str(m.get("product_id")) for m in matriculas}:
            erro = "Escolha um curso desta pessoa."
        elif prazo_texto and prazo is None:
            erro = "Informe um prazo válido."
        elif (progresso or situacao == Registro.SituacaoCurso.ATIVIDADE_OBSERVADA) and not fonte:
            erro = "Informe a fonte do progresso ou da atividade observada."
        else:
            Registro.objects.create(
                site_id=site_id, email=email, product_id=product_id,
                status=status, situacao_curso=situacao, progresso_externo=progresso,
                fonte=fonte, dificuldade=_texto(dados.get("dificuldade"), 3000),
                responsavel=_texto(dados.get("responsavel"), 200),
                proximo_contato=_texto(dados.get("proximo_contato"), 3000),
                prazo=prazo, resultado=_texto(dados.get("resultado"), 3000),
                registrado_por=_texto(request.admin.get("email"), 200) or "administrador",
            )
            return HttpResponseRedirect(_url_ficha(site_id, email) + "&salvo=1")
    return render(request, "admin/acompanhamento_aluno.html", _contexto(
        request, site_id, email, matriculas, erro=erro, dados=request.POST if erro else None,
    ), status=400 if erro else 200)
