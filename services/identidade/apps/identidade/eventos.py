"""Os fatos que esta célula AFIRMA ao resto da plataforma.

Até 31/08/2026 ela não afirmava nenhum: cunhava a `Identidade` e ficava calada.
Ganhou voz para que o pedido mais óbvio do mantenedor — *"após o cadastro,
mandar uma mensagem de boas-vindas"* — tivesse o que escutar
(`PLANO-SEQUENCIAS-DE-MENSAGENS` §2, degrau 1).

Lei do assunto: `contracts/eventos/identidade.pessoa-cadastrada.v1.json`,
congelado no Rito de Contrato de 31/08/2026 com o mantenedor presente. Nada
aqui inventa campo, renomeia campo ou acrescenta campo "que seria útil" —
divergir do contrato é parar e avisar, nunca editar `contracts/`.

**Nenhum `data` carrega PII.** Nem nome, nem e-mail, nem provedor: só o id
opaco da plataforma e o site. Quem precisar falar com a pessoa PERGUNTA a esta
célula, sob o token do par, na hora do envio — e é isso que permite este fato
circular pela plataforma inteira sem espalhar o e-mail de ninguém
(`DECISAO-EVO-01` §3).

**Este NÃO é a carta.** A carta é `notificacao.devida.v1`, e quem decide se
este fato merece uma é quem escuta, nunca quem publica.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction

from .models import OutboxEvent

PESSOA_CADASTRADA = "identidade.pessoa-cadastrada"


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
    return OutboxEvent.objects.create(
        event=event,
        version=version,
        payload=data,
        envelope_extra=envelope_extra or {},
    )


def pessoa_cadastrada(*, site_id: str, pessoa_id: str) -> OutboxEvent:
    """Alguém entrou no site pela primeira vez.

    Só na CUNHAGEM. Reentrar não é cadastrar-se, e um evento por login faria a
    plataforma mandar boas-vindas para sempre à mesma pessoa — quem garante
    isso é o chamador, que é quem sabe se a linha nasceu agora.

    **Nada de preenchimento retroativo** (decisão do mantenedor, §8.7.2 do
    plano): só quem se cadastrar daqui em diante é anunciado. Ele pesou contra
    mandar "bem-vindo" a quem usa o site há meses.
    """
    return emitir(
        PESSOA_CADASTRADA,
        {"site_id": site_id, "pessoa_id": pessoa_id},
    )
