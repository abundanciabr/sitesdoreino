# apps/core/fusoes.py — juntar ideias de verdade, e poder desfazer
"""A junção de ideias: prévia, fusão e desfazer.

Pedido do mantenedor em 05/09/2026: *"Coloque o botão de fundir que mostra o
modal de como ficaria se fossem fundidas, e pede a confirmação da fusão, com a
opção de desfazer tudo"*. Lei: `docs/decisoes/DECISAO-fundir-ideias.md`.

## Por que isto não existia até hoje

`Sugestao.Status.MESCLADO` existe desde o primeiro dia, e a
`ESPECIFICACAO-CELULA.md` §8 (V1.1) já escrevia o que uma junção teria de
respeitar. O que a casa fez até aqui foi **proibir fingir**: `mesclado` não
entra pela tela de status (`STATUS_QUE_A_EQUIPE_ESCOLHE` não o lista), com
teste-guarda, *"senão a lista de mescladas nasceria mentindo"*. Este módulo é a
outra metade — a operação de verdade, que torna o status honesto.

## Os três invariantes da espec, e onde cada um mora aqui

1. **Transacional.** Um `atomic` cobre tudo: mover votos, mover comentários,
   escrever o recibo, mudar o status e avisar a plateia. Falhou no meio, não
   aconteceu nada.
2. **Quem votou nas duas não vira dois votos.** O `Voto` tem
   `unique_together(sugestao, autor)`; mover cegamente estouraria. O voto
   repetido é APAGADO da absorvida e o id fica anotado em `votos_descartados`,
   que é o que permite devolvê-lo no desfazer.
3. **Comentário e histórico preservados, e a URL antiga resolvendo.** Os
   comentários mudam de ideia (com os ids anotados); o `HistoricoStatus` é
   append-only e ninguém o toca; a absorvida continua existindo, com
   `sugestao_canonica` apontando para onde ela foi.

## O que este módulo NÃO faz, e por quê

Não emite evento novo. A mudança de status já emite `sugestao.status-alterado`
e já acorda o leque de avisos de toda a plateia — quem votou na ideia absorvida
recebe a carta contando para onde ela foi. Um `sugestao.mesclada` novo, sem um
único consumidor, seria contrato a mais para não fazer nada.
"""

from datetime import datetime, timezone as tz

from django.db import transaction

from apps.sugestoes.models import (
    Comentario,
    Fusao,
    IdeiaAbsorvida,
    Sugestao,
    Voto,
)

from .moderacao import registrar_mudanca_de_status


class FusaoInvalida(Exception):
    """Recusada ANTES de qualquer escrita — recusa não precisa de rollback.

    A mensagem é em português e diz o caso, porque quem a lê é o mantenedor
    numa tela, não um programador num log.
    """


# O que impede uma junção, conferido na prévia e de novo na hora de fundir. A
# prévia mostra o impedimento em vez de esconder o botão: "não dá, e o motivo é
# este" ensina; um botão que some, não.
def _impedimento(canonica: Sugestao, absorvidas: list) -> str:
    if canonica.apagada_em or any(a.apagada_em for a in absorvidas):
        return "Ideia apagada não entra em junção: o texto dela não existe mais."
    if canonica.arquivada_em:
        return (
            "A ideia que ficaria de pé está arquivada. Desarquive antes de "
            "juntar as outras nela."
        )
    if any(a.arquivada_em for a in absorvidas):
        return (
            "Uma das ideias a juntar está arquivada. Arquivar já a tirou do "
            "quadro; juntar de novo só confundiria quem a escreveu."
        )
    if canonica.status == Sugestao.Status.MESCLADO:
        return (
            "A ideia que ficaria de pé já foi juntada a outra. Junte na ideia "
            "que está valendo, ou desfaça a junção anterior primeiro."
        )
    if any(a.status == Sugestao.Status.MESCLADO for a in absorvidas):
        return "Uma das ideias já foi juntada a outra. Desfaça aquela junção primeiro."
    if any(a.quadro_id != canonica.quadro_id for a in absorvidas):
        return "As ideias são de quadros diferentes, e juntá-las misturaria turmas."
    return ""


def _gente(sugestoes: list) -> set:
    """Quem está atrás destas ideias, cada pessoa uma vez.

    Mesma definição de `gestao.plateia_de` e de `avisos.interessados_em`: autor,
    quem votou e quem comentou. Aqui ela precisa ser a UNIÃO, e não a soma por
    ideia — a conta que a tela mostra ("depois da junção serão N pessoas") só é
    honesta se quem está nas duas contar uma vez.
    """
    ids = [s.id for s in sugestoes]
    pessoas = {s.autor_id for s in sugestoes}
    if not ids:
        return pessoas
    pessoas |= set(
        Voto.objects.filter(sugestao_id__in=ids).values_list("autor_id", flat=True)
    )
    pessoas |= set(
        Comentario.objects.filter(sugestao_id__in=ids).values_list(
            "autor_id", flat=True
        )
    )
    return pessoas


def _votantes(sugestoes: list) -> set:
    ids = [s.id for s in sugestoes]
    if not ids:
        return set()
    return set(
        Voto.objects.filter(sugestao_id__in=ids).values_list("autor_id", flat=True)
    )


def _retrato(sugestao: Sugestao) -> dict:
    return {
        "id": sugestao.id,
        "titulo": sugestao.titulo,
        "votos": sugestao.votos.count(),
        "pessoas": len(_gente([sugestao])),
        "comentarios": sugestao.comentarios.count(),
    }


def previa(*, canonica_id: int, absorvidas_ids: list) -> dict:
    """Como ficaria, sem mexer em nada.

    Só leitura, de propósito: é o que a tela mostra ANTES de perguntar "tem
    certeza?". O número que importa é `votos_depois`, e ele quase nunca é a
    soma — quem votou em duas ideias juntadas continua sendo uma pessoa com um
    voto. Mostrar a soma seria prometer uma popularidade que a junção não
    entrega, e o mantenedor descobriria isso depois de clicar.
    """
    canonica = _ideia(canonica_id)
    absorvidas = [_ideia(i) for i in dict.fromkeys(absorvidas_ids) if i != canonica_id]
    if not absorvidas:
        raise FusaoInvalida(
            "Escolha ao menos uma ideia diferente para juntar na que fica de pé."
        )

    todas = [canonica] + absorvidas
    votantes_canonica = _votantes([canonica])
    votantes_absorvidas = _votantes(absorvidas)
    votos_hoje = sum(s.votos.count() for s in todas)
    votos_depois = len(_votantes(todas))

    return {
        "canonica": _retrato(canonica),
        "absorvidas": [_retrato(s) for s in absorvidas],
        "votos_hoje": votos_hoje,
        "votos_depois": votos_depois,
        # Quantas pessoas votaram em mais de uma das ideias desta junção. É a
        # diferença entre a soma e a verdade, e a tela a diz com todas as
        # letras para o número menor não parecer um erro.
        "votos_em_comum": len(votantes_canonica & votantes_absorvidas),
        "pessoas_depois": len(_gente(todas)),
        "comentarios_depois": sum(s.comentarios.count() for s in todas),
        "impedimento": _impedimento(canonica, absorvidas),
    }


def _ideia(sugestao_id: int) -> Sugestao:
    ideia = Sugestao.objects.filter(pk=sugestao_id).first()
    if ideia is None:
        raise FusaoInvalida(f"A ideia {sugestao_id} não existe neste quadro.")
    return ideia


def fundir(*, canonica_id: int, absorvidas_ids: list, nota: str, por) -> Fusao:
    """Junta de verdade, numa transação só, e guarda o recibo do que moveu.

    A ordem das travas é por id crescente, e isso não é gosto: duas junções
    acontecendo ao mesmo tempo com as mesmas ideias em ordens opostas se
    travariam uma na outra (`ESPECIFICACAO-CELULA.md` §9 já avisava do merge
    correndo junto com um voto). Ordem estável, sem impasse.
    """
    nota = (nota or "").strip()
    with transaction.atomic():
        canonica = Sugestao.objects.select_for_update().filter(pk=canonica_id).first()
        if canonica is None:
            raise FusaoInvalida(f"A ideia {canonica_id} não existe neste quadro.")
        pedidas = sorted({i for i in absorvidas_ids if i != canonica_id})
        absorvidas = list(
            Sugestao.objects.select_for_update().filter(pk__in=pedidas).order_by("pk")
        )
        if len(absorvidas) != len(pedidas):
            achadas = {s.id for s in absorvidas}
            faltando = sorted(set(pedidas) - achadas)
            raise FusaoInvalida(
                f"Não achei a ideia {faltando[0]} neste quadro."
                if faltando
                else "Não achei uma das ideias deste pedido."
            )
        if not absorvidas:
            raise FusaoInvalida(
                "Escolha ao menos uma ideia diferente para juntar na que fica de pé."
            )
        impedimento = _impedimento(canonica, absorvidas)
        if impedimento:
            raise FusaoInvalida(impedimento)

        fusao = Fusao.objects.create(canonica=canonica, nota=nota, feita_por=por)

        for absorvida in absorvidas:
            # Relido DENTRO da transação: entre a prévia que o mantenedor viu e
            # o clique dele, alguém pode ter votado.
            ja_votaram = set(
                Voto.objects.filter(sugestao=canonica).values_list(
                    "autor_id", flat=True
                )
            )
            movidos, descartados = [], []
            for voto in Voto.objects.filter(sugestao=absorvida):
                if voto.autor_id in ja_votaram:
                    descartados.append(voto.autor_id)
                    voto.delete()
                else:
                    voto.sugestao = canonica
                    voto.save(update_fields=["sugestao"])
                    movidos.append(voto.autor_id)
                    ja_votaram.add(voto.autor_id)

            comentarios = list(
                Comentario.objects.filter(sugestao=absorvida).values_list(
                    "id", flat=True
                )
            )
            Comentario.objects.filter(id__in=comentarios).update(sugestao=canonica)

            IdeiaAbsorvida.objects.create(
                fusao=fusao,
                sugestao=absorvida,
                status_anterior=absorvida.status,
                votos_movidos=movidos,
                votos_descartados=descartados,
                comentarios_movidos=comentarios,
            )

            # A ligação que faz a URL antiga continuar resolvendo (espec §8): a
            # ideia absorvida não some, ela passa a apontar para onde foi.
            absorvida.sugestao_canonica = canonica
            absorvida.save(update_fields=["sugestao_canonica"])

            # E o status muda pelo ÚNICO caminho que escreve histórico e acorda
            # os avisos de toda a plateia. Quem votou na ideia absorvida fica
            # sabendo para onde ela foi, na mesma transação.
            registrar_mudanca_de_status(
                sugestao=absorvida,
                status_novo=Sugestao.Status.MESCLADO,
                nota=(
                    f"Juntada à ideia {canonica.id} ({canonica.titulo})."
                    + (f" {nota}" if nota else "")
                ),
                por=por,
            )

    return fusao


def desfazer(*, fusao_id: int, por) -> Fusao:
    """Devolve tudo: votos, comentários e o status de cada ideia absorvida.

    **O que a realidade não deixa devolver, e isto é honestidade e não
    descuido:** um voto movido que a pessoa TIROU depois da junção não existe
    mais para voltar, e um comentário apagado também não. O desfazer devolve o
    que ainda existe e nunca inventa linha nova por conta própria — ressuscitar
    um voto que a pessoa retirou seria votar no lugar dela.

    O voto DESCARTADO é caso diferente e é recriado: ele existia, foi esta
    operação que o apagou, e a pessoa não fez nada. `get_or_create` porque ela
    pode ter votado de novo na ideia absorvida no meio do caminho.
    """
    with transaction.atomic():
        fusao = (
            Fusao.objects.select_for_update()
            .select_related("canonica")
            .filter(pk=fusao_id)
            .first()
        )
        if fusao is None:
            raise FusaoInvalida(f"A junção {fusao_id} não existe.")
        if not fusao.em_vigor:
            raise FusaoInvalida("Esta junção já foi desfeita.")

        for absorvida in fusao.absorvidas.select_related("sugestao"):
            ideia = absorvida.sugestao
            Voto.objects.filter(
                sugestao=fusao.canonica, autor_id__in=absorvida.votos_movidos
            ).update(sugestao=ideia)
            for autor_id in absorvida.votos_descartados:
                Voto.objects.get_or_create(sugestao=ideia, autor_id=autor_id)
            Comentario.objects.filter(
                id__in=absorvida.comentarios_movidos, sugestao=fusao.canonica
            ).update(sugestao=ideia)

            ideia.sugestao_canonica = None
            ideia.save(update_fields=["sugestao_canonica"])
            registrar_mudanca_de_status(
                sugestao=ideia,
                status_novo=absorvida.status_anterior,
                nota=(
                    f"Junção desfeita: a ideia voltou a andar sozinha, com os "
                    f"votos e comentários que tinha antes de entrar na ideia "
                    f"{fusao.canonica_id}."
                ),
                por=por,
            )

        fusao.desfeita_em = datetime.now(tz=tz.utc)
        fusao.desfeita_por = por
        fusao.save(update_fields=["desfeita_em", "desfeita_por"])

    return fusao


def em_vigor(quadro) -> list:
    """As junções que ainda valem, para a tela poder oferecer o desfazer."""
    return list(
        Fusao.objects.filter(canonica__quadro=quadro, desfeita_em__isnull=True)
        .select_related("canonica")
        .prefetch_related("absorvidas__sugestao")
        .order_by("-feita_em")
    )
