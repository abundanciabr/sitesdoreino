"""Fatos das FAIXAS do aluno, publicados para a gamificação.

Quatro eventos saem daqui pela outbox que já existe (`OutboxMarketplace` + relay,
stream `eventos.<event>`):

- `encomendas.sandbox-trabalho-criado`: nasce uma ParticipacaoSandbox.
- `encomendas.fila-trabalho-aceito`: o ALUNO aceita um pedido da Fila do Dólar
  (nasce o AcordoMarketplace). O pedido criado pelo cliente não é fato do aluno.
- `encomendas.rendimento-real-confirmado` / `...-revertido`: dinheiro REAL de
  cliente que passou a valer / deixou de valer para o aluno.

`pessoa_id` = `PerfilProfissional.pessoa_id` / `ParticipacaoSandbox.pessoa_id`
(o id de plataforma, o mesmo que a gamificação guarda em `Pessoa.id_da_plataforma`)
e `site_id` = campo `site_id` do próprio registro.

`event_id` é determinístico: uuid5(NAMESPACE_URL, "meshcraft-faixas:<event>:<chave>").
A emissão é idempotente (a chave do fato é única em `EventoMarketplace`).

RENDIMENTO REAL. Um recebível conta quando, ao mesmo tempo: o pedido está
`aprovado`, tem o sinal de pagamento real de `fila_real._depositado` (cliente da
Fila com `pagamento_real_confirmado_em` + `referencia_provedor`, ambiente
`production` e `pagamento_confirmado_em`), o recebível não está em `excecao` e
`valor_liquido_cents > 0`. Créditos internos do ClienteFila, carteira, MESH, XP,
Cristais, propostas, previstos e ambiente sandbox nunca entram.
`sincronizar_rendimento` compara o que vale AGORA com o que já foi publicado e
emite só a diferença (confirma, reverte, ou reverte e confirma o novo valor).
Cada ciclo confirma -> reverte -> confirma de novo ganha um event_id próprio
(sufixo `:n` na chave).
"""

from __future__ import annotations

import uuid

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

EV_SANDBOX = "encomendas.sandbox-trabalho-criado"
EV_FILA = "encomendas.fila-trabalho-aceito"
EV_CONFIRMADO = "encomendas.rendimento-real-confirmado"
EV_REVERTIDO = "encomendas.rendimento-real-revertido"


def event_id(evento: str, chave) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"meshcraft-faixas:{evento}:{chave}")


def _iso(quando) -> str:
    return (quando or timezone.now()).isoformat()


def emitir(EventoMarketplace, OutboxMarketplace, *, site_id, evento, chave, dados,
           pedido_id=None, extra_evento=None):
    """Grava o fato na outbox uma única vez. Devolve (EventoMarketplace, criado)."""
    with transaction.atomic():
        fato, criado = EventoMarketplace.objects.get_or_create(
            chave=f"faixas:{evento}:{chave}",
            defaults={"site_id": site_id, "pedido_id": pedido_id, "tipo": f"{evento}.v1",
                      "dados": extra_evento or {}},
        )
        if criado:
            OutboxMarketplace.objects.create(
                site_id=site_id, evento=fato, event=evento, version=1,
                event_id=event_id(evento, chave),
                payload={"site_id": site_id, **dados},
            )
        return fato, criado


def _modelos():
    from .models import EventoMarketplace, OutboxMarketplace
    return EventoMarketplace, OutboxMarketplace


def sandbox_trabalho_criado(participacao, *, historico=False):
    E, O = _modelos()
    return emitir(E, O, site_id=participacao.site_id, evento=EV_SANDBOX, chave=participacao.pk, dados={
        "pessoa_id": str(participacao.pessoa_id), "trabalho_id": str(participacao.pk),
        "ocorrido_em": _iso(participacao.aceite_em), "historico": historico,
    })


def fila_trabalho_aceito(acordo, *, historico=False):
    E, O = _modelos()
    return emitir(E, O, site_id=acordo.site_id, evento=EV_FILA, chave=acordo.pk, pedido_id=acordo.pedido_id, dados={
        "pessoa_id": str(acordo.aluno.pessoa_id), "pedido_id": str(acordo.pedido_id),
        "ocorrido_em": _iso(acordo.aceito_em), "historico": historico,
    })


# ---------------------------------------------------------------------------
# Rendimento real
# ---------------------------------------------------------------------------
def valor_que_vale(recebivel) -> int | None:
    """Centavos que contam como rendimento real AGORA, ou None se não conta."""
    from .fila_real import _depositado
    from .models import RecebivelMarketplace

    pedido = recebivel.pedido
    valor = recebivel.valor_liquido_cents
    if (recebivel.status == RecebivelMarketplace.Status.EXCECAO or pedido.status != "aprovado"
            or not valor or valor <= 0 or not hasattr(pedido, "fila_cliente")):
        return None
    return int(valor) if _depositado(pedido) else None


def recebiveis_validos(Recebivel):
    """Mesma condição de `valor_que_vale`/`_depositado`, como consulta (para a carga histórica)."""
    return Recebivel.objects.filter(
        pedido__status="aprovado", pedido__ambiente="production",
        pedido__pagamento_confirmado_em__isnull=False,
        pedido__fila_cliente__pagamento_real_confirmado_em__isnull=False,
        valor_liquido_cents__gt=0,
    ).exclude(status="excecao").exclude(pedido__fila_cliente__referencia_provedor="")


def _estado_publicado(Evento, rid):
    """(ciclos confirmados, ciclos revertidos, valor da última confirmação)."""
    base = f"faixas:{EV_CONFIRMADO}:{rid}:"
    confirmados = list(Evento.objects.filter(tipo=f"{EV_CONFIRMADO}.v1", chave__startswith=base))
    n_rev = Evento.objects.filter(tipo=f"{EV_REVERTIDO}.v1", chave__startswith=f"faixas:{EV_REVERTIDO}:{rid}:").count()
    # Os ciclos vêm das chaves (`<recebível>:<n>`), não de datas.
    n_conf = max((int(e.chave.rsplit(":", 1)[1]) for e in confirmados), default=0)
    ultimo = next((e for e in confirmados if e.chave.endswith(f":{n_conf}")), None)
    return n_conf, n_rev, int(ultimo.dados.get("valor_cents", 0)) if ultimo else 0


def sincronizar_rendimento(recebivel, *, historico=False, ocorrido_em=None) -> list[str]:
    """Publica a diferença entre o que vale agora e o que já foi publicado.

    Chame depois de qualquer mudança que possa alterar o critério. Repetir é seguro."""
    E, O = _modelos()
    from .models import PedidoMarketplace, RecebivelMarketplace

    emitidos: list[str] = []
    with transaction.atomic():
        # Mesma ordem das ações do usuário: pedido primeiro, recebível depois.
        PedidoMarketplace.objects.select_for_update().filter(pk=recebivel.pedido_id).first()
        recebivel = RecebivelMarketplace.objects.select_for_update(of=("self",)).select_related(
            "pedido", "aluno").get(pk=recebivel.pk)
        agora = ocorrido_em or timezone.now()
        valor = valor_que_vale(recebivel)
        n_conf, n_rev, publicado = _estado_publicado(E, recebivel.pk)
        confirmado = n_conf > n_rev
        if confirmado and publicado == valor:
            return emitidos
        if not confirmado and valor is None:
            return emitidos
        base = {"pessoa_id": str(recebivel.aluno.pessoa_id), "rendimento_id": str(recebivel.pk),
                "ocorrido_em": _iso(agora), "historico": historico}
        if confirmado:  # deixou de valer, ou o valor mudou: tira o que foi publicado
            _, criado = emitir(E, O, site_id=recebivel.site_id, evento=EV_REVERTIDO,
                               chave=f"{recebivel.pk}:{n_conf}", pedido_id=recebivel.pedido_id,
                               dados={**base, "valor_cents": publicado, "ciclo": n_conf})
            if criado:
                emitidos.append(EV_REVERTIDO)
        if valor is not None:
            ciclo = n_conf + 1
            _, criado = emitir(E, O, site_id=recebivel.site_id, evento=EV_CONFIRMADO,
                               chave=f"{recebivel.pk}:{ciclo}", pedido_id=recebivel.pedido_id,
                               dados={**base, "valor_cents": valor, "ciclo": ciclo}, extra_evento={"valor_cents": valor})
            if criado:
                emitidos.append(EV_CONFIRMADO)
    return emitidos


def sincronizar_do_pedido(pedido_id) -> None:
    """Atalho para os ganchos que só conhecem o pedido."""
    from .models import RecebivelMarketplace

    recebivel = RecebivelMarketplace.objects.filter(pedido_id=pedido_id).first()
    if recebivel is not None:
        sincronizar_rendimento(recebivel)


def reconciliar(*, site_id=None, limite=500) -> int:
    """Publica o que mudou por caminhos sem gancho (ex.: `update()` direto).

    Só olha o que pode ter mudado: recebíveis que valem agora sem confirmação
    publicada (ou com valor diferente) e os confirmados que deixaram de valer.
    Falha de um item não derruba os seguintes. Roda no batimento da célula."""
    import logging

    from .models import RecebivelMarketplace

    E, _ = _modelos()
    estado: dict[int, list[int]] = {}  # rid -> [ciclos confirmados, revertidos, valor da última]
    filtro = {"site_id": site_id} if site_id else {}
    for ev in E.objects.filter(tipo=f"{EV_CONFIRMADO}.v1", **filtro).only("chave", "dados"):
        rid, ciclo = ev.chave.rsplit(":", 2)[-2:]
        rid, ciclo = int(rid), int(ciclo)
        e = estado.setdefault(rid, [0, 0, 0])
        if ciclo >= e[0]:
            e[0], e[2] = ciclo, int((ev.dados or {}).get("valor_cents", 0))
    for ev in E.objects.filter(tipo=f"{EV_REVERTIDO}.v1", **filtro).only("chave"):
        rid = int(ev.chave.rsplit(":", 2)[-2])
        estado.setdefault(rid, [0, 0, 0])[1] += 1

    validos = {r.pk: r.valor_liquido_cents for r in recebiveis_validos(RecebivelMarketplace).filter(**filtro)
               .only("pk", "valor_liquido_cents")}
    pendentes = set()
    for rid, (n_conf, n_rev, publicado) in estado.items():
        confirmado = n_conf > n_rev
        if confirmado and (rid not in validos or validos[rid] != publicado):
            pendentes.add(rid)
    pendentes |= {rid for rid in validos if not (estado.get(rid, [0, 0, 0])[0] > estado.get(rid, [0, 0, 0])[1])}

    total = 0
    log = logging.getLogger(__name__)
    for pk in sorted(pendentes)[:limite]:
        try:
            r = RecebivelMarketplace.objects.filter(pk=pk).first()
            if r is not None:
                total += len(sincronizar_rendimento(r))
        except Exception:  # noqa: BLE001 - um item ruim não pode parar o lote
            log.exception("faixas: reconciliar falhou no recebível %s", pk)
    return total


# ---------------------------------------------------------------------------
# Ganchos: qualquer gravação que mude o critério reavalia o recebível do pedido
# (cancelamento, exceção, sinal de pagamento real desfeito). O que passar por
# `update()` em massa é pego por `reconciliar`, no batimento.
# ---------------------------------------------------------------------------
def _ao_salvar_recebivel(sender, instance, raw=False, **kwargs):
    if not raw:
        sincronizar_rendimento(instance)


def _ao_salvar_pedido(sender, instance, raw=False, **kwargs):
    if not raw:
        sincronizar_do_pedido(instance.pk)


def _ao_salvar_vinculo_da_fila(sender, instance, raw=False, **kwargs):
    if not raw:
        sincronizar_do_pedido(instance.pedido_id)


def ligar_sinais() -> None:
    from django.db.models.signals import post_save

    post_save.connect(_ao_salvar_recebivel, sender="encomendas.RecebivelMarketplace",
                      dispatch_uid="faixas-recebivel")
    post_save.connect(_ao_salvar_pedido, sender="encomendas.PedidoMarketplace",
                      dispatch_uid="faixas-pedido")
    post_save.connect(_ao_salvar_vinculo_da_fila, sender="encomendas.PedidoClienteFila",
                      dispatch_uid="faixas-vinculo-fila")
