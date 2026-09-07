"""O tique de um minuto: a reavaliação periódica que faz os relógios andarem.

Lei: `docs/decisoes/DECISAO-fila-do-primeiro-dolar.md` §5 ([INV-ENC-J9] e
[INV-ENC-J10]). Produto: `PLANO-MESTRE-FILA-DO-PRIMEIRO-DOLAR.md` §6.3, §6.4,
§7.4 (o bloco `tique:` do algoritmo) e §8.6 (*"um tique por minuto reavalia (...)
nada agendado individualmente"*).

POR QUE NÃO EXISTE TIMER AGENDADO, E ISSO É A PARTE IMPORTANTE
---------------------------------------------------------------
O caminho óbvio, ao criar uma oferta que expira em três horas úteis, é agendar
alguma coisa para daqui a três horas: um `revoke_at` do Huey, um `sleep`, uma
linha numa tabela de agendamentos. **Nenhum deles entra aqui**, e a lei é
explícita: *"relógios não são timers agendados; são reavaliação periódica.
Sobrevive a reinício, deploy e queda do Redis"* (plano §7.4).

A diferença aparece no pior dia, não no dia comum. Um timer agendado vive FORA
do banco: ele mora na fila do Redis, ou na memória de um processo. O deploy
desta célula troca o container; o Redis pode cair; a máquina pode reiniciar. Um
timer agendado que morre não deixa rastro — a oferta simplesmente fica pendente
para sempre, a encomenda nunca volta para a fila, e ninguém recebe erro nenhum.
O cliente espera, o aluno esquece, e o painel de plantão mostra tudo verde.

A reavaliação periódica não tem esse estado: **a verdade inteira está nas
colunas** (`Oferta.expira_em`, `Encomenda.status`, o histórico). Se o processo
sumir por seis horas, a primeira passada quando ele voltar faz exatamente o que
as seis passadas perdidas fariam — porque ela não pergunta "o que devia ter
acontecido às 14h?", pergunta "o que está vencido AGORA?". É o cenário 15 do
anexo B do plano, e ele tem guarda próprio
(`tests/test_inv_j10_motor_idempotente.py`).

A ORDEM DOS TRÊS GESTOS É REGRA, NÃO ARRUMAÇÃO
-----------------------------------------------
1. **Expirar** as ofertas vencidas (a encomenda volta a `na_fila`).
2. **Abrir** o que esperou demais na fila ([INV-ENC-J9]).
3. **Oferecer** o que sobrou em `na_fila` (o motor do degrau 2.3).

Trocar 1 com 2 mudaria o desfecho de quem estava com o relógio vencido no exato
minuto das 24h: a oferta seria CANCELADA em vez de EXPIRADA, e a auditoria de
justiça leria "a plataforma tirou a oferta dele" onde a verdade é "o prazo dele
acabou". Trocar 2 com 3 daria uma oferta nova, de três horas, a uma encomenda
que já devia estar em chamada aberta — e o [INV-ENC-J9] cairia por um minuto a
cada volta.

O SILÊNCIO ACONTECE AQUI, E SÓ AQUI
------------------------------------
`expirar_ofertas_vencidas` é o único lugar desta célula onde um silêncio
acontece: em todos os outros caminhos alguém clicou em alguma coisa. Por isso é
daqui que sai a contagem da pausa automática (plano §6.3 e §7.4: *"expirou;
silencios_consecutivos += 1; se == 3 → pausar aluno"*), chegada no degrau 2.5.

**A regra em si não mora neste arquivo, e a separação é de propósito:** quem
conta e quem pausa é `gestos.contar_o_silencio`, ao lado do `zerar_o_silencio`
que os gestos do aluno chamam. As duas metades do mesmo contador em arquivos
diferentes é como um contador aprende a crescer e esquece de zerar.

O QUE ESTE ARQUIVO **NÃO** FAZ
-------------------------------
Os prazos de produção, o abandono, a aprovação tácita e o SLA do revisor são as
Fases 3 e 5. Todos vão pendurar-se neste mesmo tique quando chegarem, e é para
isso que ele devolve um resumo nomeado em vez de `None`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from django.db import transaction

from . import gestos, motor, mural, negociacao
from .models import (
    Encomenda,
    ESTADOS_DO_MURAL_RESERVAVEL,
    MudancaDeStatus,
    Oferta,
    Parametro,
    PerfilProfissional,
    Proposta,
    ReservaDoMural,
)
from .relogio import prazo_para_virar_aberta

# OS DOIS ESTADOS EM QUE A ENCOMENDA ESTÁ ESPERANDO UM ALUNO DA FILA. O
# [INV-ENC-J9] nomeia os dois, e a razão de serem dois é que a encomenda pinga
# entre eles enquanto desce a fila: `na_fila` → `oferecida` → (silêncio) →
# `na_fila` → ... Um prazo que zerasse a cada volta nunca chegaria às 24h.
ESTADOS_DA_ESPERA = frozenset({Encomenda.Status.NA_FILA, Encomenda.Status.OFERECIDA})

# O motivo escrito no histórico, para a mediação de daqui a seis meses ter o que
# ler. `ator_id` fica vazio nos dois: quem agiu foi o relógio, e inventar uma
# pessoa ali seria inventar autoria.
MOTIVO_DA_EXPIRACAO = "o relogio da oferta venceu sem resposta do aluno"
MOTIVO_DA_ABERTURA = "esperou o prazo da fila sem aceite: virou chamada aberta"


@dataclass(frozen=True)
class Tique:
    """O que uma passada do tique fez. Nomeado, e não um `None`.

    Cada lista é de ids, e não uma contagem, porque quem chama (o teste, o
    simulador do degrau 2.6, a tela de plantão da Fase 7) precisa saber QUAL
    encomenda mudou, não quantas.
    """

    ofertas_expiradas: tuple[object, ...] = ()
    reservas_expiradas: tuple[object, ...] = ()
    propostas_expiradas: tuple[object, ...] = ()
    encomendas_abertas: tuple[object, ...] = ()
    projetos_ao_plantao: tuple[object, ...] = ()
    rodada: motor.Rodada = field(default_factory=motor.Rodada)


def entrou_na_espera_em(encomenda: Encomenda, estados=ESTADOS_DA_ESPERA) -> datetime:
    """Desde quando esta encomenda espera um aluno da fila. O relógio do [INV-ENC-J9].

    **Não é `criada_em`, e a diferença é o que impede uma injustiça silenciosa.**
    A encomenda pode voltar para a fila depois de já ter saído dela: o plantão a
    devolve por `para_reclassificar`, o aluno a abandona, a negociação se
    desfaz. Se o prazo contasse desde o nascimento, uma encomenda devolvida à
    fila três dias depois viraria chamada aberta no primeiro tique — sem nenhum
    aluno da fila ter tido a chance de vê-la, que é exatamente a promessa que a
    Fila do Primeiro Dólar existe para cumprir.

    Então o marco é a última ENTRADA na espera: a mudança de status mais recente
    que trouxe a encomenda para `na_fila` ou `oferecida` vinda de FORA desse
    par. As idas e vindas internas (`na_fila` → `oferecida` → `na_fila`, que é o
    silêncio de um aluno) não zeram nada — se zerassem, uma fila com muitos
    alunos nunca chegaria às 24h, e o [INV-ENC-J9] seria letra morta justamente
    onde ele mais importa.

    Sem nenhuma mudança dessas no histórico, o marco é `criada_em`: a encomenda
    nasce na pista dela (`na_fila` ou `no_mural`, conforme o nível) e essa
    primeira entrada não gera linha de histórico.

    **O `estados` é argumento porque as duas pistas fazem a MESMA conta.** No
    Mural o projeto pinga entre `no_mural` e `reservada` do mesmo jeito que na
    fila pinga entre `na_fila` e `oferecida`, e as idas e vindas internas
    também não podem zerar nada: um relógio que reiniciasse a cada reserva
    vencida nunca chegaria às 24h, e o [INV-ENC-M5] seria letra morta
    exatamente no Mural cheio de gente que não pode pegar nada. Uma conta só,
    com a lista de estados por argumento, é o que impede as duas de divergirem.
    """
    entrada = (
        MudancaDeStatus.objects.filter(encomenda=encomenda, para__in=estados)
        .exclude(de__in=estados)
        .order_by("-em", "-id")
        .first()
    )
    return entrada.em if entrada else encomenda.criada_em


def expirar_ofertas_vencidas(agora: datetime, *, site_id: str) -> tuple[object, ...]:
    """Fecha como `expirou` toda oferta pendente cujo prazo já passou.

    `expira_em <= agora`: o instante exato do vencimento já conta como vencido,
    a mesma convenção de borda de `relogio.esta_na_janela`. Sem uma convenção
    única, o minuto do vencimento pertenceria aos dois lados e o comportamento
    dependeria da ordem em que as comparações foram escritas.

    A encomenda volta para `na_fila` na MESMA transação em que a oferta se
    fecha. Separar as duas escritas abriria a janela em que existe uma encomenda
    `oferecida` sem oferta viva — um estado que nenhuma tela sabe desenhar e que
    o motor trataria como "já tem oferta pendente" para sempre.

    **Silêncio não custa o lugar na fila** ([INV-ENC-J4]): nada aqui escreve em
    `data_entrada_fila`, e o varredor `ast` daquele guarda reprovaria se
    escrevesse. O que ele custa é uma linha no contador de silêncios
    consecutivos, e a pausa automática quando a conta chega ao limite da lei §6
    — as duas coisas na MESMA transação em que a oferta se fecha, para não
    existir instante nenhum com o silêncio contado e o aluno ainda recebendo
    ofertas.

    A ordem das travas é a mesma dos gestos do aluno: encomenda, depois perfil.
    """
    vencidas = list(
        Oferta.objects.filter(
            site_id=site_id,
            resultado=Oferta.Resultado.PENDENTE,
            expira_em__lte=agora,
        )
        .order_by("expira_em", "id")
        .values_list("pk", "encomenda_id")
    )

    fechadas: list[object] = []
    for oferta_id, encomenda_id in vencidas:
        with transaction.atomic():
            # A trava é na ENCOMENDA, e não na oferta, de propósito: é ela que
            # os dois gestos deste arquivo e a varredura do motor disputam. Duas
            # passadas do tique no mesmo minuto (deploy com dois workers de pé,
            # que acontece) serializam aqui.
            encomenda = Encomenda.objects.select_for_update().get(pk=encomenda_id)
            oferta = Oferta.objects.get(pk=oferta_id)
            if oferta.resultado != Oferta.Resultado.PENDENTE:
                # A outra passada chegou primeiro, ou o aluno respondeu entre a
                # leitura e a trava. Não é erro: é a corrida sendo perdida.
                #
                # ESTA LINHA NÃO FICA VERMELHA NUM TESTE DE UM PROCESSO SÓ, e
                # está escrito aqui para ninguém a apagar por causa disso. Quem
                # dá a idempotência da passada seguinte é o FILTRO da consulta
                # (`resultado=pendente`): oferta já fechada não volta na lista, e
                # é isso que o guarda do [INV-ENC-J10] mede. O que esta linha
                # cobre é a corrida entre DOIS processos, que nenhum teste
                # sequencial encena — apagá-la deixa a suíte verde e um
                # `TransicaoProibida` esperando o primeiro deploy com dois
                # workers de pé (`armadilhas/319`: mutação que fica verde nem
                # sempre acusa guarda cego).
                continue
            perfil = PerfilProfissional.objects.select_for_update().get(
                pk=oferta.aluno_id
            )
            oferta.responder(Oferta.Resultado.EXPIROU, em=agora)
            gestos.contar_o_silencio(perfil, agora, site_id=site_id)
            if encomenda.status == Encomenda.Status.OFERECIDA:
                encomenda.mudar_status(
                    Encomenda.Status.NA_FILA, motivo=MOTIVO_DA_EXPIRACAO
                )
            fechadas.append(oferta_id)
    return tuple(fechadas)


def abrir_o_que_esperou_demais(agora: datetime, *, site_id: str) -> tuple[object, ...]:
    """[INV-ENC-J9]: nenhuma encomenda passa do prazo da fila sem virar aberta.

    O prazo é lido UMA VEZ, antes da varredura, pela mesma razão que o motor
    calcula a expiração uma vez: a passada tem de ser função de (estado,
    `agora`). Duas encomendas com a mesma idade no mesmo tique não podem ter
    desfechos diferentes porque o parâmetro mudou no meio.

    **Uma oferta viva no minuto das 24h é CANCELADA, e o aluno não perde nada.**
    Parece duro, e a alternativa é pior: esperar a oferta vencer para só então
    abrir daria a uma encomenda que já está atrasada mais três horas úteis de
    espera, que é justamente o que o invariante existe para impedir. E o aluno
    que estava com ela continua elegível — a chamada aberta é para todos os
    elegíveis, e a exceção *"salvo em chamada aberta"* do [INV-ENC-J6] é
    literalmente este caso. Quem espera de verdade é o cliente, que pagou.

    A encomenda SEM NINGUÉM ELEGÍVEL sai por aqui também, e não por um caminho
    próprio. O plano §6.4 diz *"há 24h na fila sem aceite (ou sem elegíveis
    disponíveis)"*, e a tentação é abrir na hora quando o motor devolve
    `sem_elegivel`. Não abrimos: nos primeiros meses NINGUÉM tem entrega
    aprovada, então toda encomenda intermediária nasceria aberta no primeiro
    minuto — e chamada aberta também respeita o nível mínimo, ou seja, seria uma
    chamada para ninguém, um minuto depois do pagamento. Uma regra, um
    parâmetro, um relógio.
    """
    prazo = prazo_para_virar_aberta(agora, site_id=site_id)
    esperando = list(
        Encomenda.objects.filter(site_id=site_id, status__in=ESTADOS_DA_ESPERA)
        .order_by("criada_em", "id")
        .values_list("pk", flat=True)
    )

    abertas: list[object] = []
    for encomenda_id in esperando:
        with transaction.atomic():
            encomenda = Encomenda.objects.select_for_update().get(pk=encomenda_id)
            if encomenda.status not in ESTADOS_DA_ESPERA:
                # A mesma corrida do gesto de cima, e a mesma observação: quem
                # faz a segunda passada não reabrir o que já abriu é o FILTRO da
                # consulta. Esta linha é para a encomenda que saiu da espera
                # ENTRE a varredura e a trava — um aceite, um cancelamento, a
                # outra passada do tique.
                continue
            if agora - entrou_na_espera_em(encomenda) < prazo:
                continue
            viva = Oferta.objects.filter(
                encomenda=encomenda, resultado=Oferta.Resultado.PENDENTE
            ).first()
            if viva is not None:
                viva.responder(Oferta.Resultado.CANCELADA, em=agora)
            # A CHAMADA ABERTA MOVE O PROJETO PARA O MURAL, e a coluna `pista`
            # passa a dizer isso. É a exceção do [INV-ENC-M2] escrita como dado:
            # o projeto Iniciante que a fila não colocou em 24h aparece no Mural
            # para todos os elegíveis, inclusive quem tem zero entregas
            # (`PLANO-AREA-DE-NEGOCIACAO.md` §3.1). O NÍVEL não muda, e é por
            # isso que a pista é coluna e não conta derivada: quem pergunta
            # "onde este projeto está sendo mostrado?" precisa de uma resposta,
            # e não de uma regra para reexecutar.
            encomenda.pista = Encomenda.Pista.MURAL
            encomenda.save(update_fields=["pista", "atualizada_em"])
            encomenda.mudar_status(Encomenda.Status.ABERTA, motivo=MOTIVO_DA_ABERTURA)
            abertas.append(encomenda_id)
    return tuple(abertas)


def expirar_reservas_vencidas(agora: datetime, *, site_id: str) -> tuple[object, ...]:
    """Fecha como `expirou` toda reserva do Mural cujo relógio já venceu.

    Produto: `PLANO-AREA-DE-NEGOCIACAO.md` §3.2. *"Se a negociação falhar ou o
    relógio vencer, o projeto volta ao Mural para o próximo."* Aqui mora a
    segunda metade dessa frase; a primeira é da TAR-134.

    **`negociando` não aparece no filtro, e essa ausência é a passagem de
    bastão.** A reserva que já recebeu a primeira proposta parou o relógio: quem
    manda dali em diante são as 24 horas úteis da rodada de negociação (§4.2).
    Se este gesto a varresse, ele venceria a reserva no meio da primeira rodada
    e o projeto voltaria ao Mural com uma proposta de pé.

    **O projeto volta SEM DONO.** Limpar `aluno` na mesma transação não é
    arrumação: um projeto na prateleira apontando para quem perdeu a vez é um
    estado que nenhuma tela sabe desenhar, e que a mediação de daqui a seis
    meses leria como "ele estava com o projeto quando o prazo venceu".

    E quem já teve o projeto não o recebe de volta: quem impede é o índice
    `ninguem_pega_o_mesmo_projeto_duas_vezes`, e não uma linha aqui.

    A ordem das travas é a de sempre: encomenda, depois a reserva.
    """
    vencidas = list(
        ReservaDoMural.objects.filter(
            site_id=site_id,
            resultado=ReservaDoMural.Resultado.PENDENTE,
            expira_em__lte=agora,
        )
        .order_by("expira_em", "id")
        .values_list("pk", "encomenda_id")
    )

    fechadas: list[object] = []
    for reserva_id, encomenda_id in vencidas:
        with transaction.atomic():
            projeto = Encomenda.objects.select_for_update().get(pk=encomenda_id)
            reserva = ReservaDoMural.objects.get(pk=reserva_id)
            if reserva.resultado != ReservaDoMural.Resultado.PENDENTE:
                # A outra passada chegou primeiro, ou a primeira proposta entrou
                # entre a leitura e a trava. Não é erro: é a corrida sendo
                # perdida, e vale aqui a mesma observação de
                # `expirar_ofertas_vencidas` — esta linha não fica vermelha num
                # teste de um processo só, e quem dá a idempotência da passada
                # seguinte é o FILTRO da consulta (`armadilhas/319`).
                continue
            reserva.responder(ReservaDoMural.Resultado.EXPIROU, em=agora)
            if projeto.status == Encomenda.Status.RESERVADA:
                projeto.aluno = None
                projeto.save(update_fields=["aluno", "atualizada_em"])
                projeto.mudar_status(
                    Encomenda.Status.NO_MURAL, motivo=mural.MOTIVO_DA_RESERVA_VENCIDA
                )
            fechadas.append(reserva_id)
    return tuple(fechadas)


def expirar_propostas_vencidas(agora: datetime, *, site_id: str) -> tuple[object, ...]:
    """Fecha como `expirou` toda proposta de pé cuja validade já venceu.

    Produto: `PLANO-AREA-DE-NEGOCIACAO.md` §4.2. **O destino depende de quem
    ficou calado, e essa distinção não é detalhe:**

    - **calou o CLIENTE** (recebeu a proposta do aluno e não respondeu): o
      projeto vai ao PLANTÃO, nunca para outro aluno ([INV-ENC-N7]). Mandá-lo ao
      próximo faria cada aluno da fila gastar a própria vez num cliente
      fantasma, um depois do outro, e nenhum deles saberia por quê.
    - **calou o ALUNO** (recebeu a contraproposta e não respondeu): o projeto
      volta à pista de origem, para o próximo. Ele perde este projeto e nada
      mais: nenhuma linha daqui toca `data_entrada_fila` ([INV-ENC-N5]).

    `valida_ate <= agora`: o instante exato do vencimento já conta como vencido,
    a mesma convenção de borda da oferta e da reserva. Sem uma convenção única,
    o minuto do vencimento pertenceria aos dois lados.

    **O silêncio do aluno aqui NÃO conta para a pausa automática**, e a ausência
    de `gestos.contar_o_silencio` nesta função é deliberada: aquele contador
    mede silêncio diante de uma OFERTA (lei §6.3, três silêncios pausam o
    aluno), e o degrau que o criou o mediu contra a `Oferta`. Somar a negociação
    ali mudaria a régua de uma pausa que a lei já definiu, e isso é decisão do
    mantenedor, não efeito colateral de um degrau novo.

    A ordem das travas é a de sempre: encomenda, depois a proposta.
    """
    vencidas = list(
        Proposta.objects.filter(
            site_id=site_id,
            resultado=Proposta.Resultado.PENDENTE,
            valida_ate__lte=agora,
        )
        .order_by("valida_ate", "id")
        .values_list("pk", "encomenda_id")
    )

    fechadas: list[object] = []
    for proposta_id, encomenda_id in vencidas:
        with transaction.atomic():
            projeto = Encomenda.objects.select_for_update().get(pk=encomenda_id)
            proposta = Proposta.objects.get(pk=proposta_id)
            if proposta.resultado != Proposta.Resultado.PENDENTE:
                # A outra passada chegou primeiro, ou alguém respondeu entre a
                # leitura e a trava. Não é erro: é a corrida sendo perdida, e
                # vale aqui a mesma observação dos dois gestos de cima. Quem dá
                # a idempotência da passada seguinte é o FILTRO da consulta
                # (`armadilhas/319`).
                continue
            proposta.responder(Proposta.Resultado.EXPIROU, em=agora)
            if projeto.status == Encomenda.Status.EM_NEGOCIACAO:
                if proposta.de_quem == Proposta.DeQuem.ALUNO:
                    negociacao.mandar_ao_plantao(
                        projeto, negociacao.MOTIVO_DO_CLIENTE_CALADO
                    )
                else:
                    negociacao.devolver_a_pista(
                        projeto, negociacao.MOTIVO_DO_ALUNO_CALADO
                    )
            fechadas.append(proposta_id)
    return tuple(fechadas)


def mandar_ao_plantao_o_que_ninguem_pode_pegar(
    agora: datetime, *, site_id: str
) -> tuple[object, ...]:
    """[INV-ENC-M5]: nenhum projeto encalha no Mural em silêncio.

    A quarta regra do §3.1, e ela fecha o buraco dos primeiros meses: nesse
    período ninguém terá entrega aprovada, então o Mural nasce sem ninguém para
    olhá-lo, e um projeto Intermediário ou Avançado ficaria parado para sempre.
    Mesmo relógio (`horas_para_virar_aberta`) e mesmo destino
    (`para_reclassificar`) que a lei já dava à encomenda encalhada na fila
    (§6.4). O professor decide: reclassificar, segurar, ou avisar o cliente.

    **AS DUAS CONDIÇÕES SÃO E, E NÃO OU**, e essa é a diferença entre este gesto
    e o `abrir_o_que_esperou_demais` da outra pista. Um projeto que passou o
    prazo COM elegíveis disponíveis fica onde está: ele ainda pode ser pego, e
    tirá-lo da prateleira seria recolher o que a prateleira ainda pode vender. O
    que este gesto impede é o encalhe SILENCIOSO, e não a espera.

    Os candidatos e as regras são lidos UMA VEZ, antes da varredura, pela mesma
    razão que o motor calcula a expiração uma vez: a passada tem de ser função
    de (estado, `agora`). Dois projetos com a mesma idade no mesmo tique não
    podem ter desfechos diferentes porque alguém entrou na fila no meio.

    `reservada` não é varrido de propósito: projeto reservado tem dono e
    relógio, e o relógio dele é o gesto de cima. Mas o MARCO da espera conta os
    dois estados, então uma reserva que veio e venceu não presenteia o projeto
    com 24 horas novas de silêncio.
    """
    prazo = prazo_para_virar_aberta(agora, site_id=site_id)
    regras = motor.Regras.do_banco(agora, site_id=site_id)
    candidatos = motor.candidatos_do_banco(site_id)
    na_prateleira = list(
        Encomenda.objects.filter(site_id=site_id, status=Encomenda.Status.NO_MURAL)
        .order_by("criada_em", "id")
        .values_list("pk", flat=True)
    )

    ao_plantao: list[object] = []
    for encomenda_id in na_prateleira:
        with transaction.atomic():
            projeto = Encomenda.objects.select_for_update().get(pk=encomenda_id)
            if projeto.status != Encomenda.Status.NO_MURAL:
                continue
            if (
                agora - entrou_na_espera_em(projeto, ESTADOS_DO_MURAL_RESERVAVEL)
                < prazo
            ):
                continue
            if mural.tem_elegivel_disponivel(projeto, candidatos, regras, agora):
                continue
            projeto.mudar_status(
                Encomenda.Status.PARA_RECLASSIFICAR,
                motivo=mural.MOTIVO_SEM_ELEGIVEL_NO_MURAL,
            )
            ao_plantao.append(encomenda_id)
    return tuple(ao_plantao)


def rodar(agora: datetime, *, site_id: str) -> Tique:
    """Uma passada do tique nas duas pistas. A ordem é regra, e não arrumação.

    1. **Expirar** as ofertas vencidas (a encomenda volta a `na_fila`).
    2. **Expirar** as reservas vencidas (o projeto volta ao Mural).
    3. **Expirar** as propostas vencidas (o projeto volta à pista, ou vai ao
       plantão, conforme quem ficou calado).
    4. **Abrir** o que esperou demais na fila ([INV-ENC-J9]).
    5. **Mandar ao plantão** o que encalhou no Mural ([INV-ENC-M5]).
    6. **Oferecer** o que sobrou em `na_fila` (o motor do degrau 2.3).

    O 2 vem antes do 5 pela mesma razão que o 1 vem antes do 4: o projeto cuja
    reserva acabou de vencer volta à prateleira NESTA passada, e é nesta passada
    que ele tem de ser julgado. Com a ordem trocada, um projeto sem elegível
    ficaria um tique inteiro escondido dentro de `reservada`, e o [INV-ENC-M5]
    cairia por um minuto a cada volta.

    E o 3 vem antes dos dois pela mesma razão outra vez: a negociação que morreu
    devolve o projeto à fila ou ao Mural agora, e quem acabou de voltar tem de
    ser oferecido nesta passada, e não na seguinte. O aluno solto por ela também
    volta a `disponivel` a tempo de o motor o enxergar.

    Chamar duas vezes seguidas com o mesmo estado não muda nada na segunda
    ([INV-ENC-J10]): cada gesto filtra pelo que ainda está pendente, e o que já
    foi fechado não aparece no filtro. É a mesma propriedade do motor, e é ela
    que faz um worker reiniciado no meio de uma fila cheia não duplicar nada.
    """
    expiradas = expirar_ofertas_vencidas(agora, site_id=site_id)
    reservas = expirar_reservas_vencidas(agora, site_id=site_id)
    propostas = expirar_propostas_vencidas(agora, site_id=site_id)
    abertas = abrir_o_que_esperou_demais(agora, site_id=site_id)
    ao_plantao = mandar_ao_plantao_o_que_ninguem_pode_pegar(agora, site_id=site_id)
    rodada = motor.rodar(agora, site_id=site_id)
    return Tique(
        ofertas_expiradas=expiradas,
        reservas_expiradas=reservas,
        propostas_expiradas=propostas,
        encomendas_abertas=abertas,
        projetos_ao_plantao=ao_plantao,
        rodada=rodada,
    )


def sites_com_parametros() -> tuple[str, ...]:
    """Os sites em que esta célula tem régua para trabalhar (Lei 9: uma fábrica, N lojas).

    A lista sai do BANCO, e não de uma configuração: um site cujos parâmetros
    nunca foram semeados não tem relógio nem elegibilidade, e o tique não deve
    inventar nenhum dos dois para ele. É o mesmo fail-closed do motor, um nível
    acima — em vez de estourar `ParametroAusente` a cada minuto para um site
    que ninguém instalou, ele simplesmente não é varrido.

    **O `order_by()` vazio não é enfeite, e tirá-lo quebra a função em
    silêncio.** `Parametro.Meta.ordering` é `["site_id", "chave", "-desde"]`, e o
    Django acrescenta as colunas de ordenação ao `SELECT DISTINCT` — então o
    `distinct()` passa a deduplicar pela TRINCA, e cada site volta 27 vezes, uma
    por chave. O efeito não é um erro: é o tique rodando 27 passadas por site a
    cada minuto, todas idempotentes, todas verdes, com o custo multiplicado e
    ninguém percebendo. Limpar a ordenação antes do `distinct()` é o conserto.
    """
    return tuple(
        sorted(
            Parametro.objects.order_by().values_list("site_id", flat=True).distinct()
        )
    )
