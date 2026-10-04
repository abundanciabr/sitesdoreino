"""O funil comercial: a leitura que a `metricas` faz do CRM com agentes.

Etapa 6 do plano (`PLANO-CRM-COM-AGENTES-20261003.md`, "Como medir resultado e
custo"), preparada pela seção 12 da especificação do lote 1. Dois fatos
projetados do livro e UMA conta sobre eles:

- `projetar(evento)` — abre em colunas `crm.oportunidade-atualizada` (E3) e
  `mensagem.recebida` (E2, o nome que a `mensageria` publica de fato em
  `apps/conversas/entrada.py`). Idempotente por `event_id`: a mesma
  reentrega grava uma vez, como no `Evento`.
- `funil(site_id, desde, ate)` — por `estrategia_versao` e por `atendente`:
  abertas (motivo `quiz`), com resposta (mensagem recebida do mesmo lead, ou
  do mesmo telefone quando o E2 o trouxer, depois da abertura), com link
  enviado, com pedido, ganhas
  (`pagamento_aprovado`), receita em centavos (UMA vez por `payment_id`,
  menos os estornos que trazem valor) e perdidas. Grupo com menos de
  `AMOSTRA_MINIMA` oportunidades abertas vem com `amostra_insuficiente=True`:
  o número existe, mas não sustenta decisão (seção "Efeito incremental").

A oportunidade pertence ao grupo do ÚLTIMO valor conhecido de estratégia e de
atendente na janela: quem começou com o robô e passou para uma pessoa conta
como "pessoa", porque foi com a pessoa que a venda fechou ou não.
"""

from __future__ import annotations

import datetime as dt
import logging
from collections import defaultdict

from django.db import IntegrityError, transaction

from .models import FUSO, Evento, FatoMensagemRecebida, FatoOportunidade

logger = logging.getLogger(__name__)

OPORTUNIDADE = "crm.oportunidade-atualizada"
MENSAGEM_RECEBIDA = "mensagem.recebida"

#: Abaixo disto, o grupo é pequeno demais para comparar estratégias.
AMOSTRA_MINIMA = 30

MOTIVOS_COM_PAYMENT_ID = frozenset({"pagamento_aprovado", "estorno"})


def _texto(valor: object, maximo: int) -> str:
    return valor[:maximo] if isinstance(valor, str) else ""


def _inteiro(valor: object) -> int | None:
    if isinstance(valor, bool) or not isinstance(valor, int):
        return None
    return valor


def _instante(valor: object, padrao: dt.datetime) -> dt.datetime | None:
    """`valor` como data e hora com fuso; `padrao` quando é só verdadeiro; None quando falso."""
    if not valor:
        return None
    if isinstance(valor, str):
        try:
            lido = dt.datetime.fromisoformat(valor)
        except ValueError:
            return padrao
        return lido if lido.tzinfo else padrao
    return padrao


def _projetar_oportunidade(evento: Evento) -> FatoOportunidade | None:
    d = evento.dados
    motivo = _texto(d.get("motivo"), 30)
    payment_id = (
        _texto(d.get("payment_id"), 120)
        or (_texto(d.get("referencia"), 120) if motivo in MOTIVOS_COM_PAYMENT_ID else "")
    )
    link = d.get("link_enviado_em") or d.get("link_url")
    return FatoOportunidade(
        event_id=evento.event_id,
        site_id=evento.site_id,
        oportunidade_id=_texto(d.get("oportunidade_id"), 60),
        lead_id=_texto(d.get("lead_id"), 60),
        etapa=_texto(d.get("etapa"), 30),
        motivo=motivo,
        atendente=_texto(d.get("atendente"), 20),
        estrategia_versao=_inteiro(d.get("estrategia_versao")),
        oferta_slug=_texto(d.get("oferta_slug"), 120),
        order_id=_texto(d.get("order_id"), 120),
        payment_id=payment_id,
        valor_centavos=_inteiro(d.get("valor_centavos")),
        telefone=_texto(d.get("telefone"), 30),
        link_enviado_em=_instante(link, evento.ocorrido_em),
        ocorrido_em=evento.ocorrido_em,
    )


def _tipo_da_mensagem(d: dict) -> str:
    """`tipo` quando o payload o traz; senão o tipo da mídia, ou `texto`."""
    tipo = _texto(d.get("tipo"), 20)
    if tipo:
        return tipo
    midia = d.get("midia")
    if isinstance(midia, dict) and _texto(midia.get("tipo"), 20):
        return _texto(midia.get("tipo"), 20)
    return "texto"


def _projetar_mensagem(evento: Evento) -> FatoMensagemRecebida:
    d = evento.dados
    recebida_em = _instante(d.get("recebida_em"), evento.ocorrido_em) or evento.ocorrido_em
    # A `mensageria` manda `lead` (o id do lead, quando a conversa está ligada
    # a um); `lead_id` e `telefone` ficam aceitos para um publicador que os
    # traga com esses nomes.
    return FatoMensagemRecebida(
        event_id=evento.event_id,
        site_id=evento.site_id,
        lead_id=_texto(d.get("lead") or d.get("lead_id"), 60),
        telefone=_texto(d.get("telefone"), 30),
        canal=_texto(d.get("canal"), 20),
        tipo=_tipo_da_mensagem(d),
        descadastro=bool(d.get("descadastro")),
        recebida_em=recebida_em,
    )


def projetar(evento: Evento | None) -> None:
    """Grava a projeção do fato, se o assunto for um dos dois do CRM.

    Roda DEPOIS de o `Evento` estar no livro, inclusive na reentrega
    (`JA_TINHA`): se o processo caiu entre gravar o fato e projetá-lo, a
    próxima entrega completa o que faltou. A unicidade de `event_id` é o que
    impede a duplicata, nunca a comparação de conteúdo.
    """
    if evento is None or not isinstance(evento.dados, dict):
        return
    if evento.tipo == OPORTUNIDADE:
        fato = _projetar_oportunidade(evento)
    elif evento.tipo == MENSAGEM_RECEBIDA:
        fato = _projetar_mensagem(evento)
    else:
        return
    try:
        with transaction.atomic():
            fato.save()
    except IntegrityError:
        return  # reentrega: já projetado


# ---------------------------------------------------------------------------
# O funil
# ---------------------------------------------------------------------------


def _janela(desde: dt.date, ate: dt.date) -> tuple[dt.datetime, dt.datetime]:
    inicio = dt.datetime.combine(desde, dt.time.min, tzinfo=FUSO)
    fim = dt.datetime.combine(ate + dt.timedelta(days=1), dt.time.min, tzinfo=FUSO)
    return inicio, fim


def _contagens_vazias() -> dict:
    return {
        "abertas": 0,
        "com_resposta": 0,
        "com_link_enviado": 0,
        "com_pedido": 0,
        "ganhas": 0,
        "receita_centavos": 0,
        "perdidas": 0,
    }


def funil(site_id: str, desde: dt.date, ate: dt.date) -> dict:
    inicio, fim = _janela(desde, ate)
    fatos = list(
        FatoOportunidade.objects.filter(
            site_id=site_id, ocorrido_em__gte=inicio, ocorrido_em__lt=fim
        ).order_by("ocorrido_em", "id")
    )
    mensagens = list(
        FatoMensagemRecebida.objects.filter(
            site_id=site_id, recebida_em__gte=inicio, recebida_em__lt=fim
        ).values_list("lead_id", "telefone", "recebida_em")
    )
    # A resposta liga-se à oportunidade pelo lead (o que a `mensageria` manda)
    # ou pelo telefone (quando um dos dois lados o traz).
    recebidas_por_lead: dict[str, list[dt.datetime]] = defaultdict(list)
    recebidas_por_telefone: dict[str, list[dt.datetime]] = defaultdict(list)
    for lead_id, telefone, quando in mensagens:
        if lead_id:
            recebidas_por_lead[lead_id].append(quando)
        if telefone:
            recebidas_por_telefone[telefone].append(quando)

    por_oportunidade: dict[str, list[FatoOportunidade]] = defaultdict(list)
    for fato in fatos:
        por_oportunidade[fato.oportunidade_id].append(fato)

    por_estrategia: dict[int | None, dict] = defaultdict(_contagens_vazias)
    por_atendente: dict[str, dict] = defaultdict(_contagens_vazias)
    # Receita UMA vez por payment_id, por grupo: {chave do grupo: {payment_id: valor}}
    aprovados_e: dict = defaultdict(dict)
    estornos_e: dict = defaultdict(dict)
    aprovados_a: dict = defaultdict(dict)
    estornos_a: dict = defaultdict(dict)

    for linhas in por_oportunidade.values():
        estrategia = next(
            (f.estrategia_versao for f in reversed(linhas) if f.estrategia_versao is not None),
            None,
        )
        atendente = next((f.atendente for f in reversed(linhas) if f.atendente), "")
        telefone = next((f.telefone for f in reversed(linhas) if f.telefone), "")
        lead_id = next((f.lead_id for f in reversed(linhas) if f.lead_id), "")
        aberturas = [f.ocorrido_em for f in linhas if f.motivo == "quiz"]
        aberta = bool(aberturas)
        respostas = recebidas_por_lead.get(lead_id, []) if lead_id else []
        if telefone:
            respostas = respostas + recebidas_por_telefone.get(telefone, [])
        com_resposta = False
        if respostas:
            marco = min(aberturas) if aberturas else min(f.ocorrido_em for f in linhas)
            com_resposta = any(q >= marco for q in respostas)
        com_link = any(f.link_enviado_em is not None for f in linhas)
        com_pedido = any(f.motivo == "pedido" for f in linhas)
        ganha = any(f.motivo == "pagamento_aprovado" for f in linhas)
        perdida = any(f.etapa == "perdida" for f in linhas)

        for grupo, chave, aprovados, estornos in (
            (por_estrategia, estrategia, aprovados_e, estornos_e),
            (por_atendente, atendente, aprovados_a, estornos_a),
        ):
            c = grupo[chave]
            c["abertas"] += aberta
            c["com_resposta"] += com_resposta
            c["com_link_enviado"] += com_link
            c["com_pedido"] += com_pedido
            c["ganhas"] += ganha
            c["perdidas"] += perdida
            for f in linhas:
                if not f.payment_id or f.valor_centavos is None:
                    continue
                if f.motivo == "pagamento_aprovado":
                    aprovados[chave].setdefault(f.payment_id, f.valor_centavos)
                elif f.motivo == "estorno":
                    estornos[chave].setdefault(f.payment_id, f.valor_centavos)

    def _fechar(grupo, aprovados, estornos, nome_da_chave):
        saida = []
        for chave, c in grupo.items():
            c["receita_centavos"] = sum(aprovados[chave].values()) - sum(
                estornos[chave].values()
            )
            c["amostra_insuficiente"] = c["abertas"] < AMOSTRA_MINIMA
            saida.append({nome_da_chave: chave, **c})
        saida.sort(key=lambda linha: (linha[nome_da_chave] is None, str(linha[nome_da_chave])))
        return saida

    return {
        "site_id": site_id,
        "desde": desde,
        "ate": ate,
        "amostra_minima": AMOSTRA_MINIMA,
        "oportunidades": len(por_oportunidade),
        "mensagens_recebidas": len(mensagens),
        "por_estrategia": _fechar(por_estrategia, aprovados_e, estornos_e, "estrategia_versao"),
        "por_atendente": _fechar(por_atendente, aprovados_a, estornos_a, "atendente"),
    }
