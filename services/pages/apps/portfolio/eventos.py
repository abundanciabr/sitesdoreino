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

DOIS EVENTOS SAEM DO MESMO SIM, E ELES DIZEM COISAS DIFERENTES
---------------------------------------------------------------
`pages.portfolio.conferido.v1` é o FATO: "o selo saiu deste portfólio". Quem o
escuta é máquina, e a gamificação acende o marco com ele.

`notificacao.devida.v1` é a CARTA: "esta pessoa precisa ficar sabendo". Quem a
lê é gente, no sininho. O contrato do fato não serve para as duas coisas de
propósito, e essa separação é a lei da caixa central (o fato tem evento
próprio; a carta é genérica e já endereçada a UMA pessoa, com o leque feito na
origem). Uma célula que só publicasse o fato deixaria o aluno esperando na
frente de uma tela que ele teria de reabrir para descobrir a resposta.

O assunto da carta é `pages.portfolio-conferido`, acrescentado ao enum de
`contracts/eventos/notificacao.devida.v1.json` no Rito de Contrato de
06/09/2026, com o mantenedor presente. **No mesmo Rito ele RECUSOU o segundo
assunto que esta célula pediu** (`pages.peca-quebrada`, o aviso de link que
parou de responder): o aluno descobre a peça quebrada abrindo a página, e essa
decisão é dele.

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

#: A CARTA ENDEREÇADA: uma pessoa a avisar, um evento. O nome e a forma são da
#: caixa central, não desta casa, e é por isso que a constante não tem o
#: prefixo `pages.`.
NOTIFICACAO_DEVIDA = "notificacao.devida"

#: O assunto desta célula no enum da carta. Assunto novo entra por Rito de
#: Contrato (RITOS §3), nunca por uma string escrita aqui: o `enum` do contrato
#: é fechado, e um assunto que ele não conheça viraria aviso mudo na tela de
#: alguém.
ASSUNTO_DO_SELO = "pages.portfolio-conferido"


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


def carta_do_selo(portfolio, *, conferido_por: str, origem_event_id) -> OutboxEvent:
    """O aluno fica sabendo, no sininho, que a escola conferiu (critério AC-12).

    **A carta é irmã do fato, e não substituta dele.** Ela sai da mesma
    transação e do mesmo sim, endereçada à única pessoa que estava esperando:
    o dono do portfólio. A caixa central não faz leque nenhum, e aqui não há
    leque a fazer.

    **`origem_event_id` é o `event_id` do FATO**, e não um id novo. É o que
    torna a promessa rastreável: de um aviso na tela se chega ao acontecimento
    que o causou. Cunhar um valor solto aqui deixaria a carta e o fato do mesmo
    sim sem nenhum elo, e o campo passaria a apontar para si mesmo.

    **O papel de quem conferiu NÃO viaja hoje, e a ausência é medida.** O
    contrato o prevê como opcional (`professor`/`monitor`), e esta célula
    reconhece a equipe por uma lista de ids no env (`apps/core/equipe.py`,
    `IDS_DA_EQUIPE`): ela sabe que quem decidiu está na lista, e não sabe qual
    é o papel dele. Emitir um dos dois valores seria escrever na tela do aluno
    um cargo que ninguém conferiu. Sem o campo, o sininho não diz quem
    conferiu, e a frase que sobra é a mesma que a estante dele já mostra: uma
    pessoa da equipe olhou. Quando a porta passar a repassar o papel
    (`apps/core/menu.py::_quem_esta_aqui` diz onde), é esta chamada que ganha o
    campo, sem Rito novo.

    **`ator_id` é quem conferiu, e continua não aparecendo para o aluno.** A
    regra do envelope é a de sempre: guardar sim, mostrar não. É por ela que o
    cartão fala da equipe e nunca de uma pessoa.
    """
    return emitir(
        NOTIFICACAO_DEVIDA,
        {
            "site_id": portfolio.site_id,
            "destinatario_id": portfolio.aluno_id,
            "assunto": ASSUNTO_DO_SELO,
            "parametros": {"portfolio_id": str(portfolio.pk)},
            "origem_event_id": str(origem_event_id),
        },
        envelope_extra={"ator_id": conferido_por},
    )
