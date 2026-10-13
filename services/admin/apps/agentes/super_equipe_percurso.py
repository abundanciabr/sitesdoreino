"""Leitura agregada do percurso comercial; não altera as fontes nem consome IA."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time, timedelta
from math import ceil
from statistics import median
from zoneinfo import ZoneInfo

from django.utils import timezone

FUSO = ZoneInfo("America/Sao_Paulo")
MAX_QUIZZES = 30


def periodo(inicio="", fim="", janela="semana", agora=None):
    agora = (agora or timezone.now()).astimezone(FUSO)
    hoje = agora.date()
    finais = date.fromisoformat(fim) if fim else hoje
    padroes = {"dia": hoje, "semana": hoje - timedelta(days=hoje.weekday()),
               "mes": hoje.replace(day=1), "45": hoje - timedelta(days=44),
               "84": hoje - timedelta(days=83)}
    iniciais = date.fromisoformat(inicio) if inicio else padroes.get(janela, padroes["semana"])
    if iniciais > finais or finais > hoje or (finais - iniciais).days > 365:
        raise ValueError("Escolha datas em ordem, até hoje, com no máximo 366 dias.")
    return {"inicio": iniciais.isoformat(), "fim": finais.isoformat(),
            "desde": datetime.combine(iniciais, time.min, FUSO).isoformat(),
            "ate": min(datetime.combine(finais, time.max, FUSO), agora).isoformat(),
            "observado_em": agora.isoformat(), "fuso": str(FUSO)}


def instante(valor):
    try:
        d = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
        return d if d.tzinfo else None
    except (ValueError, TypeError):
        return None


def duracoes(valores):
    valores = sorted(valores)
    return {"amostra": len(valores), "mediana_s": round(median(valores), 2) if valores else None,
            "p95_s": round(valores[ceil(.95 * len(valores)) - 1], 2) if valores else None,
            "min_s": round(valores[0], 2) if valores else None,
            "max_s": round(valores[-1], 2) if valores else None}


def _numero(valor):
    if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
        raise ValueError("Contagem ausente ou inválida")
    return valor


def resumir_quiz(slug, dados):
    funil = dados["funil"]
    versoes = funil["versoes"]
    visitas = _numero(funil["visitas_elegiveis"])
    conclusoes = sum(_numero(v["conclusoes"]) for v in versoes)
    if conclusoes > visitas:
        raise ValueError("Conclusões excedem a população de visitas")
    return {"quiz": slug, "estado": "medido", "visitas": visitas,
            "conclusoes": conclusoes,
            "taxa": round(100 * conclusoes / visitas, 2) if visitas else None,
            "saidas": sum(_numero(v["saidas_reais"]) for v in versoes),
            "orfas": _numero(funil["conclusoes_sem_visita"]),
            "teste_visitas": _numero(funil["teste"]["visitas"]),
            "teste_conclusoes": _numero(funil["teste"]["conclusoes"])}


def resumir_crm(dados, site_id, p):
    """Retorna apenas agregados; identificadores de origem não saem desta função."""
    if str(dados["filtros"]["site_id"]) != str(site_id):
        raise ValueError("Fonte de outro site")
    ops = dados["oportunidades"]
    compras = dados["compras"]
    totais = dados["totais"]
    truncado = (bool(dados.get("oportunidades_truncadas"))
                or len(ops) < _numero(totais["elegiveis"])
                or len(compras) < _numero(totais["compras_aprovadas"]))
    por_id = {}
    inconsistentes = 0
    desde, ate, observado = (instante(p[k]) for k in ("desde", "ate", "observado_em"))
    for o in ops:
        criada = instante(o.get("criada_em"))
        if (str(o.get("site_id")) != str(site_id) or not o.get("id") or not o.get("lead_id")
                or not criada or not desde <= criada <= ate):
            inconsistentes += 1
            continue
        por_id[str(o["id"])] = o
    pessoas = {str(o["lead_id"]) for o in por_id.values()}
    compradores, pedidos, tempos = set(), set(), []
    sem_tempo = invertidos = posteriores = revertidas = sem_campanha = 0
    for o in por_id.values():
        if not o.get("campanha") or o["campanha"] == "sem campanha":
            sem_campanha += 1
    for c in compras:
        pedido = c.get("pedido_id")
        if not pedido or str(pedido) in pedidos:
            inconsistentes += 1
            continue
        o = por_id.get(str(c.get("oportunidade_id")))
        if not o or str(c.get("lead_id")) != str(o["lead_id"]):
            inconsistentes += 1
            continue
        aprovada = instante(c.get("aprovado_em"))
        if aprovada and aprovada > observado:
            posteriores += 1
            continue
        pedidos.add(str(pedido))
        compradores.add(str(o["lead_id"]))
        revertidas += int(bool(c.get("revertida")))
        if not aprovada:
            sem_tempo += 1
        else:
            segundos = (aprovada - instante(o["criada_em"])).total_seconds()
            if segundos < 0:
                invertidos += 1
            else:
                tempos.append(segundos)
    completa = not (truncado or inconsistentes or posteriores)
    return {"estado": "medido" if completa else "parcial", "completa": completa,
            "oportunidades": len(por_id), "contatos": len(pessoas),
            "pedidos": len(pedidos), "compradores": len(compradores),
            "revertidas": revertidas,
            "taxa": round(100 * len(compradores) / len(pessoas), 2) if pessoas and completa else None,
            "sem_campanha": sem_campanha,
            "totais_fonte_oportunidades": _numero(totais["elegiveis"]),
            "totais_fonte_compras": _numero(totais["compras_aprovadas"]),
            "truncado": truncado, "inconsistentes": inconsistentes,
            "tempos": duracoes(tempos), "sem_tempo": sem_tempo,
            "invertidos": invertidos, "posteriores": posteriores,
            "testes_oportunidades": _numero(dados["testes_fora"]["oportunidades"]),
            "testes_compras": _numero(dados["testes_fora"]["compras"])}


def resumir_escola(fichas, site_id, p):
    """Matrícula liberada não comprova primeiro login nem qual pedido a originou."""
    from apps.core.placar import vendeu_pelo_site
    if not isinstance(fichas, list):
        raise ValueError("Escola indisponível")
    desde, ate = instante(p["desde"]), instante(p["ate"])
    pessoas, anteriores = set(), set()
    matriculas = sem_data = sem_identidade = reembolsadas = 0
    for ficha in fichas:
        if str(ficha.get("site_id")) != str(site_id):
            continue
        quando = instante(ficha.get("virou_aluno_em"))
        if ficha.get("status") == "reembolsada" and quando and desde <= quando <= ate:
            reembolsadas += 1
        if not vendeu_pelo_site(ficha):
            continue
        if not quando:
            sem_data += 1
            continue
        email = str(ficha.get("email") or "").strip().lower()
        if quando < desde:
            if email:
                anteriores.add(email)
        elif quando <= ate:
            matriculas += 1
            if email:
                pessoas.add(email)
            else:
                sem_identidade += 1
    return {"estado": "parcial" if sem_data or sem_identidade else "medido",
            "matriculas": matriculas, "pessoas": len(pessoas),
            "pessoas_sem_registro_anterior": len(pessoas - anteriores),
            "pessoas_com_registro_anterior": len(pessoas & anteriores),
            "sem_data": sem_data, "sem_identidade": sem_identidade,
            "reembolsadas": reembolsadas}


def resumir_ligacao(dados, fichas, site_id, p):
    """Associação por contato explícito; não é a ligação entre pedido e matrícula."""
    from apps.core.placar import vendeu_pelo_site
    desde, ate, observado = (instante(p[k]) for k in ("desde", "ate", "observado_em"))
    ops = {str(o["id"]): str(o["lead_id"]) for o in dados["oportunidades"]
           if str(o.get("site_id")) == str(site_id) and o.get("id") and o.get("lead_id")
           and instante(o.get("criada_em")) and desde <= instante(o["criada_em"]) <= ate}
    compradores = {ops[str(c["oportunidade_id"])] for c in dados["compras"]
                   if str(c.get("oportunidade_id")) in ops and c.get("pedido_id")
                   and str(c.get("lead_id")) == ops[str(c["oportunidade_id"])]
                   and instante(c.get("aprovado_em")) and instante(c["aprovado_em"]) <= observado}
    associados = set()
    sem_vinculo = 0
    for f in fichas:
        if str(f.get("site_id")) != str(site_id) or not vendeu_pelo_site(f):
            continue
        quando = instante(f.get("virou_aluno_em"))
        if not quando or quando > observado:
            continue
        contato = str(f.get("contato_crm_id") or "")
        if not contato:
            sem_vinculo += 1
        elif contato in compradores:
            associados.add(contato)
    return {"compradores_observados": len(compradores), "com_matricula": len(associados),
            "sem_matricula_vinculada": len(compradores - associados),
            "matriculas_sem_contato": sem_vinculo,
            "limite": "Associação pelo contato_crm_id explícito, em qualquer curso/data até a coleta. "
                      "Ausência de vínculo não comprova ausência de matrícula. Sem order_id, "
                      "não prova que esse pedido liberou esse acesso, nem mede o tempo compra → acesso."}


def coletar(site_id, host, p=None):
    from apps.core.clients import AlunosClient, LeadsClient
    from apps.core.conteudos import pedir_por_host
    p = p or periodo()
    resultado = {"versao": 1, "estado": "parcial", "periodo": p,
                 "fonte": "APIs existentes do quiz, CRM e escola; somente leitura",
                 "url": f"https://{host}/admin/super-equipe/percurso-comercial/",
                 "quizzes": [], "crm": {"estado": "indisponivel"},
                 "escola": {"estado": "indisponivel"},
                 "limites": [
                     "Tráfego medido começa na abertura do quiz. Impressões, cliques e custo da mídia não estão nesta fonte.",
                     "Sessões são distintas por quiz; somar quizzes não deduplica pessoas. Clique de saída não é compra.",
                     "A coorte do quiz usa a data da primeira abertura; a coorte do CRM usa a criação da oportunidade.",
                     "Conclusões/saídas do quiz são observadas até a consulta, inclusive depois do período de entrada; a API não expõe corte por instante.",
                     "Sem vínculo de sessão com o contato nas APIs consultadas: não há conversão contínua tráfego → compra.",
                     "Pedidos aprovados são os vinculados às oportunidades da coorte, até a coleta; não são todas as vendas do site no período.",
                     "Tempo CRM → aprovação usa criação da oportunidade, não o instante exato de conclusão do quiz. Inclui pedidos posteriormente revertidos.",
                     "Matrículas são vendas reconhecidas pela escola, por virou_aluno_em; não são primeiros logins nem necessariamente novos alunos.",
                     "Pessoas da escola são deduplicadas pelo e-mail normalizado apenas em memória. Não se somam compras de produtos diferentes como pessoas.",
                     "Sem pedido exposto pela escola ou evento de primeiro login: tempos compra → acesso e acesso → primeiro login indisponíveis.",
                     "Leituras independentes, sem transação entre serviços; mostram datas da coleta e podem diferir enquanto eventos chegam.",
                 ]}
    if not site_id:
        resultado["motivo"] = "Site não identificado; fontes não consultadas."
        return resultado
    def crm():
        try:
            cliente = LeadsClient()
            status, dados = cliente._pedir("/resultados/comerciais", {
                "site_id": str(site_id), "desde": p["desde"], "ate": p["ate"]})
            return (resumir_crm(dados, site_id, p), dados) if status == cliente.OK else ({"estado": "indisponivel"}, None)
        except (TypeError, ValueError, KeyError):
            return {"estado": "indisponivel"}, None
    def escola():
        try:
            fichas = AlunosClient().alunos()
            return resumir_escola(fichas, site_id, p), fichas
        except (TypeError, ValueError, KeyError):
            return {"estado": "indisponivel"}, None
    def quiz(slug):
        try:
            status, dados = pedir_por_host(host, "quiz", "GET", slug, "campanhas",
                                          params={"inicio": p["inicio"], "fim": p["fim"]})
            return resumir_quiz(slug, dados) if status == 200 else {"quiz": slug, "estado": "indisponivel"}
        except (TypeError, ValueError, KeyError):
            return {"quiz": slug, "estado": "indisponivel"}
    with ThreadPoolExecutor(max_workers=4) as pool:
        c, e = pool.submit(crm), pool.submit(escola)
        status, inventario = pedir_por_host(host, "quiz", "GET")
        if status == 200 and isinstance(inventario, dict) and isinstance(inventario.get("items"), list):
            slugs = sorted({i["slug"] for i in inventario["items"] if isinstance(i, dict) and isinstance(i.get("slug"), str)})
            resultado["inventario"] = {"estado": "medido", "total": len(slugs), "omitidos": max(0, len(slugs) - MAX_QUIZZES)}
            resultado["quizzes"] = list(pool.map(quiz, slugs[:MAX_QUIZZES]))
        else:
            resultado["inventario"] = {"estado": "indisponivel"}
        resultado["crm"], crm_dados = c.result()
        resultado["escola"], fichas = e.result()
    if crm_dados is not None and fichas is not None:
        resultado["ligacao"] = resumir_ligacao(crm_dados, fichas, site_id, p)
    resultado["concluido_em"] = timezone.now().astimezone(FUSO).isoformat()
    return resultado
