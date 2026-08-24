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


class EventoForaDaTransacao(Exception):
    """`emitir()` chamado sem transação aberta — o evento não seria transacional.

    Levantar aqui é a Lei 1 aplicada ao INV-P6: em vez de confiar que todo
    ponto de emissão futuro se lembre do `atomic`, a própria função recusa a
    escrita. Um evento gravado em autocommit sobrevive ao rollback do fato que
    o justifica, e aí a plataforma inteira passa a acreditar em algo que não
    aconteceu — o modo de falha mais caro que uma outbox existe para impedir.
    """


def emitir(event: str, data: dict[str, Any], *, version: int = 1) -> OutboxEvent:
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
    return OutboxEvent.objects.create(event=event, version=version, payload=data)


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


def emitir_status_alterado(
    *, sugestao: Sugestao, status_anterior: str, status_novo: str, nota: str = ""
) -> OutboxEvent:
    """`sugestao.status-alterado.v1` — o fato que o aviso do aluno (EVO-21) lê.

    `autor_da_sugestao_id` é quem SUGERIU (não quem moderou): o consumidor
    deste evento precisa saber a quem avisar. Quem moderou fica no
    `HistoricoStatus`, dentro da Caixa, porque é auditoria interna e não
    interessa a ninguém de fora.

    `nota` só entra quando existe. O contrato a tem como opcional; mandar
    `""` obrigaria todo consumidor a distinguir "sem justificativa" de
    "justificativa vazia" — dois nomes para a mesma coisa.
    """
    data: dict[str, Any] = {
        "site_id": _site_de(sugestao),
        "suggestion_id": str(sugestao.pk),
        "autor_da_sugestao_id": sugestao.autor_id,
        "status_anterior": status_anterior,
        "status_novo": status_novo,
    }
    if nota:
        data["nota"] = nota
    return emitir(STATUS_ALTERADO, data)
