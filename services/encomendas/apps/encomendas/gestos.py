"""Os quatro gestos do aluno na fila, e o silêncio, que é a ausência deles.

Lei: `docs/decisoes/DECISAO-fila-do-primeiro-dolar.md` (§5 os invariantes de
justiça, §6 os parâmetros, §7 a escada). Produto:
`PLANO-MESTRE-FILA-DO-PRIMEIRO-DOLAR.md` §6.3 (aceitar, passar, silêncio), §6.4
(a chamada aberta), §6.5 (uma por vez) e §6.11 (a reclassificação). Cenários de
aceite 2, 3, 4 e 16 do anexo B.

Este é o degrau 2.5 da escada. Até aqui a fila só sabia OFERECER: o motor
escolhia a pessoa (degrau 2.3) e os relógios andavam sozinhos (degrau 2.4), mas
ninguém do outro lado podia responder. É este arquivo que dá voz ao aluno, e ele
tem quatro gestos e mais nada:

| Gesto | O que muda |
|---|---|
| **Aceitar** | a encomenda vai para a negociação, o aluno mantém sua disponibilidade |
| **Passar** | com um dos quatro motivos; a encomenda volta à fila, ou vai ao plantão |
| **Pausar** | o interruptor desligado: sai das ofertas, **mantém o lugar** |
| **Voltar à fila** | o interruptor religado, no MESMO lugar de antes |

ESTE ARQUIVO É O ÚNICO DONO DE `silencios_consecutivos`
--------------------------------------------------------
A coluna cresce em um lugar (`contar_o_silencio`, chamada pelo tique quando uma
oferta vence) e zera em um lugar (`zerar_o_silencio`, chamada pelos gestos). As
duas metades moram juntas de propósito: um contador que cresce num arquivo e
zera em outro é um contador que, no dia em que alguém acrescentar um gesto novo,
vai esquecer de zerar — e o aluno será pausado por "estar ocupado" no dia em que
mais respondeu.

**"Consecutivos" é o nome da regra, e ele é literal**: qualquer sinal de vida
zera a conta. O plano §6.3 nomeia dois (*"um Aceitar ou Passar zera a
contagem"*), e o terceiro sai da frase seguinte do mesmo parágrafo — *"o aluno
religa e volta ao mesmo lugar"*. Sem zerar no religar, quem voltasse da pausa
seria pausado de novo no primeiro silêncio seguinte, para sempre, e o botão
"Voltar à fila" seria enfeite.

O QUE ZERA A CONTA NÃO É O QUE MOVE O LUGAR
--------------------------------------------
Nada aqui escreve em `data_entrada_fila`, e isso é [INV-ENC-J4]: passar, ficar em
silêncio e pausar **nunca** custam a vez; só o abandono custa, e o abandono é da
Fase 5. O guarda daquele invariante varre este arquivo com `ast`
(`tests/test_inv_j4_so_abandono_muda_o_lugar.py`) e reprova a linha antes de ela
chegar à `main`.

A CHAMADA ABERTA MUDA UMA COISA SÓ, E ELA É DADO
-------------------------------------------------
`aceitar_a_chamada_aberta` **não tem régua própria de elegibilidade**: ela chama
o mesmo `motor.por_que_nao` que a fila chama, com a mesma `Vaga` — só que com a
memória de quem já viu a encomenda VAZIA. É exatamente isso que o [INV-ENC-J6]
escreve ("nenhum aluno recebe a mesma encomenda duas vezes, **salvo em chamada
aberta**"), e escrever a exceção como dado em vez de como um `if` é o que impede
uma segunda régua de elegibilidade de nascer aqui e divergir da primeira no
primeiro parâmetro que mudar.

O nível mínimo continua valendo (plano §6.4), e continua valendo porque é a
mesma função que o mede.

DOIS ACEITES AO MESMO TEMPO: QUEM RESOLVE É O BANCO
----------------------------------------------------
Chamada aberta é o único lugar desta célula onde duas pessoas disputam a mesma
encomenda no mesmo segundo (cenário 4 do anexo B). Nenhum `if` em Python resolve
isso: os dois processos leem `status = aberta` antes de qualquer um escrever.
Quem resolve é `select_for_update` na linha da encomenda — o segundo espera, e
quando entra encontra `em_negociacao` e recebe a recusa nomeada `JA_FOI_LEVADA`.

**A ordem das travas é sempre encomenda → perfil**, nos três gestos e no tique.
Duas ordens diferentes na mesma célula é um `deadlock` esperando o dia de
movimento, e ele não aparece em teste nenhum.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from django.db import transaction

from . import motor
from .models import Encomenda, Oferta, Parametro, PerfilProfissional

# ---------------------------------------------------------------------------
# AS RAZÕES DE UMA RECUSA — uma por nome, como os desfechos do motor
# ---------------------------------------------------------------------------
#
# A tela do aluno (Fase 4) mostra UMA frase quando um botão não funciona, e a
# frase sai daqui. Uma recusa sem nome vira "algo deu errado", que é a mensagem
# que faz a pessoa clicar de novo e o plantão não ter o que responder.

OFERTA_JA_RESPONDIDA = "oferta_ja_respondida"
NAO_E_SUA = "nao_e_sua"
MOTIVO_FORA_DOS_QUATRO = "motivo_fora_dos_quatro"
NAO_ESTA_ABERTA = "nao_esta_aberta"
JA_FOI_LEVADA = "ja_foi_levada"
JA_ESTA_PAUSADO = "ja_esta_pausado"
JA_ESTA_DISPONIVEL = "ja_esta_disponivel"
ESTA_TRABALHANDO = "esta_trabalhando"
A_PAUSA_NAO_E_SUA = "a_pausa_nao_e_sua"

# As pausas que o próprio aluno desliga. As outras duas do vocabulário
# (`por_segundo_abandono`, com prazo de 30 dias, e `suspensao_pelo_plantao`) são
# decisão de outra pessoa: se o botão "Voltar à fila" as desfizesse, a pausa de
# 30 dias do plano §6.6 e a suspensão do plantão seriam decorativas.
PAUSAS_QUE_O_ALUNO_RELIGA = frozenset(
    {
        PerfilProfissional.ModoDaPausa.MANUAL,
        PerfilProfissional.ModoDaPausa.POR_SILENCIO,
    }
)

MOTIVO_DO_ACEITE = "o aluno aceitou a oferta e a negociacao comecou"
MOTIVO_DO_ACEITE_ABERTO = "o aluno levou a chamada aberta"
MOTIVO_DO_PASSE = "o aluno passou a oferta"
MOTIVO_DA_RECLASSIFICACAO = "passes de nao me sinto pronto: o plantao reclassifica"


@dataclass(frozen=True)
class Desfecho:
    """O que aconteceu com um gesto: feito, ou recusado com razão nomeada.

    `encomenda_em` é o status em que a encomenda ficou, e ele vem junto porque
    quem passou precisa saber, na mesma resposta, se ela voltou para a fila ou
    foi para o plantão (plano §6.11). Uma segunda consulta responderia outra
    coisa se o tique mexesse nela no meio. Fica vazio nos gestos do interruptor,
    que não são sobre encomenda nenhuma.
    """

    feito: bool
    razao: str = ""
    encomenda_em: str = ""


# ---------------------------------------------------------------------------
# O CONTADOR DE SILÊNCIOS — as duas metades, no mesmo arquivo
# ---------------------------------------------------------------------------


def zerar_o_silencio(perfil: PerfilProfissional) -> None:
    """Qualquer sinal de vida zera a conta de silêncios CONSECUTIVOS.

    Escrever só quando há o que zerar não é economia de banco: é não sujar
    `atualizado_em` de todo mundo a cada gesto, que é a coluna pela qual a tela
    de plantão vai ordenar "quem apareceu por último".
    """
    if perfil.silencios_consecutivos:
        perfil.silencios_consecutivos = 0
        perfil.save(update_fields=["silencios_consecutivos", "atualizado_em"])


def contar_o_silencio(
    perfil: PerfilProfissional, agora: datetime, *, site_id: str
) -> bool:
    """Um silêncio a mais, e a pausa automática quando a conta chega ao limite.

    Devolve se a pausa aconteceu agora. Quem chama é o tique, dentro da MESMA
    transação em que a oferta se fecha: contar o silêncio numa transação e pausar
    noutra deixaria, na queda entre as duas, um aluno com três silêncios e o
    interruptor ligado — que é o estado que esta função existe para não permitir.

    **O limite é parâmetro** (`silencios_para_pausa`, lei §6), lido no valor
    vigente em `agora`. A comparação é `>=` e não `==` de propósito: com `==`, um
    perfil que chegasse a quatro por qualquer caminho nunca mais seria pausado, e
    o guarda morreria em silêncio no dia em que mais importasse.

    A pausa nasce **sem prazo** (`pausa_ate` nulo): quem religa é o aluno, no
    botão "Voltar à fila", e o lugar dele continua guardado.
    """
    perfil.silencios_consecutivos += 1
    perfil.save(update_fields=["silencios_consecutivos", "atualizado_em"])

    limite = Parametro.inteiro_vigente("silencios_para_pausa", agora, site_id=site_id)
    if perfil.silencios_consecutivos < limite:
        return False
    if not perfil.pode_ir_para(PerfilProfissional.Disponibilidade.PAUSADO):
        # Já pausado, ou trabalhando. Não é erro: é o estado já sendo o certo.
        return False
    perfil.mudar_disponibilidade(
        PerfilProfissional.Disponibilidade.PAUSADO,
        modo_da_pausa=PerfilProfissional.ModoDaPausa.POR_SILENCIO,
    )
    return True


# ---------------------------------------------------------------------------
# OS GESTOS SOBRE UMA OFERTA — aceitar e passar
# ---------------------------------------------------------------------------


def _travar_a_oferta(oferta_id, perfil_id, *, site_id: str):
    """Trava a encomenda, relê a oferta, e confere que o gesto é de quem diz ser.

    Devolve `(oferta, encomenda, None)` quando o gesto pode seguir, e
    `(None, None, Desfecho)` quando não. A recusa é nomeada porque é ela que a
    tela do aluno vai mostrar.

    "Reconhecer não é autorizar" é invariante desta célula: quem devolve o dono
    do cookie é a `identidade`, e quem decide se aquela pessoa pode responder
    ESTA oferta é isto aqui, fail-closed. Oferta que não existe e oferta de outra
    pessoa recebem a MESMA razão de propósito: distinguir as duas contaria, a
    quem tentasse adivinhar identificadores, quais existem.
    """
    oferta = Oferta.objects.filter(pk=oferta_id, site_id=site_id).first()
    if oferta is None:
        return None, None, Desfecho(feito=False, razao=NAO_E_SUA)
    # Trava a ENCOMENDA primeiro, sempre: é a linha que o tique, o motor e os
    # dois gestos disputam, e uma ordem só de travamento é o que evita deadlock.
    encomenda = Encomenda.objects.select_for_update().get(pk=oferta.encomenda_id)
    oferta.refresh_from_db()
    if oferta.aluno_id != perfil_id:
        return None, None, Desfecho(feito=False, razao=NAO_E_SUA)
    if oferta.resultado != Oferta.Resultado.PENDENTE:
        return (
            None,
            None,
            Desfecho(
                feito=False,
                razao=OFERTA_JA_RESPONDIDA,
                encomenda_em=encomenda.status,
            ),
        )
    return oferta, encomenda, None


@transaction.atomic
def aceitar(oferta_id, perfil_id, agora: datetime, *, site_id: str) -> Desfecho:
    """O aluno aceita a oferta: a encomenda vai negociar, sem travar o aluno.

    **Aceitar deixou de ser começar a produzir**: com a negociação que o
    mantenedor liberou em 04/09/2026, o valor e o prazo só existem depois do
    acordo, e por isso o destino é `em_negociacao`
    (`PLANO-AREA-DE-NEGOCIACAO.md` §5; a máquina de estado já dizia isso desde a
    TAR-140). O que a negociação FAZ a partir daí é o degrau 2.12.

    O aluno continua disponível no mesmo gesto. O motor consulta a negociação
    viva para impedir a oferta seguinte, sem punir o aluno pela espera do cliente.

    **A corrida com o relógio é resolvida pela trava, não por uma comparação.**
    Um aceite que chega no mesmo segundo em que o tique expira a oferta não é
    julgado por `expira_em <= agora` aqui: os dois travam a encomenda, e o
    primeiro a entrar decide. Comparar de novo daria a ESTA função uma segunda
    definição de "vencida", e as duas divergiriam na borda.
    """
    oferta, encomenda, recusa = _travar_a_oferta(oferta_id, perfil_id, site_id=site_id)
    if recusa is not None:
        return recusa

    perfil = PerfilProfissional.objects.select_for_update().get(pk=perfil_id)
    if perfil.disponibilidade != PerfilProfissional.Disponibilidade.DISPONIVEL:
        return Desfecho(feito=False, razao=motor.NAO_ESTA_DISPONIVEL)

    oferta.responder(Oferta.Resultado.ACEITA, em=agora)
    encomenda.aluno = perfil
    encomenda.save(update_fields=["aluno", "atualizada_em"])
    encomenda.mudar_status(
        Encomenda.Status.EM_NEGOCIACAO,
        ator_id=perfil.pessoa_id,
        motivo=MOTIVO_DO_ACEITE,
    )
    zerar_o_silencio(perfil)
    return Desfecho(feito=True, encomenda_em=encomenda.status)


@transaction.atomic
def passar(
    oferta_id, perfil_id, motivo: str, agora: datetime, *, site_id: str
) -> Desfecho:
    """O aluno passa a oferta, com um dos quatro motivos. Instantâneo e sem punição.

    **O motivo é obrigatório e o vocabulário é fechado** (plano §6.3: *"Por quê?
    Um toque"* — sem tempo agora, valor baixo, não curto esse tipo, ainda não me
    sinto pronto). O banco já recusa passe sem motivo
    (`motivo_de_passe_so_em_oferta_passada`) e motivo fora da lista não é uma
    escolha do vocabulário: a conferência é aqui, ANTES de qualquer escrita, para
    a tela receber uma razão em vez de um `IntegrityError`.

    Os quatro não são enfeite de métrica: `nao_me_sinto_pronto` é o único que
    tem consequência mecânica (a reclassificação do §6.11), e os outros três só
    existem para que ele signifique alguma coisa. Um botão único de "passar"
    tornaria a reclassificação impossível de calcular.

    **Passar nunca custa o lugar na fila** ([INV-ENC-J4]) e nunca devolve esta
    encomenda a quem passou ([INV-ENC-J6], memória da própria `Oferta`).
    """
    if motivo not in Oferta.MotivoDoPasse.values:
        return Desfecho(feito=False, razao=MOTIVO_FORA_DOS_QUATRO)

    oferta, encomenda, recusa = _travar_a_oferta(oferta_id, perfil_id, site_id=site_id)
    if recusa is not None:
        return recusa

    perfil = PerfilProfissional.objects.select_for_update().get(pk=perfil_id)
    oferta.responder(Oferta.Resultado.PASSOU, motivo_passe=motivo, em=agora)
    zerar_o_silencio(perfil)

    if _passou_do_limite_de_nao_me_sinto_pronto(encomenda, agora, site_id=site_id):
        encomenda.mudar_status(
            Encomenda.Status.PARA_RECLASSIFICAR,
            ator_id=perfil.pessoa_id,
            motivo=MOTIVO_DA_RECLASSIFICACAO,
        )
    else:
        encomenda.mudar_status(
            Encomenda.Status.NA_FILA,
            ator_id=perfil.pessoa_id,
            motivo=MOTIVO_DO_PASSE,
        )
    return Desfecho(feito=True, encomenda_em=encomenda.status)


def _passou_do_limite_de_nao_me_sinto_pronto(
    encomenda: Encomenda, agora: datetime, *, site_id: str
) -> bool:
    """A regra da reclassificação (plano §6.11), contada na própria `Oferta`.

    *"Dois 'Ainda não me sinto pronto(a)' na mesma encomenda → ela sai da fila
    para o plantão reclassificar"*. O quanto é parâmetro
    (`passes_nao_pronto_para_reclassificar`), e a contagem é de TODAS as ofertas
    desta encomenda, de qualquer rodada: o sinal é sobre a ENCOMENDA estar no
    nível errado, e uma encomenda que voltou à fila continua sendo a mesma peça
    difícil demais.

    E é sinal, nunca punição: quem disse "não me sinto pronto" mantém o lugar, a
    contagem e o título. O que muda de lugar é a encomenda.
    """
    limite = Parametro.inteiro_vigente(
        "passes_nao_pronto_para_reclassificar", agora, site_id=site_id
    )
    passes = Oferta.objects.filter(
        encomenda=encomenda,
        resultado=Oferta.Resultado.PASSOU,
        motivo_passe=Oferta.MotivoDoPasse.NAO_ME_SINTO_PRONTO,
    ).count()
    return passes >= limite


# ---------------------------------------------------------------------------
# A CHAMADA ABERTA — o primeiro elegível que aceitar leva
# ---------------------------------------------------------------------------


@transaction.atomic
def aceitar_a_chamada_aberta(
    encomenda_id, perfil_id, agora: datetime, *, site_id: str
) -> Desfecho:
    """Cenário 4 do anexo B: a encomenda está `aberta`, e o primeiro que aceitar leva.

    Não há oferta aqui, e a ausência é o desenho: a chamada aberta é o estado em
    que a plataforma parou de escolher e avisou todos os elegíveis (plano §6.4).
    Criar uma `Oferta` já aceita para "ter registro" seria mentir na auditoria de
    justiça — a taxa de aceite e o tempo de resposta da fila passariam a somar
    ofertas que nunca ficaram pendentes. O registro é o `aluno` da encomenda e a
    linha de `MudancaDeStatus`, com autor.

    A elegibilidade é a MESMA do motor, com uma diferença que é dado e não código:
    `ja_ofertada_a` vazio. É a exceção literal do [INV-ENC-J6] — quem passou ou
    ficou em silêncio nesta encomenda pode levá-la na chamada aberta.
    """
    encomenda = (
        Encomenda.objects.select_for_update()
        .filter(pk=encomenda_id, site_id=site_id)
        .first()
    )
    if encomenda is None:
        return Desfecho(feito=False, razao=NAO_ESTA_ABERTA)
    if encomenda.status != Encomenda.Status.ABERTA:
        # Já em negociação quer dizer que alguém chegou primeiro; qualquer outro
        # estado quer dizer que esta encomenda nunca esteve em chamada aberta.
        razao = (
            JA_FOI_LEVADA
            if encomenda.status == Encomenda.Status.EM_NEGOCIACAO
            else NAO_ESTA_ABERTA
        )
        return Desfecho(feito=False, razao=razao, encomenda_em=encomenda.status)

    perfil = (
        PerfilProfissional.objects.select_for_update()
        .filter(pk=perfil_id, site_id=site_id)
        .first()
    )
    if perfil is None:
        return Desfecho(feito=False, razao=motor.FORA_DA_FILA)

    regras = motor.Regras.do_banco(agora, site_id=site_id)
    vaga = motor.Vaga(encomenda_id=encomenda.pk, nivel=encomenda.nivel)
    candidato = motor.Candidato(
        perfil_id=perfil.id,
        titulo_banca=perfil.titulo_banca,
        disponibilidade=perfil.disponibilidade,
        entregas_aprovadas=perfil.entregas_aprovadas,
        data_entrada_fila=perfil.data_entrada_fila,
        tem_oferta_pendente=Oferta.objects.filter(
            aluno=perfil, resultado=Oferta.Resultado.PENDENTE
        ).exists(),
        abandonos=tuple(perfil.abandonos or ()),
    )
    razao = motor.por_que_nao(vaga, candidato, regras, agora)
    if razao:
        return Desfecho(feito=False, razao=razao, encomenda_em=encomenda.status)

    encomenda.aluno = perfil
    encomenda.save(update_fields=["aluno", "atualizada_em"])
    encomenda.mudar_status(
        Encomenda.Status.EM_NEGOCIACAO,
        ator_id=perfil.pessoa_id,
        motivo=MOTIVO_DO_ACEITE_ABERTO,
    )
    perfil.mudar_disponibilidade(PerfilProfissional.Disponibilidade.TRABALHANDO)
    zerar_o_silencio(perfil)
    return Desfecho(feito=True, encomenda_em=encomenda.status)


# ---------------------------------------------------------------------------
# O INTERRUPTOR — "Disponível" e "Voltar à fila"
# ---------------------------------------------------------------------------


@transaction.atomic
def pausar(perfil_id, *, site_id: str) -> Desfecho:
    """O aluno desliga o interruptor. Sai das ofertas e **mantém o lugar**.

    Só de "disponível", e é aí que este gesto se separa da pausa que o plantão
    aplica: a máquina de disponibilidade também permite `trabalhando → pausado`,
    mas essa seta é a SUSPENSÃO (lei §3.10), decidida por outra pessoa. Quem está
    no meio de uma encomenda não se desliga da fila pelo próprio botão — ele
    entrega ou abandona, e ambos são outros gestos.
    """
    perfil = PerfilProfissional.objects.select_for_update().get(
        pk=perfil_id, site_id=site_id
    )
    if perfil.disponibilidade == PerfilProfissional.Disponibilidade.PAUSADO:
        return Desfecho(feito=False, razao=JA_ESTA_PAUSADO)
    if perfil.disponibilidade == PerfilProfissional.Disponibilidade.TRABALHANDO:
        return Desfecho(feito=False, razao=ESTA_TRABALHANDO)

    perfil.mudar_disponibilidade(
        PerfilProfissional.Disponibilidade.PAUSADO,
        modo_da_pausa=PerfilProfissional.ModoDaPausa.MANUAL,
    )
    return Desfecho(feito=True)


@transaction.atomic
def religar(perfil_id, agora: datetime, *, site_id: str) -> Desfecho:
    """ "Voltar à fila": o aluno religa e volta ao MESMO lugar (plano §6.3).

    O lugar continua guardado porque `data_entrada_fila` não é tocada aqui nem em
    lugar nenhum desta célula ([INV-ENC-J4]) — não há nada a restaurar, e é essa
    ausência que faz a promessa da tela ser verdade.

    **Nem toda pausa é do aluno.** A que o plantão aplica e a de 30 dias do
    segundo abandono (plano §6.6) não se desfazem por este botão, e a de prazo
    também não se desfaz antes da hora: um botão que apagasse as duas tornaria as
    duas decorativas. A recusa é nomeada, para a tela poder dizer até quando.
    """
    perfil = PerfilProfissional.objects.select_for_update().get(
        pk=perfil_id, site_id=site_id
    )
    if perfil.disponibilidade == PerfilProfissional.Disponibilidade.DISPONIVEL:
        return Desfecho(feito=False, razao=JA_ESTA_DISPONIVEL)
    if perfil.disponibilidade == PerfilProfissional.Disponibilidade.TRABALHANDO:
        return Desfecho(feito=False, razao=ESTA_TRABALHANDO)
    if perfil.modo_da_pausa not in PAUSAS_QUE_O_ALUNO_RELIGA:
        return Desfecho(feito=False, razao=A_PAUSA_NAO_E_SUA)
    if perfil.pausa_ate is not None and perfil.pausa_ate > agora:
        return Desfecho(feito=False, razao=A_PAUSA_NAO_E_SUA)

    perfil.mudar_disponibilidade(PerfilProfissional.Disponibilidade.DISPONIVEL)
    zerar_o_silencio(perfil)
    return Desfecho(feito=True)
