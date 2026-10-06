"""Avaliação de satisfação interna, isolada do funil comercial do quiz."""

import copy
import json

from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt

from .editor import _authorized
from .models import NPSAtendimento, NPSConfig, NPSTentativa, Site


CALCULO_VERSAO = 1
PERGUNTAS = {
    "nota": ("De 0 a 10, quanto você recomendaria sua experiência?", "nota", []),
    "repercussao": ("Quantas pessoas demonstraram interesse no seu progresso desde que você entrou no curso?", "escolha", [("mais_3", "Mais de três pessoas"), ("1_2", "Uma ou duas pessoas"), ("nenhuma", "Nenhuma pessoa")]),
    "nome_indicado": ("Quer registrar o nome de alguém? É opcional e não implica desconto ou promessa.", "texto", []),
    "indicacao": ("Você indicou o curso?", "escolha", [("sim", "Sim"), ("nao", "Não"), ("sem_oportunidade", "Ainda não tive oportunidade")]),
    "orcamento": ("Se o orçamento apertasse e você precisasse cortar gastos, o curso seria...", "escolha", [("ultimo", "O último item que eu cogitaria cortar"), ("pausar", "Algo que eu tentaria renegociar ou pausar temporariamente")]),
    "gargalo": ("Qual foi o principal gargalo?", "escolha", [("pedagogico", "Pedagógico"), ("tecnologico", "Tecnológico"), ("tempo", "Tempo"), ("outro", "Outro")]),
    "concorrente": ("Se um concorrente oferecesse a mesma grade por 20% menos, o que você faria?", "escolha", [("migrar", "Migraria para o concorrente"), ("pesquisar", "Pesquisaria melhor antes de decidir"), ("permanecer", "Permaneceria neste curso")]),
    "escopo": ("O problema foi isolado ou recorrente?", "escolha", [("isolado", "Isolado"), ("recorrente", "Recorrente")]),
    "continuar": ("Hipoteticamente, se houvesse solução em 48 horas, continuaria? Isso não é uma promessa de solução.", "escolha", [("sim", "Sim"), ("indiferente", "Indiferente")]),
    "vinculo_anterior": ("Já tinha vínculo positivo anterior?", "escolha", [("sim", "Sim"), ("nao", "Não"), ("nao_sei", "Não sei")]),
    "comentario": ("Quer contar mais sobre sua experiência?", "texto", []),
}


def _default():
    return {"perguntas": {key: {"texto": text, "tipo": kind, "opcoes": [{"valor": value, "texto": label} for value, label in options], "obrigatoria": key not in ("nome_indicado", "comentario")} for key, (text, kind, options) in PERGUNTAS.items()}, "caminhos": {"9-10": ["repercussao", "indicacao", "orcamento", "comentario"], "7-8": ["gargalo", "concorrente", "comentario"], "0-6": ["escopo", "continuar", "vinculo_anterior", "comentario"]}}


def _error(message, status=400):
    return JsonResponse({"detail": message}, status=status)


def _body(request):
    try:
        value = json.loads(request.body or b"{}")
    except (ValueError, UnicodeDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _config(site_id):
    config = NPSConfig.objects.filter(site_id=site_id).order_by("-versao").first()
    if config:
        return config
    config, _ = NPSConfig.objects.get_or_create(site_id=site_id, versao=1, defaults={"documento": _default()})
    return config


def _valid_document(document):
    if not isinstance(document, dict) or not isinstance(document.get("perguntas"), dict):
        return False
    for key, (original, kind, options) in PERGUNTAS.items():
        question = document["perguntas"].get(key)
        if not isinstance(question, dict) or not isinstance(question.get("texto"), str) or not question["texto"].strip() or question.get("tipo") != kind:
            return False
        if kind == "escolha" and {o.get("valor") for o in question.get("opcoes", []) if isinstance(o, dict)} != {v for v, _ in options}:
            return False
        if kind == "escolha" and not all(isinstance(o.get("texto"), str) and o["texto"].strip() for o in question["opcoes"]):
            return False
    paths = document.get("caminhos")
    expected = {"9-10": {"repercussao", "indicacao", "orcamento", "comentario"}, "7-8": {"gargalo", "concorrente", "comentario"}, "0-6": {"escopo", "continuar", "vinculo_anterior", "comentario"}}
    if not isinstance(paths, dict):
        return False
    for band, names in expected.items():
        path = paths.get(band)
        if not isinstance(path, list) or not all(isinstance(item, str) for item in path) or len(path) != len(names) or set(path) != names or path[-1] != "comentario":
            return False
    if paths["9-10"][0] != "repercussao":
        return False
    return True


@csrf_exempt
def config(request):
    if not _authorized(request):
        return _error("Não autorizado.", 401)
    if request.method not in ("GET", "POST"):
        return _error("Método inválido.", 405)
    data = request.GET if request.method == "GET" else _body(request)
    if data is None:
        return _error("JSON inválido.")
    site_id = data.get("site_id", "")
    if not Site.objects.filter(pk=site_id, active=True).exists():
        return _error("Site inválido.")
    if request.method == "POST":
        document = data.get("documento")
        if not _valid_document(document):
            return _error("Documento NPS inválido.")
        with transaction.atomic():
            Site.objects.select_for_update().get(pk=site_id)
            current = _config(site_id)
            current = NPSConfig.objects.create(site_id=site_id, versao=current.versao + 1, documento=document)
    else:
        current = _config(site_id)
    return JsonResponse({"site_id": site_id, "versao": current.versao, "documento": current.documento})


def _flow(answers, document=None):
    paths = (document or _default())["caminhos"]
    note = answers.get("nota")
    if note is None:
        return ["nota"]
    if note >= 9:
        path = ["nota", *paths["9-10"]]
        if answers.get("repercussao") in ("mais_3", "1_2"):
            path.insert(2, "nome_indicado")
    elif note >= 7:
        path = ["nota", *paths["7-8"]]
    else:
        path = ["nota", *paths["0-6"]]
    return path


def _next(answers, document=None):
    for key in _flow(answers, document):
        if key not in answers and key != "nome_indicado" and key != "comentario":
            return key
        if key not in answers:
            return key
    return None


def _question(attempt, key):
    question = copy.deepcopy(attempt.config_documento["perguntas"][key])
    question["id"] = key
    if key not in attempt.perguntas_exibidas:
        attempt.perguntas_exibidas = [*attempt.perguntas_exibidas, key]
        attempt.save(update_fields=["perguntas_exibidas"])
    _event(attempt, key, "exibida")
    return question


def _event(attempt, key, action, **details):
    quality = dict(attempt.qualidade)
    quality["eventos"] = [*quality.get("eventos", []), {"pergunta_id": key, "acao": action, "registrado_em": timezone.now().isoformat(), **details}]
    attempt.qualidade = quality
    attempt.save(update_fields=["qualidade"])


def _classify(a):
    note = a["nota"]
    result = {"nps": note, "classificacao": None, "motivos": [], "indicacao_declarada": a.get("indicacao") == "sim", "repercussao_pontos": None, "evangelismo": None, "neutralidade": None, "detracao": None, "participacao_externa": "não disponível"}
    if note >= 9:
        result["repercussao_pontos"] = {"mais_3": 2, "1_2": 1, "nenhuma": 0}[a["repercussao"]]
        result["evangelismo"] = result["repercussao_pontos"]
        if a["repercussao"] in ("mais_3", "1_2") and a["orcamento"] == "ultimo":
            result["classificacao"] = "Promotor confirmado"
            result["motivos"].append("Nota alta, repercussão positiva e curso como último gasto a cortar.")
        elif a["repercussao"] == "nenhuma" and a["orcamento"] == "pausar":
            result["classificacao"] = "Neutro"
            result["motivos"].append("Nota alta, sem repercussão observada e com possibilidade de pausa.")
    elif note >= 7:
        if a["concorrente"] == "permanecer" and a.get("gargalo") in ("pedagogico", "tecnologico"):
            result["motivos"].append("Deseja permanecer, mas relata gargalo pedagógico ou tecnológico; sinais em conflito.")
        else:
            result["classificacao"] = {"migrar": "Alto risco de saída", "pesquisar": "Neutro", "permanecer": "Promotor potencial"}[a["concorrente"]]
            result["motivos"].append({"migrar": "Considera migrar para concorrente equivalente mais barato.", "pesquisar": "Ainda pesquisaria antes de decidir.", "permanecer": "Permaneceria mesmo diante de concorrente equivalente mais barato."}[a["concorrente"]])
    elif a["escopo"] == "recorrente" and a["continuar"] == "indiferente":
        result["classificacao"] = "Detrator real"
        result["motivos"].append("Problema recorrente e indiferença diante de solução hipotética.")
    elif a["escopo"] == "isolado" and a["continuar"] == "sim":
        if a["vinculo_anterior"] == "sim":
            result["classificacao"] = "Promotor em Crise"
            result["motivos"].append("Problema isolado, intenção de continuar e vínculo positivo anterior.")
        elif a["vinculo_anterior"] == "nao":
            result["classificacao"] = "Neutro sob Risco"
            result["motivos"].append("Problema isolado, intenção de continuar e ausência de vínculo positivo anterior.")
    if result["classificacao"] is None:
        result["classificacao"] = "Classificação ainda não confirmada"
        if not result["motivos"]:
            result["motivos"].append("Os sinais declarados ainda não confirmam uma das classificações definidas.")
    return result


def _serialize(attempt, include_question=True):
    readable = []
    for key, value in attempt.respostas.items():
        question = attempt.config_documento["perguntas"].get(key, {})
        shown = next((choice.get("texto") for choice in question.get("opcoes", []) if choice.get("valor") == value), value)
        readable.append({"pergunta_id": key, "pergunta": question.get("texto", key), "valor": value, "resposta": shown})
    data = {"id": str(attempt.id), "site_id": attempt.site_id, "aluno_id": attempt.aluno_id, "status": attempt.status, "site": attempt.site, "aluno": attempt.aluno, "produto": attempt.produto, "curso": attempt.curso, "matricula": attempt.matricula, "config_versao": attempt.config_versao, "config_documento": attempt.config_documento, "calculo_versao": attempt.calculo_versao, "respostas": attempt.respostas, "respostas_legiveis": readable, "respostas_registro": attempt.respostas_registro, "perguntas_exibidas": attempt.perguntas_exibidas, "resultado": attempt.resultado, "qualidade": attempt.qualidade, "criada_em": attempt.criada_em.isoformat(), "concluida_em": attempt.concluida_em.isoformat() if attempt.concluida_em else None}
    if include_question and attempt.status != "concluida":
        next_key = _next(attempt.respostas, attempt.config_documento)
        data["proxima_pergunta"] = _question(attempt, next_key) if next_key else None
        data["perguntas_exibidas"] = attempt.perguntas_exibidas
    return data


def _owned(attempt, site_id, aluno_id):
    return bool(site_id and aluno_id and attempt.site_id == site_id and attempt.aluno_id == aluno_id)


@csrf_exempt
def tentativas(request):
    if not _authorized(request):
        return _error("Não autorizado.", 401)
    if request.method != "POST":
        return _error("Método inválido.", 405)
    data = _body(request)
    if data is None:
        return _error("JSON inválido.")
    site_id, aluno_id = data.get("site_id"), data.get("aluno_id")
    site = Site.objects.filter(pk=site_id, active=True).first()
    if not site or not isinstance(aluno_id, str) or not aluno_id.strip():
        return _error("Site ou aluno inválido.")
    for key in ("aluno", "produto", "curso", "matricula", "evidencias"):
        if key in data and not isinstance(data[key], dict):
            return _error(f"{key} deve ser objeto.")
    config_row = _config(site_id)
    with transaction.atomic():
        attempt = NPSTentativa.objects.create(site_id=site_id, aluno_id=aluno_id, site={"id": site.id, "nome": site.name, "host": site.host}, aluno=data.get("aluno", {}), produto=data.get("produto", {}), curso=data.get("curso", {}), matricula=data.get("matricula", {}), config_versao=config_row.versao, config_documento=config_row.documento, qualidade={"evidencias": data.get("evidencias", {}), "participacao_externa": "não disponível"})
        result = _serialize(attempt)
    return JsonResponse(result, status=201)


@csrf_exempt
def tentativa(request, tentativa_id):
    if not _authorized(request):
        return _error("Não autorizado.", 401)
    if request.method != "GET":
        return _error("Método inválido.", 405)
    with transaction.atomic():
        attempt = NPSTentativa.objects.select_for_update().filter(pk=tentativa_id).first()
        if not attempt or not _owned(attempt, request.GET.get("site_id"), request.GET.get("aluno_id")):
            return _error("Tentativa não encontrada.", 404)
        result = _serialize(attempt)
    return JsonResponse(result)


@csrf_exempt
def respostas(request, tentativa_id):
    if not _authorized(request):
        return _error("Não autorizado.", 401)
    if request.method != "POST":
        return _error("Método inválido.", 405)
    data = _body(request)
    if data is None:
        return _error("JSON inválido.")
    with transaction.atomic():
        attempt = NPSTentativa.objects.select_for_update().filter(pk=tentativa_id).first()
        if not attempt or not _owned(attempt, data.get("site_id"), data.get("aluno_id")):
            return _error("Tentativa não encontrada.", 404)
        if attempt.status == "concluida":
            return _error("Histórico concluído é imutável.", 409)
        action = data.get("acao", "responder")
        if action == "voltar":
            path = _flow(attempt.respostas, attempt.config_documento)
            current = _next(attempt.respostas, attempt.config_documento)
            prior = path.index(current) - 1 if current in path else len(path) - 1
            if prior < 0:
                return _error("Já está na primeira pergunta.")
            answer = dict(attempt.respostas)
            for key in path[prior:]:
                if key in answer:
                    _event(attempt, key, "descartada_para_edicao")
                answer.pop(key, None)
            attempt.respostas = answer
            attempt.save(update_fields=["respostas"])
            _event(attempt, path[prior], "voltar")
        elif action == "concluir":
            if _next(attempt.respostas, attempt.config_documento) is not None:
                return _error("Responda todas as perguntas antes de concluir.")
            elapsed = max(0, (timezone.now() - attempt.criada_em).total_seconds())
            count = len(set(attempt.perguntas_exibidas))
            quality = dict(attempt.qualidade)
            quality.update({"duracao_segundos": elapsed, "perguntas_exibidas_unicas": count, "tempo_minimo_segundos": count * 3, "audit_failed": elapsed < count * 3, "estado": "inconclusiva" if elapsed < count * 3 else "conclusiva"})
            quality["eventos"] = [*quality.get("eventos", []), {"pergunta_id": None, "acao": "concluida", "registrado_em": timezone.now().isoformat()}]
            attempt.qualidade = quality
            attempt.resultado = _classify(attempt.respostas)
            attempt.status = "concluida"
            attempt.concluida_em = timezone.now()
            attempt.save(update_fields=["qualidade", "resultado", "status", "concluida_em"])
        elif action == "responder":
            key, value = data.get("pergunta_id"), data.get("valor")
            path = _flow(attempt.respostas, attempt.config_documento)
            next_key = _next(attempt.respostas, attempt.config_documento)
            if key not in path or (key != next_key and key not in attempt.respostas):
                return _error("Pergunta fora do ramo atual.")
            question = attempt.config_documento["perguntas"][key]
            kind = question["tipo"]
            if kind == "nota":
                if isinstance(value, str) and value.isdecimal():
                    value = int(value)
                if type(value) is not int or not 0 <= value <= 10:
                    return _error("Nota deve ser de 0 a 10.")
            elif kind == "escolha":
                if value not in [o["valor"] for o in question["opcoes"]]:
                    return _error("Opção inválida.")
            elif not isinstance(value, str) or len(value) > 3000 or (question.get("obrigatoria") and not value.strip()):
                return _error("Texto inválido.")
            old_path = _flow(attempt.respostas, attempt.config_documento)
            answers = dict(attempt.respostas)
            changed = key in answers and answers[key] != value
            previous = answers.get(key)
            answers[key] = value
            if changed:
                for downstream in old_path[old_path.index(key) + 1:]:
                    if downstream in answers:
                        _event(attempt, downstream, "ramo_abandonado")
                    answers.pop(downstream, None)
            attempt.respostas = answers
            attempt.respostas_registro = [*attempt.respostas_registro, {"pergunta_id": key, "valor": value, "valor_anterior": previous, "registrado_em": timezone.now().isoformat()}]
            attempt.save(update_fields=["respostas", "respostas_registro"])
            _event(attempt, key, "respondida", alterada=changed)
        else:
            return _error("Ação inválida.")
        response = _serialize(attempt)
    return JsonResponse(response)


def historico(request):
    if not _authorized(request):
        return _error("Não autorizado.", 401)
    if request.method != "GET":
        return _error("Método inválido.", 405)
    site_id, aluno_id = request.GET.get("site_id"), request.GET.get("aluno_id")
    email = request.GET.get("email", "").strip()
    if not site_id or not (aluno_id or email):
        return _error("site_id e aluno_id ou email obrigatórios.")
    evaluations = NPSTentativa.objects.filter(site_id=site_id, status="concluida")
    if aluno_id:
        evaluations = evaluations.filter(aluno_id=aluno_id)
        cases = NPSAtendimento.objects.filter(site_id=site_id, aluno_id=aluno_id)
    else:
        evaluations = evaluations.filter(aluno__email__iexact=email)
        matched_ids = list(evaluations.values_list("aluno_id", flat=True).distinct())
        cases = NPSAtendimento.objects.filter(site_id=site_id, aluno_id__in=matched_ids)
    return JsonResponse({"site_id": site_id, "aluno_id": aluno_id, "email": email or None, "avaliacoes": [_serialize(a, False) for a in evaluations.order_by("-concluida_em")], "atendimentos": [_case(a) for a in cases.order_by("-atualizada_em")]})


def _case(case):
    return {"id": str(case.id), "site_id": case.site_id, "aluno_id": case.aluno_id, "tentativa_id": str(case.tentativa_id) if case.tentativa_id else None, "responsavel": case.responsavel, "proximo_passo": case.proximo_passo, "prazo": case.prazo.isoformat() if case.prazo else None, "solucao": case.solucao, "status": case.status, "historico": case.historico, "criada_em": case.criada_em.isoformat(), "atualizada_em": case.atualizada_em.isoformat()}


@csrf_exempt
def atendimentos(request):
    if not _authorized(request):
        return _error("Não autorizado.", 401)
    if request.method != "POST":
        return _error("Método inválido.", 405)
    data = _body(request)
    if data is None:
        return _error("JSON inválido.")
    site_id, aluno_id = data.get("site_id"), data.get("aluno_id")
    if not site_id or not aluno_id:
        return _error("site_id e aluno_id obrigatórios.")
    with transaction.atomic():
        if data.get("id"):
            case = NPSAtendimento.objects.select_for_update().filter(pk=data["id"], site_id=site_id, aluno_id=aluno_id).first()
            if not case:
                return _error("Atendimento não encontrado.", 404)
        else:
            case = NPSAtendimento(site_id=site_id, aluno_id=aluno_id)
        if "tentativa_id" in data:
            linked = NPSTentativa.objects.filter(pk=data["tentativa_id"], site_id=site_id, aluno_id=aluno_id, status="concluida").first() if data["tentativa_id"] else None
            if data["tentativa_id"] and not linked:
                return _error("Tentativa inválida.")
            case.tentativa = linked
        for field in ("responsavel", "proximo_passo", "solucao", "status"):
            if field in data:
                if not isinstance(data[field], str):
                    return _error(f"{field} deve ser texto.")
                setattr(case, field, data[field])
        if "prazo" in data:
            deadline = parse_datetime(data["prazo"]) if isinstance(data["prazo"], str) else None
            if data["prazo"] and (deadline is None or timezone.is_naive(deadline)):
                return _error("Prazo deve ter data e fuso horário.")
            case.prazo = deadline
        case.historico = [*case.historico, {"registrado_em": timezone.now().isoformat(), "responsavel": case.responsavel, "proximo_passo": case.proximo_passo, "prazo": case.prazo.isoformat() if case.prazo else None, "solucao": case.solucao, "status": case.status}]
        case.save()
    return JsonResponse({"atendimento": _case(case)}, status=201 if not data.get("id") else 200)
