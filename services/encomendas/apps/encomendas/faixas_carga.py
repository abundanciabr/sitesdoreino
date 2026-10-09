"""Carga histórica dos fatos das faixas (migração de dados 0026).

Grava na outbox, com `historico=true` e os MESMOS event_id determinísticos dos
eventos ao vivo, o PRIMEIRO trabalho de Sandbox e o PRIMEIRO trabalho aceito na
Fila de cada (pessoa, site), e TODOS os rendimentos reais que cumprem o critério.
Reexecutar não duplica. Recebe as classes de modelo (históricas na migração).
"""
from . import faixas_eventos as fe


def _pares_ja_emitidos(Outbox, evento):
    return {(e["payload"].get("pessoa_id"), e["payload"].get("site_id"))
            for e in Outbox.objects.filter(event=evento).values("payload").iterator()}


def carregar(Participacao, Acordo, Recebivel, Evento, Outbox) -> dict:
    novos = {"sandbox": 0, "fila": 0, "rendimento": 0}

    vistos = _pares_ja_emitidos(Outbox, fe.EV_SANDBOX)
    for p in Participacao.objects.order_by("aceite_em", "pk").iterator(chunk_size=500):
        chave = (str(p.pessoa_id), p.site_id)
        if chave in vistos:
            continue
        vistos.add(chave)
        _, criado = fe.emitir(Evento, Outbox, site_id=p.site_id, evento=fe.EV_SANDBOX, chave=p.pk, dados={
            "pessoa_id": str(p.pessoa_id), "trabalho_id": str(p.pk),
            "ocorrido_em": p.aceite_em.isoformat(), "historico": True})
        novos["sandbox"] += int(criado)

    vistos = _pares_ja_emitidos(Outbox, fe.EV_FILA)
    for a in Acordo.objects.select_related("aluno").order_by("aceito_em", "pk").iterator(chunk_size=500):
        chave = (str(a.aluno.pessoa_id), a.site_id)
        if chave in vistos:
            continue
        vistos.add(chave)
        _, criado = fe.emitir(Evento, Outbox, site_id=a.site_id, evento=fe.EV_FILA, chave=a.pk,
                              pedido_id=a.pedido_id, dados={
            "pessoa_id": str(a.aluno.pessoa_id), "pedido_id": str(a.pedido_id),
            "ocorrido_em": a.aceito_em.isoformat(), "historico": True})
        novos["fila"] += int(criado)

    for r in fe.recebiveis_validos(Recebivel).select_related("aluno", "pedido").order_by("pk").iterator(chunk_size=500):
        quando = r.recebido_em or r.creditado_em or r.pedido.aprovado_em or r.criado_em
        _, criado = fe.emitir(Evento, Outbox, site_id=r.site_id, evento=fe.EV_CONFIRMADO,
                              chave=f"{r.pk}:1", pedido_id=r.pedido_id,
                              extra_evento={"valor_cents": int(r.valor_liquido_cents)}, dados={
            "pessoa_id": str(r.aluno.pessoa_id), "rendimento_id": str(r.pk),
            "valor_cents": int(r.valor_liquido_cents),
            "ocorrido_em": quando.isoformat(), "historico": True})
        novos["rendimento"] += int(criado)
    return novos
