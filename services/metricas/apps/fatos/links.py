"""Os links rastreados de WhatsApp: projeção e consulta (`/api/metricas/links`).

- `projetar_link(evento)` abre em colunas `link.enviado` e `link.acessado`
  (contrato da `mensageria`). Idempotente por `event_id`. `link.acessado`
  pode chegar antes de `link.enviado` (relays independentes): nenhum dos dois
  exige o outro; o elo é o `link_id`, resolvido só na consulta.
- `contar(...)` agrupa os links ENVIADOS da janela e diz quantos tiveram ao
  menos um acesso "provavel" (pessoa), quantos passaram `horas` sem nenhum, e
  quantos acessos "automatico" (prévia/robô) houve. Acesso automático nunca
  conta como visita: é o WhatsApp lendo o link para montar a prévia.

A janela é por `enviado_em`, em dias de São Paulo (como as demais consultas):
`de` 00:00 até o fim de `ate`. "Sem acesso após N horas" compara instantes UTC
com `agora`, nunca dias.
"""

from __future__ import annotations

import datetime as dt
import logging
import uuid
from collections import defaultdict

from django.db import IntegrityError, transaction

from .crm import AMOSTRA_MINIMA, _instante, _inteiro, _janela, _texto
from .models import Evento, FatoLinkAcesso, FatoLinkEnviado

logger = logging.getLogger(__name__)

LINK_ENVIADO = "link.enviado"
LINK_ACESSADO = "link.acessado"

AGRUPAMENTOS = ("destino", "mensagem", "campanha", "variacao")

SEM_CHAVE = "(sem)"


def _uuid(valor: object) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(valor))
    except (ValueError, TypeError, AttributeError):
        return None


def _versao(valor: object) -> int | None:
    """Número da versão; fora do que cabe em IntegerField vira None (não derruba o consumidor)."""
    numero = _inteiro(valor)
    return numero if numero is not None and 0 <= numero <= 2_147_483_647 else None


def _id_ou_vazio(valor: object) -> str:
    """Id opaco (string) do payload; `null` e ausente viram vazio."""
    return _texto(valor, 60) if valor else ""


def _enviado(evento: Evento) -> FatoLinkEnviado | None:
    d = evento.dados
    link_id = _uuid(d.get("link_id"))
    if link_id is None:
        return None
    return FatoLinkEnviado(
        event_id=evento.event_id,
        site_id=evento.site_id,
        link_id=link_id,
        token=_texto(d.get("token"), 10),
        destino_id=_id_ou_vazio(d.get("destino_id")),
        destino_nome=_texto(d.get("destino_nome"), 200),
        versao=_versao(d.get("versao")),
        origem=_texto(d.get("origem"), 20),
        campanha=_texto(d.get("campanha"), 100),
        mensagem_id=_id_ou_vazio(d.get("mensagem_id")),
        passo_id=_id_ou_vazio(d.get("passo_id")),
        enviado_em=_instante(d.get("enviado_em"), evento.ocorrido_em) or evento.ocorrido_em,
    )


def _acesso(evento: Evento) -> FatoLinkAcesso | None:
    d = evento.dados
    link_id = _uuid(d.get("link_id"))
    if link_id is None:
        return None
    return FatoLinkAcesso(
        event_id=evento.event_id,
        site_id=evento.site_id,
        link_id=link_id,
        destino_id=_id_ou_vazio(d.get("destino_id")),
        versao=_versao(d.get("versao")),
        origem=_texto(d.get("origem"), 20),
        campanha=_texto(d.get("campanha"), 100),
        mensagem_id=_id_ou_vazio(d.get("mensagem_id")),
        passo_id=_id_ou_vazio(d.get("passo_id")),
        classificacao=_texto(d.get("classificacao"), 16),
        metodo=_texto(d.get("metodo"), 8),
        ocorrido_em=_instante(d.get("ocorrido_em"), evento.ocorrido_em) or evento.ocorrido_em,
    )


def projetar_link(evento: Evento | None) -> None:
    """Grava a projeção de `link.enviado` ou `link.acessado`; outro assunto é ignorado.

    Roda também na reentrega (`JA_TINHA`); a unicidade de `event_id` (e de
    `link_id` no enviado) impede a duplicata.
    """
    if evento is None or not isinstance(evento.dados, dict):
        return
    if evento.tipo == LINK_ENVIADO:
        fato = _enviado(evento)
    elif evento.tipo == LINK_ACESSADO:
        fato = _acesso(evento)
    else:
        return
    if fato is None:
        logger.error(
            "%s sem link_id válido: guardado no livro, mas fora da projeção (event_id=%s)",
            evento.tipo,
            evento.event_id,
        )
        return
    try:
        with transaction.atomic():
            fato.save()
    except IntegrityError:
        return  # reentrega: já projetado


def _chave(fato: FatoLinkEnviado, agrupar: str) -> tuple[str, str]:
    """(chave, rótulo) do grupo a que o link enviado pertence."""
    if agrupar == "destino":
        return (fato.destino_id or SEM_CHAVE, fato.destino_nome or SEM_CHAVE)
    if agrupar == "campanha":
        return (fato.campanha or SEM_CHAVE, fato.campanha or "(sem campanha)")
    if agrupar == "variacao":
        if fato.versao is None:
            return (SEM_CHAVE, SEM_CHAVE)
        return (str(fato.versao), f"versão {fato.versao}")
    # mensagem: a da conversa, ou o passo da jornada
    if fato.mensagem_id:
        return (fato.mensagem_id, f"mensagem {fato.mensagem_id}")
    if fato.passo_id:
        return (fato.passo_id, f"passo {fato.passo_id}")
    return (SEM_CHAVE, SEM_CHAVE)


def contar(
    site_id: str,
    de: dt.date,
    ate: dt.date,
    *,
    agrupar: str = "destino",
    horas: int = 24,
    agora: dt.datetime | None = None,
) -> dict:
    """Links enviados na janela, por grupo, com o que se acessou deles."""
    if agrupar not in AGRUPAMENTOS:
        raise ValueError(f"agrupar deve ser um de {AGRUPAMENTOS}")
    agora = agora or dt.datetime.now(dt.timezone.utc)
    limite = agora - dt.timedelta(hours=horas)
    inicio, fim = _janela(de, ate)
    enviados = list(
        FatoLinkEnviado.objects.filter(
            site_id=site_id, enviado_em__gte=inicio, enviado_em__lt=fim
        )
    )
    ids_da_janela = FatoLinkEnviado.objects.filter(
        site_id=site_id, enviado_em__gte=inicio, enviado_em__lt=fim
    ).values("link_id")
    por_link: dict[uuid.UUID, dict] = defaultdict(lambda: {"provavel": 0, "automatico": 0})
    for link_id, classificacao in FatoLinkAcesso.objects.filter(
        site_id=site_id, link_id__in=ids_da_janela
    ).values_list("link_id", "classificacao"):
        if classificacao in ("provavel", "automatico"):
            por_link[link_id][classificacao] += 1

    grupos: dict[str, dict] = {}
    for fato in enviados:
        chave, rotulo = _chave(fato, agrupar)
        g = grupos.setdefault(
            chave,
            {
                "chave": chave,
                "rotulo": rotulo,
                "enviados": 0,
                "com_acesso_provavel": 0,
                "sem_acesso_apos_horas": 0,
                "acessos_automaticos": 0,
            },
        )
        acessos = por_link.get(fato.link_id, {"provavel": 0, "automatico": 0})
        g["enviados"] += 1
        g["acessos_automaticos"] += acessos["automatico"]
        if acessos["provavel"]:
            g["com_acesso_provavel"] += 1
        elif fato.enviado_em < limite:
            g["sem_acesso_apos_horas"] += 1
    saida = sorted(grupos.values(), key=lambda g: (-g["enviados"], g["chave"]))
    for g in saida:
        g["amostra_insuficiente"] = g["enviados"] < AMOSTRA_MINIMA
    return {"base": "enviados", "horas": horas, "agrupar": agrupar, "grupos": saida}
