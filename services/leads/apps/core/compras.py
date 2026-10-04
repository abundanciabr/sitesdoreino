"""A compra fecha só a oportunidade certa, e uma compra é uma receita.

Quem é a oportunidade de um pedido, nesta ordem:

1. `oportunidade_ref` (e `oferta_ref`) vindos do pedido ou do pagamento;
2. a oportunidade já ligada a esse pedido;
3. a oferta ou o produto do pedido, comparados com as compras já ligadas às
   ofertas abertas da pessoa;
4. a única oferta aberta da pessoa, quando ela não é de outro produto e o
   pedido não aponta, por `oportunidade_ref`, para uma oportunidade que não
   existe.

"A pessoa" é sempre a dona do pedido (`compra.lead`), nunca quem mandou o
evento: o e-mail do pagamento pode ser outro, e a compra de uma pessoa não
fecha a oferta de outra.

Fora disso, a compra fica sem oportunidade. Nunca se fecha todas as ofertas
da pessoa por causa de um pagamento.

O estado da compra vem só dos fatos do provedor (pagamentos): aprovação,
recusa, Pix vencido, estorno e contestação. A primeira aprovação de um pedido
é a venda; aprovação repetida, tardia ou fora de ordem não cria outra.
"""

import uuid
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from .models import (
    CompraDaOportunidade,
    Oportunidade,
    PerfilDoLead,
    QuizDoLead,
    RegistroHistoricoOportunidade,
    ReversaoDePagamento,
    TimelineEvent,
)


FONTE_OFERTA = "quiz"
FONTE_RECUPERACAO = "pagamento"
PREFIXO_RECUPERACAO = "recuperar:"
ETAPAS_ANTES_DO_PEDIDO = ("nova", "qualificada", "proposta")
EVENTOS_DE_FALHA = {"pagamento.recusado", "pix.expirado"}
EVENTOS_DA_COMPRA = (
    "pedido.criado", "pagamento.recusado", "pix.expirado", "pagamento.aprovado",
)


# ---------------------------------------------------------------------------
# O que o pedido diz de si
# ---------------------------------------------------------------------------


def _texto(valor) -> str:
    if valor is None:
        return ""
    return str(valor).strip()


def _blocos(data: dict):
    yield data
    for chave in ("metadata", "contexto", "context"):
        bloco = data.get(chave)
        if isinstance(bloco, dict):
            yield bloco


def referencias(data: dict) -> tuple[str, str]:
    """(`oportunidade_ref`, `oferta_ref`) do evento, no topo ou no contexto."""
    oportunidade_ref = oferta_ref = ""
    for bloco in _blocos(data):
        oportunidade_ref = oportunidade_ref or _texto(bloco.get("oportunidade_ref"))
        oferta_ref = oferta_ref or _texto(bloco.get("oferta_ref"))
    return oportunidade_ref[:200], oferta_ref[:200]


def produtos_do_evento(data: dict) -> list[str]:
    vistos = []
    for item in data.get("items") or []:
        if isinstance(item, dict):
            produto = _texto(item.get("product_id"))
            if produto and produto not in vistos:
                vistos.append(produto)
    produto = _texto(data.get("product_id"))
    if produto and produto not in vistos:
        vistos.append(produto)
    return vistos


def _sandbox(data: dict) -> bool:
    return any(
        bloco.get("sandbox") is True
        or _texto(bloco.get("ambiente")).lower() == "sandbox"
        for bloco in _blocos(data)
    )


def _centavos(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def _momento(evento_timeline):
    return evento_timeline.occurred_at if evento_timeline is not None else timezone.now()


# ---------------------------------------------------------------------------
# A linha da compra
# ---------------------------------------------------------------------------


def _travar(site_id: str, pedido: str):
    return CompraDaOportunidade.objects.select_for_update().filter(
        site_id=site_id, pedido_id=pedido
    ).first()


def compra_do_evento(lead, data: dict):
    """A compra (site, pedido) do evento, criada se ainda não existe.

    Acrescenta o que o evento sabe e a linha ainda não sabia; nunca troca uma
    referência já gravada (a primeira que chegou é a do pedido).
    """
    pedido = _texto(data.get("order_id"))
    if not pedido:
        return None
    compra = _travar(lead.site_id, pedido)
    if compra is None:
        try:
            with transaction.atomic():
                CompraDaOportunidade.objects.create(
                    site_id=lead.site_id, pedido_id=pedido, lead=lead
                )
        except IntegrityError:
            pass
        compra = _travar(lead.site_id, pedido)
    mudou = []
    oportunidade_ref, oferta_ref = referencias(data)
    if oportunidade_ref and not compra.oportunidade_ref:
        compra.oportunidade_ref = oportunidade_ref
        mudou.append("oportunidade_ref")
    if oferta_ref and not compra.oferta_ref:
        compra.oferta_ref = oferta_ref
        mudou.append("oferta_ref")
    novos = [p for p in produtos_do_evento(data) if p not in (compra.produtos or [])]
    if novos:
        compra.produtos = list(compra.produtos or []) + novos
        mudou.append("produtos")
    total = _centavos(data.get("total_cents"))
    if total is not None and compra.valor_pedido_centavos is None:
        compra.valor_pedido_centavos = total
        mudou.append("valor_pedido_centavos")
    if _sandbox(data) and not compra.sandbox:
        compra.sandbox = True
        mudou.append("sandbox")
    if mudou:
        compra.save(update_fields=mudou + ["atualizada_em"])
    return compra


def _aprovacao_na_timeline(site_id: str, pedido: str, antes_de=None):
    """A primeira aprovação do pedido; com `antes_de`, só a que veio antes dele.

    A ordem dos fatos é (`occurred_at`, `id`): o relógio pode repetir o mesmo
    instante, e então vale a ordem em que foram gravados.
    """
    consulta = TimelineEvent.objects.filter(
        lead__site_id=site_id, event="pagamento.aprovado", payload__order_id=pedido
    )
    if antes_de is not None:
        consulta = consulta.filter(
            Q(occurred_at__lt=antes_de.occurred_at)
            | Q(occurred_at=antes_de.occurred_at, id__lt=antes_de.id)
        )
    return consulta.order_by("occurred_at", "id").first()


def _marcar_aprovada(compra, *, momento, valor, evidencia) -> None:
    compra.aprovado_em = momento
    compra.valor_aprovado_centavos = (
        valor if valor is not None else compra.valor_pedido_centavos
    )
    compra.aprovacao_evidencia = _texto(evidencia)[:200]
    compra.save(update_fields=[
        "aprovado_em", "valor_aprovado_centavos", "aprovacao_evidencia",
        "atualizada_em",
    ])


def _hidratar_aprovacao(compra, antes_de=None) -> None:
    """Aprovação gravada antes desta linha existir (base antiga) também conta."""
    if compra.aprovado_em is not None:
        return
    aprovado = _aprovacao_na_timeline(compra.site_id, compra.pedido_id, antes_de)
    if aprovado is None:
        return
    _marcar_aprovada(
        compra, momento=aprovado.occurred_at,
        valor=_centavos((aprovado.payload or {}).get("amount_cents")),
        evidencia=aprovado.event_id or aprovado.id,
    )


# ---------------------------------------------------------------------------
# Qual oportunidade é a desta compra
# ---------------------------------------------------------------------------


def _por_referencia(compra, lead):
    referencia = compra.oportunidade_ref
    if not referencia:
        return None
    try:
        identificador = uuid.UUID(referencia)
    except (ValueError, TypeError, AttributeError):
        return Oportunidade.objects.select_for_update().filter(
            lead=lead, fonte_referencia_id=referencia
        ).first()
    # A referência pode chegar com outro e-mail no checkout: vale dentro do
    # mesmo site, nunca de um site para outro.
    return Oportunidade.objects.select_for_update().filter(
        pk=identificador, lead__site_id=compra.site_id
    ).first()


def _ofertas_conhecidas(oportunidade, *, exceto=None) -> set:
    conhecidas = set()
    compras = CompraDaOportunidade.objects.filter(oportunidade=oportunidade)
    if exceto is not None:
        compras = compras.exclude(pk=exceto.pk)
    for oferta_ref, produtos in compras.values_list("oferta_ref", "produtos"):
        if oferta_ref:
            conhecidas.add(oferta_ref)
        conhecidas.update(p for p in (produtos or []) if p)
    referencia = oportunidade.fonte_referencia_id or ""
    if oportunidade.fonte_tipo == FONTE_OFERTA and referencia.startswith("oferta:"):
        # O quiz pode dizer qual oferta indica (oferta_ref no evento ou no contexto).
        for payload in TimelineEvent.objects.filter(
            lead_id=oportunidade.lead_id, event="quiz.completado",
            payload__quiz_slug=referencia[len("oferta:"):],
        ).values_list("payload", flat=True):
            _, oferta_ref = referencias(payload or {})
            if oferta_ref:
                conhecidas.add(oferta_ref)
    return conhecidas


def _quiz_respondido_em(oportunidade):
    """Quando a pessoa respondeu o quiz desta oferta (None se não se sabe)."""
    referencia = oportunidade.fonte_referencia_id or ""
    if oportunidade.fonte_tipo != FONTE_OFERTA or not referencia.startswith("oferta:"):
        return None
    primeiro = TimelineEvent.objects.filter(
        lead_id=oportunidade.lead_id, event="quiz.completado",
        payload__quiz_slug=referencia[len("oferta:"):],
    ).order_by("occurred_at", "id").first()
    return primeiro.occurred_at if primeiro is not None else None


def _chave(valor) -> str:
    return _texto(valor).lower()


def _chaves(valores) -> set:
    return {c for c in (_chave(v) for v in valores) if c}


def _slug_do_quiz(oportunidade) -> str:
    referencia = oportunidade.fonte_referencia_id or ""
    if oportunidade.fonte_tipo != FONTE_OFERTA or not referencia.startswith("oferta:"):
        return ""
    return referencia[len("oferta:"):]


def _sinais_da_oferta(oportunidade, conhecidas: set) -> set:
    """O que liga a oferta a um produto: o que ela já conhece e o resultado do quiz.

    O resultado do quiz (`QuizDoLead.resultado` e o `result_key` do evento) é
    um sinal mais fraco que uma referência de oferta: só compara por igualdade
    com o produto ou a oferta do pedido.
    """
    sinais = _chaves(conhecidas)
    slug = _slug_do_quiz(oportunidade)
    if not slug:
        return sinais
    sinais |= _chaves(
        QuizDoLead.objects.filter(
            lead_id=oportunidade.lead_id, quiz_slug=slug
        ).values_list("resultado", flat=True)
    )
    for payload in TimelineEvent.objects.filter(
        lead_id=oportunidade.lead_id, event="quiz.completado",
        payload__quiz_slug=slug,
    ).values_list("payload", flat=True):
        sinais |= _chaves([(payload or {}).get("result_key")])
    return sinais


def _oferta_indicada_do_perfil(lead_id) -> set:
    """Produto ou oferta que o perfil vigente da pessoa indica (vale para a pessoa
    toda, não para uma oferta só)."""
    perfil = PerfilDoLead.objects.filter(lead_id=lead_id).order_by("-versao").first()
    indicada = perfil.oferta_indicada if perfil is not None else None
    if isinstance(indicada, str):
        return _chaves([indicada])
    if not isinstance(indicada, dict):
        return set()
    return _chaves(
        indicada.get(campo)
        for campo in ("oferta_ref", "product_id", "produto_id")
    )


def _produtos_das_outras(lead, excecao, compra) -> set:
    """Produtos já conhecidos de todas as outras oportunidades da pessoa.

    Inclui as já fechadas (uma recompra de produto ganho não é a oferta que
    ainda está aberta). Recuperação ainda aberta é tentativa que falhou, não
    compra, e não conta.
    """
    outras = Oportunidade.objects.filter(lead=lead)
    if excecao is not None:
        outras = outras.exclude(pk=excecao.pk)
    produtos = set()
    for outra in outras:
        if outra.fonte_tipo == FONTE_RECUPERACAO and not outra.encerrada:
            continue
        conhecidas = _ofertas_conhecidas(outra, exceto=compra)
        produtos |= _sinais_da_oferta(outra, conhecidas)
    return produtos


def resolver_oportunidade(compra, lead, momento=None):
    """A oportunidade desta compra, ou None quando não dá para saber qual é.

    `momento` é quando o fato aconteceu; sem referência explícita, uma oferta
    de quiz respondido depois da compra não é a desta compra. `lead` fica na
    assinatura por compatibilidade: vale sempre a dona da compra.

    Sem referência, casa por produto: o produto ou a oferta do pedido contra o
    que cada oferta aberta conhece (compras já ligadas, oferta indicada pelo
    quiz e resultado do quiz). A única oferta aberta só vale se o pedido tem
    produto ou oferta e esse produto não é de outra oportunidade da pessoa,
    aberta ou já fechada. Pedido sem produto nem oferta não casa sozinho.
    """
    lead = compra.lead
    achada = _por_referencia(compra, lead)
    if achada is not None:
        return achada
    if compra.oportunidade_id:
        return Oportunidade.objects.select_for_update().get(pk=compra.oportunidade_id)
    abertas = list(
        Oportunidade.objects.select_for_update()
        .filter(lead=lead, fonte_tipo=FONTE_OFERTA, desfecho_encerrada_em__isnull=True)
        .order_by("-atualizada_em", "-id")
    )
    if momento is not None:
        abertas = [
            o for o in abertas
            if (_quiz_respondido_em(o) or momento) <= momento
        ]
    da_compra = _chaves({compra.oferta_ref} | set(compra.produtos or []))
    conhecidas = {o.pk: _ofertas_conhecidas(o, exceto=compra) for o in abertas}
    if da_compra:
        casadas = [
            o for o in abertas
            if _sinais_da_oferta(o, conhecidas[o.pk]) & da_compra
        ]
        if casadas:
            # Mais de uma casa: vale a que conhece a oferta exata da compra, depois
            # a de atividade mais recente, depois o id (não depende da ordem de criação).
            oferta = _chave(compra.oferta_ref)
            # O id é UUID: no empate, o maior (em texto) ganha, sempre o mesmo.
            casadas.sort(key=lambda o: str(o.pk), reverse=True)
            return min(casadas, key=lambda o: (
                0 if oferta and oferta in _chaves(conhecidas[o.pk]) else 1,
                -o.atualizada_em.timestamp(),
            ))
    if len(abertas) == 1 and not compra.oportunidade_ref:
        unica = abertas[0]
        if not da_compra:
            # Pedido sem produto nem oferta: não há com o que conferir, e a única
            # oportunidade aberta pode ser de outro produto. Fica sem oportunidade.
            return None
        if da_compra & _produtos_das_outras(lead, unica, compra):
            return None
        if not conhecidas[unica.pk] or da_compra & _oferta_indicada_do_perfil(lead.pk):
            return unica
    return None


def _desfazer_fechamento_errado(compra, anterior) -> None:
    """A compra passou para outra oportunidade: a que ela fechou antes reabre.

    Só desfaz o que esta mesma compra causou (mesma evidência) e só se nenhuma
    outra compra aprovada da pessoa sustenta esse fechamento. A recuperação do
    pedido continua sendo da compra, então não reabre.
    """
    if anterior.fonte_tipo == FONTE_RECUPERACAO or not anterior.encerrada:
        return
    if anterior.desfecho_motivo not in ("Pagamento aprovado", "Pagamento revertido"):
        return
    if anterior.desfecho_evidencia != _texto(compra.aprovacao_evidencia or compra.pedido_id):
        return
    outras = CompraDaOportunidade.objects.filter(oportunidade=anterior).exclude(
        pk=compra.pk
    )
    if outras.filter(aprovado_em__isnull=False).exists():
        return
    anterior.etapa = "negociacao" if outras.exists() else "nova"
    anterior.desfecho_resultado = ""
    anterior.desfecho_motivo = ""
    anterior.desfecho_evidencia = ""
    anterior.desfecho_encerrada_em = None
    anterior.save(update_fields=[
        "etapa", "desfecho_resultado", "desfecho_motivo", "desfecho_evidencia",
        "desfecho_encerrada_em", "atualizada_em",
    ])
    _registrar(
        anterior, "etapa_alterada",
        f"Reaberta: o pedido {compra.pedido_id} é de outra oportunidade.",
        compra.pedido_id,
    )


def _vincular(compra, oportunidade) -> bool:
    if oportunidade is None or compra.oportunidade_id == oportunidade.pk:
        return False
    if compra.oportunidade_id is not None:
        anterior = Oportunidade.objects.select_for_update().get(
            pk=compra.oportunidade_id
        )
        _desfazer_fechamento_errado(compra, anterior)
    compra.oportunidade = oportunidade
    compra.save(update_fields=["oportunidade", "atualizada_em"])
    return True


def _recuperacao_do_pedido(compra):
    return Oportunidade.objects.select_for_update().filter(
        lead__site_id=compra.site_id, fonte_tipo=FONTE_RECUPERACAO,
        fonte_referencia_id=f"{PREFIXO_RECUPERACAO}{compra.pedido_id}",
    ).first()


def oportunidades_da_compra(compra) -> list:
    """A oportunidade da compra e a recuperação do mesmo pedido: uma receita só."""
    alvos = []
    if compra.oportunidade_id:
        alvos.append(
            Oportunidade.objects.select_for_update().get(pk=compra.oportunidade_id)
        )
    recuperacao = _recuperacao_do_pedido(compra)
    if recuperacao is not None and all(o.pk != recuperacao.pk for o in alvos):
        alvos.append(recuperacao)
    return alvos


# ---------------------------------------------------------------------------
# O que cada fato faz na oportunidade
# ---------------------------------------------------------------------------


def _registrar(oportunidade, tipo, descricao, evidencia=""):
    RegistroHistoricoOportunidade.objects.create(
        oportunidade=oportunidade, autor_id="sistema", tipo=tipo,
        descricao=descricao, evidencia=_texto(evidencia),
    )


def _ganhar(oportunidade, evidencia, descricao) -> bool:
    if oportunidade.etapa == "ganha" and oportunidade.encerrada:
        return False
    oportunidade.etapa = "ganha"
    oportunidade.desfecho_resultado = "ganha"
    oportunidade.desfecho_motivo = "Pagamento aprovado"
    oportunidade.desfecho_evidencia = _texto(evidencia)
    oportunidade.desfecho_encerrada_em = timezone.now()
    oportunidade.save(update_fields=[
        "etapa", "desfecho_resultado", "desfecho_motivo",
        "desfecho_evidencia", "desfecho_encerrada_em", "atualizada_em",
    ])
    _registrar(oportunidade, "encerramento", descricao, evidencia)
    return True


def _desqualificar_por_reversao(oportunidade, evidencia) -> bool:
    if (
        oportunidade.etapa == "desqualificada" and oportunidade.encerrada
        and oportunidade.desfecho_motivo == "Pagamento revertido"
    ):
        return False
    oportunidade.etapa = "desqualificada"
    oportunidade.desfecho_resultado = "desqualificada"
    oportunidade.desfecho_motivo = "Pagamento revertido"
    oportunidade.desfecho_evidencia = _texto(evidencia)
    oportunidade.desfecho_encerrada_em = timezone.now()
    oportunidade.save(update_fields=[
        "etapa", "desfecho_resultado", "desfecho_motivo",
        "desfecho_evidencia", "desfecho_encerrada_em", "atualizada_em",
    ])
    _registrar(
        oportunidade, "encerramento",
        "Pagamento revertido; compra retirada das vendas.", evidencia,
    )
    return True


def _descricao_do_ganho(oportunidade, compra) -> str:
    if oportunidade.fonte_tipo == FONTE_RECUPERACAO:
        return "Compra recuperada: pagamento aprovado."
    return f"Venda feita: pagamento aprovado do pedido {compra.pedido_id}."


def ganhar_compra(compra) -> None:
    """Fecha como ganha só as oportunidades desta compra."""
    if compra.aprovado_em is None or compra.revertida_em is not None:
        return
    evidencia = compra.aprovacao_evidencia or compra.pedido_id
    for oportunidade in oportunidades_da_compra(compra):
        _ganhar(oportunidade, evidencia, _descricao_do_ganho(oportunidade, compra))


def reverter_compra(compra, *, motivo: str, evidencia, momento=None) -> None:
    """Estorno ou contestação confirmados: a receita líquida da compra zera."""
    if compra.aprovado_em is None:
        return
    if compra.revertida_em is None:
        compra.revertida_em = momento or timezone.now()
        compra.valor_revertido_centavos = int(compra.valor_aprovado_centavos or 0)
        compra.motivo_reversao = _texto(motivo)[:40] or "estorno"
        compra.save(update_fields=[
            "revertida_em", "valor_revertido_centavos", "motivo_reversao",
            "atualizada_em",
        ])
    for oportunidade in oportunidades_da_compra(compra):
        _desqualificar_por_reversao(oportunidade, evidencia)


def _levar_para_negociacao(oportunidade, compra, event_id) -> None:
    pedido = compra.pedido_id
    if oportunidade.etapa in ETAPAS_ANTES_DO_PEDIDO:
        oportunidade.etapa = "negociacao"
        oportunidade.passo_descricao = f"Acompanhar o pagamento do pedido {pedido}"
        oportunidade.passo_executar_ate = timezone.now() + timedelta(days=1)
        oportunidade.passo_evidencia_esperada = "Pagamento aprovado"
        oportunidade.save(update_fields=[
            "etapa", "passo_descricao", "passo_executar_ate",
            "passo_evidencia_esperada", "atualizada_em",
        ])
        _registrar(
            oportunidade, "etapa_alterada",
            f"Fez o pedido {pedido}; oferta em negociação.", event_id,
        )
    else:
        _registrar(
            oportunidade, "nota", f"Pedido {pedido} ligado a esta oportunidade.",
            event_id,
        )


def _levar_para_recuperacao(oportunidade, compra, evento, event_id) -> None:
    descricao = (
        "Recuperar pagamento recusado" if evento == "pagamento.recusado"
        else "Recuperar Pix vencido"
    )
    if oportunidade.etapa in ETAPAS_ANTES_DO_PEDIDO:
        oportunidade.etapa = "negociacao"
    oportunidade.passo_descricao = f"{descricao} do pedido {compra.pedido_id}"
    oportunidade.passo_executar_ate = timezone.now() + timedelta(days=1)
    oportunidade.passo_evidencia_esperada = (
        "Contato com o cliente e nova tentativa de pagamento"
    )
    oportunidade.save(update_fields=[
        "etapa", "passo_descricao", "passo_executar_ate",
        "passo_evidencia_esperada", "atualizada_em",
    ])
    _registrar(
        oportunidade, "etapa_alterada",
        f"{descricao}; pedido {compra.pedido_id}.", event_id,
    )


def _abrir_recuperacao(lead, compra, evento, event_id):
    from .recuperacao import _responsavel

    existente = _recuperacao_do_pedido(compra)
    if existente is not None:
        return existente
    descricao = (
        "Recuperar pagamento recusado" if evento == "pagamento.recusado"
        else "Recuperar Pix vencido"
    )
    oportunidade = Oportunidade.objects.create(
        lead=lead, etapa="nova", titular_id=_responsavel(lead.site_id),
        fonte_tipo=FONTE_RECUPERACAO,
        fonte_referencia_id=f"{PREFIXO_RECUPERACAO}{compra.pedido_id}",
        passo_descricao=descricao,
        passo_executar_ate=timezone.now() + timedelta(days=1),
        passo_evidencia_esperada="Contato com o cliente e nova tentativa de pagamento",
    )
    _registrar(
        oportunidade, "etapa_alterada",
        f"{descricao}; pedido {compra.pedido_id}.", event_id,
    )
    return oportunidade


def _reversao_pendente(compra):
    return ReversaoDePagamento.objects.filter(
        site_id=compra.site_id, order_id=compra.pedido_id
    ).first()


# ---------------------------------------------------------------------------
# As portas: uma por fato
# ---------------------------------------------------------------------------


def _travar_lead(lead):
    type(lead).objects.select_for_update().get(pk=lead.pk)


@transaction.atomic
def registrar_pedido(lead, data, event_id, evento_timeline=None):
    """Pedido criado: liga o pedido à oportunidade e a leva para negociação."""
    _travar_lead(lead)
    compra = compra_do_evento(lead, data)
    if compra is None:
        return None
    oportunidade = resolver_oportunidade(compra, lead, _momento(evento_timeline))
    vinculou = _vincular(compra, oportunidade)
    if (
        oportunidade is not None and not oportunidade.encerrada
        and compra.aprovado_em is None
        and (vinculou or oportunidade.etapa in ETAPAS_ANTES_DO_PEDIDO)
    ):
        _levar_para_negociacao(oportunidade, compra, event_id)
    _aplicar_estado(compra)
    return compra


@transaction.atomic
def registrar_aprovacao(lead, data, event_id, evento_timeline=None, chave=""):
    """Pagamento aprovado: a primeira aprovação do pedido é a venda."""
    _travar_lead(lead)
    compra = compra_do_evento(lead, data)
    if compra is None:
        return None
    if compra.aprovado_em is not None:
        return compra  # aprovação repetida ou tardia: a venda já existe
    _marcar_aprovada(
        compra, momento=_momento(evento_timeline),
        valor=_centavos(data.get("amount_cents")), evidencia=chave or event_id,
    )
    _vincular(compra, resolver_oportunidade(compra, lead, compra.aprovado_em))
    _aplicar_estado(compra)
    return compra


@transaction.atomic
def registrar_falha(lead, evento, data, event_id, evento_timeline=None):
    """Recusa ou Pix vencido: recuperação da compra correspondente.

    Pagamento confirmado sempre vence falha: se o pedido já foi aprovado
    (mesmo que a falha chegue depois, fora de ordem), nada muda.
    """
    if evento not in EVENTOS_DE_FALHA:
        return None
    _travar_lead(lead)
    compra = compra_do_evento(lead, data)
    if compra is None:
        return None
    _hidratar_aprovacao(compra, evento_timeline)
    if compra.aprovado_em is not None:
        return None
    identidade = f"{evento}:{event_id}"
    nova = all(falha.get("id") != identidade for falha in compra.falhas or [])
    if nova:
        compra.falhas = list(compra.falhas or []) + [{
            "id": identidade, "evento": evento,
            "em": _momento(evento_timeline).isoformat(),
            "motivo": _texto(data.get("reason_code"))[:120],
        }]
        compra.save(update_fields=["falhas", "atualizada_em"])
    oportunidade = resolver_oportunidade(compra, lead, _momento(evento_timeline))
    if (
        oportunidade is not None and not oportunidade.encerrada
        and oportunidade.fonte_tipo != FONTE_RECUPERACAO
    ):
        _vincular(compra, oportunidade)
        if nova:
            _levar_para_recuperacao(oportunidade, compra, evento, event_id)
        return oportunidade
    recuperacao = _abrir_recuperacao(compra.lead, compra, evento, event_id)
    if compra.oportunidade_id is None:
        _vincular(compra, recuperacao)
    return recuperacao


def _aplicar_estado(compra) -> None:
    if compra.aprovado_em is None:
        return
    reversao = _reversao_pendente(compra)
    if reversao is not None:
        from .recuperacao import _aplicar_reversao

        _aplicar_reversao(reversao)
        return
    ganhar_compra(compra)


@transaction.atomic
def ligar_compras_soltas(lead, oportunidade, desde=None) -> None:
    """Oferta aberta depois do pedido: liga as compras da pessoa sem oportunidade."""
    if oportunidade.encerrada:
        return
    compras = CompraDaOportunidade.objects.select_for_update().filter(
        lead=lead, oportunidade__isnull=True
    ).order_by("criada_em", "id")
    for compra in compras:
        if desde is not None and (compra.aprovado_em or compra.criada_em) < desde:
            continue
        if resolver_oportunidade(compra, lead, compra.aprovado_em) != oportunidade:
            continue
        _vincular(compra, oportunidade)
        _aplicar_estado(compra)
        oportunidade.refresh_from_db()
        if oportunidade.encerrada:
            return


# ---------------------------------------------------------------------------
# Reconstrução a partir da linha do tempo (backfill)
# ---------------------------------------------------------------------------


def reconstruir_compras(eventos) -> None:
    """Repassa pedidos e pagamentos já guardados, na ordem em que aconteceram.

    Pode rodar quantas vezes for preciso: cada fato só muda a compra uma vez.
    """
    for evento in eventos.filter(event__in=EVENTOS_DA_COMPRA).order_by(
        "occurred_at", "id"
    ).select_related("lead").iterator():
        dados = evento.payload or {}
        identidade = evento.event_id or evento.id
        if evento.event == "pedido.criado":
            registrar_pedido(evento.lead, dados, identidade, evento)
        elif evento.event == "pagamento.aprovado":
            registrar_aprovacao(evento.lead, dados, identidade, evento)
        else:
            registrar_falha(evento.lead, evento.event, dados, identidade, evento)
