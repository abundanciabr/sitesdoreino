"""Os interruptores da economia: ligar e desligar cada regra, como DADO.

Este módulo existe por causa do critério de morte nº 5 da lei
(`DECISAO-gamificacao.md` §10.5): *"ajustar a economia passar a exigir PR de
código"* é motivo de parar e reabrir a decisão com o mantenedor. Enquanto ligar
uma regra dependesse de um agente editar `semear_economia.py` e esperar um
deploy, a economia era código com aparência de dado. Aqui ela vira dado de
verdade: `UPDATE` numa linha, com versão, com data, anunciado.

AS TRÊS COISAS QUE `mudar()` FAZ JUNTAS, E POR QUE AS TRÊS
-----------------------------------------------------------
1. **`ativa`** — o que o motor lê para decidir se paga (`motor.creditos_de`).
2. **`versao` +1** — a lei manda ("UPDATE + versão"), e o motor GRAVA a versão
   dentro de cada lançamento. É o que faz mudar a economia amanhã não reescrever
   o passado: um ponto pago hoje continua sabendo por qual versão da regra foi
   pago.
3. **`vigente_desde = agora`** — a metade da lei que não tinha mecanismo até
   31/08/2026. "Nunca retroativo" era só uma frase; agora é uma coluna que o
   motor compara com o instante do FATO. Ligar hoje não paga o que aconteceu
   ontem, nem quando a fila estava represada, nem quando um evento é reentregue.

**Ligar de novo redefine a data.** Desligar e religar não paga a janela em que a
regra esteve desligada — seria retroatividade entrando pela porta dos fundos.

**Chamada que não muda nada não gasta versão.** Dois cliques no mesmo botão (ou
um navegador que reenvia o POST) devolvem a linha como está. Sem isto, a versão
inflaria sozinha e o histórico contaria mudanças que ninguém fez.

O QUE ESTE MÓDULO NÃO FAZ: DECIDIR QUEM PODE
---------------------------------------------
Nada aqui pergunta quem está chamando. Esta célula **não assina sessão**
([INV-P12]) e o `papel` que a `identidade` devolve **nunca autoriza rota** — é o
invariante "reconhecer não é autorizar" da `DECISAO-onde-mora-a-sessao` §4. Quem
autoriza é a célula DONA da tela, sobre a lista DELA: a `admin`, que já guarda o
crachá do mantenedor e já faz isso para `/admin/menu/`. Aqui a porta se fecha no
Bearer do par, como todas as outras desta célula.
"""

from __future__ import annotations

import logging

from django.db import transaction

from .models import RegraDePontuacao

logger = logging.getLogger(__name__)


class RegraDesconhecida(LookupError):
    """Não existe regra com esse slug NESTE site. Vira 404 na porta."""


# ---------------------------------------------------------------------------
# Os impedimentos — por que ligar esta regra não faria nada
# ---------------------------------------------------------------------------
# VOCABULÁRIO FECHADO, e é slug porque o contrato desta célula manda: "slug,
# nunca frase pronta" (invariante 3). Quem escreve a frase em português é a tela
# da `admin`; o site serve três idiomas e uma frase que sai daqui congela o
# idioma de quem a escreveu.
#
# ISTO EXISTE PARA UMA FALHA ESPECÍFICA, e ela quase aconteceu em 31/08/2026: o
# mantenedor ligaria a primeira regra para "ver o número mexer", o número ficaria
# zero, e não haveria NADA na tela dizendo por quê. Um zero sem explicação parece
# defeito da tela — e a busca começaria pelo lugar errado, que é exatamente o que
# o handler do quiz já evita escrevendo o motivo no log.
SEM_PRODUTOR = "sem-produtor"
SEM_CREDITO = "sem-credito"
CRISTAIS_SEM_EFEITO = "cristais-sem-efeito"


# Os assuntos que ALGUÉM publica hoje. É a mesma lista que o consumidor assina
# (`apps/eventos/.../consume_eventos.py::STREAMS`), e ela é IMPORTADA de lá em
# vez de recopiada: duas listas da mesma verdade divergem no primeiro dia em que
# alguém mexe numa delas, e divergir aqui significa a tela do mantenedor mentir
# sobre o que está ligado de verdade. É a lei anti-duplicação do `CLAUDE.md`.
def _assuntos_entregues() -> set[str]:
    from apps.eventos.management.commands.consume_eventos import STREAMS

    return {nome.removeprefix("eventos.") for nome in STREAMS}


def _assuntos_que_nao_creditam() -> set[str]:
    """Os assuntos que CHEGAM e mesmo assim não viram ponto.

    Hoje é só o `quiz.completado`: o contrato dele identifica a pessoa por
    e-mail, não por id de plataforma, e inventar de quem é o ponto seria pior
    que não pagá-lo. O fato é DECLARADO em `handlers.py`, ao lado do handler que
    não credita — e não deduzido aqui — para que os dois não possam divergir no
    dia em que o quiz ganhar a tradução de e-mail para id.
    """
    from .handlers import NAO_CREDITAM

    return set(NAO_CREDITAM)


def impedimentos_de(regra: RegraDePontuacao) -> list[str]:
    """O que impede ESTA regra de pagar, mesmo ligada. Vazio = nada impede."""
    assunto = regra.evento_gatilho.rsplit(".v", 1)[0]
    achados = []
    if assunto not in _assuntos_entregues():
        achados.append(SEM_PRODUTOR)
    elif assunto in _assuntos_que_nao_creditam():
        achados.append(SEM_CREDITO)
    if regra.cristais > 0:
        # O motor não credita Cristais, e a ausência é decisão do mantenedor,
        # não esquecimento: `MovimentoDeCristais.Origem` é vocabulário FECHADO e
        # nenhuma das cinco origens é "regra de pontuação". Acrescentar uma é
        # mexer no que o [INV-GAM1] protege ("Cristais são earn-only por
        # construção do banco"). Ligar a regra paga o XP e NÃO paga os Cristais
        # — e a tela precisa dizer isso antes do clique, não depois.
        achados.append(CRISTAIS_SEM_EFEITO)
    return achados


# ---------------------------------------------------------------------------
# Ler e mudar
# ---------------------------------------------------------------------------
def listar(site_id: str) -> list[RegraDePontuacao]:
    """Todas as regras deste site, ligadas e desligadas, em ordem estável."""
    return list(RegraDePontuacao.objects.filter(site_id=site_id).order_by("slug"))


def mudar(*, site_id: str, slug: str, ativa: bool, agora) -> RegraDePontuacao:
    """Liga ou desliga UMA regra. Devolve a linha como ela ficou.

    `agora` entra como argumento em vez de ser lido aqui dentro para que o teste
    possa provar a recusa do retroativo sem depender do relógio da máquina.
    """
    with transaction.atomic():
        try:
            regra = RegraDePontuacao.objects.select_for_update().get(
                site_id=site_id, slug=slug
            )
        except RegraDePontuacao.DoesNotExist as erro:
            raise RegraDesconhecida(
                f"não há regra {slug!r} no site {site_id!r}"
            ) from erro

        if regra.ativa == ativa:
            return regra

        regra.ativa = ativa
        regra.versao += 1
        if ativa:
            regra.vigente_desde = agora
        regra.save(update_fields=["ativa", "versao", "vigente_desde", "atualizada_em"])

    # O ANÚNCIO que a lei pede, na parte que cabe a esta célula: o log diz o quê,
    # quando e a partir de quando vale. Quem registra QUEM mexeu é a `admin`, que
    # é quem conhece a pessoa — o mesmo fato não mora em dois lugares.
    logger.info(
        "economia: regra %s do site %s ficou %s (versao %s, vigente desde %s)",
        regra.slug,
        site_id,
        "LIGADA" if ativa else "desligada",
        regra.versao,
        regra.vigente_desde.isoformat() if regra.vigente_desde else "-",
    )
    return regra
