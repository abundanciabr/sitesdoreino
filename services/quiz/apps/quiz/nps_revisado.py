"""Roteiro NPS para o aluno adulto que comprou o próprio curso.

As versões publicadas do roteiro anterior continuam em nps.py. O documento
de cada tentativa é um snapshot; esta implementação nunca reclassifica o passado.
"""

import copy
import random
from datetime import datetime

from django.utils import timezone


ROTEIRO = "revisado"
CALCULO_VERSAO = 2
NAO_ENTENDI = "__nao_entendi__"
ORDEM = ("P1", "A1", "R2", "A3", "R4", "R5", "R5b", "R6", "R7", "A8", "R10", "R11", "R12", "R13", "R14")
PERGUNTAS_RETRATO = {"A1", "R2", "A3", "R4", "R5", "R5b", "R7", "A8", "R11"}


def _options(items):
    return [{"valor": key, "texto": label} for key, label in items]


SITUACOES = [
    ("aula_dificil", "Achei alguma aula difícil demais", "opiniao", "Sobre as aulas"),
    ("aula_facil", "Acho as aulas fáceis demais", "opiniao", "Sobre as aulas"),
    ("aula_chata", "Acho as aulas chatas", "opiniao", "Sobre as aulas"),
    ("conteudo_diferente", "O curso não ensina o que eu queria aprender", "opiniao", "Sobre as aulas"),
    ("site_sem_acesso", "Não consegui entrar no site das aulas", "escola", "Sobre o site e o computador"),
    ("video_trava", "O vídeo da aula trava ou não abre", "escola", "Sobre o site e o computador"),
    ("blender_instalar", "Não consegui instalar o Blender", "escola", "Sobre o site e o computador"),
    ("blender_trava", "O Blender fica travando no meu computador", "escola", "Sobre o site e o computador"),
    ("sem_computador", "Não tenho computador para fazer o curso", "pessoal", "Sobre o site e o computador"),
    ("duvida_sem_canal", "Tive uma dúvida e não sabia que podia perguntar no fórum do curso", "escola", "Sobre pedir ajuda"),
    ("sem_resposta", "Perguntei no fórum do curso e ninguém da equipe respondeu", "escola", "Sobre pedir ajuda"),
    ("resposta_sem_solucao", "A equipe respondeu no fórum do curso, mas não resolveu", "escola", "Sobre pedir ajuda"),
    ("sem_tempo", "Fiquei sem tempo para as aulas", "pessoal", "Sobre você"),
    ("sem_vontade", "Perdi a vontade de fazer as aulas", "pessoal", "Sobre você"),
    ("esperando_ajuda", "Estou esperando alguém de casa me ajudar a começar", "pessoal", "Sobre você"),
    ("entrou_recentemente", "Entrei no curso faz pouco tempo", "nenhum", "Sobre você"),
    ("cobranca", "Cobrança errada ou dificuldade para pagar", "escola", "Pagamento"),
    ("cancelamento", "Pedi cancelamento ou reembolso e não consegui", "escola", "Pagamento"),
    ("compra_sem_curso", "Paguei e o curso não apareceu", "escola", "Acesso"),
    ("promessa_venda", "O curso entrega menos do que foi prometido na venda", "escola", "O curso"),
    ("outra", "Outra situação (escreva)", "escola", "No fim"),
    ("nenhuma", "Nenhuma destas situações aconteceu", "nenhum", "No fim"),
]


def _base_default_document():
    questions = {
        "P1": ("Quem está respondendo agora?", "escolha", [("aluno_pagante", "Sou o aluno, e fui eu que paguei o curso")]),
        "A1": ("Qual destas frases combina com você hoje?", "escolha", [("nenhuma", "Ainda não assisti a nenhuma aula"), ("recente", "Já assisti a algumas aulas e vi alguma neste último mês"), ("antiga", "Já assisti a algumas aulas, mas faz mais de um mês que não vejo nenhuma"), ("todas", "Já assisti a todas as aulas")]),
        "R2": ("Até agora, você está satisfeito(a) ou insatisfeito(a) com o curso?", "escolha", [("muito_satisfeito", "Muito satisfeito(a)"), ("satisfeito", "Satisfeito(a)"), ("morno", "Nem satisfeito(a) nem insatisfeito(a)"), ("insatisfeito", "Insatisfeito(a)"), ("muito_insatisfeito", "Muito insatisfeito(a)"), ("sem_opiniao", "Ainda não dá para avaliar")]),
        "A3": ("Alguma destas situações aconteceu com você desde a compra do curso? Marque todas.", "multipla", []),
        "R4": ("Qual das situações da escola que você marcou foi a mais grave?", "escolha", []),
        "R5": ("Você marcou: “{situacao_principal}”. E hoje, como está isso?", "escolha", [("resolvido", "Foi resolvido"), ("acabou", "Acabou sem ninguém resolver"), ("continua", "Continua igual"), ("desistiu", "Não foi resolvido, e desisti de tentar"), ("nao_sei", "Não sei dizer")]),
        "R5b": ("Você também marcou: “{outras_situacoes}”. E essas?", "escolha", [("acabaram", "Também acabaram"), ("alguma_continua", "Alguma continua"), ("nao_sei", "Não sei dizer")]),
        "R6": ("Você ou alguém da sua casa pediu ajuda no fórum do curso para resolver isso?", "escolha", [("esperando", "Sim, e estamos esperando resposta"), ("sem_solucao", "Sim, responderam, mas não resolveu"), ("nao", "Não, ninguém pediu ajuda"), ("nao_sei", "Não sei")]),
        "R7": ("Antes das situações da escola que você marcou acontecerem, como você estava com o curso?", "escolha", [("satisfeito", "Satisfeito(a)"), ("morno", "Mais ou menos"), ("insatisfeito", "Insatisfeito(a)"), ("comeco", "Aconteceu logo no começo: não deu tempo de formar opinião")]),
        "A8": ("Você quer continuar as aulas ou prefere parar?", "escolha", [("sim", "Quero continuar"), ("duvida", "Ainda não sei"), ("nao", "Prefiro parar")]),
        "R10": ("Qual o principal motivo?", "escolha", [("situacao", "Por causa da situação da escola que marquei antes"), ("aprendeu", "Já aprendi o que queria"), ("sem_interesse", "Perdi o interesse por modelagem 3D"), ("aulas_abaixo", "As aulas ficaram abaixo do que eu esperava"), ("nao_valeu", "O curso não valeu o que custou"), ("preco", "O preço pesou no orçamento"), ("outro", "Outro motivo (escreva)")]),
        "R11": ("Você já falou do curso para outras pessoas? Marque tudo o que aconteceu.", "multipla", [("recomendou_comprou", "Recomendei, e alguém comprou o curso"), ("recomendou_nao_comprou", "Recomendei, e ninguém comprou"), ("recomendou_nao_sei", "Recomendei, e não sei se alguém comprou"), ("comentou", "Comentei, sem recomendar nem desaconselhar"), ("contou_problema", "Contei um problema que tive"), ("desaconselhou", "Aconselhei a não comprar"), ("publicou_reclamacao", "Publiquei reclamação ou avaliação ruim na internet"), ("nao_falou", "Não falei com ninguém")]),
        "R12": ("De 0 a 10, qual a chance de você recomendar o curso a alguém interessado em modelagem 3D?", "nota", []),
        "R13": ("Quer contar mais alguma coisa? Se não quiser escrever, é só pular.", "texto", []),
        "R14": ("Podemos entrar em contato para resolver?", "escolha", [("whatsapp", "Sim, por WhatsApp"), ("email", "Sim, por e-mail"), ("nao_precisa", "Não precisa")]),
    }
    return {"roteiro": ROTEIRO, "settings": {"publico": "adultos", "compra": "unica", "ajuda": "forum"}, "textos": {"abertura": "Queremos saber como está o curso para você. São poucas perguntas. Não existe resposta certa nem errada.", "aviso_aluno_pagante": "Suas respostas ficam ligadas ao cadastro, para a equipe poder ajudar se algo não estiver bom. Nada do que você responder muda o acesso ao curso.", "ajuda_nao_entendi": "Você pode dizer que não entendeu. A equipe poderá conversar com você sobre a pergunta."}, "perguntas": {key: {"texto": text, "tipo": kind, "opcoes": _options(options), "obrigatoria": key != "R13"} for key, (text, kind, options) in questions.items()}, "situacoes": {"aluno_pagante": [{"id": key, "texto": text, "tipo": kind, "bloco": group} for key, text, kind, group in SITUACOES]}}


def default_document():
    document = _base_default_document()
    document["textos"].update({"a3_sem_aula": "Alguma destas coisas está impedindo você de começar? Marque todas.", "a3_nenhuma_sem_aula": "Nada está impedindo: é só começar"})
    document["perguntas"]["A8"]["variantes"] = {
        "nenhuma": {"texto": "Você quer começar as aulas ou prefere não fazer o curso?", "opcoes": _options((("sim", "Quero começar"), ("duvida", "Ainda não sei"), ("nao", "Prefiro não fazer")))},
        "recente": {"texto": "Você quer continuar as aulas ou prefere parar?", "opcoes": _options((("sim", "Quero continuar"), ("duvida", "Ainda não sei"), ("nao", "Prefiro parar")))},
        "antiga": {"texto": "Você quer voltar a fazer as aulas ou prefere não voltar?", "opcoes": _options((("sim", "Quero voltar"), ("duvida", "Ainda não sei"), ("nao", "Prefiro não voltar")))},
        "todas": {"texto": "Se a escola tiver outro curso, você vai querer fazer?", "opcoes": _options((("sim", "Sim"), ("duvida", "Talvez"), ("nao", "Não")))},
        NAO_ENTENDI: {"texto": "Você quer fazer as aulas do curso ou prefere não fazer?", "opcoes": _options((("sim", "Quero fazer"), ("duvida", "Ainda não sei"), ("nao", "Prefiro não fazer")))},
    }
    return document


def valid_document(document):
    if not isinstance(document, dict) or document.get("roteiro") != ROTEIRO:
        return False
    reference = default_document()
    if document.get("settings") != reference["settings"]:
        return False
    if not isinstance(document.get("textos"), dict) or not isinstance(document.get("perguntas"), dict):
        return False
    if not all(isinstance(document["textos"].get(key), str) and document["textos"][key].strip() for key in reference["textos"]):
        return False
    for key, original in reference["perguntas"].items():
        question = document["perguntas"].get(key)
        if not isinstance(question, dict) or question.get("tipo") != original["tipo"] or not isinstance(question.get("texto"), str) or not question["texto"].strip():
            return False
        options = question.get("opcoes")
        if not isinstance(options, list) or not all(isinstance(item, dict) and isinstance(item.get("valor"), str) and isinstance(item.get("texto"), str) and item["texto"].strip() for item in options):
            return False
        if {item["valor"] for item in options} != {item["valor"] for item in original["opcoes"]} or len(options) != len(original["opcoes"]):
            return False
        if key == "A8":
            variants = question.get("variantes")
            if not isinstance(variants, dict) or set(variants) != set(original["variantes"]):
                return False
            for stage, standard in original["variantes"].items():
                item = variants[stage]
                if not isinstance(item, dict) or not isinstance(item.get("texto"), str) or not item["texto"].strip() or not isinstance(item.get("opcoes"), list):
                    return False
                choices = item["opcoes"]
                if len(choices) != 3 or not all(isinstance(choice, dict) and isinstance(choice.get("texto"), str) and choice["texto"].strip() for choice in choices) or {choice.get("valor") for choice in choices} != {"sim", "duvida", "nao"}:
                    return False
    situations = document.get("situacoes", {}).get("aluno_pagante") if isinstance(document.get("situacoes"), dict) else None
    if not isinstance(situations, list) or len(situations) != len(SITUACOES):
        return False
    by_id = {item.get("id"): item for item in situations if isinstance(item, dict) and isinstance(item.get("id"), str)}
    if len(by_id) != len(SITUACOES):
        return False
    for key, _text, kind, _group in SITUACOES:
        item = by_id.get(key)
        if not item or item.get("tipo") != kind or not isinstance(item.get("texto"), str) or not item["texto"].strip() or not isinstance(item.get("bloco"), str):
            return False
    return True


def new_order(document):
    reverse = bool(random.getrandbits(1))
    group_orders = {}
    situations = document["situacoes"]["aluno_pagante"]
    for group in {item["bloco"] for item in situations}:
        ids = [item["id"] for item in situations if item["bloco"] == group]
        if group != "No fim":
            random.shuffle(ids)
        group_orders[group] = ids
    return {"escalas_invertidas": reverse, "situacoes_por_bloco": group_orders}


def _value(answers, key):
    value = answers.get(key)
    return value.get("valor") if isinstance(value, dict) else value


def _situations(attempt, overrides=None):
    definitions = {item["id"]: item for item in attempt.config_documento["situacoes"]["aluno_pagante"]}
    overrides = overrides or {}
    return [{**definitions[key], "tipo": overrides.get(key, definitions[key]["tipo"])} for key in (_value(attempt.respostas, "A3") or []) if key in definitions]


def _school(attempt, overrides=None):
    return [item for item in _situations(attempt, overrides) if item["tipo"] == "escola"]


def _main(attempt, overrides=None):
    school = _school(attempt, overrides)
    selected = _value(attempt.respostas, "R4")
    return next((item for item in school if item["id"] == selected), school[0] if school else None)


def _open(attempt, overrides=None):
    if not _school(attempt, overrides):
        return False
    status = _value(attempt.respostas, "R5")
    extra = _value(attempt.respostas, "R5b")
    return status in ("continua", "desistiu", "nao_sei") or extra in ("alguma_continua", "nao_sei")


def _monthly(attempt):
    # O mantenedor confirmou compra única para este produto. R9 não existe.
    return False


def path(attempt, overrides=None):
    answers = attempt.respostas
    watched = _value(answers, "A1")
    selected = _school(attempt, overrides)
    sequence = ["P1", "A1", "R2", "A3"]
    if len(selected) > 1:
        sequence.append("R4")
    if selected:
        sequence.append("R5")
        if len(selected) > 1 and _value(answers, "R5") in ("resolvido", "acabou"):
            sequence.append("R5b")
        if _open(attempt, overrides):
            if (_main(attempt, overrides) or {}).get("id") not in ("sem_resposta", "resposta_sem_solucao"):
                sequence.append("R6")
            if _value(answers, "R2") in ("morno", "insatisfeito", "muito_insatisfeito"):
                sequence.append("R7")
    sequence.append("A8")
    if watched != "todas" and _value(answers, "A8") in ("duvida", "nao"):
        sequence.append("R10")
    sequence += ["R11", "R12", "R13"]
    if _open(attempt, overrides):
        sequence.append("R14")
    return sequence


def next_key(attempt):
    return next((key for key in path(attempt) if key not in attempt.respostas), None)


def _ordered_options(attempt, key, options):
    options = copy.deepcopy(options)
    if key in ("R2", "R7", "A8") and attempt.qualidade.get("ordem", {}).get("escalas_invertidas"):
        tail = {"sem_opiniao", "comeco"}
        options = list(reversed([item for item in options if item["valor"] not in tail])) + [item for item in options if item["valor"] in tail]
    return options


def question(attempt, key, overrides=None):
    document = attempt.config_documento
    result = copy.deepcopy(document["perguntas"][key])
    result["id"] = key
    answers = attempt.respostas
    watched = _value(answers, "A1")
    if key == "A1":
        result["aviso"] = document["textos"]["aviso_aluno_pagante"]
    elif key == "R2" and watched not in ("nenhuma", NAO_ENTENDI):
        result["opcoes"] = [item for item in result["opcoes"] if item["valor"] != "sem_opiniao"]
    elif key == "A3":
        if watched == "nenhuma":
            result["texto"] = document["textos"]["a3_sem_aula"]
        definitions = document["situacoes"]["aluno_pagante"]
        groups = list(dict.fromkeys(item["bloco"] for item in definitions))
        ordered = []
        for group in groups:
            selected = {item["id"]: item for item in definitions if item["bloco"] == group}
            ids = attempt.qualidade.get("ordem", {}).get("situacoes_por_bloco", {}).get(group, list(selected))
            ordered.extend(selected[item] for item in ids if item in selected)
        if watched == "nenhuma":
            ordered = [item for item in ordered if item["bloco"] != "Sobre as aulas"]
        else:
            ordered = [item for item in ordered if item["id"] not in ("esperando_ajuda", "entrou_recentemente")]
        result["opcoes"] = [{"valor": item["id"], "texto": document["textos"]["a3_nenhuma_sem_aula"] if watched == "nenhuma" and item["id"] == "nenhuma" else item["texto"], "bloco": item["bloco"], "exclusiva": item["id"] == "nenhuma", "complemento": item["id"] == "outra"} for item in ordered]
    elif key == "R4":
        result["opcoes"] = _options([(item["id"], item["texto"]) for item in _school(attempt, overrides)])
    elif key in ("R5", "R5b"):
        main = _main(attempt, overrides)
        others = [item["texto"] for item in _school(attempt, overrides) if item["id"] != (main or {}).get("id")]
        result["texto"] = result["texto"].format(situacao_principal=(main or {}).get("texto", ""), outras_situacoes="; ".join(others))
    elif key == "A8":
        variants = document["perguntas"]["A8"]["variantes"]
        variant = variants.get(watched, variants[NAO_ENTENDI])
        result["texto"] = variant["texto"]
        result["opcoes"] = copy.deepcopy(variant["opcoes"])
    elif key == "R10":
        if _value(answers, "A8") == "duvida":
            result["texto"] = "O que deixa você em dúvida? Escolha o motivo principal."
        if not _school(attempt, overrides):
            result["opcoes"] = [item for item in result["opcoes"] if item["valor"] != "situacao"]
        result["opcoes"] = [{**item, "complemento": item["valor"] == "outro"} for item in result["opcoes"]]
    elif key == "R11":
        result["opcoes"] = [{**item, "exclusiva": item["valor"] == "nao_falou"} for item in result["opcoes"]]
    elif key == "R13" and _open(attempt, overrides):
        result["texto"] = "Conte o que aconteceu, para a equipe poder ajudar. Se não quiser escrever, é só pular."
    if key not in ("A3",):
        result["opcoes"] = _ordered_options(attempt, key, result["opcoes"])
    result["nao_entendi"] = True
    result["ajuda_nao_entendi"] = "Você é quem assiste às aulas, ou o adulto que cuida de quem assiste?" if key == "P1" else document["textos"]["ajuda_nao_entendi"]
    return result


def readable(attempt):
    rows = []
    for key in path(attempt):
        if key == "P1":
            continue  # identidade implícita; não é pergunta mostrada nem corrigível
        if key not in attempt.respostas:
            continue
        item = question(attempt, key)
        raw = attempt.respostas[key]
        value = _value(attempt.respostas, key)
        labels = {option["valor"]: option["texto"] for option in item["opcoes"]}
        if isinstance(value, list):
            response = "; ".join(labels.get(v, v) for v in value)
        elif item["tipo"] == "nota" or item["tipo"] == "texto":
            response = str(value)
        else:
            response = labels.get(value, "Não entendi a pergunta" if value == NAO_ENTENDI else str(value))
        complement = raw.get("complemento", "") if isinstance(raw, dict) else ""
        if complement:
            response += ": " + complement
        rows.append({"pergunta_id": key, "pergunta": item["texto"], "valor": value, "resposta": response, "complemento": complement})
    return rows


def conference_summary(items):
    by_id = {item["pergunta_id"]: item["resposta"] for item in items}
    summary = []
    for key, prefix in (("A1", "Você contou que"), ("R2", "Sobre sua satisfação com o curso, marcou"), ("A3", "Situações que marcou"), ("R4", "Situação principal"), ("R5", "A situação principal hoje"), ("R5b", "As demais situações hoje"), ("R6", "Sobre a ajuda pedida, marcou"), ("R7", "Antes do problema, marcou"), ("A8", "Daqui para a frente, marcou"), ("R10", "Motivo principal"), ("R11", "Sobre o que falou a outras pessoas, marcou"), ("R12", "Nota de recomendação de 0 a 10"), ("R14", "Contato para resolver")):
        if key in by_id:
            summary.append(f"{prefix}: {by_id[key]}.")
    if "R13" in by_id and by_id["R13"].strip():
        summary.append("Você acrescentou: " + by_id["R13"])
    return summary


def _reading(value, source=None):
    return {"valor": value, "estado": "declarada" if value is not None else "sem_valor", "fonte": source}


FACT_VALUES = {
    "reclamacao": {"Em aberto", "Resolvida", "Só opinião ou barreira pessoal", "Nenhuma"},
    "continuidade": {"Fica", "Em dúvida", "Sai", "Concluiu"},
    "boca_a_boca": {"A favor", "Contra", "Dos dois jeitos", "Nenhum"},
    "ponto_curso": {"nenhuma", "recente", "antiga", "todas"},
}


def portrait_from_readings(sat, complaint, continuity, word, previously):
    """First matching portrait; independent of the 0–10 recommendation note."""
    if word in ("Contra", "Dos dois jeitos") and sat != "Satisfeito":
        return "Detrator", "Falou contra o curso e não declarou satisfação."
    if complaint == "Em aberto" and (sat == "Satisfeito" or previously):
        return "Promotor em crise", "Há reclamação em aberto, mas existe satisfação atual ou anterior."
    if sat == "Insatisfeito" and continuity in ("Sai", "Concluiu"):
        return "Insatisfeito de saída", "Declarou insatisfação e saída ou conclusão."
    if complaint == "Em aberto":
        return "Em risco por problema", "Há reclamação da escola em aberto."
    if continuity in ("Sai", "Em dúvida") or sat == "Insatisfeito":
        return "Em risco", "Há dúvida ou intenção de sair, ou insatisfação."
    if sat == "Sem opinião ainda":
        return "Cedo para avaliar", "Ainda não há opinião formada sobre o curso."
    if sat == "Satisfeito" and word in ("A favor", "Dos dois jeitos"):
        return "Promotor", "Declarou satisfação e recomendação."
    if sat == "Satisfeito":
        return "Promotor em potencial", "Declarou satisfação, ainda sem recomendação a favor."
    return "Neutro", "Sinais restantes sem reclamação em aberto."


def _effective_context(attempt, facts=None, clarifications=None):
    """Use facts to choose the right question variant, keeping stored answers intact."""
    facts, clarifications = facts or {}, clarifications or {}
    original = attempt.respostas
    answers = {**original, **clarifications}
    point = facts.get("ponto_curso", {}).get("valor")
    point_changed = bool(point and point != _value(original, "A1"))
    if point:
        answers["A1"] = point
    if point_changed and point != "todas":
        # A8 answered for another stage (including a hypothetical next course)
        # cannot describe the factual stage of this course.
        if "A8" not in clarifications:
            answers.pop("A8", None)
        if "R10" not in clarifications:
            answers.pop("R10", None)
    context = copy.copy(attempt)
    context.respostas = answers
    return context, point_changed and point != "todas"


def calculate(attempt, overrides=None, facts=None, clarifications=None):
    original_answers = attempt.respostas
    attempt, point_needs_a8 = _effective_context(attempt, facts, clarifications)
    answers = attempt.respostas
    watched = _value(answers, "A1")
    satisfaction = _value(answers, "R2")
    if satisfaction == "sem_opiniao":
        sat = "Sem opinião ainda"
    elif satisfaction in ("muito_satisfeito", "satisfeito"):
        sat = "Satisfeito"
    elif satisfaction == "morno":
        sat = "Morno"
    elif satisfaction in ("insatisfeito", "muito_insatisfeito"):
        sat = "Insatisfeito"
    else:
        sat = None

    situations = _situations(attempt, overrides)
    school = _school(attempt, overrides)
    if school:
        complaint = "Em aberto" if _open(attempt, overrides) else "Resolvida"
    elif any(item["tipo"] in ("opiniao", "pessoal") for item in situations):
        complaint = "Só opinião ou barreira pessoal"
    else:
        complaint = "Nenhuma"

    future = _value(answers, "A8")
    if watched == "todas":
        continuity = "Concluiu"
    else:
        continuity = {"sim": "Fica", "duvida": "Em dúvida", "nao": "Sai"}.get(future)

    spoken = set(_value(answers, "R11") or [])
    favorable = bool(spoken & {"recomendou_comprou", "recomendou_nao_comprou", "recomendou_nao_sei"})
    unfavorable = bool(spoken & {"desaconselhou", "publicou_reclamacao"})
    if favorable and unfavorable:
        word = "Dos dois jeitos"
    elif favorable:
        word = "A favor"
    elif unfavorable:
        word = "Contra"
    else:
        word = "Nenhum"

    declared_point = _value({"A1": (clarifications or {}).get("A1", original_answers.get("A1"))}, "A1")
    readings = {"satisfacao": _reading(sat), "reclamacao": _reading(complaint), "continuidade": _reading(continuity), "boca_a_boca": _reading(word), "ponto_curso": _reading(declared_point)}
    if clarifications and "A1" in clarifications:
        readings["ponto_curso"]["valor_original"] = _value(original_answers, "A1")
    for key, proof in (facts or {}).items():
        if key not in FACT_VALUES:
            continue
        value = proof["valor"]
        reading = readings[key]
        reading["valor_declarado"] = reading["valor"]
        reading["valor"] = value
        reading["estado"] = "confirmada" if value == reading["valor_declarado"] else "em_conflito"
        reading["fonte"] = {"fonte": proof["fonte"], "referencia": proof["referencia"]}
    complaint = readings["reclamacao"]["valor"]
    continuity = readings["continuidade"]["valor"]
    word = readings["boca_a_boca"]["valor"]
    watched = readings["ponto_curso"]["valor"]
    if watched == "todas":
        continuity = "Concluiu"
        readings["continuidade"]["valor"] = continuity
    previously = _value(answers, "R7") == "satisfeito"
    # A primeira linha válida define o retrato; a nota R12 fica fora da regra.
    portrait, reason = portrait_from_readings(sat, complaint, continuity, word, previously)

    signals = []
    unclear = [key for key in PERGUNTAS_RETRATO if _value(original_answers, key) == NAO_ENTENDI and key not in (clarifications or {})]
    if unclear:
        signals.append({"codigo": "nao_entendi", "motivo": "Pergunta não entendida que alimenta o retrato: " + ", ".join(sorted(unclear))})
    if "outra" in (_value(answers, "A3") or []) and not (overrides or {}).get("outra"):
        signals.append({"codigo": "outra_situacao", "motivo": "Outra situação aguarda leitura e definição do tipo pela equipe."})
    if sat == "Insatisfeito" and not situations:
        signals.append({"codigo": "insatisfeito_sem_situacao", "motivo": "Insatisfação sem situação marcada; pedir o motivo."})
    if sat == "Satisfeito" and unfavorable and not situations:
        signals.append({"codigo": "satisfeito_falou_contra", "motivo": "Satisfeito e falou contra sem situação marcada; conferir."})
    note = _value(answers, "R12")
    if isinstance(note, int) and note >= 9 and spoken & {"desaconselhou", "publicou_reclamacao"}:
        signals.append({"codigo": "nota_boca_conflito", "motivo": "Nota de recomendação 9 ou 10 com fala contra; conferir."})
    if attempt.qualidade.get("confirmacao_recusada"):
        signals.append({"codigo": "conferencia_pendente", "motivo": "A pessoa pediu correção na conferência e ainda não confirmou o resumo."})
    missing_after_clarification = [key for key in path(attempt, overrides) if key not in attempt.respostas]
    if (clarifications or point_needs_a8) and missing_after_clarification:
        signals.append({"codigo": "revisao_incompleta", "motivo": "Revisão abriu perguntas ainda sem resposta: " + ", ".join(missing_after_clarification)})
    suspended = bool(unclear or attempt.qualidade.get("confirmacao_recusada") or ((clarifications or point_needs_a8) and missing_after_clarification))
    if suspended:
        affected = set()
        for key in unclear:
            if key == "A1":
                affected.update(("ponto_curso", "continuidade"))
            elif key == "R2":
                affected.add("satisfacao")
            elif key in ("A3", "R4", "R5", "R5b"):
                affected.add("reclamacao")
            elif key == "A8":
                affected.add("continuidade")
            elif key == "R11":
                affected.add("boca_a_boca")
        for key in affected:
            if readings[key]["estado"] == "declarada":
                readings[key]["estado"] = "sem_valor"
    if point_needs_a8 and "A8" in missing_after_clarification:
        readings["continuidade"]["valor"] = None
        readings["continuidade"]["estado"] = "sem_valor"
    confirmed = [key for key, reading in readings.items() if reading["estado"] == "confirmada"]
    pending_stage = point_needs_a8 and "A8" in missing_after_clarification
    return {"nps": note if isinstance(note, int) else None, "classificacao": "A conferir" if suspended else portrait, "retrato": "A conferir" if suspended else portrait, "retrato_calculado": None if pending_stage else portrait, "motivos": ["O ponto real do curso exige perguntar novamente sobre a continuidade."] if pending_stage else [reason], "leituras": readings, "pessoa_respondente": "aluno_pagante", "sinais": signals, "suspenso": suspended, "provisorio": any(item["codigo"] == "outra_situacao" for item in signals), "confirmado": bool(confirmed), "fatos_confirmados": confirmed, "participacao_externa": "não disponível"}


def review_context(attempt, revisions):
    overrides = {item.situacao_id: item.tipo for item in revisions if item.tipo in ("escola", "opiniao", "pessoal", "nenhum")}
    facts = {item.situacao_id: item.prova for item in revisions if item.tipo == "fato"}
    clarifications = {}
    for item in revisions:
        if item.tipo == "esclarecimento":
            proof = item.prova
            clarifications[item.situacao_id] = {"valor": proof["valor"], "complemento": proof["complemento"]} if proof.get("complemento") else proof["valor"]
    context, _point_needs_a8 = _effective_context(attempt, facts, clarifications)
    missing = [key for key in path(context, overrides) if key not in context.respostas]
    questions = [question(context, key, overrides) for key in missing]
    return overrides, facts, clarifications, context, questions


DEPENDENTS = {
    "P1": set(ORDEM) - {"P1"},
    "A1": {"R2", "A3", "R4", "R5", "R5b", "R6", "R7", "A8", "R10", "R14"},
    "R2": {"R7"},
    "A3": {"R4", "R5", "R5b", "R6", "R7", "R10", "R14"},
    "R4": {"R5", "R5b", "R6", "R7", "R14"},
    "R5": {"R5b", "R6", "R7", "R14"},
    "R5b": {"R6", "R7", "R14"},
    "A8": {"R10"},
}


def _record(attempt, key, action, **extra):
    quality = dict(attempt.qualidade)
    quality["eventos"] = [*quality.get("eventos", []), {"pergunta_id": key, "acao": action, "registrado_em": timezone.now().isoformat(), **extra}]
    attempt.qualidade = quality
    attempt.save(update_fields=["qualidade"])


def _show(attempt, key):
    if key not in attempt.perguntas_exibidas:
        attempt.perguntas_exibidas = [*attempt.perguntas_exibidas, key]
        attempt.save(update_fields=["perguntas_exibidas"])
    quality = dict(attempt.qualidade)
    current = quality.get("pergunta_em_exibicao") or {}
    if current.get("pergunta_id") != key:
        quality["pergunta_em_exibicao"] = {"pergunta_id": key, "inicio": timezone.now().isoformat()}
        attempt.qualidade = quality
        attempt.save(update_fields=["qualidade"])
        _record(attempt, key, "exibida")
    return question(attempt, key)


def _finish_timer(attempt, key):
    quality = dict(attempt.qualidade)
    current = quality.pop("pergunta_em_exibicao", {})
    if current.get("pergunta_id") == key:
        now = timezone.now()
        try:
            start = datetime.fromisoformat(current["inicio"])
            elapsed = max(0, (now - start).total_seconds())
        except (ValueError, TypeError, KeyError):
            start, elapsed = None, None
        quality["tempos_perguntas"] = [*quality.get("tempos_perguntas", []), {"pergunta_id": key, "inicio": start.isoformat() if start else None, "respondida_em": now.isoformat(), "duracao_segundos": elapsed}]
    attempt.qualidade = quality
    attempt.save(update_fields=["qualidade"])


def serialize(attempt, include_question=True):
    items = readable(attempt)
    data = {"id": str(attempt.id), "site_id": attempt.site_id, "aluno_id": attempt.aluno_id, "status": attempt.status, "site": attempt.site, "aluno": attempt.aluno, "produto": attempt.produto, "curso": attempt.curso, "matricula": attempt.matricula, "config_versao": attempt.config_versao, "config_documento": attempt.config_documento, "calculo_versao": attempt.calculo_versao, "roteiro": ROTEIRO, "respostas": attempt.respostas, "respostas_legiveis": items, "respostas_registro": attempt.respostas_registro, "perguntas_exibidas": attempt.perguntas_exibidas, "resultado": attempt.resultado, "qualidade": attempt.qualidade, "criada_em": attempt.criada_em.isoformat(), "concluida_em": attempt.concluida_em.isoformat() if attempt.concluida_em else None}
    if include_question and attempt.status != "concluida":
        key = next_key(attempt)
        data["proxima_pergunta"] = _show(attempt, key) if key else None
        data["conferencia"] = {"resumo": conference_summary(items), "confirmacao_pendente": key is None, "corrigir": bool(attempt.qualidade.get("confirmacao_recusada"))} if key is None else None
        data["qualidade"] = attempt.qualidade
        data["perguntas_exibidas"] = attempt.perguntas_exibidas
    return data


def _validate_answer(attempt, key, value, complement, overrides=None):
    item = question(attempt, key, overrides)
    kind = item["tipo"]
    if not isinstance(complement, str) or len(complement) > 3000:
        return "Complemento inválido."
    if kind == "nota":
        if isinstance(value, str) and value.isdecimal():
            value = int(value)
        if type(value) is not int or value < 0 or value > 10:
            return "Nota deve ser de 0 a 10."
    elif kind == "multipla":
        if not isinstance(value, list) or not value or not all(isinstance(v, str) for v in value) or len(value) != len(set(value)):
            return "Escolha ao menos uma opção válida."
        valid = {option["valor"] for option in item["opcoes"]}
        if not set(value) <= valid:
            return "Opção inválida."
        exclusive = {option["valor"] for option in item["opcoes"] if option.get("exclusiva")}
        if len(value) > 1 and set(value) & exclusive:
            return "A opção exclusiva não pode acompanhar outras respostas."
        if "outra" in value and not complement.strip():
            return "Descreva a outra situação."
    elif kind == "escolha":
        if value not in [option["valor"] for option in item["opcoes"]]:
            return "Opção inválida."
        if value == "outro" and not complement.strip():
            return "Descreva o outro motivo."
    elif kind == "texto":
        if not isinstance(value, str) or len(value) > 3000 or (item.get("obrigatoria") and not value.strip()):
            return "Texto inválido."
    return None


def process(attempt, data):
    """Return None on success, or an error string. Caller holds a row lock."""
    action = data.get("acao", "responder")
    was_back = action == "voltar"
    if was_back:
        sequence = path(attempt)
        pending = next_key(attempt)
        before = sequence.index(pending) if pending in sequence else len(sequence)
        previous = next((key for key in reversed(sequence[:before]) if key != "P1" and key in attempt.respostas), None)
        if previous is None:
            return "Já está na primeira pergunta."
        data = {**data, "pergunta_id": previous}
        action = "corrigir"
    if action == "revisar_conferencia":
        if next_key(attempt):
            return "Responda as perguntas antes da conferência."
        quality = dict(attempt.qualidade)
        quality["confirmacao_recusada"] = True
        attempt.qualidade = quality
        attempt.save(update_fields=["qualidade"])
        _record(attempt, None, "conferencia_recusada")
        return None
    if action == "corrigir":
        key = data.get("pergunta_id")
        if key == "P1" or key not in attempt.respostas or key not in path(attempt):
            return "Pergunta não respondida."
        removed = {key, *DEPENDENTS.get(key, set())}
        answers = dict(attempt.respostas)
        for child in removed:
            if child in answers:
                answers.pop(child)
                _record(attempt, child, "descartada_para_correcao")
        attempt.respostas = answers
        attempt.save(update_fields=["respostas"])
        quality = dict(attempt.qualidade)
        quality.pop("pergunta_em_exibicao", None)
        if not was_back:
            quality["confirmacao_recusada"] = True
        attempt.qualidade = quality
        attempt.save(update_fields=["qualidade"])
        _record(attempt, key, "voltar" if was_back else "corrigir")
        return None
    if action == "nao_entendi":
        key = data.get("pergunta_id")
        if key != next_key(attempt):
            return "Pergunta fora da ordem atual."
        if key == "P1":
            _record(attempt, key, "nao_entendi", ajuda=question(attempt, key)["ajuda_nao_entendi"])
            return None
        value, complement = NAO_ENTENDI, ""
    elif action == "responder":
        key, value, complement = data.get("pergunta_id"), data.get("valor"), data.get("complemento", "")
        if key != next_key(attempt) and key not in attempt.respostas:
            return "Pergunta fora da ordem atual."
        if key not in path(attempt):
            return "Pergunta fora do caminho atual."
        error = _validate_answer(attempt, key, value, complement)
        if error:
            return error
        if question(attempt, key)["tipo"] == "nota" and isinstance(value, str):
            value = int(value)
    elif action == "concluir":
        if next_key(attempt):
            return "Responda todas as perguntas antes de concluir."
        if data.get("confirmado") is not True:
            return "Confirme o resumo antes de concluir."
        quality = dict(attempt.qualidade)
        quality["confirmacao_recusada"] = False
        quality["conferencia_confirmada_em"] = timezone.now().isoformat()
        quality["duracao_segundos"] = max(0, (timezone.now() - attempt.criada_em).total_seconds())
        quality["perguntas_exibidas_unicas"] = len(set(attempt.perguntas_exibidas))
        quality["audit_failed"] = False
        quality["estado"] = "tempos_medidos_sem_punicao"
        attempt.qualidade = quality
        attempt.resultado = calculate(attempt)
        attempt.status = "concluida"
        attempt.concluida_em = timezone.now()
        attempt.save(update_fields=["qualidade", "resultado", "status", "concluida_em"])
        _record(attempt, None, "concluida")
        return None
    else:
        return "Ação inválida."

    previous = attempt.respostas.get(key)
    answer = {"valor": value, "complemento": complement} if complement else value
    answers = dict(attempt.respostas)
    changed = key in answers and previous != answer
    if changed:
        for child in DEPENDENTS.get(key, set()):
            if child in answers:
                answers.pop(child)
                _record(attempt, child, "ramo_abandonado")
    answers[key] = answer
    attempt.respostas = answers
    attempt.respostas_registro = [*attempt.respostas_registro, {"pergunta_id": key, "valor": value, "complemento": complement, "valor_anterior": previous, "registrado_em": timezone.now().isoformat(), "acao": action}]
    attempt.save(update_fields=["respostas", "respostas_registro"])
    _finish_timer(attempt, key)
    _record(attempt, key, action, alterada=changed)
    return None
