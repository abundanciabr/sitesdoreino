"""O Mural: a segunda pista por onde um projeto chega ao aluno.

Produto: `PLANO-AREA-DE-NEGOCIACAO.md` §3 (o Mural), §8 (os invariantes M1 a M5)
e §9 (o `relogio_da_reserva_no_mural`). Lei:
`docs/decisoes/DECISAO-fila-do-primeiro-dolar.md` §2.1, que registra a reabertura
que o mantenedor decidiu em 04/09/2026. Este é o degrau 2.11 da escada (TAR-133).

A FILA CONTINUA INTEIRA, E O MURAL NÃO A TOCA
----------------------------------------------
Os dez invariantes de justiça (J1 a J10) valem sem exceção depois deste arquivo:
nada aqui muda a ordem da fila, o lugar de ninguém ou a régua de elegibilidade.
O que este arquivo acrescenta é uma SEGUNDA PORTA para a mesma esteira, e a
promessa da fila continua sendo a de sempre: ela garante o primeiro trabalho de
quem nunca entregou, e o Mural é para onde a pessoa vai depois.

AS TRÊS REGRAS DE PISTA, E NENHUMA INVENTADA
---------------------------------------------
1. **O Mural mostra a um aluno o que ele é elegível a pegar, e só isso.** Não há
   régua nova: é o mesmo `motor.por_que_nao` que a fila chama, com a mesma
   `Regras` lida do mesmo banco. A elegibilidade da lei já carrega as entregas
   (Intermediário exige 1, Avançado exige 5), então quem nunca entregou vê um
   Mural vazio sem que ninguém precise escrever essa frase em lugar nenhum.

   **A revisão de 04/09/2026 mora exatamente aqui.** A versão anterior do plano
   dizia "só quem já entregou vê o Mural", e isso contradizia a chamada aberta,
   que avisa TODOS os elegíveis e, num projeto Iniciante, inclui quem tem zero
   entregas. Duas regras que se negam viram, na construção, a interpretação de
   quem codar primeiro. A régua é a elegibilidade, nunca "já entregou".

2. **Projeto de nível Iniciante nasce na fila.** Ele chega ao Mural pela chamada
   aberta, e por nenhum outro caminho: `na_fila` não tem seta para `no_mural`, o
   gatilho do PostgreSQL recusa a transição, e o
   `iniciante_nunca_no_mural_reservavel` recusa até o INSERT que tentasse pular
   a fila inteira.

3. **Projeto Intermediário ou Avançado nasce no Mural**, porque a elegibilidade
   da lei já exige entregas aprovadas para eles: colocá-los na fila seria
   oferecê-los, um por um, a gente que não pode aceitá-los.

A QUARTA REGRA, QUE FECHA O BURACO DOS PRIMEIROS MESES
-------------------------------------------------------
Nos primeiros meses ninguém terá entrega aprovada, então o Mural nasce sem
ninguém para olhá-lo. Um projeto Intermediário aberto nesse período ficaria
parado para sempre, sem ninguém elegível e sem ninguém sabendo. Então: projeto
que passa `horas_para_virar_aberta` no Mural SEM nenhum elegível disponível vai
ao plantão, com a razão escrita. Mesmo relógio e mesmo destino que a lei já dava
à encomenda encalhada na fila (§6.4). Quem varre é o `tique.py`, que é onde os
relógios desta célula moram.

**As duas condições são E, e não OU.** Um projeto que passou 24 horas no Mural
COM elegíveis disponíveis fica onde está: alguém ainda pode pegá-lo, e mandá-lo
ao plantão seria tirar da prateleira o que a prateleira ainda pode vender. O que
o invariante impede é o encalhe SILENCIOSO, e não a espera.

O MURAL NÃO É LEILÃO
---------------------
Pegar não é dar lance. Um projeto fica reservado a UM aluno por vez, com relógio
visível, e é ele quem negocia; vencido o relógio, o projeto volta ao Mural para
o próximo, e nunca para quem já o teve. Quem faz isso valer não é este arquivo:
são os dois índices únicos da `ReservaDoMural`, porque nenhum `if` em Python
resolve dois alunos tocando "Pegar" no mesmo segundo.

A ORDEM DA LISTA É SÓ A ANTIGUIDADE
------------------------------------
Os mais antigos primeiro, e nada mais. Qualquer outra chave (destaque, peso,
relevância, preço, nível) é a SEGUNDA REGRA DE ORDEM que o critério de morte 2
da lei §9 proíbe: pare e reabra a decisão com o mantenedor antes de acrescentar
termo a esta chave.

O QUE NÃO É DESTE DEGRAU
-------------------------
- **A Proposta e o Acordo** são a TAR-134. É de `reservada` que a negociação
  parte: o gesto que criar a primeira `Proposta` fecha a reserva em
  `negociando` (o relógio para) e leva a encomenda a `em_negociacao`.
- **A tela do aluno** é a Fase 4. Aqui existe a lista, e não a página.
- **Um aluno com duas reservas vivas ao mesmo tempo** é o [INV-ENC-N6] ("uma
  negociação viva por aluno, somando as duas pistas"), e ele é da TAR-134. Este
  degrau não o inventa: o §8 escreve o M3 inteiro sobre o PROJETO, nunca sobre
  o aluno, e uma regra a mais aqui seria uma régua que o plano não pediu.
"""

from __future__ import annotations

from datetime import datetime

from django.db import IntegrityError, transaction

from . import motor
from .gestos import Desfecho
from .models import (
    Encomenda,
    Oferta,
    PerfilProfissional,
    ReservaDoMural,
)
from .relogio import calcular_expiracao_da_reserva

# ---------------------------------------------------------------------------
# AS RAZÕES DE UMA RECUSA — uma por nome, como as do motor e as dos gestos
# ---------------------------------------------------------------------------

NAO_ESTA_NO_MURAL = "nao_esta_no_mural"
JA_FOI_PEGA = "ja_foi_pega"
E_CHAMADA_ABERTA_USE_ACEITAR = "e_chamada_aberta_use_aceitar"
CORRIDA_PERDIDA = "corrida_perdida"

MOTIVO_DA_PEGADA = "o aluno pegou o projeto no mural e ganhou a vez"
MOTIVO_DA_RESERVA_VENCIDA = "o relogio da reserva venceu sem proposta: volta ao mural"
MOTIVO_SEM_ELEGIVEL_NO_MURAL = (
    "esperou o prazo no mural sem nenhum aluno elegivel disponivel"
)

# O estado em que cada nível nasce. É a regra 2 e a regra 3 escritas como DADO,
# e não como um `if`: uma tabela de três linhas cabe numa tela, é lida por quem
# revisa em cinco segundos, e não tem ramo escondido.
#
# O cartão decide o nível (o banco faz valer, `o_cartao_decide_o_nivel`), e o
# nível decide o estado inicial. Ninguém escolhe rota: nem o cliente, que sequer
# sabe que existem duas (§3.4), nem o aluno.
STATUS_DE_NASCIMENTO: dict[str, str] = {
    Encomenda.Nivel.INICIANTE: Encomenda.Status.NA_FILA,
    Encomenda.Nivel.INTERMEDIARIO: Encomenda.Status.NO_MURAL,
    Encomenda.Nivel.AVANCADO: Encomenda.Status.NO_MURAL,
}

# O QUE O MURAL MOSTRA. Dois estados, e os dois querem dizer "este projeto está
# na prateleira esperando um aluno":
#
#   `no_mural`  o projeto reservável, que se pega e dá a vez com relógio;
#   `aberta`    a chamada aberta, em que o primeiro elegível que aceitar leva.
#
# `reservada` não aparece: ela já tem dono, e mostrá-la seria oferecer o que não
# está à venda. A chamada aberta aparece porque é assim que um projeto Iniciante
# chega ao Mural (§3.1), e quem a leva usa `gestos.aceitar_a_chamada_aberta`,
# que a TAR-123 já construiu.
ESTADOS_VISIVEIS_NO_MURAL = (Encomenda.Status.NO_MURAL, Encomenda.Status.ABERTA)


# ---------------------------------------------------------------------------
# O NASCIMENTO — a regra 2 e a regra 3, num gesto só
# ---------------------------------------------------------------------------


def nascer(
    *,
    site_id: str,
    origem: str,
    cliente_id: str,
    cartao: str,
    briefing: dict | None = None,
    autorizacao_portfolio: bool = False,
) -> Encomenda:
    """Cria a encomenda já no estado que o nível dela manda.

    É a ÚNICA porta de nascimento desta célula, e é ela que a Fase 3 vai chamar
    quando o cliente descrever o projeto. Existir como função, e não como um
    `Encomenda.objects.create` espalhado por quem tiver pressa, é o que faz a
    regra de rota ser uma coisa só: uma segunda porta divergiria da primeira no
    dia em que o plano mudasse, e ninguém saberia qual das duas estava certa.

    O nível não é argumento de propósito: **o cartão decide o nível**, sempre
    (plano §5.1), e deixar o chamador informar os dois abriria a porta para o
    par incoerente que o banco recusaria depois, com uma mensagem que ninguém
    entende. Aqui a incoerência é impossível de escrever.
    """
    nivel = Encomenda.NIVEL_DO_CARTAO[cartao]
    status = STATUS_DE_NASCIMENTO[nivel]
    return Encomenda.objects.create(
        site_id=site_id,
        origem=origem,
        cliente_id=cliente_id,
        cartao=cartao,
        nivel=nivel,
        status=status,
        briefing=briefing or {},
        autorizacao_portfolio=autorizacao_portfolio,
    )


# ---------------------------------------------------------------------------
# A ELEGIBILIDADE — a MESMA do motor, com a memória que é do Mural
# ---------------------------------------------------------------------------


def _reservas_por_encomenda(encomenda_ids, *, site_id: str) -> dict:
    """Agrupa em uma leitura os alunos que já pegaram cada encomenda."""
    por_encomenda = {}
    for encomenda_id, aluno_id in ReservaDoMural.objects.filter(
        site_id=site_id, encomenda_id__in=encomenda_ids
    ).values_list("encomenda_id", "aluno_id"):
        por_encomenda.setdefault(encomenda_id, set()).add(aluno_id)
    return {
        encomenda_id: frozenset(alunos)
        for encomenda_id, alunos in por_encomenda.items()
    }


def vaga_de(
    projeto: Encomenda, reservas_por_encomenda: dict | None = None
) -> motor.Vaga:
    """A vaga do Mural, com a memória de quem já teve este projeto.

    A memória do Mural são as RESERVAS, e não as ofertas da fila, e a diferença
    é deliberada. Um projeto Iniciante chega ao Mural em chamada aberta, e a
    chamada aberta é a exceção literal do [INV-ENC-J6]: quem passou ou ficou em
    silêncio na fila continua elegível ali (plano §6.4). Ler as ofertas aqui
    reintroduziria, pela porta dos fundos, a proibição que a lei já excetuou.

    O que a memória impede é o giro em falso do §3.2: o mesmo aluno pega, deixa
    vencer, pega de novo, e o projeto nunca sai do lugar. Esta é a leitura
    EDUCADA da regra, para o aluno receber uma frase em vez de um
    `IntegrityError`; quem a torna impossível de violar é o índice único
    `ninguem_pega_o_mesmo_projeto_duas_vezes`.
    """
    alunos_que_ja_pegaram = (
        _reservas_por_encomenda([projeto.pk], site_id=projeto.site_id).get(
            projeto.pk, frozenset()
        )
        if reservas_por_encomenda is None
        else reservas_por_encomenda.get(projeto.pk, frozenset())
    )
    return motor.Vaga(
        encomenda_id=projeto.pk,
        nivel=projeto.nivel,
        ja_ofertada_a=alunos_que_ja_pegaram,
    )


def _candidato(perfil: PerfilProfissional) -> motor.Candidato:
    """Um perfil congelado no `Candidato` que o miolo puro do motor recebe.

    Nenhum campo é calculado aqui: é transcrição. A régua inteira mora em
    `motor.por_que_nao`, e ter uma segunda régua neste arquivo seria exatamente
    o que a regra 1 do cabeçalho existe para impedir.
    """
    return motor.Candidato(
        perfil_id=perfil.id,
        titulo_banca=perfil.titulo_banca,
        disponibilidade=perfil.disponibilidade,
        entregas_aprovadas=perfil.entregas_aprovadas,
        data_entrada_fila=perfil.data_entrada_fila,
        tem_oferta_pendente=Oferta.objects.filter(
            aluno=perfil, resultado=Oferta.Resultado.PENDENTE
        ).exists(),
        abandonos=tuple(perfil.abandonos or ()),
        tem_negociacao_viva=Encomenda.objects.filter(
            site_id=perfil.site_id,
            aluno=perfil,
            status__in=motor.ESTADOS_DE_NEGOCIACAO_VIVA,
        ).exists(),
    )


def tem_elegivel_disponivel(
    projeto: Encomenda,
    candidatos,
    regras: motor.Regras,
    agora: datetime,
    reservas_por_encomenda: dict | None = None,
) -> bool:
    """Existe alguém que poderia pegar este projeto agora? A quarta regra numa linha.

    É o que separa "ninguém pegou ainda" de "ninguém PODE pegar", e a diferença
    decide o destino: a primeira é espera, e espera é normal num Mural; a
    segunda é encalhe, e encalhe silencioso é o que o [INV-ENC-M5] existe para
    impedir. Quem chama é o tique, e a resposta dele é a razão escrita que o
    professor vai ler.
    """
    return bool(
        motor.elegiveis(
            vaga_de(projeto, reservas_por_encomenda), candidatos, regras, agora
        )
    )


# ---------------------------------------------------------------------------
# A LISTA — o que ESTE aluno vê, na única ordem que existe
# ---------------------------------------------------------------------------


def listar(perfil_id, agora: datetime, *, site_id: str) -> tuple[Encomenda, ...]:
    """Os projetos que este aluno é elegível a pegar, do mais antigo para o mais novo.

    [INV-ENC-M1] e [INV-ENC-M4] num gesto só, e é bom que sejam o mesmo gesto:
    a lista que a tela desenha é a lista que os guardas medem, então não existe
    o caminho "a peneira certa no teste e a consulta solta na tela".

    A ORDEM É `criada_em`, E O `id` NÃO É UMA SEGUNDA REGRA. Ele só é consultado
    quando dois projetos nasceram no mesmo microssegundo, e existe para a lista
    ser uma função de verdade: sem ele, dois cartões empatados trocariam de
    lugar entre dois carregamentos, conforme a ordem em que o banco devolvesse
    as linhas. É o mesmo desempate, pela mesma razão, do terceiro termo do
    `motor.CHAVE_DA_ORDEM`.

    Perfil que não existe neste site recebe uma lista VAZIA, e não um erro:
    "reconhecer não é autorizar" é invariante desta célula, e quem não tem
    perfil aqui não tem Mural nenhum para ver.
    """
    perfil = PerfilProfissional.objects.filter(pk=perfil_id, site_id=site_id).first()
    if perfil is None:
        return ()

    regras = motor.Regras.do_banco(agora, site_id=site_id)
    candidato = _candidato(perfil)
    projetos = list(
        Encomenda.objects.filter(
            site_id=site_id, status__in=ESTADOS_VISIVEIS_NO_MURAL
        ).order_by("criada_em", "id")
    )
    reservas_por_encomenda = _reservas_por_encomenda(
        [projeto.pk for projeto in projetos], site_id=site_id
    )
    return tuple(
        projeto
        for projeto in projetos
        if not motor.por_que_nao(
            vaga_de(projeto, reservas_por_encomenda), candidato, regras, agora
        )
    )


# ---------------------------------------------------------------------------
# O GESTO — "Pegar"
# ---------------------------------------------------------------------------


@transaction.atomic
def pegar(encomenda_id, perfil_id, agora: datetime, *, site_id: str) -> Desfecho:
    """O aluno pega o projeto no Mural e ganha a vez, com relógio.

    A ordem das travas é a mesma dos gestos da fila e a mesma do tique:
    **encomenda, depois perfil**. Duas ordens diferentes na mesma célula é um
    `deadlock` esperando o primeiro dia de movimento, e ele não aparece em teste
    nenhum.

    **A corrida de dois alunos no mesmo segundo é resolvida pelo BANCO.** O
    `select_for_update` serializa os dois, e o segundo a entrar encontra o
    projeto em `reservada` e recebe `ja_foi_pega`. O índice único parcial é a
    trava que sobra para o caso de dois processos que nem se viram, e ela vira
    `corrida_perdida` em vez de um erro que ninguém sabe desenhar.

    O aluno NÃO vira "trabalhando": quem pegou um projeto ainda não tem trabalho
    nenhum, e travá-lo na fila por três horas porque está lendo um briefing
    seria puni-lo por estar interessado (plano §4.2). O que ele não pode é
    receber uma oferta da fila nem iniciar outra negociação enquanto isso. O
    [INV-ENC-J2] bloqueia a oferta pendente e o [INV-ENC-N6] bloqueia a
    negociação viva, inclusive quando ela começou no Mural.
    """
    projeto = (
        Encomenda.objects.select_for_update()
        .filter(pk=encomenda_id, site_id=site_id)
        .first()
    )
    if projeto is None:
        return Desfecho(feito=False, razao=NAO_ESTA_NO_MURAL)
    if projeto.status != Encomenda.Status.NO_MURAL:
        # `reservada` quer dizer que alguém chegou primeiro; qualquer outro
        # estado quer dizer que este projeto não está na prateleira. A chamada
        # aberta cai aqui de propósito: ela não se pega, se aceita, e quem a
        # leva é `gestos.aceitar_a_chamada_aberta`.
        razao = (
            JA_FOI_PEGA
            if projeto.status == Encomenda.Status.RESERVADA
            else (
                E_CHAMADA_ABERTA_USE_ACEITAR
                if projeto.status == Encomenda.Status.ABERTA
                else NAO_ESTA_NO_MURAL
            )
        )
        return Desfecho(feito=False, razao=razao, encomenda_em=projeto.status)

    perfil = (
        PerfilProfissional.objects.select_for_update()
        .filter(pk=perfil_id, site_id=site_id)
        .first()
    )
    if perfil is None:
        return Desfecho(feito=False, razao=motor.FORA_DA_FILA)

    regras = motor.Regras.do_banco(agora, site_id=site_id)
    razao = motor.por_que_nao(vaga_de(projeto), _candidato(perfil), regras, agora)
    if razao:
        return Desfecho(feito=False, razao=razao, encomenda_em=projeto.status)

    try:
        # Savepoint próprio: um `IntegrityError` engolido sem ele quebraria a
        # transação inteira, inclusive o que já foi gravado (`armadilhas/027`).
        with transaction.atomic():
            ReservaDoMural.objects.create(
                site_id=site_id,
                encomenda=projeto,
                aluno=perfil,
                expira_em=calcular_expiracao_da_reserva(agora, site_id=site_id),
            )
    except IntegrityError:
        return Desfecho(feito=False, razao=CORRIDA_PERDIDA, encomenda_em=projeto.status)

    projeto.aluno = perfil
    projeto.save(update_fields=["aluno", "atualizada_em"])
    projeto.mudar_status(
        Encomenda.Status.RESERVADA,
        ator_id=perfil.pessoa_id,
        motivo=MOTIVO_DA_PEGADA,
    )
    return Desfecho(feito=True, encomenda_em=projeto.status)
