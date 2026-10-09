"""Carga histórica do fato `cursos.item-criado` (faixas da gamificação).

Grava no outbox o PRIMEIRO Projeto3D de cada (pessoa, site) com historico=true e
o mesmo event_id determinístico do evento ao vivo. Reexecutar não duplica.
Recebe as classes de modelo para servir à migração (modelos históricos) e aos testes.
"""
import uuid

EVENTO = "cursos.item-criado"


def event_id(item_id):
    return uuid.uuid5(uuid.NAMESPACE_URL, f"meshcraft-faixas:{EVENTO}:{item_id}")


def carregar(Projeto3D, OutboxEvent):
    # Critério estável: menor pk (Projeto3D não tem data de criação; `ocorrido_em`
    # é a última edição, portanto APROXIMADA). Lê só 4 colunas (nunca imagem/receita)
    # e pula pares que já têm fato no outbox.
    vistos = {
        (e["payload"].get("pessoa_id"), e["payload"].get("site_id"))
        for e in OutboxEvent.objects.filter(event=EVENTO).values("payload").iterator()
    }
    novos = 0
    linhas = (
        Projeto3D.objects.order_by("pk")
        .values_list("pk", "pessoa_id", "curso__site_id", "atualizado_em")
        .iterator(chunk_size=500)
    )
    for pk, pessoa_id, site_id, atualizado_em in linhas:
        chave = (str(pessoa_id), site_id)
        if chave in vistos:
            continue
        vistos.add(chave)
        _, criado = OutboxEvent.objects.get_or_create(
            event_id=event_id(pk),
            defaults={
                "event": EVENTO,
                "version": 1,
                "envelope_extra": {},
                "payload": {
                    "site_id": site_id,
                    "pessoa_id": str(pessoa_id),
                    "item_id": str(pk),
                    "ocorrido_em": atualizado_em.isoformat(),
                    "historico": True,
                },
            },
        )
        novos += int(criado)
    return novos
