# apps/matriculas/eventos.py
"""Os fatos que esta célula AFIRMA ao resto da plataforma.

Até 29/08/2026 ela não afirmava nenhum: só escutava (o consumer de pagamento).
Ganhou voz para poder cumprir uma promessa — *"você é avisado quando a sua
situação muda"* —, e o primeiro fato que ela diz é a carta de liberação.

Lei do assunto: `contracts/eventos/notificacao.devida.v1.json`, congelado no
Rito de Contrato do PR #524, com o mantenedor presente. Nada aqui inventa
campo, renomeia campo ou acrescenta campo "que seria útil" — divergir do
contrato é parar e avisar, nunca editar `contracts/`.

**Por que o construtor mora aqui, e não solto no `services.py`.** O `data` de
um evento é a superfície que outras células vão ler por anos. Se cada ponto de
emissão montasse o próprio dicionário, o dia em que o contrato ganhar um campo
seriam N lugares para lembrar. Aqui é um só, e é ele que o guarda mira.

**Nenhum `data` carrega PII.** Nem nome, nem e-mail, nem telefone: só ids
opacos e estados. É a mesma disciplina que a `sugestoes` já segue, e o contrato
é `additionalProperties: false` justamente para que um campo a mais não passe
despercebido.
"""

from __future__ import annotations

import uuid
from typing import Any

from django.db import transaction

from .models import OutboxEvent

# A CARTA ENDEREÇADA (Rito de Contrato de 26/08/2026): uma pessoa a avisar, um
# evento. Genérica de propósito — a `sugestoes` publica o mesmo formato desde
# então, e esta célula entra sem contrato novo, só com um `assunto` a mais.
NOTIFICACAO_DEVIDA = "notificacao.devida"
ASSUNTO_MATRICULA = "matricula.situacao-alterada"


class EventoForaDaTransacao(Exception):
    """`emitir()` chamado sem transação aberta — o evento não seria transacional.

    Levantar aqui é a Lei 1 aplicada: em vez de confiar que todo ponto de
    emissão futuro se lembre do `atomic`, a própria função recusa a escrita. Um
    evento gravado em autocommit sobrevive ao rollback do fato que o justifica,
    e aí a plataforma inteira passa a acreditar em algo que não aconteceu — o
    modo de falha mais caro que uma outbox existe para impedir.
    """


def emitir(
    event: str,
    data: dict[str, Any],
    *,
    version: int = 1,
    envelope_extra: dict[str, Any] | None = None,
    event_id: "uuid.UUID | None" = None,
) -> OutboxEvent:
    """Grava o fato na outbox — SEMPRE dentro da transação do fato.

    Não publica nada: publicar é do relay (`tasks.py`), depois do commit. Essa
    separação É a outbox — escrever no Redis aqui dentro devolveria o problema
    que o padrão resolve (evento publicado, transação revertida).
    """
    if not transaction.get_connection().in_atomic_block:
        raise EventoForaDaTransacao(
            f"emitir({event!r}) foi chamado fora de transaction.atomic(). "
            "O evento tem de nascer na MESMA transação do fato que o justifica: "
            "sem isso, um rollback deixa a plataforma acreditando num fato que "
            "não aconteceu."
        )
    campos: dict[str, Any] = {
        "event": event,
        "version": version,
        "payload": data,
        "envelope_extra": envelope_extra or {},
    }
    # `event_id` explícito é a exceção, não a regra: quem emite normalmente
    # deixa o default do model cunhar um. Ele existe porque uma carta declara
    # `origem_event_id` DENTRO do `data`, e o valor precisa estar decidido antes
    # de o `data` ser montado — cunhar depois faria os dois discordarem, em
    # silêncio, e a rastreabilidade que o campo promete morreria na primeira
    # carta.
    if event_id is not None:
        campos["event_id"] = event_id
    return OutboxEvent.objects.create(**campos)


def carta_de_situacao(
    *,
    site_id: str,
    destinatario_id: str,
    matricula_id: str,
    situacao_nova: str,
    situacao_anterior: str = "",
    decidido_por: str = "",
) -> OutboxEvent:
    """A carta que avisa uma pessoa de que a situação dela na escola mudou.

    UMA carta por pessoa — o leque é feito na ORIGEM, e aqui a origem tem
    sempre uma destinatária só. `origem_event_id` é o `event_id` desta mesma
    carta porque não há um fato anterior separado: a decisão do mantenedor É o
    acontecimento, e ela não tem evento próprio (nenhuma célula pediu um).

    **`ator_id` vai no ENVELOPE, não no `data`** — foi assim que o Rito de
    Contrato de 26/08/2026 o colocou, para que qualquer célula leia "quem fez
    isto" sem conhecer o formato do assunto. Ele é GUARDADO e não MOSTRADO: a
    tela do aluno diz "a equipe".

    `situacao_anterior` é opcional no contrato, e vazio aqui vira ausência — a
    tela que lê trata ausência como "não registrado", nunca como erro.
    """
    # UM identificador para a DECISÃO, usado nos dois lugares. Com uma pessoa a
    # avisar, a carta e o acontecimento coincidem; no dia em que uma decisão
    # gerar N cartas, todas compartilharão este `origem_event_id` — que é
    # exatamente o que o campo promete ("as N cartas de uma mesma mudança
    # compartilham este valor").
    identificador = uuid.uuid4()

    parametros: dict[str, Any] = {
        "matricula_id": str(matricula_id),
        "situacao_nova": situacao_nova,
    }
    if situacao_anterior:
        parametros["situacao_anterior"] = situacao_anterior

    return emitir(
        NOTIFICACAO_DEVIDA,
        {
            "site_id": site_id,
            "destinatario_id": destinatario_id,
            "assunto": ASSUNTO_MATRICULA,
            "parametros": parametros,
            "origem_event_id": str(identificador),
        },
        envelope_extra={"ator_id": decidido_por or None},
        event_id=identificador,
    )
