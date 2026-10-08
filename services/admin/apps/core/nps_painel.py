"""Leitura visual da satisfação, com as respostas e os motivos já calculados."""

from urllib.parse import urlencode

from django.shortcuts import render
from django.urls import reverse
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_GET

from .nps import _site, _texto, preparar_avaliacoes
from .nps_client import NPSClient


ASSUNTOS = {
    "R12": ("Recomendação", "estrela"), "nota": ("Recomendação", "estrela"),
    "A1": ("Aulas vistas", "aula"), "R2": ("Satisfação", "rosto"),
    "A3": ("Problemas relatados", "mensagem"), "R4": ("Situação principal", "mensagem"),
    "R5": ("Situação hoje", "mensagem"), "R5b": ("Outras situações", "mensagem"),
    "R6": ("Ajuda pedida", "ajuda"), "R7": ("Satisfação anterior", "rosto"),
    "A8": ("Continuidade", "alvo"), "R10": ("Motivo para não continuar", "mensagem"),
    "R11": ("Boca a boca", "voz"), "R13": ("Comentário", "documento"),
    "comentario": ("Comentário", "documento"), "R14": ("Contato para resolver", "ajuda"),
}
LEITURAS = {
    "satisfacao": "Satisfação", "reclamacao": "Reclamação", "continuidade": "Continuidade",
    "boca_a_boca": "Boca a boca", "ponto_curso": "Aulas vistas",
}
VALORES = {"Fica": "Quer continuar", "Sai": "Quer sair", "Em dúvida": "Em dúvida sobre continuar",
           "Concluiu": "Concluiu o curso", "A favor": "Recomendou o curso", "Contra": "Falou contra o curso",
           "Dos dois jeitos": "Recomendou e também falou contra", "Nenhum": "Ainda não recomendou",
           "Em aberto": "Reclamação em aberto", "Resolvida": "Reclamação resolvida", "Nenhuma": "Nenhuma reclamação",
           "Só opinião ou barreira pessoal": "Opinião ou dificuldade pessoal",
           "nenhuma": "Ainda não viu aulas", "recente": "Viu aula no último mês",
           "antiga": "Viu aula há mais de um mês", "todas": "Concluiu as aulas"}


def tom_do_retrato(retrato):
    texto = str(retrato or "").casefold()
    if "detrator" in texto or "insatisfeito de saída" in texto or "alto risco" in texto:
        return "vermelho"
    if "crise" in texto or "risco" in texto or "potencial" in texto:
        return "amarelo"
    if "promotor" in texto:
        return "verde"
    return "cinza"


def _motivos(resultado):
    motivos = resultado.get("motivos") or []
    if isinstance(motivos, list):
        return [str(item) for item in motivos if item]
    if isinstance(motivos, str):
        return [motivos]
    return []


def _origem(leitura):
    estado = leitura.get("estado", "declarada")
    if estado == "em_conflito":
        return "Em conflito com o registro"
    if estado == "confirmada":
        return "Confirmado por registro"
    if estado == "sem_valor":
        return "Ainda precisa de esclarecimento"
    return "Resposta do aluno"


def _leitura(leitura, chave):
    valor = leitura.get("valor")
    bom = valor in ("Satisfeito", "Fica", "A favor", "Resolvida", "Nenhuma", "Concluiu", "todas")
    ruim = valor in ("Insatisfeito", "Sai", "Contra", "Em aberto")
    tom = "verde" if bom else "vermelho" if ruim else "amarelo"
    if leitura.get("estado") in ("sem_valor", "em_conflito"):
        tom = "amarelo"
    fonte = leitura.get("fonte") or {}
    return {"titulo": VALORES.get(valor, valor) or "A esclarecer", "assunto": LEITURAS.get(chave, chave),
            "tom": tom, "origem": _origem(leitura), "declarado": leitura.get("valor_declarado"),
            "fonte": fonte.get("fonte", "") if isinstance(fonte, dict) else str(fonte),
            "referencia": fonte.get("referencia", "") if isinstance(fonte, dict) else ""}


def preparar_painel(avaliacao):
    preparar_avaliacoes({"avaliacoes": [avaliacao]})
    resultado = avaliacao.get("resultado_atual") or avaliacao.get("resultado") or {}
    retrato = resultado.get("retrato") or resultado.get("classificacao") or "A conferir"
    motivos = _motivos(resultado)
    nota = resultado.get("nps")
    aluno = avaliacao.get("aluno") or {}
    leituras = resultado.get("leituras") or {}
    revisado = avaliacao.get("roteiro_revisado", False)
    linhas = []
    legiveis = avaliacao.get("respostas_legiveis") or []
    if not isinstance(legiveis, list):
        legiveis = [{"pergunta": k, "resposta": v} for k, v in legiveis.items()] if isinstance(legiveis, dict) else []
    for item in legiveis:
        if not isinstance(item, dict):
            continue
        chave = item.get("pergunta_id")
        if chave == "P1":
            continue
        titulo, icone = ASSUNTOS.get(chave, (item.get("pergunta") or "Resposta", "mensagem"))
        valor = item.get("resposta")
        if valor is None:
            valor = item.get("valor")
        if chave in ("R13", "comentario") and not str(valor or "").strip():
            valor = "Não deixou comentário"
        elif valor is None:
            valor = "Não respondido"
        elif chave in ("R12", "nota") and type(item.get("valor")) is int:
            valor = str(item["valor"]) + " de 10"
        elif isinstance(valor, list):
            valor = "; ".join(str(v) for v in valor)
        linhas.append({"chave": chave or "", "assunto": titulo, "icone": icone,
                       "pergunta": item.get("pergunta") or titulo, "resposta": valor,
                       "complemento": item.get("complemento") if item.get("complemento") and str(item["complemento"]) not in str(valor) else ""})
    ordem = {chave: n for n, chave in enumerate(("R12", "nota", "A1", "R2", "A3", "R4", "R5", "R5b", "R6", "R7", "A8", "R10", "R11", "R13", "comentario", "R14"))}
    linhas.sort(key=lambda item: ordem.get(item["chave"], 100))
    por_retrato = {
        "Detrator": ("satisfacao", "boca_a_boca"),
        "Promotor": ("satisfacao", "boca_a_boca"),
        "Promotor em potencial": ("satisfacao", "continuidade", "boca_a_boca"),
        "Promotor em crise": ("reclamacao", "satisfacao", "continuidade"),
        "Insatisfeito de saída": ("satisfacao", "continuidade"),
        "Em risco por problema": ("reclamacao", "satisfacao", "continuidade"),
        "Em risco": ("satisfacao", "continuidade"),
        "Cedo para avaliar": ("satisfacao", "ponto_curso"),
    }
    evidencias = [_leitura(leituras[chave], chave) for chave in por_retrato.get(retrato, tuple(LEITURAS))
                  if isinstance(leituras.get(chave), dict)]
    sinais = resultado.get("sinais") or []
    pendencias = [item.get("motivo", "") for item in sinais if isinstance(item, dict) and item.get("motivo")]
    return {
        "arquivada": bool(avaliacao.get("arquivada_em")),
        "id": avaliacao.get("id", ""), "nome": aluno.get("nome") or aluno.get("email") or "Aluno",
        "email": aluno.get("email") or "", "curso": avaliacao["curso_nome"],
        "data": parse_datetime(avaliacao.get("concluida_em") or avaliacao.get("criada_em") or ""),
        "status": "Concluída" if avaliacao.get("status") == "concluida" else "Conferência pendente",
        "retrato": retrato, "tom": tom_do_retrato(retrato), "motivos": motivos,
        "explicacao": " ".join(motivos) or resultado.get("explicacao") or "Os motivos desta classificação não foram registrados.",
        "nota": nota if type(nota) is int and 0 <= nota <= 10 else None,
        "respostas": linhas, "evidencias": evidencias, "pendencias": pendencias,
        "provisorio": bool(resultado.get("provisorio")), "suspenso": bool(resultado.get("suspenso")),
        "revisado": revisado, "revisoes": bool(avaliacao.get("revisoes")),
        "original": avaliacao.get("retrato_original", ""),
        "problemas": VALORES.get((leituras.get("reclamacao") or {}).get("valor"), "Situação não registrada"),
    }


@require_GET
def crm_satisfacao_painel(request):
    site_id, q = _site(request), _texto(request.GET.get("q"), 120)
    arquivadas = request.GET.get("arquivadas") == "1"
    cliente = NPSClient()
    estado_lista, lista = cliente.respondentes(site_id, q=q, pagina=_texto(request.GET.get("pagina"), 10) or "1", arquivadas=arquivadas) if site_id else ("sem-site", None)
    lista = lista if isinstance(lista, dict) else {}
    if estado_lista == cliente.OK and (not isinstance(lista.get("itens"), list)
                                       or any(type(lista.get(k)) is not int for k in ("alunos", "total", "pagina", "paginas"))):
        estado_lista, lista = cliente.INDISPONIVEL, {}
    escolhida = _texto(request.GET.get("avaliacao"), 100)
    aluno_id = _texto(request.GET.get("aluno_id"))
    email = _texto(request.GET.get("email"), 254).lower()
    if not aluno_id and not email and lista.get("itens"):
        aluno_id = lista["itens"][0].get("aluno_id", "")
        escolhida = escolhida or lista["itens"][0].get("id", "")
    estado, historico = cliente.historico(site_id, aluno_id=aluno_id, email=email) if site_id and (aluno_id or email) else ("sem-aluno", None)
    historico = historico if isinstance(historico, dict) else {}
    if estado == cliente.OK and (not isinstance(historico.get("avaliacoes"), list)
                                or not isinstance(historico.get("atendimentos"), list)):
        estado, historico = cliente.INDISPONIVEL, {}
    avaliacoes = [a for a in historico.get("avaliacoes", []) if isinstance(a, dict)]
    visiveis = [a for a in avaliacoes if bool(a.get("arquivada_em")) == arquivadas]
    avaliacao = next((a for a in avaliacoes if a.get("id") == escolhida), None) if escolhida else next(iter(visiveis), None)
    painel = preparar_painel(avaliacao) if avaliacao else None
    if avaliacao:
        aluno_id = avaliacao.get("aluno_id") or aluno_id
    def url(params, *, gestao=False):
        nome = "crm_satisfacao_gestao" if gestao else "crm_satisfacao"
        return reverse(nome) + "?" + urlencode({"site_id": site_id, **({"arquivadas": "1"} if arquivadas and not gestao else {}), **params})
    itens = []
    for item in lista.get("itens", []):
        item = dict(item)
        item["tom"] = tom_do_retrato(item.get("retrato"))
        item["ativo"] = bool(avaliacao and item.get("id") == avaliacao.get("id"))
        item["url"] = url({"aluno_id": item.get("aluno_id", ""), "avaliacao": item.get("id", ""), "q": q, "pagina": lista.get("pagina", 1)})
        itens.append(item)
    dono = {"aluno_id": aluno_id}
    if email:
        dono["email"] = email
    for a in avaliacoes:
        curso = a.get("curso") or a.get("produto") or {}
        a["curso_tela"] = curso.get("nome") or curso.get("name") or "Curso" if isinstance(curso, dict) else str(curso)
        a["data_tela"] = parse_datetime(a.get("concluida_em") or a.get("criada_em") or "")
        a["url"] = url({**dono, "avaliacao": a.get("id", ""), "q": q, "arquivadas": "1" if a.get("arquivada_em") else "0"})
    atendimentos = historico.get("atendimentos", [])
    relevantes = [a for a in atendimentos if isinstance(a, dict) and (not a.get("tentativa_id") or (avaliacao and a.get("tentativa_id") == avaliacao.get("id")))]
    ativos = [a for a in relevantes if a.get("status") != "resolvido"]
    atendimento = next(iter(ativos or relevantes), None)
    if atendimento:
        atendimento = dict(atendimento)
        atendimento["descricao_tela"] = atendimento.get("proximo_passo") or atendimento.get("solucao") or ""
        atendimento["status_tela"] = {"aberto": "Atendimento aberto", "em_andamento": "Em acompanhamento", "resolvido": "Atendimento resolvido"}.get(atendimento.get("status"), "Atendimento registrado")
        atendimento["prazo_tela"] = parse_datetime(atendimento.get("prazo") or "")
    from apps.agentes.satisfacao import contexto_painel
    contexto_robo = contexto_painel(site_id, aluno_id, avaliacao, historico)
    atual = lista.get("pagina", 1)
    return render(request, "admin/crm_satisfacao_painel.html", {
        **contexto_robo,
        "arquivadas": arquivadas, "aluno_id": aluno_id,
        "arquivo_url": reverse("crm_satisfacao_arquivo"),
        "excluir_url": reverse("crm_satisfacao_confirmar_exclusao") + "?" + urlencode({"site_id": site_id, "aluno_id": aluno_id, "avaliacao": avaliacao.get("id", "") if avaliacao else ""}),
        "admin": request.admin, "site_id": site_id, "q": q, "estado_lista": estado_lista,
        "lista": lista, "itens": itens, "estado_historico": estado, "painel": painel,
        "avaliacoes": avaliacoes, "atendimento": atendimento,
        "config_url": url({"secao": "configuracao"}, gestao=True),
        "historico_url": url({**dono, "secao": "historico"}, gestao=True),
        "atendimento_url": url({**dono, "secao": "atendimento", "avaliacao": avaliacao.get("id", "") if avaliacao else ""}, gestao=True) + "#editar-atendimento",
        "revisao_url": url({**dono, "secao": "historico", "revisao": avaliacao.get("id", "") if avaliacao else ""}, gestao=True) + "#revisao",
        "anterior_url": url({"q": q, "pagina": atual - 1}) if atual > 1 else "",
        "proxima_url": url({"q": q, "pagina": atual + 1}) if atual < lista.get("paginas", 1) else "",
        "selecao_invalida": bool(escolhida and not avaliacao),
    })
