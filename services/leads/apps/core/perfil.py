"""Perfil do lead: o que o analista entendeu da pessoa, com as provas.

Cada afirmação aponta para a resposta ou mensagem que a sustenta
(`evidencias`: tipo, id e trecho). Afirmação sem evidência é guardada como
hipótese e aparece como hipótese. Cada gravação é uma versão nova; a anterior
fica no histórico.
"""

import json
import re

from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from ninja import Router
from ninja.errors import HttpError

from .models import Lead, PerfilDoLead
from .crm import _admin
from .quiz_do_lead import lead_ou_404

router = Router()

CAMPOS_UNICOS = ("objetivo_declarado", "experiencia", "disponibilidade")
CAMPOS_LISTA = ("duvidas", "objecoes", "hipoteses")
CAMPOS_TEXTOS = ("informacoes_ausentes", "perguntas_uteis")
PERMITIDOS = {
    "resumo", *CAMPOS_UNICOS, *CAMPOS_LISTA, *CAMPOS_TEXTOS, "prioridade",
    "oferta_indicada", "analisado_em", "analisado_por", "versao_estrategia",
    "versao_base",
}
LIMITE_DE_ITENS = 30
LIMITE_DE_TEXTO = 4000


def _texto(valor, campo, limite=LIMITE_DE_TEXTO, obrigatorio=False) -> str:
    if valor is None:
        valor = ""
    if not isinstance(valor, str):
        raise HttpError(422, f"{campo} precisa ser texto")
    valor = valor.strip()
    if obrigatorio and not valor:
        raise HttpError(422, f"{campo} precisa ser um texto não vazio")
    return valor[:limite]


def _evidencias(bruto, campo) -> list:
    if bruto is None:
        return []
    if not isinstance(bruto, list):
        raise HttpError(422, f"{campo}.evidencias precisa ser uma lista")
    saida = []
    for item in bruto[:LIMITE_DE_ITENS]:
        if not isinstance(item, dict):
            raise HttpError(422, f"{campo}.evidencias: cada item é {{tipo, id, trecho}}")
        saida.append({
            "tipo": _texto(item.get("tipo"), f"{campo}.evidencias.tipo", 30, True),
            "id": _texto(item.get("id"), f"{campo}.evidencias.id", 200, True),
            "trecho": _texto(item.get("trecho"), f"{campo}.evidencias.trecho", 1000),
        })
    return saida


def _normalizado(texto) -> str:
    texto = re.sub(r"[\"'“”‘’«»]", " ", str(texto or "")).casefold()
    return " ".join(texto.split())


class ProvasDoContato:
    """O que deste contato pode ser citado como prova.

    Evidência de quiz, linha do tempo ou oportunidade precisa apontar para um
    registro DESTE contato, e o trecho precisa estar nele. Evidência de outra
    célula (mensagem, catálogo...) não é conferida aqui. A que não confere é
    deixada de fora e devolvida em `evidencias_recusadas`; sem nenhuma
    evidência, a afirmação vira hipótese.
    """

    DO_QUIZ = {"quiz", "resposta", "respostas"}
    DA_LINHA_DO_TEMPO = {"timeline", "evento", "linha_do_tempo"}
    DA_OPORTUNIDADE = {"oportunidade", "historico", "nota"}

    def __init__(self, lead):
        self.recusadas = []
        self.ids = {"quiz": set(), "linha": set(), "oportunidade": set()}
        textos = {"quiz": [], "linha": [], "oportunidade": []}
        for quiz in lead.quizzes.all():
            self.ids["quiz"] |= {str(quiz.id), quiz.submissao_id, quiz.sessao, quiz.captura_id}
            if quiz.resultado:
                self.ids["quiz"].add("resultado")
                textos["quiz"].append(quiz.resultado)
            for item in quiz.respostas or []:
                self.ids["quiz"].add(item.get("pergunta_id") or "")
                textos["quiz"].append(item.get("pergunta") or "")
                textos["quiz"] += [r.get("texto") or "" for r in item.get("respostas") or []]
                textos["quiz"].append(item.get("valor_livre") or "")
        for evento in lead.timeline.order_by("-occurred_at", "-id")[:500]:
            self.ids["linha"] |= {str(evento.id), str(evento.event_id or "")}
            textos["linha"].append(json.dumps(evento.payload, ensure_ascii=False))
        for oportunidade in lead.oportunidades.all():
            self.ids["oportunidade"].add(str(oportunidade.id))
            textos["oportunidade"] += [oportunidade.passo_descricao, oportunidade.objecao_principal]
            for registro in oportunidade.historico.all():
                self.ids["oportunidade"].add(str(registro.id))
                textos["oportunidade"] += [registro.descricao, registro.evidencia]
        for chave in self.ids:
            self.ids[chave].discard("")
        self.textos = {chave: _normalizado(" \n ".join(v)) for chave, v in textos.items()}

    def _fonte(self, tipo):
        tipo = tipo.casefold()
        if tipo in self.DO_QUIZ:
            return "quiz"
        if tipo in self.DA_LINHA_DO_TEMPO:
            return "linha"
        if tipo in self.DA_OPORTUNIDADE:
            return "oportunidade"
        return None

    def confere(self, evidencia, campo) -> bool:
        fonte = self._fonte(evidencia["tipo"])
        if fonte is None:
            return True
        partes = [p for p in re.split(r"[:#/]", evidencia["id"]) if p]
        id_ok = evidencia["id"] in self.ids[fonte] or any(p in self.ids[fonte] for p in partes)
        pedacos = [_normalizado(p) for p in re.split(r"\.\.\.|…", evidencia["trecho"])]
        trecho_ok = all(p in self.textos[fonte] for p in pedacos if p)
        if id_ok and trecho_ok:
            return True
        self.recusadas.append({
            "campo": campo, **evidencia,
            "motivo": "não é deste contato" if not id_ok else "trecho não está no registro",
        })
        return False


def _afirmacao(bruto, campo, *, hipotese=False, provas=None):
    """{texto, evidencias, hipotese}. Sem evidência, é hipótese."""
    if bruto is None or bruto == "":
        return None
    if isinstance(bruto, str):
        bruto = {"texto": bruto}
    if not isinstance(bruto, dict):
        raise HttpError(422, f"{campo} precisa ser {{texto, evidencias}}")
    texto = _texto(bruto.get("texto"), f"{campo}.texto", obrigatorio=True)
    evidencias = _evidencias(bruto.get("evidencias"), campo)
    if provas is not None:
        evidencias = [e for e in evidencias if provas.confere(e, campo)]
    return {
        "texto": texto,
        "evidencias": evidencias,
        "hipotese": bool(hipotese or bruto.get("hipotese") or not evidencias),
    }


def _lista(bruto, campo, *, hipotese=False, provas=None) -> list:
    if bruto is None:
        return []
    if not isinstance(bruto, list):
        raise HttpError(422, f"{campo} precisa ser uma lista")
    itens = [_afirmacao(item, campo, hipotese=hipotese, provas=provas)
             for item in bruto[:LIMITE_DE_ITENS]]
    return [item for item in itens if item]


def _textos(bruto, campo) -> list:
    if bruto is None:
        return []
    if not isinstance(bruto, list):
        raise HttpError(422, f"{campo} precisa ser uma lista de textos")
    return [t for t in (_texto(item, campo, 1000) for item in bruto[:LIMITE_DE_ITENS]) if t]


def _prioridade(bruto) -> tuple[str, str]:
    if bruto is None:
        return "", ""
    if isinstance(bruto, str):
        bruto = {"nivel": bruto}
    if not isinstance(bruto, dict):
        raise HttpError(422, "prioridade precisa ser {nivel, explicacao}")
    nivel = bruto.get("nivel") or ""
    if nivel and nivel not in PerfilDoLead.PRIORIDADES:
        raise HttpError(422, "prioridade.nivel precisa ser alta, media ou baixa")
    return nivel, _texto(bruto.get("explicacao"), "prioridade.explicacao")


def _oferta(bruto, provas=None):
    if bruto is None or bruto == "":
        return None
    if isinstance(bruto, str):
        bruto = {"oferta_ref": bruto}
    if not isinstance(bruto, dict):
        raise HttpError(422, "oferta_indicada precisa ser {oferta_ref, nome, motivo}")
    evidencias = _evidencias(bruto.get("evidencias"), "oferta_indicada")
    if provas is not None:
        evidencias = [e for e in evidencias if provas.confere(e, "oferta_indicada")]
    oferta = {
        "oferta_ref": _texto(bruto.get("oferta_ref"), "oferta_indicada.oferta_ref", 200),
        "nome": _texto(bruto.get("nome"), "oferta_indicada.nome", 300),
        "motivo": _texto(bruto.get("motivo"), "oferta_indicada.motivo"),
        "evidencias": evidencias,
    }
    if not (oferta["oferta_ref"] or oferta["nome"]):
        raise HttpError(422, "oferta_indicada precisa de oferta_ref ou nome")
    return oferta


def _analisado_em(bruto):
    if bruto in (None, ""):
        return timezone.now()
    momento = parse_datetime(bruto) if isinstance(bruto, str) else None
    if momento is None:
        raise HttpError(422, "analisado_em precisa ser data e hora ISO 8601")
    if timezone.is_naive(momento):
        momento = timezone.make_aware(momento, timezone.get_current_timezone())
    return momento


CAMPOS_DA_ANALISE = ("resumo", "conteudo", "prioridade", "prioridade_explicacao",
                     "oferta_indicada", "analisado_por", "versao_estrategia")


def _repete_a_vigente(perfil: PerfilDoLead | None, dados: dict) -> bool:
    """Reenvio da mesma análise (o analista tentou de novo depois de um tempo esgotado).

    Vale quando tudo o que a análise diz, e quem a fez, é igual à versão vigente;
    só a hora em que foi montada pode mudar de uma tentativa para outra.
    """
    if perfil is None:
        return False

    def forma(origem):
        return json.dumps({c: origem[c] for c in CAMPOS_DA_ANALISE}, sort_keys=True, default=str)

    return forma(dados) == forma({c: getattr(perfil, c) for c in CAMPOS_DA_ANALISE})


def como_perfil(perfil: PerfilDoLead) -> dict:
    conteudo = perfil.conteudo or {}
    visto = {
        "lead_id": str(perfil.lead_id),
        "versao": perfil.versao,
        "resumo": perfil.resumo,
    }
    for campo in CAMPOS_UNICOS:
        visto[campo] = conteudo.get(campo)
    for campo in (*CAMPOS_LISTA, *CAMPOS_TEXTOS):
        visto[campo] = conteudo.get(campo) or []
    visto.update({
        "prioridade": {
            "nivel": perfil.prioridade, "explicacao": perfil.prioridade_explicacao,
        } if perfil.prioridade or perfil.prioridade_explicacao else None,
        "oferta_indicada": perfil.oferta_indicada,
        "analisado_em": perfil.analisado_em.isoformat(),
        "analisado_por": perfil.analisado_por,
        "versao_estrategia": perfil.versao_estrategia,
        "registrado_em": perfil.registrado_em.isoformat(),
    })
    return visto


def perfil_vigente(lead) -> PerfilDoLead | None:
    return lead.perfis.order_by("-versao").first()


def resumo_do_perfil(lead) -> dict | None:
    perfil = perfil_vigente(lead)
    if perfil is None:
        return None
    visto = como_perfil(perfil)
    visto["fatos_novos_desde_a_analise"] = lead.timeline.filter(
        occurred_at__gt=perfil.analisado_em
    ).count()
    return visto


def _corpo(request) -> dict:
    try:
        corpo = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        raise HttpError(422, "JSON inválido")
    if not isinstance(corpo, dict):
        raise HttpError(422, "o corpo precisa ser um objeto JSON")
    estranhas = sorted(set(corpo) - PERMITIDOS)
    if estranhas:
        raise HttpError(422, f"campos não previstos: {', '.join(estranhas)}")
    return corpo


@router.get(
    "/leads/{lead_id}/perfil",
    operation_id="getPerfilDoLead",
    summary="Perfil vigente do contato, com evidências; 404 se ainda não foi analisado",
)
def ler_perfil(request, lead_id: str):
    _admin(request)
    lead = lead_ou_404(lead_id)
    visto = resumo_do_perfil(lead)
    if visto is None:
        raise HttpError(404, "Perfil ainda não analisado")
    visto["versoes"] = lead.perfis.count()
    return JsonResponse(visto)


@router.put(
    "/leads/{lead_id}/perfil",
    operation_id="putPerfilDoLead",
    summary="Grava uma versão nova do perfil (usado pelo agente analista)",
)
def gravar_perfil(request, lead_id: str):
    _admin(request)
    lead = lead_ou_404(lead_id)
    corpo = _corpo(request)
    provas = ProvasDoContato(lead)
    conteudo = {campo: _afirmacao(corpo.get(campo), campo, provas=provas)
                for campo in CAMPOS_UNICOS}
    conteudo["duvidas"] = _lista(corpo.get("duvidas"), "duvidas", provas=provas)
    conteudo["objecoes"] = _lista(corpo.get("objecoes"), "objecoes", provas=provas)
    conteudo["hipoteses"] = _lista(corpo.get("hipoteses"), "hipoteses", hipotese=True,
                                   provas=provas)
    for campo in CAMPOS_TEXTOS:
        conteudo[campo] = _textos(corpo.get(campo), campo)
    nivel, explicacao = _prioridade(corpo.get("prioridade"))
    dados = {
        "resumo": _texto(corpo.get("resumo"), "resumo"),
        "conteudo": conteudo,
        "prioridade": nivel,
        "prioridade_explicacao": explicacao,
        "oferta_indicada": _oferta(corpo.get("oferta_indicada"), provas),
        "analisado_em": _analisado_em(corpo.get("analisado_em")),
        "analisado_por": _texto(corpo.get("analisado_por"), "analisado_por", 200),
        "versao_estrategia": _texto(corpo.get("versao_estrategia"), "versao_estrategia", 100),
    }
    base = corpo.get("versao_base")
    if base is not None and (not isinstance(base, int) or isinstance(base, bool)):
        raise HttpError(422, "versao_base precisa ser número inteiro")
    try:
        with transaction.atomic():
            Lead.objects.select_for_update().filter(pk=lead.pk).get()
            vigente = lead.perfis.order_by("-versao").first()
            atual = vigente.versao if vigente else 0
            if base is not None and base != atual:
                raise HttpError(409, f"o perfil já está na versão {atual}; leia de novo")
            if base is None and _repete_a_vigente(vigente, dados):
                perfil = vigente
            else:
                perfil = PerfilDoLead.objects.create(lead=lead, versao=atual + 1, **dados)
    except IntegrityError:
        raise HttpError(409, "outra análise gravou ao mesmo tempo; leia de novo")
    visto = como_perfil(perfil)
    visto["versoes"] = perfil.versao
    visto["evidencias_recusadas"] = provas.recusadas
    return JsonResponse(visto)


@router.get(
    "/leads/{lead_id}/perfil/versoes",
    operation_id="listPerfilDoLeadVersoes",
    summary="Histórico de versões do perfil, da mais nova à mais antiga",
)
def versoes_do_perfil(request, lead_id: str):
    _admin(request)
    lead = lead_ou_404(lead_id)
    return JsonResponse({
        "lead_id": str(lead.id),
        "versoes": [como_perfil(p) for p in lead.perfis.order_by("-versao")[:100]],
    })
