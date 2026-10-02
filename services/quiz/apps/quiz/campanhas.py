"""Contagens de campanha pela chegada da sessão ao quiz."""

from collections import defaultdict
from datetime import date
import re
from zoneinfo import ZoneInfo

from apps.quiz.models import Submission, TelemetryEvent


FUSO = ZoneInfo("America/Sao_Paulo")
UTM_CAMPOS = ("source", "medium", "campaign", "content")
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


def _linha(chave, visitas, submissoes, saidas):
    (
        dia,
        source,
        medium,
        campaign,
        content,
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
        "version_key": version_key,
        "fmt": fmt,
        "seg": seg,
        "src": src,
        "med": med,
        "cpg": cpg,
        "ctv": ctv,
        "visitas": visitas,
        "submissoes": submissoes,
        "saidas": saidas,
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
            "version_key": chave[4],
            "fmt": chave[5],
            "seg": chave[6],
            "src": chave[7],
            "med": chave[8],
            "cpg": chave[9],
            "ctv": chave[10],
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
        lambda: {"visitas": set(), "submissoes": set(), "saidas": set()}
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
        if chave is not None and chave[5] == submissao.version.key:
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

    for evento in base.filter(event_type="checkout_exit").values(
        "session_id", "version_key"
    ):
        chave = primeiras.get(evento["session_id"])
        if (
            chave is not None
            and evento["session_id"] in conclusoes_da_coorte
            and chave[5] == evento["version_key"]
            and no_periodo(chave[0])
        ):
            grupos[chave]["saidas"].add(evento["session_id"])

    linhas = [
        _linha(
            chave,
            len(valores["visitas"]),
            len(valores["submissoes"]),
            len(valores["saidas"]),
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
        "campanhas": linhas,
        "sem_visita_registrada": avulsas,
        "submissoes_sem_correspondencia": _linhas_sem_denominador(
            sem_correspondencia,
            "Visita da sessão registrada em outra versão; filtro de data aplicado à submissão.",
        ),
    }
