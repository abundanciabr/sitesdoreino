"""Os fatos que o motor das jornadas AFIRMA ao resto da plataforma.

Até aqui esta célula só escutava: consumia pagamento e quiz, e mandava e-mail.
Ganha voz para que a primeira sequência de verdade chegue onde o aluno vê, que é
o sininho (`services/notificacoes/`) — degrau 5 da escada do
`PLANO-SEQUENCIAS-DE-MENSAGENS.md` §7.

O ASSUNTO É `jornada.passo`, E ISSO JÁ FOI DECIDIDO
----------------------------------------------------
Rito de Contrato de 31/08/2026, com o mantenedor presente (§8.7.1). Nas palavras
dele: *"serviço no contrato, incentivo na minha tela"*. Boas-vindas é INCENTIVO,
então a carta leva `jornada_slug` + `passo_id` e **o texto não viaja** — o sino o
busca na hora de ler, no idioma de quem lê. Inventar um assunto próprio para
boas-vindas exigiria um Rito de Contrato novo, e não é opção deste degrau.

Isto não fura a lei 1 do §3 ("aviso é DADO, nunca frase pronta"): é a mesma saída
que o `suggestion_id` usa desde 26/08. O título não viaja, a tela o busca. O que
muda é só quem guarda o texto.

**Nenhum `data` carrega PII.** Só o id opaco da plataforma e o site. Quem
precisar falar com a pessoa PERGUNTA à `identidade` na hora do envio.

O PADRÃO É COPIADO, NUNCA IMPORTADO
------------------------------------
A outbox e o relay espelham os que já rodam em `alunos`, `identidade`,
`pagamentos`, `quiz` e `checkout`. Não é falta de imaginação: um relay diferente
por célula significaria N modos de falha diferentes para o mesmo problema — e o
do `checkout` já se perdeu uma vez por um despacho fundir arquivos para caber no
orçamento. Copiar o padrão é a lei; importar o arquivo alheio seria furar a
fronteira de célula.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction

from .models import OutboxEvent

NOTIFICACAO_DEVIDA = "notificacao.devida"


class EventoForaDaTransacao(Exception):
    """`emitir()` chamado sem transação aberta — o evento não seria transacional.

    Em vez de confiar que todo ponto de emissão futuro se lembre do `atomic`, a
    própria função recusa a escrita. Um evento gravado em autocommit sobrevive ao
    rollback do fato que o justifica, e a plataforma inteira passa a acreditar em
    algo que não aconteceu — o modo de falha mais caro que uma outbox existe para
    impedir.

    Aqui isso tem um segundo dente: a carta e a linha de `Entrega` que diz "saiu"
    precisam viver ou morrer JUNTAS. Sem a transação comum, o aviso chega ao
    sininho e o motor acha que não entregou, e a passada seguinte manda de novo.
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
            "A carta tem de nascer na MESMA transação da linha de Entrega que "
            "diz que ela saiu: sem isso, o aviso chega ao aluno e o motor manda "
            "de novo na passada seguinte."
        )
    return OutboxEvent.objects.create(
        event=event,
        version=version,
        payload=data,
        envelope_extra=envelope_extra or {},
    )


def passo_de_jornada_devido(
    *,
    site_id: str,
    destinatario_id: str,
    jornada_slug: str,
    passo_id: str,
    ordem: int,
    origem_event_id: str,
) -> OutboxEvent:
    """Uma carta de um passo de sequência, endereçada a UMA pessoa.

    O leque é feito na ORIGEM (lei 3 do §3): uma carta, uma pessoa. A caixa
    central é burra de propósito, e é isso que a mantém barata — ela só escreve o
    que chega, e o custo por carta não cresce com a plateia.

    `ator_id` vai como `None` no envelope, e é declarado e não esquecido: não há
    gente causando um passo de sequência. Quem o causou foi o relógio.
    """
    return emitir(
        NOTIFICACAO_DEVIDA,
        {
            "site_id": site_id,
            "destinatario_id": destinatario_id,
            "assunto": "jornada.passo",
            "parametros": {
                "jornada_slug": jornada_slug,
                "passo_id": passo_id,
                "ordem": ordem,
            },
            "origem_event_id": origem_event_id,
        },
        envelope_extra={"ator_id": None},
    )
