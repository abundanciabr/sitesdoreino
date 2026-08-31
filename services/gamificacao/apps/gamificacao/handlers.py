"""O que a gamificação faz quando um fato do site chega.

Um handler por assunto, e quase todos fazem a MESMA coisa: entregam o envelope
ao motor. A separação existe porque é assim que a receita R4 v1 mapeia assunto
para função nas cinco células que já a rodam, e porque o dia em que um assunto
pedir tratamento próprio o lugar já existe. O `quiz.completado` já é esse dia.

ADAPTAÇÃO DESTA CÉLULA À RECEITA R4 v1, DECLARADA EM VEZ DE SILENCIOSA
-----------------------------------------------------------------------
Nas outras células o handler recebe `(data, *, ator_id)`. Aqui ele recebe o
ENVELOPE INTEIRO, e o motivo é concreto: nesta célula o `event_id` não serve só
para deduplicar a entrega — ele é COLUNA do ledger
(`Unique(origem_event_id, regra_slug, pessoa)`), e o `occurred_at` decide a que
DIA o ponto pertence, que é de onde sai a Sequência de quem não faltou. Os dois
moram no envelope, não no `data`.

A alternativa seria cada handler receber três argumentos soltos e remontar o
envelope, que é o mesmo acoplamento com mais chance de erro. A `notificacoes`
fez uma adaptação irmã (acrescentou `ator_id`) pelo mesmo tipo de razão, e a
declarou no ponto de chamada. Esta está declarada aqui e no consumidor.

**O `site_id` vem do EVENTO, não do env.** Aqui isto é diferente da porta de
máquina: o envelope de cada assunto carrega `data.site_id` por contrato, e é ele
que diz de qual escola é o fato. Ler `SITE_ID` do ambiente creditaria o aluno de
um site no perfil do outro no dia em que a plataforma servir dois — e ela já
serve.
"""

from __future__ import annotations

import logging

from .motor import aplicar

logger = logging.getLogger(__name__)


def _creditar(envelope: dict) -> None:
    """O caminho comum: acha o site no envelope e chama o motor.

    **Evento sem `site_id` não vira ponto.** Não há padrão razoável: creditar no
    "site principal" seria inventar um dono para o XP de alguém, e o dia em que
    isso acontecesse ninguém descobriria olhando a tela.
    """
    site_id = (envelope.get("data") or {}).get("site_id")
    if not site_id:
        logger.warning(
            "evento %s (%s) chegou sem site_id: nada a creditar",
            envelope.get("event_id"),
            envelope.get("event"),
        )
        return
    aplicar(envelope, site_id)


def ao_quiz_completado(envelope: dict) -> None:
    """Um quiz respondido, e o único assunto que este motor ainda NÃO credita.

    ATENÇÃO ao que este contrato não tem: id de pessoa. Ele chega por E-MAIL
    (`data.lead.email`) porque nasceu antes de a plataforma ter identidade, e
    está congelado. Enquanto esta célula não souber traduzir e-mail em id — o
    caminho previsto é `findPersonByEmail`, já congelada na `identidade`, e é
    degrau próprio —, creditar aqui seria inventar de quem é o ponto.

    **O log diz isso em vez de calar**, e é o ponto deste handler existir: a
    regra `quiz-aprovado` está semeada. Alguém a ligaria um dia, o XP não viria,
    e a busca começaria pelo lugar errado.
    """
    email = ((envelope.get("data") or {}).get("lead") or {}).get("email")
    logger.info(
        "quiz completado por %s: esta célula ainda não traduz e-mail em id de "
        "pessoa, então o XP do quiz não é creditado. O caminho previsto é "
        "findPersonByEmail, da identidade, e ele é um degrau próprio.",
        email or "(sem e-mail)",
    )


def ao_sugestao_criada(envelope: dict) -> None:
    _creditar(envelope)


def ao_voto_adicionado(envelope: dict) -> None:
    """Este assunto credita DUAS pessoas, por regras diferentes.

    Quem votou ganha pouco (`voto-dado`, beneficiário `ator`) e quem escreveu
    ganha mais (`sugestao-votada`, beneficiário `autor_do_alvo`). O motor
    resolve isso sozinho: ele busca TODAS as regras ativas deste gatilho, e cada
    uma tem o seu próprio teto diário.
    """
    _creditar(envelope)


def ao_status_alterado(envelope: dict) -> None:
    _creditar(envelope)


# O mapa que o consumidor usa. A chave é o `event` do envelope, SEM a versão —
# é assim que ele chega no stream. Quem junta evento e versão para casar com a
# regra é `motor.chave_do_evento`.
HANDLERS = {
    "quiz.completado": ao_quiz_completado,
    "sugestao.criada": ao_sugestao_criada,
    "sugestao.voto-adicionado": ao_voto_adicionado,
    "sugestao.status-alterado": ao_status_alterado,
}

# OS ASSUNTOS QUE CHEGAM E MESMO ASSIM NÃO VIRAM PONTO, declarados aqui porque é
# aqui que a decisão mora — ao lado do handler que a implementa. O valor é o
# MOTIVO, escrito para ser lido por gente: quem monta a tela de ligar e desligar
# (`apps/gamificacao/interruptores.py`) usa esta chave para avisar o mantenedor
# ANTES do clique que ligar esta regra não faria número nenhum se mexer.
#
# Sem a declaração, esse aviso teria de ser deduzido do código do handler, e os
# dois divergiriam no dia em que o quiz ganhasse a tradução de e-mail para id: a
# tela continuaria dizendo "não paga" depois de já pagar. Apagar a linha daqui é
# PARTE de fazer o quiz pagar, e é de propósito que as duas coisas ficam juntas.
NAO_CREDITAM = {
    "quiz.completado": (
        "o contrato do quiz identifica a pessoa por e-mail, e esta célula só "
        "sabe creditar id de plataforma; o caminho é findPersonByEmail, da "
        "identidade, e é degrau próprio"
    ),
}
