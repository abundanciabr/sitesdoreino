"""O motor de XP: onde um fato do site vira ponto no perfil de alguém.

**A economia é DADO, não código** (lei §10.5, e é critério de morte nº 5 se
deixar de ser). Nada aqui sabe quanto vale um quiz: quem sabe é
`RegraDePontuacao`, no banco, e ajustar a economia é UPDATE mais versão,
anunciado e nunca retroativo. Se um dia mudar um número exigir um PR, isso é
motivo de parar e reabrir a decisão com o mantenedor, não de acrescentar um
`if`.

AS QUATRO PROMESSAS QUE ESTE ARQUIVO CUMPRE
--------------------------------------------
1. **Regra desligada não paga.** Toda a economia nasce `ativa=False`
   (`semear_economia`), e ligar uma linha é decisão do mantenedor, com data e
   aviso. Um motor que ignorasse a coluna transformaria todo deploy numa
   mudança de economia que ninguém decidiu.
2. **O mesmo evento não paga duas vezes**, e quem garante isso é o
   `Unique(origem_event_id, regra_slug, pessoa)` do PostgreSQL, não uma
   conferência em Python. A chave tem as três colunas porque UM evento pode
   legitimamente creditar duas pessoas por regras distintas: quem votou e quem
   escreveu.
3. **Teto diário com decaimento.** Acima de `acoes_cheias_por_dia` ações no
   mesmo dia local, o rendimento decresce em vez de cortar seco. Cortar seco
   ensina a parar; decrescer deixa continuar valendo alguma coisa. Zero é
   "sem teto".
4. **Quarentena.** XP social nasce `pendente` com data de liberação. Se o
   conteúdo de origem for moderado, o estorno acontece ANTES de o número virar
   parte da identidade de alguém.

O QUE ESTE ARQUIVO NÃO FAZ, E POR QUÊ
--------------------------------------
**Não credita Cristais**, e a ausência é um limite medido, não esquecimento.
`RegraDePontuacao` tem uma coluna `cristais`, e o semeador a usa (uma sugestão
implementada dá 5). Mas `MovimentoDeCristais.Origem` é um vocabulário FECHADO,
com cinco origens de crédito, e nenhuma delas é "regra de pontuação": as origens
são medalha, missão, sequência, ajuda validada e correção da equipe. Creditar
por aqui exigiria acrescentar uma palavra àquele vocabulário, e aquele
vocabulário é exatamente o que o [INV-GAM1] protege ("cristais são earn-only por
construção do banco"). Mexer nele é decisão do mantenedor, não de um motor.
Enquanto ela não vier, o campo `cristais` das regras fica sem efeito, e este
parágrafo é onde a próxima sessão descobre por quê.

**Não emite carta de celebração.** É o degrau 9 da escada, e a TAR-061 já está
no balcão para ele.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Sum

from .models import (
    LancamentoDeXP,
    NivelDefinicao,
    PerfilJogador,
    Pessoa,
    RegraDePontuacao,
    dia_local_de,
)

logger = logging.getLogger(__name__)

# O DECAIMENTO, num lugar só. Depois do teto de ações cheias, cada ação seguinte
# vale metade da anterior, com piso de 1 ponto enquanto a regra pagar algo.
#
# Por que metade e não zero: zero ensina "parei de ganhar, então parei". A lei
# quer o oposto — o teto existe para o número não recompensar volume
# (`DECISAO-gamificacao.md` §8 veta "XP proporcional a volume"), não para punir
# quem estuda muito num dia. E por que piso de 1: um crédito de 0 seria uma
# linha no ledger que não muda nada, e o aluno veria "ganhou" sem ganhar.
FATOR_DE_DECAIMENTO = 2
PISO_APOS_DECAIMENTO = 1


@dataclass(frozen=True)
class Credito:
    """O que o motor decidiu para uma pessoa, antes de gravar."""

    regra: RegraDePontuacao
    pessoa_id: str
    pontos: int
    em_quarentena: bool


def chave_do_evento(envelope: dict) -> str:
    """`quiz.completado` + `version: 1` viram `quiz.completado.v1`.

    O envelope congelado separa as duas coisas (`event` e `version`), e
    `RegraDePontuacao.evento_gatilho` guarda a forma JUNTA, como está semeada e
    como um humano a lê ao cadastrar uma regra. Esta função é o único lugar da
    célula que faz essa costura: duas expressões da mesma conta divergem no
    primeiro dia em que alguém mexer numa delas, e aqui divergir significa uma
    regra parar de pagar em silêncio.
    """
    return f"{envelope['event']}.v{envelope['version']}"


def pontos_com_teto(regra: RegraDePontuacao, ja_feitas_hoje: int) -> int:
    """Quanto vale a próxima ação, dado quantas já houve hoje.

    `acoes_cheias_por_dia = 0` significa SEM teto: paga cheio sempre. É o
    default do modelo, e é o que uma regra de fato raro (uma sugestão
    implementada) quer.
    """
    if regra.acoes_cheias_por_dia == 0 or ja_feitas_hoje < regra.acoes_cheias_por_dia:
        return regra.pontos
    if regra.pontos == 0:
        return 0
    excedente = ja_feitas_hoje - regra.acoes_cheias_por_dia + 1
    valor = regra.pontos // (FATOR_DE_DECAIMENTO**excedente)
    return max(PISO_APOS_DECAIMENTO, valor)


def _pessoa_do_credito(regra: RegraDePontuacao, envelope: dict) -> str | None:
    """De quem é o ponto: de quem AGIU, ou de quem escreveu o que foi votado.

    **SÓ ID DE PLATAFORMA ENTRA AQUI, e é por isso que não há mais atalho.**
    Esta função tinha, até 31/08/2026, dois `or` que pareciam tolerância e eram
    um bug silencioso: `data.autor_id` e `data.autor_da_sugestao_id` são ids
    OPACOS LOCAIS DA CÉLULA `sugestoes` — o contrato de cada um dos três eventos
    diz isso com todas as letras ("id opaco da identidade DENTRO da celula
    sugestoes"), e a própria Caixa guarda os dois lado a lado ([INV-SUG11]:
    `Identidade.id` local e `Identidade.id_da_plataforma`), cunhados
    separadamente.

    `Pessoa` desta célula é chaveada por `id_da_plataforma`, e é esse o id que
    `apps/core/sessao.py::quem_e` devolve para a tela do aluno. Creditar o id
    local criava uma `Pessoa` FANTASMA: o ledger enchia, nada estourava, e o
    número na tela de quem trabalhou continuava zero. Nenhum teste pegava,
    porque os testes montavam um envelope com `ator_id` — que os contratos de
    `sugestao.criada.v1` e `sugestao.voto-adicionado.v1` nem permitiam
    (`additionalProperties: false`).

    **Ausente devolve `None` e o crédito não acontece**, com o motivo no log. É
    fail-closed de propósito, e tem de ser: o `id_da_plataforma` é `null=True`
    na Caixa por decisão dela ("nada disto pode recusar ninguém"), então o campo
    é OPCIONAL no contrato e um dia vai faltar. Não pagar é recuperável — o
    evento fica no log e a regra pode ser reprocessada. Pagar ao fantasma não é:
    ninguém descobre olhando a tela.
    """
    data = envelope.get("data") or {}
    if regra.beneficiario == RegraDePontuacao.Beneficiario.ATOR:
        # O `ator_id` do ENVELOPE é o lugar canônico do id de plataforma desde o
        # Rito de 26/08/2026 (PLANO-MESTRE das notificações §2).
        return envelope.get("ator_id") or None
    return data.get("autor_da_sugestao_id_da_plataforma") or None


def creditos_de(envelope: dict, site_id: str) -> list[Credito]:
    """As regras ATIVAS que este evento aciona, já com os pontos calculados.

    Uma lista porque um evento credita mais de uma pessoa: `voto-adicionado`
    paga quem votou (`ator`) e quem escreveu (`autor_do_alvo`), por regras
    diferentes, com tetos diferentes.
    """
    chave = chave_do_evento(envelope)
    quando = _quando(envelope)
    # NUNCA RETROATIVO (lei §10.5), e agora com mecanismo. Ligar uma regra hoje
    # não pode pagar o que aconteceu ontem: o `vigente_desde__lte` compara o
    # instante do FATO (`occurred_at`, não o da entrega) com a data em que a
    # regra passou a valer. Sem esta linha, um evento reentregue — ou uma fila
    # represada, ou um `XAUTOCLAIM` do lote de reentrega — pagaria semanas de
    # passado no segundo em que o mantenedor clicasse em "ligar", e o aluno
    # veria um número saltar sem ter feito nada.
    regras = RegraDePontuacao.objects.filter(
        site_id=site_id,
        evento_gatilho=chave,
        ativa=True,
        vigente_desde__isnull=False,
        vigente_desde__lte=quando,
    )

    dia = dia_local_de(quando)
    creditos = []
    for regra in regras:
        pessoa_id = _pessoa_do_credito(regra, envelope)
        if not pessoa_id:
            logger.warning(
                "regra %s não achou o beneficiário (%s) no evento %s",
                regra.slug,
                regra.beneficiario,
                envelope.get("event_id"),
            )
            continue
        ja_feitas = (
            LancamentoDeXP.objects.filter(
                pessoa_id=pessoa_id,
                site_id=site_id,
                regra_slug=regra.slug,
                dia_local=dia,
            )
            .exclude(status=LancamentoDeXP.Status.ESTORNADO)
            .count()
        )
        creditos.append(
            Credito(
                regra=regra,
                pessoa_id=pessoa_id,
                pontos=pontos_com_teto(regra, ja_feitas),
                em_quarentena=regra.quarentena_horas > 0,
            )
        )
    return creditos


def aplicar(envelope: dict, site_id: str) -> list[LancamentoDeXP]:
    """O caminho inteiro: evento entra, lançamentos saem, perfis atualizados.

    Cada crédito é gravado no SEU savepoint. Um `IntegrityError` de reentrega
    (a chave única do ledger) pula aquele crédito e deixa os outros passarem —
    sem savepoint próprio, o erro marcaria a transação inteira como abortada e a
    consulta seguinte estouraria `TransactionManagementError` em vez de o
    crédito ser simplesmente ignorado (§4.8 das armadilhas).
    """
    quando = _quando(envelope)
    dia = dia_local_de(quando)
    gravados = []

    for credito in creditos_de(envelope, site_id):
        pessoa, _ = Pessoa.objects.get_or_create(
            id_da_plataforma=credito.pessoa_id,
            defaults={"email": f"{credito.pessoa_id}@desconhecido.invalid"},
        )
        try:
            with transaction.atomic():
                lancamento = LancamentoDeXP.objects.create(
                    pessoa=pessoa,
                    site_id=site_id,
                    pontos=credito.pontos,
                    origem_event_id=str(envelope["event_id"]),
                    regra_slug=credito.regra.slug,
                    # A VERSÃO da regra no instante do crédito. Sem ela, mudar a
                    # economia reescreveria o passado.
                    regra_versao=credito.regra.versao,
                    occurred_at=quando,
                    dia_local=dia,
                    status=(
                        LancamentoDeXP.Status.PENDENTE
                        if credito.em_quarentena
                        else LancamentoDeXP.Status.DEFINITIVO
                    ),
                    liberado_em=(
                        quando + timedelta(hours=credito.regra.quarentena_horas)
                        if credito.em_quarentena
                        else None
                    ),
                )
        except IntegrityError:
            # Reentrega. O banco recusou, e recusar é o comportamento correto.
            logger.info(
                "evento %s já havia creditado %s por %s",
                envelope.get("event_id"),
                credito.pessoa_id,
                credito.regra.slug,
            )
            continue

        gravados.append(lancamento)
        recalcular(pessoa.id_da_plataforma, site_id)

    return gravados


def recalcular(pessoa_id: str, site_id: str) -> PerfilJogador:
    """Soma o ledger e reescreve os números do perfil.

    O `PerfilJogador` é cópia DESNORMALIZADA: a fonte da verdade é
    `LancamentoDeXP`, e é ela que esta função soma. Só o que está DEFINITIVO
    conta — o que está em quarentena ainda pode virar estorno, e mostrar um
    número que pode cair é pior que mostrá-lo alguns minutos depois.
    """
    with transaction.atomic():
        pessoa, _ = Pessoa.objects.get_or_create(
            id_da_plataforma=pessoa_id,
            defaults={"email": f"{pessoa_id}@desconhecido.invalid"},
        )
        perfil, _ = PerfilJogador.objects.select_for_update().get_or_create(
            pessoa=pessoa, site_id=site_id
        )
        total = (
            LancamentoDeXP.objects.filter(
                pessoa=pessoa,
                site_id=site_id,
                status=LancamentoDeXP.Status.DEFINITIVO,
            ).aggregate(soma=Sum("pontos"))["soma"]
            or 0
        )
        # O ledger tem lançamentos negativos (estorno é linha nova, nunca
        # apagar). O perfil guarda um `PositiveIntegerField`: um saldo negativo
        # é impossível de exibir e seria recusado pelo banco.
        perfil.xp_total = max(0, total)
        perfil.nivel = nivel_para(perfil.xp_total, site_id)
        perfil.save(update_fields=["xp_total", "nivel", "atualizado_em"])
    return perfil


def nivel_para(xp: int, site_id: str) -> int:
    """O degrau que este XP alcança, entre os níveis ATIVOS.

    Sem nenhum degrau ativo, a resposta é 1: a economia nasce desligada, e um
    perfil precisa de um número para existir. Nunca 0 — o banco recusa
    (`nivel_comeca_em_um`).
    """
    alcancados = NivelDefinicao.objects.filter(
        site_id=site_id, ativa=True, xp_necessario__lte=xp
    ).order_by("-nivel")
    degrau = alcancados.first()
    return degrau.nivel if degrau else 1


def _quando(envelope: dict):
    """O instante do FATO, não o da entrega.

    `occurred_at` vem do envelope congelado e é o que manda: uma reentrega horas
    depois não pode mudar o dia a que o ponto pertence, porque é desse dia que
    sai a Sequência de quem não faltou (`armadilhas/099`).
    """
    from django.utils.dateparse import parse_datetime

    bruto = envelope["occurred_at"]
    return parse_datetime(bruto) if isinstance(bruto, str) else bruto
