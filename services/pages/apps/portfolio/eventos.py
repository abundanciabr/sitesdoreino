"""O fato que esta célula AFIRMA ao resto da plataforma: o selo saiu.

Até o degrau 12 a casa das Páginas do aluno era muda: ela guardava o portfólio,
o roteiro e a conferência, e ninguém de fora ficava sabendo de nada. Ganhou voz
para cumprir uma promessa escrita no corredor assinado (critério AC-17): a
gamificação acende o marco do portfólio na trilha quando o selo sai, **sem
pagar XP**, e ela só ESCUTA. Quem acende é o degrau 15, nunca este arquivo.

Lei do assunto: `contracts/eventos/pages.portfolio.conferido.v1.json`,
congelado no Rito de Contrato do PR #1154, com o mantenedor presente. Nada aqui
inventa campo, renomeia campo nem acrescenta campo "que seria útil": divergir
do congelado é parar e avisar, nunca editar `contracts/`.

**Por que o construtor mora aqui, e não solto no `conferencia.py`.** O `data`
de um evento é a superfície que outras células vão ler por anos. Se cada ponto
de emissão montasse o próprio dicionário, o dia em que o contrato ganhasse um
campo seriam N lugares para lembrar. Aqui é um só, e é ele que o guarda mira.

**Só ids opacos viajam.** Nem link, nem legenda, nem apelido, nem e-mail, nem
nome. O contrato é `additionalProperties: false` justamente para que um campo a
mais não passe despercebido, e o guarda valida o envelope real contra o arquivo
do contrato, nunca contra uma cópia do formato dentro do teste.

Molde: `services/alunos/apps/matriculas/eventos.py` e
`services/cursos/apps/cursos/eventos.py`, copiados e nunca importados (Lei 3).
"""

from __future__ import annotations

from typing import Any

from django.db import transaction

from .models import OutboxEvent

#: O nome congelado no degrau 03. Ele vive no espaço `pages.portfolio.*` de
#: propósito: `portfolio.publicado.v1` já existe, é da célula `encomendas` e
#: quer dizer outra coisa (há peça nova disponível).
PORTFOLIO_CONFERIDO = "pages.portfolio.conferido"


class EventoForaDaTransacao(Exception):
    """`emitir()` chamado sem transação aberta, e aí o evento não é transacional.

    Levantar aqui é a Lei 1 aplicada: em vez de confiar que todo ponto de
    emissão futuro se lembre do `atomic`, a própria função recusa a escrita. Um
    evento gravado em autocommit sobrevive ao rollback do fato que o justifica,
    e a plataforma inteira passa a acreditar em algo que não aconteceu. É o modo
    de falha mais caro que uma outbox existe para impedir.
    """


def emitir(
    event: str,
    data: dict[str, Any],
    *,
    version: int = 1,
    envelope_extra: dict[str, Any] | None = None,
) -> OutboxEvent:
    """Grava o fato na outbox, SEMPRE dentro da transação do fato.

    Não publica nada: publicar é do relay (`tasks.py`), depois do commit. Essa
    separação É a outbox. Escrever no Redis daqui devolveria exatamente o
    problema que o padrão resolve, que é evento no fio para uma transação
    revertida.
    """
    if not transaction.get_connection().in_atomic_block:
        raise EventoForaDaTransacao(
            f"emitir({event!r}) foi chamado fora de transaction.atomic(). "
            "O evento tem de nascer na MESMA transação do fato que o justifica: "
            "sem isso, um rollback deixa a plataforma acreditando num fato que "
            "não aconteceu."
        )
    return OutboxEvent.objects.create(
        event=event,
        version=version,
        payload=data,
        envelope_extra=envelope_extra or {},
    )


def fato_do_selo(portfolio, *, conferido_por: str) -> OutboxEvent:
    """A escola conferiu este portfólio, e o selo saiu.

    **`ator_id` vai no ENVELOPE, e nunca é vazio.** O contrato o declara
    obrigatório e não nulável, e a razão está escrita nele: não existe selo que
    o relógio assine sozinho. Quem chama já recusou o anônimo antes de chegar
    aqui (`conferencia._conferir_quem_responde`), e esta função não repete a
    regra: repetida, ela viraria duas verdades capazes de divergir.

    **`occurred_at` não se escreve aqui.** Ele é `auto_now_add` na outbox, e é a
    data que o selo carrega: ele vale para o que o monitor VIU nesse dia
    (plano §6.2). Uma data escolhida por quem emite poderia discordar da que
    ficou gravada no estado do aluno.
    """
    return emitir(
        PORTFOLIO_CONFERIDO,
        {
            "site_id": portfolio.site_id,
            "aluno_id": portfolio.aluno_id,
            "portfolio_id": str(portfolio.pk),
        },
        envelope_extra={"ator_id": conferido_por},
    )
