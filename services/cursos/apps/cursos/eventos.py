# apps/cursos/eventos.py  # [RECEITA:R3 v1]
"""Os fatos que a sala de aula afirma ao resto da plataforma, e o único lugar
que monta o `data` de cada um.

Lei deste arquivo: `contracts/eventos/envio.recebido.v1.json`,
`contracts/eventos/revisao.prazo-estourado.v1.json` e, desde o degrau 2.2
(TAR-156), `contracts/eventos/laudo.emitido.v1.json`,
`contracts/eventos/aula.concluida.v1.json` e
`contracts/eventos/checkpoint.devolvido.v1.json` — os três do laudo JÁ
NASCERAM CONGELADOS na gênese da célula, e este arquivo é quem os emite pela
primeira vez. Congelados pelo Rito de Contrato com o mantenedor presente
(`PLANO-CELULA-CURSOS.md` §5). Nada aqui inventa campo, renomeia campo ou
acrescenta campo "que seria útil": divergir do contrato é parar e avisar,
nunca editar `contracts/`.

**Por que os construtores moram todos aqui, e não espalhados no serviço.** O
`data` de cada evento é a superfície que as outras células vão ler por anos. Um
lugar só é o que o guarda `tests/test_outbox_e_eventos.py` mira quando valida o
envelope real contra o JSON Schema do contrato.

**Só ids opacos viajam.** Nenhum `data` carrega link, README, texto da
autoavaliação, e-mail nem nome: os contratos são `additionalProperties: false`
justamente para que um campo a mais não passe despercebido. Quem precisar do
detalhe pergunta a esta célula na hora de mostrar.

Molde: `services/sugestoes/apps/sugestoes/eventos.py`, copiado e nunca importado
(Lei 7). A diferença que importa: aqui `emitir()` já pendura o relay no commit
da transação, porque todo ponto de emissão desta célula quer exatamente isso, e
um ponto novo que esquecesse o `on_commit` deixaria o evento esperando o
batimento de um minuto sem ninguém perceber.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction

from . import tasks
from .models import Aula, Envio, Laudo, OutboxEvent

ENVIO_RECEBIDO = "envio.recebido"
PRAZO_ESTOURADO = "revisao.prazo-estourado"
LAUDO_EMITIDO = "laudo.emitido"
AULA_CONCLUIDA = "aula.concluida"
CHECKPOINT_DEVOLVIDO = "checkpoint.devolvido"


class EventoForaDaTransacao(Exception):
    """`emitir()` chamado sem transação aberta: o evento não seria transacional.

    Levantar aqui é a Lei 1 aplicada ao INV-P6: em vez de confiar que todo
    ponto de emissão futuro se lembre do `atomic`, a própria função recusa a
    escrita. Um evento gravado em autocommit sobrevive ao rollback do fato que
    o justifica, e aí a plataforma inteira passa a acreditar em algo que não
    aconteceu, o modo de falha mais caro que uma outbox existe para impedir.
    """


def emitir(
    event: str,
    data: dict[str, Any],
    *,
    version: int = 1,
    envelope_extra: dict[str, Any] | None = None,
) -> OutboxEvent:
    """[INV-P6] Grava o fato na outbox, SEMPRE dentro da transação do fato.

    Não publica nada: publicar é do relay (`apps/cursos/tasks.py`), depois do
    commit. Essa separação É a outbox: escrever no Redis aqui dentro devolveria
    o problema que o padrão resolve (evento publicado, transação revertida).
    """
    if not transaction.get_connection().in_atomic_block:
        raise EventoForaDaTransacao(
            f"emitir({event!r}) foi chamado fora de transaction.atomic(). "
            "O evento tem de nascer na MESMA transação do fato que o justifica "
            "(INV-P6): sem isso, um rollback deixa a plataforma acreditando "
            "num fato que não aconteceu."
        )
    evento = OutboxEvent.objects.create(
        event=event,
        version=version,
        payload=data,
        envelope_extra=envelope_extra or {},
    )
    transaction.on_commit(tasks.relay_apos_commit)
    return evento


def emitir_envio_recebido(envio: Envio) -> OutboxEvent:
    """`envio.recebido.v1`: nasce no `create()` de `envio.entregar`.

    `ator_id` é o aluno, no ENVELOPE e não no `data`: é o único lugar em que
    ele viaja, e o contrato diz `type: string`, nunca nulo. É o id da
    PLATAFORMA (`Pessoa.id_da_plataforma`, a chave primária do espelho), e não
    um id local desta célula: quem consome credita a pessoa certa
    (`armadilhas/255`).
    """
    return emitir(
        ENVIO_RECEBIDO,
        {
            "site_id": envio.aula.curso.site_id,
            # str() em todos: o contrato diz `type: string`, e as chaves desta
            # célula são `BigAutoField`. Deixar o inteiro passar faria cada
            # consumidor descobrir o tipo por tentativa.
            "curso_id": str(envio.aula.curso_id),
            "aula_id": str(envio.aula_id),
            "envio_id": str(envio.pk),
            "numero": envio.numero,
        },
        envelope_extra={"ator_id": envio.pessoa_id},
    )


def emitir_prazo_estourado(envio: Envio, *, horas_de_atraso: int) -> OutboxEvent:
    """`revisao.prazo-estourado.v1`: nasce em `envio.registrar_estouros`.

    `ator_id` é `null`, PRESENTE: quem emite é o relógio, não uma pessoa, e o
    contrato declara a chave obrigatória e nulável. `{"ator_id": None}` aqui
    não é descuido; é a chave que o consumidor espera encontrar.
    """
    return emitir(
        PRAZO_ESTOURADO,
        {
            "site_id": envio.aula.curso.site_id,
            "envio_id": str(envio.pk),
            "horas_de_atraso": horas_de_atraso,
        },
        envelope_extra={"ator_id": None},
    )


def emitir_laudo_emitido(laudo: Laudo) -> OutboxEvent:
    """`laudo.emitido.v1`: nasce em `apps/cursos/laudo.py::emitir`, sempre.

    `ator_id` é quem ASSINOU o laudo (`laudo.avaliador_id`), nunca a IA
    (`PLANO-CELULA-CURSOS.md` §7, [INV-CUR-L4]): o Assistente de laudo só
    prepara, e nada que ele produz chega a este envelope.
    """
    envio = laudo.envio
    return emitir(
        LAUDO_EMITIDO,
        {
            "site_id": envio.aula.curso.site_id,
            "envio_id": str(envio.pk),
            "laudo_id": str(laudo.pk),
            "decisao": laudo.decisao,
            "avaliador_papel": laudo.papel,
        },
        envelope_extra={"ator_id": laudo.avaliador_id},
    )


def emitir_aula_concluida(aula: Aula, *, ator_id: str) -> OutboxEvent:
    """`aula.concluida.v1`: nasce em `apps/cursos/laudo.py::emitir`, só quando a
    decisão é `aberto` ou `aberto_com_ajuste` ([INV-CUR-P2]: a porta só abre
    por laudo, nunca por data, XP ou pagamento). `ator_id` é o ALUNO, o único
    lugar em que ele viaja neste evento — é a quem a gamificação credita."""
    return emitir(
        AULA_CONCLUIDA,
        {
            "site_id": aula.curso.site_id,
            "curso_id": str(aula.curso_id),
            "aula_id": str(aula.pk),
            "e_boss": aula.e_boss,
        },
        envelope_extra={"ator_id": ator_id},
    )


def emitir_checkpoint_devolvido(laudo: Laudo) -> OutboxEvent:
    """`checkpoint.devolvido.v1`: nasce em `apps/cursos/laudo.py::emitir`, só
    quando a decisão é `devolvido`. `data_de_retorno` é sempre amanhã ou
    depois no dia de São Paulo ([INV-CUR-L1]), garantido pelo serviço antes de
    chegar aqui."""
    envio = laudo.envio
    return emitir(
        CHECKPOINT_DEVOLVIDO,
        {
            "site_id": envio.aula.curso.site_id,
            "aula_id": str(envio.aula_id),
            "envio_id": str(envio.pk),
            "data_de_retorno": laudo.data_de_retorno.isoformat(),
        },
        envelope_extra={"ator_id": laudo.avaliador_id},
    )
