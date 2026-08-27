# apps/sugestoes/eventos.py  # [RECEITA:R3 v1]
"""Os quatro fatos que a Caixa afirma — e o único lugar que monta o `data`.

Lei deste arquivo: `contracts/eventos/sugestao.*.v1.json`, congelados pelo Rito
de Contrato (RITOS.md §3, PR #128) com o mantenedor presente. Nada aqui inventa
campo, renomeia campo ou acrescenta campo "que seria útil" — divergir do
contrato é parar e avisar, nunca editar `contracts/`.

**Por que os construtores moram todos aqui, e não espalhados nas views.** O
`data` de cada evento é a superfície que as outras células vão ler por anos. Se
cada ponto de emissão montasse o seu dicionário, o dia em que o contrato ganhar
um campo seriam quatro lugares para lembrar — e o guarda
`tests/test_inv_envelope_casa_com_contrato.py` estaria conferindo quatro cópias
que envelhecem em ritmos diferentes. Aqui é um lugar só, e ele é o que o guarda
mira.

**A decisão de privacidade do mantenedor vira forma neste arquivo.** Nenhum
`data` carrega e-mail, nome, título, texto do problema ou comentário: só ids
opacos, contagem e status. É a `DECISAO-EVO-01` §3 ("o e-mail vive numa linha
só, dentro da Caixa") impressa no que sai pelo fio — e os contratos são
`additionalProperties: false` justamente para que um campo a mais não passe
despercebido. Quem precisar falar com a pessoa não resolve isso sozinho: pede à
Caixa.

**Fora daqui, de propósito:** `sugestao.mesclada`. Mesclar é V1.1 (spec §10) e o
contrato dele NÃO foi congelado — não há o que emitir.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction

from .models import OutboxEvent, Sugestao

CRIADA = "sugestao.criada"
VOTO_ADICIONADO = "sugestao.voto-adicionado"
VOTO_REMOVIDO = "sugestao.voto-removido"
STATUS_ALTERADO = "sugestao.status-alterado"
# A CARTA ENDEREÇADA (Rito de Contrato de 26/08/2026): uma pessoa a avisar,
# um evento. Genérico de propósito — matrícula e pagamento publicam o mesmo
# formato quando chegar a vez deles, sem contrato novo.
NOTIFICACAO_DEVIDA = "notificacao.devida"
ASSUNTO_STATUS_ALTERADO = "sugestao.status-alterado"


class EventoForaDaTransacao(Exception):
    """`emitir()` chamado sem transação aberta — o evento não seria transacional.

    Levantar aqui é a Lei 1 aplicada ao INV-P6: em vez de confiar que todo
    ponto de emissão futuro se lembre do `atomic`, a própria função recusa a
    escrita. Um evento gravado em autocommit sobrevive ao rollback do fato que
    o justifica, e aí a plataforma inteira passa a acreditar em algo que não
    aconteceu — o modo de falha mais caro que uma outbox existe para impedir.
    """


def emitir(
    event: str,
    data: dict[str, Any],
    *,
    version: int = 1,
    envelope_extra: dict[str, Any] | None = None,
) -> OutboxEvent:
    """[INV-P6] Grava o fato na outbox — SEMPRE dentro da transação do fato.

    Não publica nada: publicar é do relay (`apps/sugestoes/tasks.py`), depois
    do commit. Essa separação É a outbox — escrever no Redis aqui dentro
    devolveria o problema que o padrão resolve (evento publicado, transação
    revertida).
    """
    if not transaction.get_connection().in_atomic_block:
        raise EventoForaDaTransacao(
            f"emitir({event!r}) foi chamado fora de transaction.atomic(). "
            "O evento tem de nascer na MESMA transação do fato que o justifica "
            "(INV-P6): sem isso, um rollback deixa a plataforma acreditando "
            "num fato que não aconteceu."
        )
    return OutboxEvent.objects.create(
        event=event,
        version=version,
        payload=data,
        envelope_extra=envelope_extra or {},
    )


def _site_de(sugestao: Sugestao) -> str:
    """A chave de roteamento de todo evento desta plataforma (INV-P11).

    Vem do quadro, que é a fronteira de contexto da spec §5 — nunca de uma
    variável de ambiente ou de um padrão. Enquanto o CONV-SITE não chega, quem
    garante que existe UM site por requisição é o `quadro_atual()` fail-closed
    da participação; aqui só se lê o que ele já resolveu.
    """
    return sugestao.quadro.site_id


def emitir_sugestao_criada(sugestao: Sugestao) -> OutboxEvent:
    """`sugestao.criada.v1` — nasce no `create()` de `nova_sugestao`."""
    return emitir(
        CRIADA,
        {
            "site_id": _site_de(sugestao),
            # str() em todos: o contrato diz `type: string`, e a chave desta
            # célula é `BigAutoField`. Deixar o inteiro passar faria cada
            # consumidor descobrir o tipo por tentativa — e o primeiro que
            # comparasse com string leria "não existe" em silêncio.
            "suggestion_id": str(sugestao.pk),
            "quadro_id": str(sugestao.quadro_id),
            "categoria_id": str(sugestao.categoria_id),
            # Já é texto opaco: `Identidade.id` é CharField (EVO-01 §3).
            "autor_id": sugestao.autor_id,
        },
    )


def emitir_voto_adicionado(*, sugestao: Sugestao, autor_id: str) -> OutboxEvent:
    """`sugestao.voto-adicionado.v1` — `autor_id` é quem VOTOU, não quem sugeriu.

    `total_votos` é contado agora, dentro da transação, e o contrato o define
    como "DEPOIS deste voto". Contar aqui (e não deixar o consumidor somar) é o
    que faz o evento ser útil sozinho: quem monta um ranking não precisa manter
    um contador próprio nem perguntar nada de volta à Caixa.
    """
    return emitir(
        VOTO_ADICIONADO,
        {
            "site_id": _site_de(sugestao),
            "suggestion_id": str(sugestao.pk),
            "autor_id": autor_id,
            "total_votos": sugestao.votos.count(),
        },
    )


def emitir_voto_removido(*, sugestao: Sugestao, autor_id: str) -> OutboxEvent:
    """`sugestao.voto-removido.v1` — só quando uma linha REALMENTE saiu.

    Desvotar apaga a linha (spec §8); desvotar de novo apaga zero linhas e não
    é fato nenhum. Quem decide é o ponto de emissão, que só chama esta função
    se o `delete()` devolveu contagem maior que zero.
    """
    return emitir(
        VOTO_REMOVIDO,
        {
            "site_id": _site_de(sugestao),
            "suggestion_id": str(sugestao.pk),
            "autor_id": autor_id,
            "total_votos": sugestao.votos.count(),
        },
    )


class AtorSemIdDaPlataforma(Exception):
    """Quem moderou não tem id de plataforma — e o fato não pode ser afirmado.

    **Fail-closed, e a assimetria com o destinatário é deliberada.** O
    `sugestao.status-alterado.v2` declara `ator_id` OBRIGATÓRIO: um consumidor
    que não pode contar com ele não consegue endereçar ninguém, que é o problema
    inteiro (PLANO-MESTRE §2). Emitir sem o campo seria publicar um envelope que
    o próprio contrato recusa.

    A pessoa que modera **está autenticada nesta requisição**: ela acabou de
    passar pela `identidade`, que responde o `id` em toda sessão autenticada
    (`SessionFull.id`), e a porta grava esse id ao lado da linha local. Chegar
    aqui sem ele significa que algo quebrou AGORA — o caso conhecido é o
    `IntegrityError` do `_casar_com_a_plataforma` (o id já pertence a outra linha
    local, quando alguém troca de e-mail lá fora). Não é dado velho: é uma
    anomalia da requisição corrente.

    Por isso aqui é fail-closed e no DESTINATÁRIO não é: um votante pode ter
    entrado pela última vez meses atrás e nunca mais; a ausência do id dele é
    dado esperado, não requisição quebrada. Bloquear a moderação de uma ideia
    popular porque um votante antigo nunca voltou seria absurdo — e a carta dele
    é aditiva, enquanto o fato é indispensável (INV-P6: estado sem evento é
    impossível).
    """


def emitir_status_alterado(
    *,
    sugestao: Sugestao,
    status_anterior: str,
    status_novo: str,
    nota: str = "",
    ator_id: str | None,
) -> OutboxEvent:
    """`sugestao.status-alterado.v2` — o FATO, um por mudança.

    Um evento por MUDANÇA — nunca um por pessoa avisada. Quem avisa quem virou
    assunto do `notificacao.devida`, logo abaixo, por decisão do mantenedor no
    Rito de Contrato de 26/08/2026 ("uma carta por pessoa").

    `autor_da_sugestao_id` continua sendo quem SUGERIU, no id LOCAL, e continua
    aqui para quem estuda o fato dentro do mundo da Caixa (análise, gamificação).
    Ele deixou de ser o caminho para falar com alguém: quem precisa disso lê o
    `destinatario_id` da carta, que já vem no id da plataforma.

    `ator_id` é quem MODEROU, no id da plataforma. Ele passou a viajar porque a
    lei mandou GUARDAR quem mexeu (para reconstruir a história se alguém
    questionar uma decisão) — a tela do aluno continua dizendo "a equipe", e o
    `HistoricoStatus` continua guardando a auditoria interna completa.

    `nota` só entra quando existe. O contrato a tem como opcional; mandar
    `""` obrigaria todo consumidor a distinguir "sem justificativa" de
    "justificativa vazia" — dois nomes para a mesma coisa.
    """
    if not ator_id:
        raise AtorSemIdDaPlataforma(
            "a mudança de status não pode ser afirmada: quem moderou não tem "
            "`id_da_plataforma` na linha local. O contrato v2 exige `ator_id` "
            "(RITOS §3, 26/08/2026). Peça à pessoa que entre de novo pelo site — "
            "a porta grava o id na reentrada (INV-SUG11)."
        )
    data: dict[str, Any] = {
        "site_id": _site_de(sugestao),
        "suggestion_id": str(sugestao.pk),
        "autor_da_sugestao_id": sugestao.autor_id,
        "status_anterior": status_anterior,
        "status_novo": status_novo,
    }
    if nota:
        data["nota"] = nota
    # `ator_id` vai no ENVELOPE, não no `data`: qualquer célula lê "quem fez
    # isto" sem conhecer o formato do assunto (DECISAO-fase-2-do-sininho §4).
    return emitir(STATUS_ALTERADO, data, version=2, envelope_extra={"ator_id": ator_id})


def emitir_cartas_de_notificacao(
    *,
    sugestao: Sugestao,
    destinatarios: list[str],
    status_anterior: str,
    status_novo: str,
    nota: str = "",
    ator_id: str | None,
    origem_event_id: str,
) -> list[OutboxEvent]:
    """`notificacao.devida.v1` — UMA CARTA POR PESSOA, escritas em UM insert.

    Decisão do mantenedor no Rito de Contrato de 26/08/2026, contra "uma lista
    com todos os nomes num evento só": assim a lista de quem votou numa ideia
    **nunca circula** pela plataforma, e o tamanho de um evento não cresce com a
    plateia. `docs/decisoes/DECISAO-fase-2-do-sininho.md` §1.

    **`bulk_create`, e isso é desenho, não otimização** — a mesma razão do
    `avisar_os_interessados` (EVO-42): esta função roda dentro da transação que
    já segura o `SELECT … FOR UPDATE` da sugestão, e um `create()` por pessoa
    alongaria essa trava proporcionalmente ao número de votantes, que é
    justamente o número que cresce quando a Caixa dá certo. O guarda que impede
    a volta do laço é `tests/test_volume_das_cartas.py`.

    **A §5.2 da `DECISAO-notificacoes` mudou de endereço, não de exigência:** o
    fan-out em lote sai da célula que recebe e passa a acontecer aqui, na que
    publica. A caixa central, do outro lado, escreve uma linha por carta e não
    faz leque nenhum — é isso que a mantém barata com dez células publicando.

    `destinatarios` já chega filtrado: quem não tem id de plataforma não recebe
    carta (e continua recebendo o `Aviso` local, como sempre). O porquê da
    assimetria com o ator está em `AtorSemIdDaPlataforma`.
    """
    if not transaction.get_connection().in_atomic_block:
        raise EventoForaDaTransacao(
            "emitir_cartas_de_notificacao() foi chamada fora de "
            "transaction.atomic(). As cartas nascem na MESMA transação da "
            "mudança de status (INV-P6): sem isso, um rollback deixa gente "
            "avisada de algo que não aconteceu."
        )
    parametros: dict[str, Any] = {
        "suggestion_id": str(sugestao.pk),
        "status_anterior": status_anterior,
        "status_novo": status_novo,
    }
    if nota:
        parametros["nota"] = nota
    site_id = _site_de(sugestao)
    # O título da ideia NÃO viaja: uma ideia renomeada deixaria avisos antigos
    # mostrando o nome velho para sempre. A tela busca pelo `suggestion_id`.
    return OutboxEvent.objects.bulk_create(
        [
            OutboxEvent(
                event=NOTIFICACAO_DEVIDA,
                version=1,
                envelope_extra={"ator_id": ator_id},
                payload={
                    "site_id": site_id,
                    "destinatario_id": destinatario_id,
                    "assunto": ASSUNTO_STATUS_ALTERADO,
                    # cópia por carta: um dicionário compartilhado entre N linhas
                    # é uma referência só, e quem mexer numa mexe em todas.
                    "parametros": dict(parametros),
                    "origem_event_id": origem_event_id,
                },
            )
            for destinatario_id in destinatarios
        ]
    )
