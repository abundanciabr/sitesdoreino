# apps/gamificacao/validacao.py
"""A ESPINHA: um marco real acontece fora do site, e alguém da escola confere.

Tudo o que veio antes desta entrega era andaime. XP, níveis e comemorações
medem o que a pessoa faz DENTRO do site, e a lei desta célula é explícita sobre
a ordem que decide todo conflito de desenho: **Realidade > Criação > Maestria >
Comunidade > XP**. O marco real é a espinha — a primeira obra terminada, o
primeiro cliente, os primeiros dólares — e ele não tem como ser contado por
máquina nenhuma: alguém precisa olhar a evidência e dizer sim.

Este arquivo é esse caminho. Ele é o degrau 12 da escada
(`docs/decisoes/PLANO-CELULA-GAMIFICACAO.md` §6), e as tabelas que ele usa
existem, vazias, desde 30/08/2026.

AS SEIS TRAVAS QUE ELE CARREGA, E POR QUE CADA UMA
---------------------------------------------------
1. **Marco rende ZERO XP**, e quem recusa o contrário é o PostgreSQL
   (`marco_real_rende_zero_xp`). A razão é o coração do produto: se conseguir o
   primeiro cliente pagasse 500 XP, o marco viraria mais um item do andaime e o
   aluno aprenderia a perseguir o número em vez da coisa.
2. **Ninguém valida o próprio marco.** Não há restrição de banco para isto e
   não poderia haver: `pessoa` e `validador_id` são colunas que o banco não sabe
   comparar com uma regra de negócio. A trava mora aqui, e é a primeira coisa
   que um sistema de reputação precisa ter.
3. **Um par não fecha marco de dinheiro.** A definição já exige validador da
   equipe (`marco_de_dinheiro_so_a_equipe_valida`), mas a definição não sabe
   QUEM está clicando. Aqui sabe.
4. **Devolver exige motivo da lista fechada.** "Não" sem razão, vindo de um
   colega, é bullying com verniz de processo. O banco recusa a linha sem motivo;
   este arquivo recusa um motivo inventado.
5. **Duas devoluções de par escalam para a equipe.** É o anti-anel: se um grupo
   combinar de recusar o trabalho de alguém, o caminho termina numa pessoa da
   escola, não no aluno.
6. **A evidência nunca viaja.** Ela nasce privada, fica na linha do pedido, e a
   carta que avisa a pessoa carrega o slug do marco e nada mais.

O QUE ESTE ARQUIVO **NÃO** FAZ
-------------------------------
**Não avisa quem teve o pedido devolvido**, e a ausência é decisão, não
esquecimento. Só BOA NOTÍCIA vira carta (lei da célula), e o contrato congelado
de `notificacao.devida` não tem assunto para "seu pedido voltou". Quem conta é a TELA do aluno, que
mostra o estado do pedido e o que falta. Enquanto essa tela não existir (degrau
13), a devolução é silenciosa, e isto está dito no registro do livro em vez de
escondido aqui.

**Não concede medalha sozinho.** As medalhas automáticas — o motor que confere
os critérios do vocabulário fechado — são a TAR-090. O que já está pronto para
elas é a porta: `conceder()` é a única forma de uma conquista existir, e ela
serve tanto ao clique de um professor quanto à conta de uma máquina.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .cartas import ASSUNTO_CONQUISTA, ASSUNTO_MARCO, carta_de_celebracao
from .criterios import criterio_em_portugues
from .models import (
    Concessao,
    ConquistaDefinicao,
    HistoricoDaConcessao,
    LancamentoDeXP,
    MovimentoDeCristais,
    PedidoDeValidacao,
    Pessoa,
    dia_local_de,
)
from .motor import recalcular
from .tasks import relay_apos_commit

logger = logging.getLogger(__name__)

# O SLA da lei, em dias ÚTEIS. "48h úteis para respostas" são dois dias de
# trabalho, não 48 horas de relógio: um pedido feito na sexta à noite não vence
# no domingo, quando não há ninguém para atendê-lo. Prazo que vence enquanto a
# escola dorme não mede atraso nenhum — mede fim de semana.
DIAS_UTEIS_PARA_MARCO = 5
DIAS_UTEIS_PARA_RESPOSTA = 2

# O ANTI-ANEL. Duas devoluções vindas de PARES bastam para a próxima passar
# obrigatoriamente por alguém da escola. Dois e não cinco porque o custo dos
# dois lados é assimétrico: um pedido escalado à toa custa alguns minutos de um
# professor; um aluno recusado em série por um grupo de colegas custa o aluno.
DEVOLUCOES_DE_PAR_ATE_ESCALAR = 2

# O prefixo da referência dos Cristais de uma conquista, e o do lançamento de
# XP. Ficam em constante porque o teste e o código precisam ler a MESMA palavra:
# a idempotência da moeda é `Unique(pessoa, site_id, referencia)`, e uma segunda
# expressão da mesma chave se desalinha no primeiro dia em que alguém mexer numa
# delas.
REFERENCIA_DE_CRISTAL = "conquista:{slug}"
REGRA_DA_CONQUISTA = "conquista-{slug}"
EVENTO_DA_CONCESSAO = "concessao:{id}"
# O estorno e a devolução do XP de uma concessão revogada e restaurada. A linha
# do histórico entra na chave porque a mesma concessão pode ser retirada,
# devolvida e retirada de novo, e cada gesto é um lançamento próprio.
EVENTO_DO_GESTO = "concessao:{id}:{gesto}:{linha}"
# A referência que a concessão de um marco guarda: o pedido, que é onde a prova
# mora, privada. O texto da prova nunca sai de lá.
ORIGEM_DO_PEDIDO = "pedido:{id}"


class ValidacaoRecusada(Exception):
    """O gesto não pode acontecer, e o motivo é regra de negócio, não erro.

    Uma exceção e não um `return None`: quem chama é uma tela, e uma tela que
    recebe `None` mostra "nada aconteceu" — que é exatamente o que um aluno
    recusado NÃO deve ver. A mensagem desta exceção é escrita para ser lida por
    gente.
    """


class PedidoInvalido(ValidacaoRecusada):
    """O pedido não pode nem nascer: falta a conquista, ou ela não está no ar."""


# ---------------------------------------------------------------------------
# O PRAZO
# ---------------------------------------------------------------------------
def _proximo_dia_util(momento):
    """O mesmo horário, no próximo dia que não é sábado nem domingo."""
    seguinte = momento + timedelta(days=1)
    while seguinte.weekday() >= 5:  # 5 = sábado, 6 = domingo
        seguinte += timedelta(days=1)
    return seguinte


def prazo_de(tipo: str, a_partir_de=None):
    """Quando este pedido passa a estar atrasado.

    **Dias úteis contados no fuso da escola**, que é `America/Sao_Paulo` — o
    mesmo `TIME_ZONE` de que sai o dia do ledger e a semana da Sequência. Contar
    em UTC daria um dia diferente para todo pedido feito depois das 21h, e a
    fila mostraria atraso onde não há (`armadilhas/099`).

    **Feriado não é considerado, e a ausência é declarada.** Uma tabela de
    feriados é dado que envelhece e que ninguém mantém; o custo de errar aqui é
    um pedido que aparece como atrasado um dia antes, numa fila que uma pessoa
    olha. Quando a escola tiver calendário próprio, este é o lugar de ligá-lo.
    """
    dias = (
        DIAS_UTEIS_PARA_MARCO
        if tipo == PedidoDeValidacao.Tipo.MARCO
        else DIAS_UTEIS_PARA_RESPOSTA
    )
    return prazo_em_dias_uteis(dias, a_partir_de)


def prazo_em_dias_uteis(dias: int, a_partir_de=None):
    """O mesmo horário, `dias` dias úteis adiante, no fuso da escola.

    A conta de `prazo_de` num lugar só, para a fila das contribuições
    (`contribuicoes.py`) medir atraso com a MESMA régua da fila dos marcos.
    """
    prazo = timezone.localtime(a_partir_de or timezone.now())
    for _ in range(dias):
        prazo = _proximo_dia_util(prazo)
    return prazo


# ---------------------------------------------------------------------------
# A PORTA ÚNICA DE UMA CONQUISTA EXISTIR
# ---------------------------------------------------------------------------
def conceder(
    *,
    pessoa: Pessoa,
    site_id: str,
    conquista: ConquistaDefinicao,
    validador_id: str = "",
    validador_papel: str = Concessao.PapelDoValidador.SISTEMA,
    origem_event_id: str = "",
) -> tuple[Concessao, bool]:
    """Dá a conquista a alguém, com tudo que vem junto. Devolve (concessão, é nova).

    **É a única porta**, e por isso serve aos dois caminhos: o clique de um
    professor aceitando um marco, e a conta automática de uma medalha (TAR-090).
    Dois caminhos com dois códigos dariam duas auditorias diferentes para a mesma
    pergunta — *quem disse que sim?* — e é essa pergunta que precisa ter resposta
    meses depois.

    **Idempotente por construção:** `Unique(pessoa, conquista)` no banco. Conceder
    duas vezes devolve a mesma linha, não credita de novo e não escreve segunda
    carta. É o que faz o backfill do Fundador poder ser re-executado sem medo.

    O que acontece quando é nova, nesta ordem e dentro de UMA transação: a
    concessão nasce, o XP e os Cristais são creditados (quando a conquista os
    tem), o perfil é recalculado e a carta é escrita. Se qualquer passo falhar,
    nada aconteceu — e ninguém recebe parabéns por uma medalha que não existe.

    **A regra do dia vai junto** (dossiê da Comunidade §5): a versão, a cópia e
    a frase do critério, lidas do BANCO na hora e não do objeto que chegou, que
    pode ter sido carregado antes de alguém mudar o critério. E nasce a primeira
    linha do histórico. Uma concessão revogada continua existindo, então
    conceder de novo não a reabre: devolvê-la é `restaurar()`, gesto da equipe.
    """
    with transaction.atomic():
        vigente = ConquistaDefinicao.objects.get(pk=conquista.pk)
        concessao, nova = Concessao.objects.get_or_create(
            pessoa=pessoa,
            conquista=conquista,
            defaults={
                "site_id": site_id,
                "validador_id": validador_id,
                "validador_papel": validador_papel,
                "origem_event_id": origem_event_id,
                "criterio_versao": vigente.versao,
                "criterio": vigente.criterio or {},
                "criterio_em_texto": criterio_em_portugues(vigente),
            },
        )
        if not nova:
            return concessao, False

        HistoricoDaConcessao.objects.create(
            concessao=concessao,
            site_id=site_id,
            gesto=HistoricoDaConcessao.Gesto.CONCEDIDA,
            estado_novo=concessao.estado,
            quem_id=validador_id,
            origem_nova=origem_event_id,
            registrado_em=concessao.concedida_em,
        )

        agora = timezone.now()

        # O XP da conquista. Marco NUNCA cai aqui: o banco o obriga a valer zero
        # (`marco_real_rende_zero_xp`), e é a hierarquia da lei virando coluna.
        if conquista.pontos:
            LancamentoDeXP.objects.create(
                pessoa=pessoa,
                site_id=site_id,
                pontos=conquista.pontos,
                origem_event_id=EVENTO_DA_CONCESSAO.format(id=concessao.pk),
                regra_slug=REGRA_DA_CONQUISTA.format(slug=conquista.slug)[:60],
                regra_versao=vigente.versao,
                occurred_at=agora,
                dia_local=dia_local_de(agora),
                status=LancamentoDeXP.Status.DEFINITIVO,
            )

        # Os Cristais. `conquista` é UMA das cinco origens legítimas de ganho —
        # a moeda desta escola nasce de esforço, e a lista de jeitos de ela
        # nascer é fechada no BANCO ([INV-GAM1]). É por isso que uma medalha
        # pode pagar Cristal e uma regra de evento não: aquela lista não tem a
        # palavra "regra", e acrescentá-la é decisão do mantenedor.
        if conquista.cristais:
            MovimentoDeCristais.objects.create(
                pessoa=pessoa,
                site_id=site_id,
                delta=conquista.cristais,
                origem=MovimentoDeCristais.Origem.CONQUISTA,
                referencia=REFERENCIA_DE_CRISTAL.format(slug=conquista.slug),
                occurred_at=agora,
                dia_local=dia_local_de(agora),
            )

        # O perfil é cópia desnormalizada: sem esta linha, o número na tela do
        # aluno continuaria o de antes da medalha, sem erro em lugar nenhum.
        # `celebrar=True` de propósito: se a medalha empurrou a pessoa para o
        # próximo nível, as duas notícias são verdadeiras e as duas saem.
        recalcular(pessoa.id_da_plataforma, site_id)

        _carta_da_conquista(concessao)
        transaction.on_commit(relay_apos_commit)

    return concessao, True


def _carta_da_conquista(concessao: Concessao) -> None:
    """A carta certa para o que aconteceu: medalha e marco falam com pesos diferentes.

    São dois assuntos e não um justamente para o sininho poder dizer cada coisa
    com o tom que ela merece. Medalha é o andaime (o sistema contou); marco é a
    espinha (uma pessoa da escola olhou e disse sim).

    **A evidência não entra na carta**, e nem poderia: o contrato do assunto é
    `additionalProperties: false` e só conhece o slug e o papel de quem validou.
    Marco de dinheiro carrega print de pagamento e conversa com cliente — isso
    mora na camada privada do pedido e não passa por fila de evento nenhuma.
    """
    conquista = concessao.conquista
    e_marco = conquista.classe == ConquistaDefinicao.Classe.MARCO

    if e_marco:
        parametros = {
            "conquista_slug": conquista.slug,
            "validador_papel": concessao.validador_papel,
        }
    else:
        parametros = {
            "conquista_slug": conquista.slug,
            "familia": conquista.familia,
        }

    carta_de_celebracao(
        site_id=concessao.site_id,
        destinatario_id=concessao.pessoa_id,
        assunto=ASSUNTO_MARCO if e_marco else ASSUNTO_CONQUISTA,
        parametros=parametros,
    )


# ---------------------------------------------------------------------------
# O RASTRO DE UMA CONCESSÃO: revogar, corrigir e restaurar
# ---------------------------------------------------------------------------
# Os três gestos da equipe sobre uma conquista que já existe. Cada um é uma
# linha nova em `HistoricoDaConcessao`, com quem, quando, por quê e o estado de
# antes e de depois; a concessão nunca é apagada. Quem pode fazê-los é a porta
# da equipe (`apps/core/equipe.py`), conferida pela view, como em `aceitar()`.
#
# **Os Cristais de uma medalha revogada ficam**, e não é esquecimento: o banco
# só aceita Cristal negativo como compra na loja
# (`cristal_negativo_so_com_referencia_de_compra`), e abrir um débito por
# correção é decisão do mantenedor (`MovimentoDeCristais`, "o que esta tabela
# ainda não sabe fazer"). O XP volta, pela linha negativa de sempre.


def _travar_para_o_gesto(
    concessao: Concessao, quem_id: str, motivo: str
) -> tuple[Concessao, str]:
    """Relê a concessão travada e confere quem. Chamar dentro de transação.

    O motivo é opcional: se vier, fica na história; se não vier, a linha fica do
    mesmo jeito, com quem mexeu, quando e o estado de antes e de depois.
    """
    motivo = (motivo or "").strip()
    if not quem_id:
        raise ValidacaoRecusada(
            "toda decisão tem nome. Sem o id de quem decidiu, a história desta "
            "conquista não responderia 'quem mexeu aqui?'."
        )
    concessao = (
        Concessao.objects.select_for_update()
        .select_related("conquista")
        .get(pk=concessao.pk)
    )
    return concessao, motivo


def _registrar(
    concessao: Concessao,
    gesto: str,
    *,
    anterior: str,
    quem_id: str,
    motivo: str,
    origem_anterior: str,
) -> HistoricoDaConcessao:
    return HistoricoDaConcessao.objects.create(
        concessao=concessao,
        site_id=concessao.site_id,
        gesto=gesto,
        estado_anterior=anterior,
        estado_novo=concessao.estado,
        quem_id=quem_id,
        motivo=motivo,
        origem_anterior=origem_anterior,
        origem_nova=concessao.origem_event_id,
    )


def _mover_o_xp(concessao: Concessao, linha: HistoricoDaConcessao, sinal: int) -> None:
    """Estorna (-1) ou devolve (+1) o XP que a concessão pagou quando nasceu.

    O valor sai do lançamento ORIGINAL, e não dos pontos que a conquista vale
    hoje: se a escola mudou os pontos depois, estornar o valor novo tiraria da
    pessoa o que ela nunca recebeu.
    """
    credito = LancamentoDeXP.objects.filter(
        pessoa_id=concessao.pessoa_id,
        origem_event_id=EVENTO_DA_CONCESSAO.format(id=concessao.pk),
    ).first()
    if credito is None:
        return
    agora = timezone.now()
    LancamentoDeXP.objects.create(
        pessoa_id=concessao.pessoa_id,
        site_id=concessao.site_id,
        pontos=sinal * credito.pontos,
        origem_event_id=EVENTO_DO_GESTO.format(
            id=concessao.pk, gesto=linha.gesto, linha=linha.pk
        ),
        regra_slug=credito.regra_slug,
        regra_versao=credito.regra_versao,
        occurred_at=agora,
        dia_local=dia_local_de(agora),
        status=LancamentoDeXP.Status.DEFINITIVO,
    )
    # `celebrar=False`: devolver o que foi retirado por engano não é a pessoa
    # subir de nível, e retirar não avisa ninguém (só boa notícia vira carta).
    # Sem avaliação também: um gesto de correção não concede medalha nova.
    recalcular(concessao.pessoa_id, concessao.site_id, celebrar=False)


def revogar(*, concessao: Concessao, quem_id: str, motivo: str = "") -> Concessao:
    """A equipe retira a conquista. A linha fica, e a história diz por quê.

    A pessoa deixa de ter a conquista em toda tela e em toda conta
    (`criterios`, a porta de máquina), o XP que ela pagou é estornado, e
    nenhuma conta automática a devolve: a concessão continua existindo, e
    `Unique(pessoa, conquista)` não deixa nascer outra.
    """
    with transaction.atomic():
        concessao, motivo = _travar_para_o_gesto(concessao, quem_id, motivo)
        if concessao.estado == Concessao.Estado.REVOGADA:
            raise ValidacaoRecusada(
                "Esta conquista já foi retirada. Se foi engano, o gesto é devolver."
            )
        anterior = concessao.estado
        concessao.estado = Concessao.Estado.REVOGADA
        concessao.save(update_fields=["estado"])
        linha = _registrar(
            concessao,
            HistoricoDaConcessao.Gesto.REVOGADA,
            anterior=anterior,
            quem_id=quem_id,
            motivo=motivo,
            origem_anterior=concessao.origem_event_id,
        )
        _mover_o_xp(concessao, linha, -1)
    return concessao


def restaurar(*, concessao: Concessao, quem_id: str, motivo: str = "") -> Concessao:
    """A equipe devolve uma conquista retirada, ao estado que ela tinha antes."""
    with transaction.atomic():
        concessao, motivo = _travar_para_o_gesto(concessao, quem_id, motivo)
        if concessao.estado != Concessao.Estado.REVOGADA:
            raise ValidacaoRecusada(
                "Esta conquista não foi retirada. Não há o que devolver."
            )
        retirada = concessao.historico.filter(
            gesto=HistoricoDaConcessao.Gesto.REVOGADA
        ).last()
        concessao.estado = retirada.estado_anterior
        concessao.save(update_fields=["estado"])
        linha = _registrar(
            concessao,
            HistoricoDaConcessao.Gesto.RESTAURADA,
            anterior=Concessao.Estado.REVOGADA,
            quem_id=quem_id,
            motivo=motivo,
            origem_anterior=concessao.origem_event_id,
        )
        _mover_o_xp(concessao, linha, +1)
    return concessao


def corrigir(
    *, concessao: Concessao, quem_id: str, origem_nova: str, motivo: str = ""
) -> Concessao:
    """A equipe corrige de onde a conquista veio. A referência antiga fica na história.

    O que se corrige é a REFERÊNCIA da origem ou da evidência (`pedido:7`,
    `contribuicao:15`, o id de um evento), nunca a regra, a data ou quem
    validou: esses são fatos do dia em que a conquista nasceu.
    """
    origem_nova = (origem_nova or "").strip()
    if not origem_nova:
        raise ValidacaoRecusada(
            "Escreva a referência certa da origem, como pedido:7 ou contribuicao:15."
        )
    if len(origem_nova) > 64:
        raise ValidacaoRecusada("A referência da origem cabe em até 64 caracteres.")
    with transaction.atomic():
        concessao, motivo = _travar_para_o_gesto(concessao, quem_id, motivo)
        if concessao.estado == Concessao.Estado.REVOGADA:
            raise ValidacaoRecusada(
                "Esta conquista está retirada. Devolva primeiro, e depois corrija."
            )
        if origem_nova == concessao.origem_event_id:
            raise ValidacaoRecusada(
                "Essa é a mesma referência que já está gravada. Nada a corrigir."
            )
        anterior = concessao.estado
        origem_anterior = concessao.origem_event_id
        concessao.estado = Concessao.Estado.CORRIGIDA
        concessao.origem_event_id = origem_nova
        concessao.save(update_fields=["estado", "origem_event_id"])
        _registrar(
            concessao,
            HistoricoDaConcessao.Gesto.CORRIGIDA,
            anterior=anterior,
            quem_id=quem_id,
            motivo=motivo,
            origem_anterior=origem_anterior,
        )
    return concessao


def reconhecimentos_da_escola(site_id: str, pessoa_id: str = ""):
    """As concessões da escola com a história de cada uma, a mais nova em cima.

    Bastidor da equipe. Sem filtro, as 50 mais recentes: a tela é para achar
    uma conquista e decidir sobre ela, não para ler a escola inteira.
    """
    concessoes = Concessao.objects.filter(site_id=site_id)
    if pessoa_id:
        concessoes = concessoes.filter(pessoa_id=pessoa_id)
    return (
        concessoes.select_related("conquista")
        .prefetch_related("historico")
        .order_by("-concedida_em")[:50]
    )


# ---------------------------------------------------------------------------
# A FILA
# ---------------------------------------------------------------------------
def pedir_validacao(
    *,
    pessoa: Pessoa,
    site_id: str,
    conquista: ConquistaDefinicao | None = None,
    tipo: str = PedidoDeValidacao.Tipo.MARCO,
    evidencia: str = "",
    evidencia_privada: bool = True,
) -> PedidoDeValidacao:
    """O aluno diz "consegui", e mostra a prova. O relógio começa a correr.

    O estado inicial se chama **em análise**, e o nome é a decisão: a lei manda
    que esperar nunca pareça recusa. Uma fila cujo primeiro estado se chamasse
    "pendente" ou "não aprovado" ensinaria o aluno a se sentir recusado nos cinco
    dias em que ninguém fez nada de errado.

    **Fail-closed na porta:** conquista desligada não aceita pedido, e pedir de
    novo o que já se tem, ou o que já está na fila, é recusado com a razão em
    português. Sem isso, a fila que uma pessoa olha enche de repetição e o SLA
    vira ficção.
    """
    if tipo == PedidoDeValidacao.Tipo.MARCO:
        if conquista is None:
            raise PedidoInvalido(
                "um pedido de marco precisa dizer QUAL marco. Sem isso não há o "
                "que validar, e a fila receberia uma linha que ninguém sabe julgar."
            )
        if conquista.classe != ConquistaDefinicao.Classe.MARCO:
            raise PedidoInvalido(
                f"{conquista.slug!r} é uma medalha, não um marco real. Medalha a "
                "escola concede quando a conta bate; ela não se pede."
            )

    if conquista is not None:
        if not conquista.ativa:
            raise PedidoInvalido(
                f"o marco {conquista.slug!r} ainda não está no ar nesta escola. "
                "Ligar uma conquista é decisão do mantenedor, com data."
            )
        if Concessao.objects.filter(
            pessoa=pessoa, conquista=conquista, estado=Concessao.Estado.REVOGADA
        ).exists():
            raise PedidoInvalido(
                f"a equipe retirou {conquista.nome!r}, e o que ficou registrado "
                "está nesta página. Se você discorda, fale com a equipe: só ela "
                "devolve."
            )
        if Concessao.objects.filter(pessoa=pessoa, conquista=conquista).exists():
            raise PedidoInvalido(
                f"você já tem {conquista.nome!r}. Esta não volta, e não precisa "
                "ser pedida de novo."
            )
        if PedidoDeValidacao.objects.filter(
            pessoa=pessoa,
            conquista=conquista,
            estado=PedidoDeValidacao.Estado.EM_ANALISE,
        ).exists():
            raise PedidoInvalido(
                f"o seu pedido de {conquista.nome!r} já está na fila, em análise. "
                "Pedir de novo não faz a fila andar mais rápido."
            )

    return PedidoDeValidacao.objects.create(
        pessoa=pessoa,
        site_id=site_id,
        tipo=tipo,
        conquista=conquista,
        evidencia=evidencia,
        evidencia_privada=evidencia_privada,
        estado=PedidoDeValidacao.Estado.EM_ANALISE,
        prazo_ate=prazo_de(tipo),
    )


def _conferir_quem_valida(
    pedido: PedidoDeValidacao, validador_id: str, validador_papel: str
) -> None:
    """As três recusas que nenhuma restrição de banco consegue fazer."""
    if validador_papel == Concessao.PapelDoValidador.SISTEMA:
        raise ValidacaoRecusada(
            "o papel 'sistema' não decide pedido de gente. Ele existe para a "
            "medalha que a escola concede sozinha, onde não há ninguém a quem "
            "perguntar 'quem disse que sim?'."
        )
    if not validador_id:
        raise ValidacaoRecusada(
            "toda decisão humana tem nome. Sem o id de quem decidiu, a auditoria "
            "de um marco contestado não teria resposta meses depois."
        )
    if validador_id == pedido.pessoa_id:
        raise ValidacaoRecusada(
            "ninguém valida o próprio marco. Um sistema de reconhecimento em que "
            "a pessoa se aprova sozinha não reconhece nada."
        )
    conquista = pedido.conquista
    if (
        conquista is not None
        and conquista.exige_validador_da_equipe
        and validador_papel == Concessao.PapelDoValidador.PAR
    ):
        raise ValidacaoRecusada(
            f"{conquista.nome!r} envolve dinheiro e só a equipe da escola fecha. "
            "Um colega pode ajudar a conferir, mas não é ele quem assina."
        )


def aceitar(
    *, pedido: PedidoDeValidacao, validador_id: str, validador_papel: str
) -> Concessao:
    """Alguém da escola olhou a prova e disse sim.

    O gesto inteiro numa transação: o pedido fecha, a concessão nasce, o que a
    conquista paga é creditado e a carta é escrita. Se a carta falhasse depois do
    commit do pedido, existiria um marco aceito que ninguém soube — e o aluno
    ficaria esperando por algo que já aconteceu.
    """
    if pedido.estado == PedidoDeValidacao.Estado.ACEITO:
        raise ValidacaoRecusada(
            "este pedido já foi aceito. Aceitar de novo não muda nada, e a "
            "conquista continua sendo uma só."
        )
    _conferir_quem_valida(pedido, validador_id, validador_papel)
    if pedido.conquista is None:
        raise ValidacaoRecusada(
            "este pedido não aponta para nenhuma conquista, então não há o que "
            "conceder. Pedidos de obra e de ajuda ganham caminho próprio nos "
            "degraus da galeria."
        )

    with transaction.atomic():
        concessao, _ = conceder(
            pessoa=pedido.pessoa,
            site_id=pedido.site_id,
            conquista=pedido.conquista,
            validador_id=validador_id,
            validador_papel=validador_papel,
            origem_event_id=ORIGEM_DO_PEDIDO.format(id=pedido.pk),
        )
        pedido.estado = PedidoDeValidacao.Estado.ACEITO
        pedido.respondido_em = timezone.now()
        pedido.atribuido_a = validador_id
        pedido.save(update_fields=["estado", "respondido_em", "atribuido_a"])

    return concessao


def devolver(
    *,
    pedido: PedidoDeValidacao,
    validador_id: str,
    validador_papel: str,
    motivo: str,
) -> PedidoDeValidacao:
    """Ainda não. Com o que falta dito por escrito, e em particular.

    **O motivo é da lista fechada**, e essa é a diferença entre um processo e uma
    humilhação: o aluno recebe "falta a evidência" ou "a evidência não dá para
    ler", nunca a opinião de alguém sobre o trabalho dele. O banco recusa a linha
    sem motivo; esta função recusa um motivo inventado.

    **A segunda devolução vinda de um par escala para a equipe.** A partir daí o
    pedido não volta para colegas: quem decide é a escola. É a única defesa
    possível contra o combinado entre amigos, e ela é automática — não depende de
    o aluno reclamar, que é justamente o que ele não vai fazer.
    """
    if pedido.estado == PedidoDeValidacao.Estado.ACEITO:
        raise ValidacaoRecusada(
            "este pedido já foi aceito. Desfazer uma conquista concedida é outro "
            "gesto, com auditoria própria, e não passa por aqui."
        )
    _conferir_quem_valida(pedido, validador_id, validador_papel)
    if motivo not in PedidoDeValidacao.MotivoDaDevolucao.values:
        raise ValidacaoRecusada(
            f"{motivo!r} não é um dos motivos que esta escola aceita: "
            f"{PedidoDeValidacao.MotivoDaDevolucao.values}. Devolução com texto "
            "livre vira crítica pessoal, e é exatamente o que a lista fechada "
            "existe para impedir."
        )

    pedido.estado = PedidoDeValidacao.Estado.DEVOLVIDO
    pedido.motivo_da_devolucao = motivo
    pedido.devolucoes += 1
    pedido.respondido_em = timezone.now()
    pedido.atribuido_a = validador_id

    if (
        validador_papel == Concessao.PapelDoValidador.PAR
        and pedido.devolucoes >= DEVOLUCOES_DE_PAR_ATE_ESCALAR
    ) or motivo == PedidoDeValidacao.MotivoDaDevolucao.PRECISA_DE_ADULTO:
        pedido.escalado_para_adulto = True

    pedido.save(
        update_fields=[
            "estado",
            "motivo_da_devolucao",
            "devolucoes",
            "respondido_em",
            "atribuido_a",
            "escalado_para_adulto",
        ]
    )
    return pedido


def reenviar(*, pedido: PedidoDeValidacao, evidencia: str) -> PedidoDeValidacao:
    """O aluno corrigiu o que faltava e mandou de novo. O relógio recomeça.

    **O contador de devoluções NÃO zera**, e é isso que mantém o anti-anel de pé:
    zerá-lo daria a um grupo mal-intencionado devoluções infinitas, bastando
    esperar o aluno reenviar. O que recomeça é o PRAZO, porque a fila passou a ter
    coisa nova para olhar.

    Um pedido escalado continua escalado: uma vez que o caminho subiu para a
    equipe, ele não desce de novo para os colegas.
    """
    if pedido.estado != PedidoDeValidacao.Estado.DEVOLVIDO:
        raise ValidacaoRecusada(
            "só se reenvia um pedido que voltou. Este está em análise ou já foi "
            "aceito."
        )
    pedido.evidencia = evidencia
    pedido.estado = PedidoDeValidacao.Estado.EM_ANALISE
    # O motivo da devolução anterior sai da linha: ele descrevia a versão velha
    # da evidência, e mantê-lo faria a fila mostrar "falta a evidência" ao lado
    # de um pedido que acabou de ganhar uma.
    pedido.motivo_da_devolucao = ""
    pedido.respondido_em = None
    pedido.prazo_ate = prazo_de(pedido.tipo)
    pedido.save(
        update_fields=[
            "evidencia",
            "estado",
            "motivo_da_devolucao",
            "respondido_em",
            "prazo_ate",
        ]
    )
    return pedido


def marcos_da_pessoa(pessoa: Pessoa, site_id: str) -> list[dict]:
    """Os marcos ativos da escola, cada um com o estado DESTA pessoa.

    Uma consulta e não uma tela: quem desenha é a view. Mora aqui porque juntar
    "o que existe" com "o que é meu" é regra de negócio, e um template que
    perguntasse isso sozinho faria N consultas por marco — a forma preguiçosa de
    ficar lento exatamente quando a escola crescer.

    Os cinco estados possíveis são o vocabulário que a tela usa:
    `conquistado`, `revogado`, `em_analise`, `devolvido` e `disponivel`. Não há
    "recusado": a lei manda que esperar nunca pareça recusa, e devolver não é
    dizer não — é dizer o que falta. `revogado` é o marco que a equipe retirou,
    e a linha traz `retirada`, o gesto com a data e o motivo: a história mostra
    que ele existiu.
    """
    marcos = ConquistaDefinicao.objects.filter(
        site_id=site_id, classe=ConquistaDefinicao.Classe.MARCO, ativa=True
    ).order_by("slug")

    concedidos = {
        c.conquista_id: c
        for c in Concessao.objects.filter(pessoa=pessoa, site_id=site_id)
    }
    retiradas = HistoricoDaConcessao.retiradas_de(concedidos.values())
    # O pedido mais RECENTE de cada marco. Ordenar por id decrescente e deixar o
    # primeiro vencer é o que faz um reenvio aparecer no lugar da devolução
    # antiga — a linha velha continua no banco, e é isso que mantém a história.
    pedidos: dict[int, PedidoDeValidacao] = {}
    for pedido in PedidoDeValidacao.objects.filter(
        pessoa=pessoa, site_id=site_id, conquista__isnull=False
    ).order_by("id"):
        pedidos[pedido.conquista_id] = pedido

    linhas = []
    for marco in marcos:
        concessao = concedidos.get(marco.pk)
        pedido = pedidos.get(marco.pk)
        if concessao is not None and concessao.estado == Concessao.Estado.REVOGADA:
            estado = "revogado"
        elif concessao is not None:
            estado = "conquistado"
        elif (
            pedido is not None and pedido.estado == PedidoDeValidacao.Estado.EM_ANALISE
        ):
            estado = "em_analise"
        elif pedido is not None and pedido.estado == PedidoDeValidacao.Estado.DEVOLVIDO:
            estado = "devolvido"
        else:
            estado = "disponivel"
        linhas.append(
            {
                "marco": marco,
                "estado": estado,
                "concessao": concessao,
                "retirada": retiradas.get(concessao.pk) if concessao else None,
                "pedido": pedido,
            }
        )
    return linhas


def fila_da_equipe(site_id: str, *, incluir_respondidos: bool = False):
    """A fila única, na ordem em que uma pessoa deve olhar: o mais atrasado primeiro.

    Uma consulta e não uma tela: quem a desenha é o degrau 13. Ela mora aqui
    porque a ORDEM é regra de negócio — uma tela que ordenasse por data de
    criação mostraria primeiro o pedido mais velho, e não o mais urgente, que são
    coisas diferentes quando os prazos são de 2 e de 5 dias úteis.
    """
    fila = PedidoDeValidacao.objects.filter(site_id=site_id).select_related(
        "conquista", "pessoa"
    )
    if not incluir_respondidos:
        fila = fila.filter(estado=PedidoDeValidacao.Estado.EM_ANALISE)
    return fila.order_by("prazo_ate", "criado_em")
