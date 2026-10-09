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

from .criterios import avaliar
from .models import (
    AjudaAceita,
    Concessao,
    ConquistaDefinicao,
    ConversaAberta,
    EntregaAceita,
    Pessoa,
)
from .motor import _quando, aplicar
from .validacao import conceder

logger = logging.getLogger(__name__)

#: O marco da trilha que o selo do portfólio acende. O slug é o mesmo que
#: `semear_economia.CONQUISTAS` planta, e quem impede os dois de divergirem é
#: `tests/test_o_marco_do_portfolio.py`, que procura no banco a linha semeada
#: por este nome.
MARCO_DO_PORTFOLIO = "portfolio-publicado"
CONQUISTA_DO_BOSS = "boss-do-modulo"


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
# ---------------------------------------------------------------------------
# O FÓRUM (degrau 17, 01/09/2026) — o que acontece lá dentro vira ponto aqui
# ---------------------------------------------------------------------------
# O fórum estava no ar e era MUDO para esta célula. Estes handlers são a outra
# metade da ponte: ele fala, ela escuta.


def ao_forum_topico_criado(envelope: dict) -> None:
    """Alguém abriu uma conversa. Paga a quem abriu, com teto e quarentena.

    DUAS COISAS ACONTECEM AQUI, e elas são independentes de propósito — é a
    mesma separação de `ao_forum_resposta_aceita`, pela mesma razão:

    1. **O XP**, pela regra de pontuação, que o mantenedor liga e desliga.
    2. **O REGISTRO de quem abriu** (`ConversaAberta`), que é de onde os
       Destaques da semana tiram o endereço da carta de parabéns. Ele acontece
       MESMO COM A REGRA DESLIGADA, e hoje a economia inteira está desligada:
       amarrar o registro ao crédito faria a tabela nascer vazia e o Destaque
       nascer morto.

    **Por que o registro precisa existir:** quando alguém da equipe escolhe um
    trabalho para destacar, ele o vê pelo fórum (`listRecentTopics`), que devolve
    o TÍTULO e o NOME DE EXIBIÇÃO do autor. Nome de exibição não endereça carta
    nenhuma, e o id opaco de quem abriu só existe aqui, no `ator_id` do envelope.
    Antes de 02/09/2026 ele chegava e era jogado fora.
    """
    _registrar_a_conversa(envelope)
    _creditar(envelope)


def _registrar_a_conversa(envelope: dict) -> None:
    """Grava de quem é esta conversa, uma vez por tópico. Nunca inventa dono.

    Idempotente pelo par (site, tópico): o mesmo evento reentregue pelo relay
    não vira uma segunda linha, porque uma discussão é aberta uma vez, por uma
    pessoa. O `site_id` entra na chave porque o id do tópico é do fórum daquela
    escola — o tópico 7 de duas escolas são duas conversas.

    **Envelope sem `ator_id` não vira linha.** O contrato do evento o declara
    obrigatório e não anulável ("tópico do fórum sempre tem gente atrás"), mas
    quem consome fato de outra célula não confia na promessa: um envelope torto
    que virasse linha atribuiria a conversa a um dono inventado, e a carta de
    parabéns iria para a pessoa errada — ou para ninguém, com a tela afirmando o
    contrário.
    """
    data = envelope.get("data") or {}
    site_id = data.get("site_id")
    topico_id = data.get("topico_id")
    autor = envelope.get("ator_id")
    if not (site_id and topico_id and autor):
        logger.warning(
            "tópico criado %s chegou sem site, tópico ou autor: não registro",
            envelope.get("event_id"),
        )
        return

    pessoa, _ = Pessoa.objects.get_or_create(
        id_da_plataforma=autor,
        defaults={"email": f"{autor}@desconhecido.invalid"},
    )
    ConversaAberta.objects.get_or_create(
        site_id=site_id,
        topico_id=str(topico_id),
        defaults={"pessoa": pessoa, "occurred_at": _quando(envelope)},
    )


def ao_forum_mensagem_criada(envelope: dict) -> None:
    """Alguém falou.

    O envelope traz `caracteres` e NÃO traz o texto — decisão da Sessão B. Este
    handler não usa o tamanho hoje; quem o usará é o teto anti-spam, quando ele
    passar a olhar volume em vez de contagem.
    """
    _creditar(envelope)


def ao_forum_resposta_aceita(envelope: dict) -> None:
    """A resposta que resolveu a dúvida. É o fato mais valioso do sistema.

    DUAS COISAS ACONTECEM AQUI, e elas são independentes de propósito:

    1. **O XP**, pela regra de pontuação — que o mantenedor liga e desliga.
    2. **O REGISTRO da ajuda** (`AjudaAceita`), que é o que a medalha "Mão amiga"
       conta. Ele acontece MESMO COM A REGRA DESLIGADA: reconhecimento é uma
       coisa, pagamento é outra, e amarrar os dois faria a medalha sumir junto
       com a regra num dia em que o mantenedor a desligasse por uma semana.

    O crédito vai para quem ESCREVEU (`autor_da_resposta_id`), não para quem
    marcou (`ator_id` do envelope) — são pessoas diferentes, e o contrato carrega
    os dois exatamente para que ninguém confunda.

    **A avaliação das medalhas roda aqui, depois do registro** (27/09/2026). Sem
    ela, só o crédito de XP chamava `avaliar` (por `motor.recalcular`), e com a
    regra desligada a "Primeira ajuda aceita" e a "Mão amiga" nunca caíam pelo
    fato: esperavam alguém rodar a conta à mão.
    """
    ajuda = _registrar_a_ajuda(envelope)
    _creditar(envelope)
    if ajuda is not None:
        avaliar(
            ajuda.pessoa_id,
            ajuda.site_id,
            origem_event_id=str(envelope.get("event_id") or ""),
        )


def _registrar_a_ajuda(envelope: dict) -> AjudaAceita | None:
    """Grava a ajuda aceita, uma vez por mensagem. Nunca derruba o crédito.

    Idempotente pelo par (pessoa, mensagem): marcar, desmarcar e remarcar conta
    UMA vez. Se a chave fosse o evento, dois amigos alternando a marca
    fabricariam a medalha em minutos. Devolve a linha, ou `None` quando o
    envelope não diz de quem é a ajuda.
    """
    data = envelope.get("data") or {}
    site_id = data.get("site_id")
    autor = data.get("autor_da_resposta_id")
    mensagem_id = data.get("mensagem_id")
    if not (site_id and autor and mensagem_id):
        logger.warning(
            "resposta aceita %s chegou sem site, autor ou mensagem: não registro",
            envelope.get("event_id"),
        )
        return None

    pessoa, _ = Pessoa.objects.get_or_create(
        id_da_plataforma=autor,
        defaults={"email": f"{autor}@desconhecido.invalid"},
    )
    ajuda, _ = AjudaAceita.objects.get_or_create(
        pessoa=pessoa,
        site_id=site_id,
        mensagem_id=str(mensagem_id),
        defaults={
            "topico_id": str(data.get("topico_id") or ""),
            "marcada_por": str(data.get("marcada_por") or ""),
            "quem_marcou": str(envelope.get("ator_id") or ""),
            "occurred_at": _quando(envelope),
        },
    )
    return ajuda


# ---------------------------------------------------------------------------
# A SALA DE AULA (degrau 2.5, 05/09/2026) — a porta que abre vira ponto aqui
# ---------------------------------------------------------------------------


def ao_aula_concluida(envelope: dict) -> None:
    """A porta de uma aula abriu para o aluno: um laudo aceitou a entrega.

    É o fato que a lei desta célula chamava de tomada futura ("entregar dá XP,
    aprovar dá porta"), e ele chega pronto para o motor: o `ator_id` do envelope
    é o id de PLATAFORMA do aluno (o contrato o declara obrigatório, e nunca
    e-mail), e a regra `aula-concluida` tem beneficiário `ator`. A direção
    importa: a célula LÊ que a porta abriu. Nada aqui decide se alguém pode
    assistir a coisa alguma, e é isso que o terceiro invariante protege.

    `data.e_boss` chega `true` quando a aula fecha um módulo. O XP continua
    sendo o da aula, sem bônus. Quando a conquista concreta estiver ligada,
    este mesmo fato concede o reconhecimento privado do Boss; não é critério
    genérico, não abre aula e não altera a progressão.

    **A entrega aceita fica REGISTRADA com a economia desligada**
    (`EntregaAceita`, 27/09/2026), e as medalhas são avaliadas em seguida: é o
    que faz o "Primeiro ciclo concluído" cair pelo próprio fato, pela mesma
    separação de `ao_forum_resposta_aceita` entre reconhecer e pagar.
    """
    entrega = _registrar_a_entrega(envelope)
    _creditar(envelope)
    if (envelope.get("data") or {}).get("e_boss") is True:
        _conceder_boss(envelope)
    if entrega is not None:
        avaliar(
            entrega.pessoa_id,
            entrega.site_id,
            origem_event_id=entrega.origem_event_id,
        )


def _registrar_a_entrega(envelope: dict) -> EntregaAceita | None:
    """Grava a entrega aceita, uma vez por evento. Nunca inventa aluno.

    Idempotente pelo `event_id`: o mesmo fato reentregue pelo relay não vira
    uma segunda linha. Guarda o fato e nunca a aula, pelo invariante 3 da
    economia. Envelope sem aluno, site ou id não vira linha nem pessoa fantasma.
    """
    data = envelope.get("data") or {}
    site_id = data.get("site_id")
    aluno_id = envelope.get("ator_id")
    event_id = envelope.get("event_id")
    if not (site_id and aluno_id and event_id):
        logger.warning(
            "aula concluída %s chegou sem site, aluno ou id do evento: não registro",
            event_id,
        )
        return None

    pessoa, _ = Pessoa.objects.get_or_create(
        id_da_plataforma=aluno_id,
        defaults={"email": f"{aluno_id}@desconhecido.invalid"},
    )
    entrega, _ = EntregaAceita.objects.get_or_create(
        origem_event_id=str(event_id),
        defaults={
            "pessoa": pessoa,
            "site_id": site_id,
            "occurred_at": _quando(envelope),
        },
    )
    return entrega


def _conceder_boss(envelope: dict) -> None:
    """Reconhece um Boss concluído, sem inventar aluno e sem XP extra."""
    data = envelope.get("data") or {}
    site_id = data.get("site_id")
    aluno_id = envelope.get("ator_id")
    if not (site_id and aluno_id):
        logger.warning(
            "Boss concluído %s chegou sem site ou aluno: não concedo conquista",
            envelope.get("event_id"),
        )
        return

    conquista = ConquistaDefinicao.objects.filter(
        site_id=site_id, slug=CONQUISTA_DO_BOSS
    ).first()
    if conquista is None:
        logger.warning(
            "o site %s não tem a conquista %s: rode `semear_economia` antes "
            "de esperar o reconhecimento do Boss",
            site_id,
            CONQUISTA_DO_BOSS,
        )
        return
    if conquista.classe != ConquistaDefinicao.Classe.MEDALHA:
        logger.error(
            "a conquista %s do site %s não é uma medalha: não concedo "
            "reconhecimento de Boss",
            CONQUISTA_DO_BOSS,
            site_id,
        )
        return
    if not conquista.ativa:
        logger.info(
            "a conquista %s do site %s está desligada: Boss recebido sem "
            "concessão. Ligar é decisão do mantenedor em /admin/economia/.",
            CONQUISTA_DO_BOSS,
            site_id,
        )
        return

    pessoa, _ = Pessoa.objects.get_or_create(
        id_da_plataforma=aluno_id,
        defaults={"email": f"{aluno_id}@desconhecido.invalid"},
    )
    conceder(
        pessoa=pessoa,
        site_id=site_id,
        conquista=conquista,
        validador_papel=Concessao.PapelDoValidador.SISTEMA,
        origem_event_id=str(envelope.get("event_id") or ""),
    )


# ---------------------------------------------------------------------------
# O PORTFÓLIO (degrau 15, 06/09/2026) — o selo da escola acende o marco
# ---------------------------------------------------------------------------


def ao_portfolio_conferido(envelope: dict) -> None:
    """Compatibilidade do consumidor: selo de portfólio não concede Marcos."""
    return None


from .faixas import (  # noqa: E402
    ao_fila_trabalho_aceito,
    ao_item_criado,
    ao_rendimento_real_confirmado,
    ao_rendimento_real_revertido,
    ao_sandbox_trabalho_criado,
)

HANDLERS = {
    "quiz.completado": ao_quiz_completado,
    "sugestao.criada": ao_sugestao_criada,
    "sugestao.voto-adicionado": ao_voto_adicionado,
    "sugestao.status-alterado": ao_status_alterado,
    "forum.topico-criado": ao_forum_topico_criado,
    "forum.mensagem-criada": ao_forum_mensagem_criada,
    "forum.resposta-aceita": ao_forum_resposta_aceita,
    "aula.concluida": ao_aula_concluida,
    "pages.portfolio.conferido": ao_portfolio_conferido,
    # AS FAIXAS (08/10/2026): ver apps/gamificacao/faixas.py
    "cursos.item-criado": ao_item_criado,
    "encomendas.sandbox-trabalho-criado": ao_sandbox_trabalho_criado,
    "encomendas.fila-trabalho-aceito": ao_fila_trabalho_aceito,
    "encomendas.rendimento-real-confirmado": ao_rendimento_real_confirmado,
    "encomendas.rendimento-real-revertido": ao_rendimento_real_revertido,
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
    "cursos.item-criado": "progressão de faixa, não paga XP",
    "encomendas.sandbox-trabalho-criado": "progressão de faixa, não paga XP",
    "encomendas.fila-trabalho-aceito": "progressão de faixa, não paga XP",
    "encomendas.rendimento-real-confirmado": "progressão de faixa, não paga XP",
    "encomendas.rendimento-real-revertido": "progressão de faixa, não paga XP",
    "forum.mensagem-removida": (
        "o estorno precisa achar o lançamento que pagou AQUELA mensagem, e o "
        "ledger guarda o id do EVENTO, não o da mensagem; o fórum já emite o "
        "fato, então ele está guardado para o dia em que o estorno existir"
    ),
    "quiz.completado": (
        "o contrato do quiz identifica a pessoa por e-mail, e esta célula só "
        "sabe creditar id de plataforma; o caminho é findPersonByEmail, da "
        "identidade, e é degrau próprio"
    ),
    "pages.portfolio.conferido": (
        "o selo da escola acende um MARCO REAL, e marco real vale zero XP de "
        "propósito; pendurar uma regra de pontuação neste fato não faria número "
        "nenhum mexer, e o banco recusaria o marco que tentasse pagar"
    ),
}
