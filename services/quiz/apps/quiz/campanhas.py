"""Contagens de campanha pela chegada da sessão ao quiz."""

from collections import defaultdict
from datetime import date
import re
from zoneinfo import ZoneInfo

from apps.quiz.models import Submission, TelemetryEvent


FUSO = ZoneInfo("America/Sao_Paulo")
UTM_CAMPOS = ("source", "medium", "campaign", "content", "term")
CONTEXTO_CAMPOS = ("fmt", "seg", "src", "med", "cpg", "ctv")


def _data(valor):
    if valor is None:
        return None
    if type(valor) is date:
        return valor
    if not isinstance(valor, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", valor):
        raise ValueError("A data deve estar no formato AAAA-MM-DD.")
    try:
        return date.fromisoformat(valor)
    except (TypeError, ValueError) as erro:
        raise ValueError("A data deve estar no formato AAAA-MM-DD.") from erro


def eh_teste(contexto, utm=None):
    """Tráfego de teste: src=teste, cpg começando com "teste" ou utm de teste."""
    contexto = contexto if isinstance(contexto, dict) else {}
    utm = utm if isinstance(utm, dict) else {}
    return (
        str(contexto.get("src") or "").strip().lower() == "teste"
        or str(contexto.get("cpg") or "").strip().lower().startswith("teste")
        or str(utm.get("source") or "").strip().lower() == "teste"
        or str(utm.get("campaign") or "").strip().lower().startswith("teste")
    )


def _dia(instante):
    return instante.astimezone(FUSO).date()


def _utm(valor):
    if not isinstance(valor, dict):
        valor = {}
    return tuple(str(valor.get(campo) or "") for campo in UTM_CAMPOS)


def _contexto(valor):
    if not isinstance(valor, dict):
        valor = {}
    return tuple(str(valor.get(campo) or "") for campo in CONTEXTO_CAMPOS)


def _chave_visita(evento):
    metadata = evento["metadata"] if isinstance(evento["metadata"], dict) else {}
    return (
        _dia(evento["occurred_at"]),
        *_utm(metadata.get("utm")),
        evento["version_key"],
        *_contexto(metadata.get("context")),
    )


def _demonstracao(metadata):
    return isinstance(metadata, dict) and metadata.get("demonstracao") is True


def _linha(chave, visitas, submissoes, saidas, demonstracoes=0):
    (
        dia,
        source,
        medium,
        campaign,
        content,
        term,
        version_key,
        fmt,
        seg,
        src,
        med,
        cpg,
        ctv,
    ) = chave
    perda = max(0, visitas - submissoes)
    sem_clique = max(0, submissoes - saidas)
    alertas = []
    if perda:
        alertas.append(f"{perda} sessão(ões) com visita registrada sem conclusão")
    if sem_clique:
        alertas.append(f"{sem_clique} conclusão(ões) sem clique de saída registrado")
    if saidas > submissoes:
        alertas.append("Saídas superam conclusões registradas; conferir a telemetria")
    return {
        "dia_origem": dia.isoformat(),
        "source": source,
        "medium": medium,
        "campaign": campaign,
        "content": content,
        "term": term,
        "version_key": version_key,
        "fmt": fmt,
        "seg": seg,
        "src": src,
        "med": med,
        "cpg": cpg,
        "ctv": ctv,
        "trafego_teste": eh_teste({"src": src, "cpg": cpg}, {"campaign": campaign}),
        "visitas": visitas,
        "submissoes": submissoes,
        "saidas": saidas,
        "saidas_reais": saidas - demonstracoes,
        "saidas_demonstracao": demonstracoes,
        "perda_ate_conclusao": perda,
        "conclusoes_sem_clique": sem_clique,
        "alertas": alertas,
    }


def _linhas_sem_denominador(grupos, observacao):
    return [
        {
            "dia_origem": None,
            "source": chave[0],
            "medium": chave[1],
            "campaign": chave[2],
            "content": chave[3],
            "term": chave[4],
            "version_key": chave[5],
            "fmt": chave[6],
            "seg": chave[7],
            "src": chave[8],
            "med": chave[9],
            "cpg": chave[10],
            "ctv": chave[11],
            "submissoes": quantidade,
            "visitas": None,
            "saidas": None,
            "observacao": observacao,
        }
        for chave, quantidade in sorted(grupos.items())
    ]


def relatorio_campanhas(quiz, inicio=None, fim=None):
    """Agrupa pela primeira visita da sessão, mesmo quando o evento veio antes do período.

    Sem visita, a data da submissão serve apenas para limitar o bloco avulso;
    ela nunca é apresentada como data de origem nem cria denominador.
    """
    inicio, fim = _data(inicio), _data(fim)
    if inicio and fim and inicio > fim:
        raise ValueError("--inicio não pode ser posterior a --fim.")

    base = TelemetryEvent.objects.filter(site_id=quiz.site_id, quiz_slug=quiz.slug)
    primeiras = {}
    for evento in (
        base.filter(event_type="view_quiz")
        .order_by("occurred_at", "id")
        .values("session_id", "occurred_at", "metadata", "version_key")
    ):
        primeiras.setdefault(evento["session_id"], _chave_visita(evento))

    def no_periodo(dia):
        return (inicio is None or dia >= inicio) and (fim is None or dia <= fim)

    grupos = defaultdict(
        lambda: {
            "visitas": set(),
            "submissoes": set(),
            "saidas": set(),
            "demonstracoes": set(),
        }
    )
    for sessao, chave in primeiras.items():
        if no_periodo(chave[0]):
            grupos[chave]["visitas"].add(sessao)

    sem_visita = defaultdict(int)
    sem_correspondencia = defaultdict(int)
    conclusoes_da_coorte = set()
    for submissao in (
        Submission.objects.filter(quiz=quiz, site_id=quiz.site_id)
        .select_related("version")
        .only("id", "session_id", "created_at", "utm", "context", "version__key")
    ):
        chave = primeiras.get(submissao.session_id) if submissao.session_id else None
        if chave is not None and chave[6] == submissao.version.key:
            if no_periodo(chave[0]):
                grupos[chave]["submissoes"].add(submissao.session_id)
                conclusoes_da_coorte.add(submissao.session_id)
        elif no_periodo(_dia(submissao.created_at)):
            destino = sem_visita if chave is None else sem_correspondencia
            destino[
                (
                    *_utm(submissao.utm),
                    submissao.version.key,
                    *_contexto(submissao.context),
                )
            ] += 1

    reais = set()
    for evento in base.filter(event_type="checkout_exit").values(
        "session_id", "version_key", "metadata"
    ):
        chave = primeiras.get(evento["session_id"])
        if (
            chave is not None
            and evento["session_id"] in conclusoes_da_coorte
            and chave[6] == evento["version_key"]
            and no_periodo(chave[0])
        ):
            grupos[chave]["saidas"].add(evento["session_id"])
            if not _demonstracao(evento["metadata"]):
                reais.add(evento["session_id"])
    for chave, valores in grupos.items():
        valores["demonstracoes"] = valores["saidas"] - reais

    linhas = [
        _linha(
            chave,
            len(valores["visitas"]),
            len(valores["submissoes"]),
            len(valores["saidas"]),
            len(valores["demonstracoes"]),
        )
        for chave, valores in sorted(grupos.items())
    ]
    avulsas = _linhas_sem_denominador(
        sem_visita, "Sem visita registrada; filtro de data aplicado à submissão."
    )
    return {
        "site_id": quiz.site_id,
        "quiz_slug": quiz.slug,
        "inicio": inicio.isoformat() if inicio else None,
        "fim": fim.isoformat() if fim else None,
        "fuso": FUSO.key,
        "campanhas": linhas,
        "funil": funil_por_etapa(quiz, inicio, fim, comercial=False),
        "sem_visita_registrada": avulsas,
        "submissoes_sem_correspondencia": _linhas_sem_denominador(
            sem_correspondencia,
            "Visita da sessão registrada em outra versão; filtro de data aplicado à submissão.",
        ),
    }


# ---------------------------------------------------------------------------
# Funil por etapa. Cada contagem é de SESSÕES distintas: atualizar a página
# repete eventos, mas não cria visita, clique ou abandono novo.
# ---------------------------------------------------------------------------

AMOSTRA_MINIMA = 30
ETAPA_LEAD = "lead"
SEM_COMPRA = "sem dados de compra"
REGRAS_DO_FUNIL = (
    "Visita elegível é uma sessão distinta com a abertura do quiz registrada; "
    "o dia e a versão são os da primeira abertura (fuso America/Sao_Paulo).",
    "Cada etapa conta sessões distintas. Abandono na etapa só vale para quem não "
    "concluiu e não viu nenhuma etapa depois dela; atualizar a página não conta como abandono.",
    "Tráfego de teste (src=teste, cpg começando com teste ou utm de teste) fica fora das taxas.",
    "Conclusões sem abertura registrada ficam de fora do funil e são contadas à parte.",
    "Saída real é clique para o checkout; saída de demonstração é clique na oferta ainda sem checkout.",
    "Com menos de 30 sessões no denominador a taxa é inconclusiva.",
)


def taxa(numerador, denominador):
    return {
        "valor": round(numerador / denominador, 4) if denominador else None,
        "numerador": numerador,
        "denominador": denominador,
        "amostra": denominador,
        "inconclusiva": denominador < AMOSTRA_MINIMA,
    }


def coletar_sessoes(quiz, inicio=None, fim=None):
    """Uma entrada por sessão com abertura registrada, deduplicada por sessão."""
    inicio, fim = _data(inicio), _data(fim)
    if inicio and fim and inicio > fim:
        raise ValueError("--inicio não pode ser posterior a --fim.")

    def no_periodo(dia):
        return (inicio is None or dia >= inicio) and (fim is None or dia <= fim)

    eventos = list(
        TelemetryEvent.objects.filter(
            site_id=quiz.site_id,
            quiz_slug=quiz.slug,
            event_type__in=(
                "view_quiz",
                "view_question",
                "click_option",
                "abandon",
                "checkout_exit",
            ),
        )
        .order_by("occurred_at", "id")
        .values(
            "session_id",
            "version_key",
            "event_type",
            "element_id",
            "metadata",
            "occurred_at",
        )
    )
    todas = {}
    for evento in eventos:
        if evento["event_type"] != "view_quiz" or evento["session_id"] in todas:
            continue
        metadata = evento["metadata"] if isinstance(evento["metadata"], dict) else {}
        utm = metadata.get("utm") if isinstance(metadata.get("utm"), dict) else {}
        contexto = (
            metadata.get("context") if isinstance(metadata.get("context"), dict) else {}
        )
        todas[evento["session_id"]] = {
            "id": evento["session_id"],
            "dia": _dia(evento["occurred_at"]),
            "versao": evento["version_key"],
            "utm": {campo: str(utm.get(campo) or "") for campo in UTM_CAMPOS},
            "contexto": {
                campo: str(contexto.get(campo) or "") for campo in CONTEXTO_CAMPOS
            },
            "teste": eh_teste(contexto, utm),
            "viu": set(),
            "clicou": set(),
            "abandonou": set(),
            "concluiu": False,
            "saida": False,
            "saida_real": False,
        }
    for evento in eventos:
        sessao = todas.get(evento["session_id"])
        if sessao is None or evento["version_key"] != sessao["versao"]:
            continue
        tipo = evento["event_type"]
        metadata = evento["metadata"] if isinstance(evento["metadata"], dict) else {}
        if tipo == "view_question":
            sessao["viu"].add(evento["element_id"])
        elif tipo == "click_option":
            sessao["clicou"].add(str(metadata.get("question_id") or ""))
        elif tipo == "abandon":
            sessao["abandonou"].add(evento["element_id"] or ETAPA_LEAD)
        elif tipo == "checkout_exit":
            sessao["saida"] = True
            if not _demonstracao(metadata):
                sessao["saida_real"] = True

    sem_visita = {"reais": 0, "teste": 0}
    sem_correspondencia = 0
    for submissao in (
        Submission.objects.filter(quiz=quiz, site_id=quiz.site_id)
        .select_related("version")
        .only("id", "session_id", "created_at", "utm", "context", "version__key")
    ):
        sessao = todas.get(submissao.session_id) if submissao.session_id else None
        if sessao is not None and sessao["versao"] == submissao.version.key:
            sessao["concluiu"] = True
        elif no_periodo(_dia(submissao.created_at)):
            if sessao is not None:
                sem_correspondencia += 1
            elif eh_teste(submissao.context, submissao.utm):
                sem_visita["teste"] += 1
            else:
                sem_visita["reais"] += 1
    sessoes = [s for s in todas.values() if no_periodo(s["dia"])]
    return {
        "sessoes": sessoes,
        "conclusoes_sem_visita": sem_visita["reais"],
        "conclusoes_sem_visita_teste": sem_visita["teste"],
        "conclusoes_versao_diferente": sem_correspondencia,
        "inicio": inicio,
        "fim": fim,
    }


def etapas_das_versoes(quiz):
    """{versao: (ativa, [(id da etapa, rótulo)])}; a etapa de cadastro vai por último."""
    resultado = {}
    for versao in quiz.versions.order_by("key").prefetch_related("questions"):
        etapas = [
            (str(pergunta.id), f"Pergunta {posicao}: {pergunta.text}"[:120])
            for posicao, pergunta in enumerate(versao.questions.all(), start=1)
        ]
        etapas.append((ETAPA_LEAD, "Cadastro e envio"))
        resultado[versao.key] = (versao.active, etapas)
    return resultado


def funil_de_versao(versao, sessoes, etapas_conhecidas):
    reais = [s for s in sessoes if not s["teste"]]
    testes = [s for s in sessoes if s["teste"]]
    etapas = [e for e in etapas_conhecidas if e[0] != ETAPA_LEAD]
    conhecidas = {e[0] for e in etapas}
    desconhecidas = sorted(
        {
            etapa
            for s in reais
            for etapa in (s["viu"] | s["clicou"] | s["abandonou"])
            if etapa and etapa not in conhecidas and etapa != ETAPA_LEAD
        }
    )
    etapas += [(e, f"Etapa fora da versão atual ({e})") for e in desconhecidas]
    etapas.append((ETAPA_LEAD, "Cadastro e envio"))
    indice = {etapa: i for i, (etapa, _) in enumerate(etapas)}

    ate = {}
    for s in reais:
        ate[s["id"]] = max(
            (indice[e] for e in (s["viu"] | s["clicou"] | s["abandonou"]) if e in indice),
            default=-1,
        )
    visitas = len(reais)
    conclusoes = sum(1 for s in reais if s["concluiu"])
    linhas = []
    ultima_pergunta = len(etapas) - 2
    for i, (etapa, rotulo) in enumerate(etapas):
        e_lead = etapa == ETAPA_LEAD
        viram = None if e_lead else sum(1 for s in reais if etapa in s["viu"])
        clicaram = None if e_lead else sum(1 for s in reais if etapa in s["clicou"])
        abandonaram = sum(
            1
            for s in reais
            if not s["concluiu"] and ate[s["id"]] == i and etapa in s["abandonou"]
        )
        if e_lead:
            avancaram = None
        elif i < ultima_pergunta:
            avancaram = sum(1 for s in reais if etapas[i + 1][0] in s["viu"])
        else:
            avancaram = conclusoes
        perda = None if avancaram is None else max(0, viram - avancaram)
        linhas.append(
            {
                "etapa": etapa,
                "ordem": i + 1,
                "rotulo": rotulo,
                "medida": not e_lead,
                "viram": viram,
                "clicaram": clicaram,
                "abandonaram": abandonaram,
                "avancaram": avancaram,
                "perda": perda,
                "taxa_clique": None if e_lead else taxa(clicaram, viram),
                "taxa_abandono": None if e_lead else taxa(abandonaram, viram),
                "taxa_perda": None if perda is None else taxa(perda, viram),
            }
        )
    saidas = sum(1 for s in reais if s["concluiu"] and s["saida"])
    demonstracoes = sum(
        1 for s in reais if s["concluiu"] and s["saida"] and not s["saida_real"]
    )
    saidas_reais = saidas - demonstracoes
    return {
        "version_key": versao,
        "visitas_elegiveis": visitas,
        "conclusoes": conclusoes,
        "saidas": saidas,
        "saidas_reais": saidas_reais,
        "saidas_demonstracao": demonstracoes,
        "conclusoes_sem_saida": conclusoes - saidas,
        "saidas_sem_conclusao": sum(
            1 for s in reais if s["saida"] and not s["concluiu"]
        ),
        "taxa_conclusao": taxa(conclusoes, visitas),
        "taxa_saida_real": taxa(saidas_reais, conclusoes),
        "taxa_saida_demonstracao": taxa(demonstracoes, conclusoes),
        "taxa_saida_total": taxa(saidas, conclusoes),
        "etapas": linhas,
        "teste": {
            "visitas": len(testes),
            "conclusoes": sum(1 for s in testes if s["concluiu"]),
        },
        "comercial": {
            "compras": None,
            "receita": None,
            "ltv": None,
            "estado": SEM_COMPRA,
        },
    }


def funis_por_versao(quiz, sessoes, conhecidas=None):
    conhecidas = etapas_das_versoes(quiz) if conhecidas is None else conhecidas
    versoes = sorted(set(conhecidas) | {s["versao"] for s in sessoes})
    funis = []
    for versao in versoes:
        ativa, etapas = conhecidas.get(
            versao, (False, [(ETAPA_LEAD, "Cadastro e envio")])
        )
        funil = funil_de_versao(
            versao, [s for s in sessoes if s["versao"] == versao], etapas
        )
        funil["ativa"] = ativa
        funil["cadastrada"] = versao in conhecidas
        funis.append(funil)
    return funis


def funil_por_etapa(quiz, inicio=None, fim=None, coleta=None, comercial=True):
    coleta = coletar_sessoes(quiz, inicio, fim) if coleta is None else coleta
    sessoes = coleta["sessoes"]
    return {
        "periodo": {
            "inicio": coleta["inicio"].isoformat() if coleta["inicio"] else None,
            "fim": coleta["fim"].isoformat() if coleta["fim"] else None,
            "fuso": FUSO.key,
        },
        "denominador": "sessões distintas com abertura do quiz registrada, sem tráfego de teste",
        "amostra_minima": AMOSTRA_MINIMA,
        "regras": list(REGRAS_DO_FUNIL),
        "visitas_elegiveis": sum(1 for s in sessoes if not s["teste"]),
        "teste": {
            "visitas": sum(1 for s in sessoes if s["teste"]),
            "conclusoes": sum(1 for s in sessoes if s["teste"] and s["concluiu"]),
            "conclusoes_sem_visita": coleta["conclusoes_sem_visita_teste"],
        },
        "conclusoes_sem_visita": coleta["conclusoes_sem_visita"],
        "conclusoes_versao_diferente": coleta["conclusoes_versao_diferente"],
        "aviso_comparacao": (
            "Campanhas são direcionadas, não aleatórias: comparar versões mostra o que "
            "aconteceu em cada link, mas não prova que uma versão causa o resultado."
        ),
        "versoes": [
            funil if comercial else {k: v for k, v in funil.items() if k != "comercial"}
            for funil in funis_por_versao(quiz, sessoes)
        ],
    }
