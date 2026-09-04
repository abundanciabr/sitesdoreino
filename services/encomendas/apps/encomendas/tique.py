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

O QUE ESTE ARQUIVO **NÃO** FAZ, E O PRÓXIMO DEGRAU FAZ INTEIRO
---------------------------------------------------------------
**O contador `silencios_consecutivos` NÃO é tocado aqui**, e a ausência é
deliberada. O plano §7.4 escreve a pausa automática em uma frase só —
*"expirou; silencios_consecutivos += 1; se == 3 → pausar aluno"* — e as duas
metades são o mesmo gesto: um contador que cresce e ninguém lê é pior do que
contador nenhum, porque parece pronto. O degrau 2.5 (TAR-123) traz as duas
juntas, com o parâmetro `silencios_para_pausa`, o "Você parece estar
ocupado(a)", o religar sem perder o lugar e o Aceitar/Passar que zera a conta.
Quem escrever aquele degrau acrescenta o incremento em
`expirar_ofertas_vencidas` — o único lugar desta célula onde um silêncio
acontece.

Também não são deste degrau: o que a chamada aberta FAZ depois de aberta
(avisar os elegíveis, o primeiro que aceitar leva), os prazos de produção, o
abandono, a aprovação tácita e o SLA do revisor. Todos vão pendurar-se neste
mesmo tique quando chegarem, e é para isso que ele devolve um resumo nomeado em
vez de `None`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from django.db import transaction

from . import motor
from .models import Encomenda, MudancaDeStatus, Oferta, Parametro
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
    encomendas_abertas: tuple[object, ...] = ()
    rodada: motor.Rodada = field(default_factory=motor.Rodada)


def entrou_na_espera_em(encomenda: Encomenda) -> datetime:
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
    nasce em `na_fila` (é o `default` do modelo) e essa primeira entrada não
    gera linha de histórico.
    """
    entrada = (
        MudancaDeStatus.objects.filter(encomenda=encomenda, para__in=ESTADOS_DA_ESPERA)
        .exclude(de__in=ESTADOS_DA_ESPERA)
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
    escrevesse.
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
            oferta.responder(Oferta.Resultado.EXPIROU, em=agora)
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
            encomenda.mudar_status(Encomenda.Status.ABERTA, motivo=MOTIVO_DA_ABERTURA)
            abertas.append(encomenda_id)
    return tuple(abertas)


def rodar(agora: datetime, *, site_id: str) -> Tique:
    """Uma passada do tique: expira, abre, oferece. Nessa ordem, e sem estado próprio.

    Chamar duas vezes seguidas com o mesmo estado não muda nada na segunda
    ([INV-ENC-J10]): cada gesto filtra pelo que ainda está pendente, e o que já
    foi fechado não aparece no filtro. É a mesma propriedade do motor, e é ela
    que faz um worker reiniciado no meio de uma fila cheia não duplicar nada.
    """
    expiradas = expirar_ofertas_vencidas(agora, site_id=site_id)
    abertas = abrir_o_que_esperou_demais(agora, site_id=site_id)
    rodada = motor.rodar(agora, site_id=site_id)
    return Tique(ofertas_expiradas=expiradas, encomendas_abertas=abertas, rodada=rodada)


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
