"""A recepção: transforma um envelope que chegou em fato guardado (degrau 7.3).

Esta é a lógica pura, sem Redis, e é ela que os testes exercitam. O laço que
lê o stream vive em `management/commands/consume_eventos.py`, no molde
[RECEITA:R4 v1] que as cinco células consumidoras já seguem (Lei 3: copia-se o
padrão entre células, nunca se importa código de uma na outra).

## Quatro decisões que valem a leitura

**1. `receber` NUNCA levanta.** Todo caminho termina em fato guardado ou em
evento morto. Um consumidor que estoura deixa a mensagem presa no PEL e, cinco
entregas depois, ela cai na fila morta do Redis — onde ninguém olha. A fila de
mortos DESTA célula é uma tabela, aparece no painel e vira incidente. O plano
pede as três ações (inspecionar, tentar de novo, descartar com motivo), e elas
só existem se o evento inválido chegar até aqui.

**2. O que se valida é o ENVELOPE, não o miolo.** As cinco chaves canônicas
(`event`, `version`, `event_id`, `occurred_at`, `data`), o fuso da data, o
formato do id e o `site_id`. O `data` é guardado como veio. O `ator_id` é
guardado quando vem e NÃO é exigido: os assuntos mais antigos da casa não o
têm, e cobrá-lo mataria fatos legítimos.

Por que não validar contra o JSON Schema do contrato: os contratos vivem em
`contracts/eventos/` e **não viajam para dentro da imagem** (o build tem por
contexto a pasta da célula). Copiá-los para cá seria pôr o mesmo fato em dois
lugares, que é a lei que esta casa mais defende — e uma cópia envelhecida
recusaria eventos legítimos, que é o pior modo de falha possível para um
livro. Quem valida o miolo contra o contrato é quem PUBLICA, no teste dele (é
o que `forum/tests/test_a_voz_do_forum.py` faz). Aqui a régua é: se o envelope
está bom, o fato é guardado como veio; interpretar o `data` é trabalho de quem
lê, e o corpo cru está lá para isso.

**3. O marco vem depois do fato, e nunca ao preço dele.** Guardado o evento,
`marcos.derivar` lê dele as conquistas que couberem (degrau 9) — fora da
transação do fato, e sem levantar. Como aqui o miolo não é validado, um `data`
fora do contrato é possível, e a resposta a ele é marco nenhum: fato guardado
sem marco é honesto, fato recusado por causa de uma leitura seria o livro
perdendo história.

**4. Assunto desconhecido é fato, não erro.** Diferente das outras
consumidoras, esta não tem "handler por assunto": tudo o que chega e tem
envelope bom é guardado. É o que faz dela um livro em vez de um contador —
guardar hoje o que ninguém perguntou ainda é a única forma de responder amanhã
uma pergunta que ainda não existe.
"""

from __future__ import annotations

import datetime as dt
import json
import uuid

from django.db import IntegrityError, transaction

from .marcos import derivar
from .models import Evento, EventoMorto, dia_em_sao_paulo

#: As chaves do envelope canônico da casa (`contracts/eventos/*.json`).
OBRIGATORIAS = ("event", "version", "event_id", "occurred_at", "data")

#: Os desfechos possíveis. `receber` devolve um deles, e o chamador só decide
#: o que registrar em log: nos três casos a mensagem é ACKada, porque em
#: nenhum deles reentregar mudaria o resultado.
GUARDADO = "guardado"
JA_TINHA = "ja-tinha"
MORTO = "morto"


def _texto(valor: object) -> str:
    return valor if isinstance(valor, str) else ""


def _matar(corpo: str, motivo: str, envelope: dict | None = None) -> tuple[str, object]:
    envelope = envelope or {}
    morto = EventoMorto.objects.create(
        corpo=corpo[:100_000],
        motivo=motivo,
        tipo_declarado=_texto(envelope.get("event"))[:120],
        event_id_declarado=_texto(envelope.get("event_id"))[:80],
    )
    return MORTO, morto


def receber(cru: bytes | str) -> tuple[str, object]:
    """`(desfecho, objeto)`. Guarda o fato, ou o manda para a fila de mortos.

    `cru` é o texto que veio no campo `json` da mensagem do stream — texto, e
    não dicionário, de propósito: a causa mais comum de um evento morto é
    justamente não ser JSON válido, e essa causa só é visível antes do parse.
    """
    if isinstance(cru, bytes):
        try:
            cru = cru.decode("utf-8")
        except UnicodeDecodeError:
            return _matar("<bytes ilegíveis>", "o corpo não é UTF-8")
    try:
        envelope = json.loads(cru)
    except (TypeError, ValueError) as erro:
        return _matar(str(cru), f"o corpo não é JSON válido: {erro}")
    if not isinstance(envelope, dict):
        return _matar(cru, "o corpo é JSON, mas não é um objeto")

    faltando = [c for c in OBRIGATORIAS if envelope.get(c) is None]
    if faltando:
        return _matar(
            cru,
            "faltam chaves do envelope canônico: " + ", ".join(faltando),
            envelope,
        )

    try:
        event_id = uuid.UUID(str(envelope["event_id"]))
    except (TypeError, ValueError):
        return _matar(cru, "`event_id` não é um UUID", envelope)

    tipo = _texto(envelope["event"])
    if "." not in tipo:
        return _matar(
            cru,
            "`event` não tem a forma `celula.assunto`, e é dela que sai a "
            "célula que afirmou o fato",
            envelope,
        )

    versao = envelope["version"]
    if not isinstance(versao, int) or isinstance(versao, bool) or versao < 1:
        return _matar(cru, "`version` não é um inteiro a partir de 1", envelope)

    try:
        ocorrido_em = dt.datetime.fromisoformat(str(envelope["occurred_at"]))
    except (TypeError, ValueError):
        return _matar(cru, "`occurred_at` não é uma data e hora legível", envelope)
    if ocorrido_em.tzinfo is None:
        return _matar(
            cru,
            "`occurred_at` veio sem fuso, e sem fuso o DIA do fato é um chute "
            "(armadilhas/099)",
            envelope,
        )

    dados = envelope["data"]
    if not isinstance(dados, dict):
        return _matar(cru, "`data` não é um objeto", envelope)
    site_id = _texto(dados.get("site_id"))
    if not site_id:
        return _matar(
            cru,
            "`data.site_id` ausente: a plataforma serve mais de um site, e "
            "fato sem site não pode ser contado para nenhum",
            envelope,
        )

    try:
        with transaction.atomic():
            evento = Evento(
                event_id=event_id,
                tipo=tipo,
                versao=versao,
                celula=tipo.split(".")[0],
                site_id=site_id[:60],
                ator_id=_texto(envelope.get("ator_id"))[:120],
                ocorrido_em=ocorrido_em,
                dia=dia_em_sao_paulo(ocorrido_em),
                dados=dados,
            )
            evento.save()
    except IntegrityError:
        # Reentrega. É o normal de qualquer fila, e não é erro: o fato já está
        # no livro, gravado uma vez, que é o que a contagem precisa.
        return JA_TINHA, Evento.objects.filter(event_id=event_id).first()
    # A leitura vem DEPOIS do fato, e fora da transação dele: um marco que não
    # dá para calcular não pode custar o fato que já foi afirmado.
    derivar(evento)
    return GUARDADO, evento
