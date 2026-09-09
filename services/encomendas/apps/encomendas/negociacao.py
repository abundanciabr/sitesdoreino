"""A negociação: o formulário que vai e volta, as rodadas contadas e o Acordo.

Produto: `PLANO-AREA-DE-NEGOCIACAO.md` §4 (a Proposta e o Acordo), §7 (a
proteção do aluno) e §8 (os invariantes N1 a N8). Lei:
`docs/decisoes/DECISAO-fila-do-primeiro-dolar.md` §2.1, que registra a
reabertura que o mantenedor decidiu em 04/09/2026. Este é o degrau 2.12 da
escada (TAR-134), e ele nasce da `ReservaDoMural` que o degrau 2.11 criou.

NEGOCIAR NÃO É CONVERSAR
-------------------------
O [INV-ENC-S1] continua valendo e não foi revogado: nenhum texto livre entre
cliente e aluno fora dos campos estruturados, e todos visíveis ao plantão. Este
arquivo não enfraquece o invariante; ele parte da percepção que o torna
desnecessário enfraquecer: **negociar é trocar propostas.** Uma proposta é um
FORMULÁRIO de seis campos, a contraproposta é o mesmo formulário preenchido
pelo outro lado, e não existe caixa de mensagem em lugar nenhum
([INV-ENC-N1]).

QUEM PROPÕE PRIMEIRO É O ALUNO, E ISSO É DESENHO
-------------------------------------------------
Quem põe preço em trabalho é quem vai fazê-lo (§4.2). A regra inversa (o
cliente abre com um número) é a âncora baixa, que é o jeito clássico de o
comprador definir o preço antes de o profissional falar, e numa escola em que o
cliente é a própria escola ela seria ainda mais desigual.

O RELÓGIO DA RESERVA PARA NA PRIMEIRA PROPOSTA
-----------------------------------------------
As três horas úteis da reserva do Mural são para o aluno olhar o briefing e
propor, e só até isso. Assim que ele propõe, `propor` fecha a reserva em
`negociando` e quem manda passam a ser as 24 horas úteis por rodada. O gancho é
do degrau 2.11, que já criou o estado e já o deixou fora da varredura do tique;
aqui ele é usado, e não reescrito.

NENHUMA LINHA DE COBRANÇA, E ISSO É ORDEM DELE
-----------------------------------------------
A trava de 22/08/2026 continua de pé, e o mantenedor a reafirmou em 04/09/2026:
*"só a escola por enquanto"*. Então não há checkout, não há Mercado Pago e não
há webhook neste arquivo. A confirmação de pagamento é o plantão registrando
"pago pela escola", com autor e data (`confirmar_pagamento_pela_escola`), e é
ela que o [INV-ENC-N4] mede.

O QUE NÃO É DESTE DEGRAU
-------------------------
- **As telas** são as Fases 4 (o aluno) e 7 (o plantão). Aqui existem os gestos,
  e não as páginas. `para_o_plantao` é a leitura que a Fase 7 vai desenhar, e
  ela nasce agora porque é ela que prova a segunda metade do [INV-ENC-N1]
  ("todos visíveis ao plantão").
- **O piso por nível avisa, e nunca bloqueia.** `aviso_de_piso` devolve o piso
  quando a proposta fica abaixo dele, e devolve `None` quando não há piso
  gravado, que é o estado de hoje, de propósito (§9: o número sai do piloto de
  papel). Nenhum caminho deste arquivo recusa uma proposta por causa do piso:
  bloquear seria decidir pelo aluno, avisar é ensinar.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from django.db import IntegrityError, transaction

from .gestos import JA_NEGOCIA_OUTRO_PROJETO, Desfecho
from .models import (
    Acordo,
    Encomenda,
    Parametro,
    PerfilProfissional,
    Proposta,
    ReservaDoMural,
)
from .relogio import calcular_validade_da_proposta

# ---------------------------------------------------------------------------
# AS RAZÕES DE UMA RECUSA, uma por nome, como as do motor, dos gestos e do Mural
# ---------------------------------------------------------------------------

NAO_ESTA_EM_NEGOCIACAO = "nao_esta_em_negociacao"
NAO_E_A_SUA_VEZ = "nao_e_a_sua_vez"
O_ALUNO_PROPOE_PRIMEIRO = "o_aluno_propoe_primeiro"
RODADAS_ESGOTADAS = "rodadas_esgotadas"
JUSTIFICATIVA_LONGA_DEMAIS = "justificativa_longa_demais"
ENTREGAVEL_FORA_DO_BRIEFING = "entregavel_fora_do_briefing"
SEM_PROPOSTA_DE_PE = "sem_proposta_de_pe"
SEM_ACORDO = "sem_acordo"
SEM_PAGAMENTO_CONFIRMADO = "sem_pagamento_confirmado"
SEM_AUTOR = "sem_autor"
SEM_MOTIVO = "sem_motivo"

# Os motivos escritos no histórico, para a mediação de daqui a seis meses ter o
# que ler. Nenhum inventa autor: `ator_id` vazio quer dizer "foi o relógio".
MOTIVO_DA_PRIMEIRA_PROPOSTA = "o aluno propos: a negociacao comecou"
MOTIVO_DO_ACORDO = "a proposta de pe foi aceita: valor, prazo e entregaveis congelaram"
MOTIVO_DAS_RODADAS_ESGOTADAS = (
    "as rodadas de negociacao se esgotaram sem acordo: vai ao plantao"
)
MOTIVO_DO_CLIENTE_CALADO = (
    "a proposta venceu sem resposta do cliente: vai ao plantao, nunca a outro aluno"
)
MOTIVO_DO_ALUNO_CALADO = (
    "a contraproposta venceu sem resposta do aluno: volta a pista de origem"
)
MOTIVO_DA_NEGOCIACAO_SEM_PROPOSTA = (
    "a negociacao venceu sem primeira proposta: vai ao plantao"
)
MOTIVO_DA_DESISTENCIA_DO_ALUNO = "o aluno desistiu da negociacao: volta a pista"
MOTIVO_DA_DESISTENCIA_DO_CLIENTE = "o cliente desistiu da negociacao: vai ao plantao"
MOTIVO_DO_CAIXA = "o acordo fechou: o projeto foi ao caixa"
MOTIVO_DO_COMECO_DA_PRODUCAO = (
    "pagamento confirmado com autor: a producao comecou e o prazo passou a correr"
)

# OS DOIS ESTADOS DE ONDE SE PROPÕE. `reservada` é a primeira proposta de quem
# pegou no Mural (e é ela que para o relógio da reserva); `em_negociacao` é o
# resto da conversa, nas duas pistas. `aberta` e `oferecida` não estão aqui de
# propósito: delas se sai por `gestos.aceitar` e
# `gestos.aceitar_a_chamada_aberta`, que já levam a encomenda a `em_negociacao`.
ESTADOS_QUE_PROPOEM = frozenset(
    {Encomenda.Status.RESERVADA, Encomenda.Status.EM_NEGOCIACAO}
)


# ---------------------------------------------------------------------------
# AS LEITURAS: o que está de pé, o que o briefing permite, o que o plantão vê
# ---------------------------------------------------------------------------


def proposta_de_pe(projeto: Encomenda) -> Proposta | None:
    """A proposta que está esperando resposta, ou `None`.

    Uma definição só para "de pé", e não um filtro repetido em cada gesto: a
    trava do banco (`uma_proposta_viva_por_encomenda`) garante que nunca há
    duas, e por isso `first()` aqui é a resposta inteira, e não uma escolha.
    """
    return Proposta.objects.filter(
        encomenda=projeto, resultado=Proposta.Resultado.PENDENTE
    ).first()


def entregaveis_do_briefing(projeto: Encomenda) -> tuple[str, ...]:
    """A lista FECHADA de entregáveis que o briefing daquele cartão declarou.

    O plano §4.1 diz *"lista fechada, marcada a partir do briefing"*, e fechada
    quer dizer isto: nenhuma proposta inventa um entregável que o cliente nunca
    descreveu. Um briefing sem a chave devolve lista vazia, e o lado fechado é o
    certo: propor entregáveis que ninguém pediu é exatamente o texto livre que o
    [INV-ENC-N1] existe para impedir, com outro nome.
    """
    return tuple(projeto.briefing.get("entregaveis", ()) or ())


def para_o_plantao(projeto: Encomenda) -> tuple[dict, ...]:
    """Tudo o que os dois lados trocaram, do primeiro formulário ao último.

    A segunda metade do [INV-ENC-N1] ("todos visíveis ao plantão") em uma
    função, e é ela que a tela da Fase 7 vai desenhar. Devolve **todos** os
    campos do formulário de **todas** as rodadas, inclusive as mortas: uma
    negociação em que o plantão só visse a proposta de pé não seria julgável, e
    julgar é para o que o registro existe.

    A lista de campos vem de `Proposta.CAMPOS_DO_FORMULARIO`, e não de uma cópia
    escrita aqui, porque uma segunda lista seria a que esquece o campo novo, e
    esquecer um campo aqui é um pedaço de conversa escondido do plantão.
    """
    return tuple(
        {
            "de_quem": proposta.de_quem,
            "rodada": proposta.rodada,
            "resultado": proposta.resultado,
            "criada_em": proposta.criada_em,
            **{
                campo: getattr(proposta, campo)
                for campo in Proposta.CAMPOS_DO_FORMULARIO
            },
        }
        for proposta in Proposta.objects.filter(encomenda=projeto).order_by(
            "criada_em", "id"
        )
    )


def aviso_de_piso(
    projeto: Encomenda, valor_cents: int, agora: datetime, *, site_id: str
) -> int | None:
    """O piso do nível, quando a proposta fica abaixo dele. `None` quando não há aviso.

    Produto: §7, trava 1. **Isto avisa, e nunca bloqueia.** A escola pode ver um
    aluno se subvalorizando e conversar com ele; bloquear seria decidir por ele,
    avisar é ensinar. Por isso nenhum gesto deste arquivo chama esta função para
    recusar nada: quem a chama é a tela do aluno, antes de enviar, e a do
    plantão, para acender a linha.

    **Sem piso gravado, não há aviso**, e o `None` é decisão e não descuido: o
    §9 diz que o piso sai do piloto de papel, e chutar um número agora seria
    inventá-lo para depois defendê-lo. É o único parâmetro desta célula lido sem
    fail-closed, e a razão é essa: aqui a ausência tem significado próprio.
    """
    linha = Parametro.vigente_em(
        f"piso_por_nivel.{projeto.nivel}", agora, site_id=site_id
    )
    if linha is None:
        return None
    piso = int(linha.valor)
    return piso if valor_cents < piso else None


# ---------------------------------------------------------------------------
# OS DOIS DESTINOS DE UMA NEGOCIAÇÃO QUE MORRE, e a diferença entre eles
# ---------------------------------------------------------------------------


def volta_para(projeto: Encomenda) -> str:
    """A pista de origem deste projeto: `na_fila` ou `no_mural`.

    O nível decide, e não a coluna `pista`, quando os dois discordam: um projeto
    Iniciante que chegou ao Mural pela chamada aberta tem `pista=mural`, e
    devolvê-lo a `no_mural` seria pô-lo na prateleira reservável, que é
    exatamente o que o [INV-ENC-M2] proíbe (e o banco recusa,
    `iniciante_nunca_no_mural_reservavel`). A fila é a casa dele.
    """
    if projeto.nivel == Encomenda.Nivel.INICIANTE:
        return Encomenda.Status.NA_FILA
    return (
        Encomenda.Status.NO_MURAL
        if projeto.pista == Encomenda.Pista.MURAL
        else Encomenda.Status.NA_FILA
    )


def _soltar_o_aluno(projeto: Encomenda) -> None:
    """Devolve o projeto à prateleira sem dono, e o aluno às ofertas.

    **Nada aqui toca `data_entrada_fila`**, e é isso que faz o [INV-ENC-N5]
    valer: propor, ser recusado, deixar vencer ou desistir custam este projeto e
    nada mais. Quem perde o lugar na fila é só quem abandona ([INV-ENC-J4]).

    E o aluno volta a `disponivel` porque a negociação acabou. Sem esta linha,
    um cliente que sumisse deixaria o aluno marcado como "trabalhando" para
    sempre, fora da fila, por uma demora que não foi dele, que é a injustiça que
    o §4.2 descreve com todas as letras. Quem está `pausado` fica onde está: a
    pausa é do aluno ou do plantão, e não desta função.
    """
    if projeto.aluno_id is not None:
        perfil = PerfilProfissional.objects.select_for_update().get(pk=projeto.aluno_id)
        if perfil.disponibilidade == PerfilProfissional.Disponibilidade.TRABALHANDO:
            perfil.mudar_disponibilidade(PerfilProfissional.Disponibilidade.DISPONIVEL)
    projeto.aluno = None
    projeto.save(update_fields=["aluno", "atualizada_em"])


def devolver_a_pista(projeto: Encomenda, motivo: str) -> None:
    """O ALUNO calou ou desistiu: o projeto volta à pista de origem, para o próximo.

    Ele não perde o lugar na fila, mas perde este projeto (§4.2). A coluna
    `pista` volta a dizer a verdade junto com o status, porque um projeto
    `na_fila` com `pista=mural` seria lido de dois jeitos por dois pedaços de
    código, e o segundo a ler é o que erra.
    """
    destino = volta_para(projeto)
    _soltar_o_aluno(projeto)
    projeto.pista = (
        Encomenda.Pista.MURAL
        if destino == Encomenda.Status.NO_MURAL
        else Encomenda.Pista.FILA
    )
    projeto.save(update_fields=["pista", "atualizada_em"])
    projeto.mudar_status(destino, motivo=motivo)


def mandar_ao_plantao(projeto: Encomenda, motivo: str) -> None:
    """O CLIENTE calou, desistiu, ou as rodadas acabaram: o projeto vai ao plantão.

    **Nunca para o próximo aluno**, e o [INV-ENC-N7] é exatamente sobre isto:
    mandá-lo ao próximo faria cada aluno da fila gastar a própria vez num
    cliente fantasma, um depois do outro, e nenhum deles saberia por quê. Um
    cliente que sumiu é problema do plantão, e não fila de espera para
    decepcionar gente.

    O aluno é solto do mesmo jeito da devolução à pista: ele volta a receber
    ofertas na hora, sem esperar o professor olhar.
    """
    _soltar_o_aluno(projeto)
    projeto.mudar_status(Encomenda.Status.PARA_RECLASSIFICAR, motivo=motivo)


# ---------------------------------------------------------------------------
# O GESTO: "Propor", e a contraproposta, que é o mesmo formulário
# ---------------------------------------------------------------------------


@transaction.atomic
def propor(
    encomenda_id,
    agora: datetime,
    *,
    site_id: str,
    de_quem: str,
    valor_cents: int,
    prazo_dias: int,
    entregaveis,
    correcoes_inclusas: int,
    justificativa: str = "",
) -> Desfecho:
    """Um lado preenche o formulário. É a proposta, e é a contraproposta.

    Um gesto só para os dois, porque *"a contraproposta tem exatamente a mesma
    forma, preenchida pelo outro lado"* (§4.1). Duas funções seriam a mesma
    regra escrita duas vezes, e a segunda envelheceria no primeiro campo novo.

    A ORDEM DAS RECUSAS É A ORDEM DAS PERGUNTAS, e ela importa:

    1. **É deste projeto que se está falando?** (o estado, e o aluno da vez)
    2. **É a sua vez?** Quem propõe primeiro é o ALUNO, e depois disso ninguém
       responde à própria proposta.
    3. **O formulário é válido?** Entregáveis dentro do briefing, justificativa
       dentro do limite do parâmetro.
    4. **Ainda há rodada?** Se não há, a negociação ACABA aqui e o projeto vai
       ao plantão: quem tenta contrapor está recusando a proposta de pé, e sem
       rodada para escrever a resposta não sobrou negociação nenhuma. É por isso
       que este caminho devolve `feito=False` e mesmo assim mexe no mundo, e o
       `encomenda_em` da resposta diz para onde o projeto foi.

    A primeira proposta faz três coisas na mesma transação: **para o relógio da
    reserva** (a reserva vai a `negociando`, o gancho que o degrau 2.11 deixou),
    leva o projeto a `em_negociacao` e grava o formulário. Separá-las abriria a
    janela em que existe um projeto `reservada` com proposta de pé, e o tique
    venceria a reserva no meio da primeira rodada.

    O piso do §7 NÃO aparece aqui, e a ausência é a decisão: ele avisa
    (`aviso_de_piso`), e nunca bloqueia.
    """
    projeto = (
        Encomenda.objects.select_for_update()
        .filter(pk=encomenda_id, site_id=site_id)
        .first()
    )
    if projeto is None:
        return Desfecho(feito=False, razao=NAO_ESTA_EM_NEGOCIACAO)
    if projeto.status not in ESTADOS_QUE_PROPOEM or projeto.aluno_id is None:
        return Desfecho(
            feito=False, razao=NAO_ESTA_EM_NEGOCIACAO, encomenda_em=projeto.status
        )
    perfil = PerfilProfissional.objects.select_for_update().get(pk=projeto.aluno_id)

    de_pe = proposta_de_pe(projeto)
    if de_pe is None:
        if de_quem != Proposta.DeQuem.ALUNO:
            return Desfecho(
                feito=False, razao=O_ALUNO_PROPOE_PRIMEIRO, encomenda_em=projeto.status
            )
        if Proposta.objects.filter(encomenda=projeto).exists():
            # Já houve propostas e nenhuma está de pé: a última foi aceita,
            # recusada ou venceu. Reabrir por aqui seria uma rodada fora da
            # contagem, e a contagem é o [INV-ENC-N2].
            return Desfecho(
                feito=False, razao=NAO_E_A_SUA_VEZ, encomenda_em=projeto.status
            )
    elif de_pe.de_quem == de_quem:
        return Desfecho(feito=False, razao=NAO_E_A_SUA_VEZ, encomenda_em=projeto.status)

    permitidos = entregaveis_do_briefing(projeto)
    if any(item not in permitidos for item in entregaveis):
        return Desfecho(
            feito=False, razao=ENTREGAVEL_FORA_DO_BRIEFING, encomenda_em=projeto.status
        )
    limite = Parametro.inteiro_vigente(
        "limite_da_justificativa", agora, site_id=site_id
    )
    if len(justificativa) > limite:
        return Desfecho(
            feito=False, razao=JUSTIFICATIVA_LONGA_DEMAIS, encomenda_em=projeto.status
        )

    rodada = Proposta.objects.filter(encomenda=projeto, de_quem=de_quem).count() + 1
    teto = Parametro.inteiro_vigente("rodadas_de_negociacao", agora, site_id=site_id)
    if rodada > teto:
        if de_pe is not None:
            de_pe.responder(Proposta.Resultado.RECUSADA, em=agora)
        mandar_ao_plantao(projeto, MOTIVO_DAS_RODADAS_ESGOTADAS)
        return Desfecho(
            feito=False, razao=RODADAS_ESGOTADAS, encomenda_em=projeto.status
        )

    try:
        # Savepoint próprio: um `IntegrityError` engolido sem ele quebraria a
        # transação inteira, inclusive o que já foi gravado (`armadilhas/027`).
        with transaction.atomic():
            if de_pe is not None:
                de_pe.responder(Proposta.Resultado.SUPERADA, em=agora)

            if projeto.status == Encomenda.Status.RESERVADA:
                reserva = (
                    ReservaDoMural.objects.select_for_update()
                    .filter(
                        encomenda=projeto,
                        resultado=ReservaDoMural.Resultado.PENDENTE,
                    )
                    .first()
                )
                if reserva is not None:
                    reserva.responder(ReservaDoMural.Resultado.NEGOCIANDO, em=agora)
                projeto.mudar_status(
                    Encomenda.Status.EM_NEGOCIACAO,
                    ator_id=perfil.pessoa_id,
                    motivo=MOTIVO_DA_PRIMEIRA_PROPOSTA,
                )

            Proposta.objects.create(
                site_id=site_id,
                encomenda=projeto,
                aluno=perfil,
                de_quem=de_quem,
                rodada=rodada,
                valor_cents=valor_cents,
                prazo_dias=prazo_dias,
                entregaveis=list(entregaveis),
                correcoes_inclusas=correcoes_inclusas,
                justificativa=justificativa,
                valida_ate=calcular_validade_da_proposta(agora, site_id=site_id),
            )
    except IntegrityError as erro:
        if not any(
            nome in str(erro)
            for nome in (
                "uma_negociacao_viva_por_aluno",
                "uma_proposta_viva_por_aluno",
            )
        ):
            raise
        # O índice `uma_proposta_viva_por_aluno` é a trava que sobra quando a
        # leitura educada falha ([INV-ENC-N6]): o aluno já tem outra negociação
        # de pé, somando as duas pistas. É a mesma forma de `mural.pegar`, e
        # pela mesma razão: uma frase nomeada em vez de um `IntegrityError`.
        projeto.refresh_from_db(fields=["status"])
        return Desfecho(
            feito=False, razao=JA_NEGOCIA_OUTRO_PROJETO, encomenda_em=projeto.status
        )
    return Desfecho(feito=True, encomenda_em=projeto.status)


# ---------------------------------------------------------------------------
# O ACORDO: aceitar a proposta de pé, e congelar o combinado
# ---------------------------------------------------------------------------


@transaction.atomic
def aceitar_a_proposta(
    encomenda_id, agora: datetime, *, site_id: str, de_quem: str, quem: str
) -> Desfecho:
    """Um lado aceita a proposta do outro, e o combinado vira pedra ([INV-ENC-N3]).

    Valor, prazo, entregáveis e correções passam da `Proposta` aceita para as
    colunas `acordo_*` da `Encomenda`, que a TAR-120 criou nulas justamente para
    este momento. **Depois disto eles não mudam**: quem faz isso valer não é
    este arquivo, é um gatilho do PostgreSQL (`encomendas_o_acordo_e_pedra`),
    que recusa o `UPDATE` venha ele de uma tela futura, de uma migração de dados
    ou de um `psql` de madrugada. Mudar depois só por mediação, com autor e
    motivo registrados (`mudar_por_mediacao`).

    `quem` é obrigatório, e é o §7 em código: enquanto a única origem for
    `escola`, quem abre o projeto e quem aceita a proposta é a mesma equipe, e o
    que faz a diferença ficar visível depois é o registro de quem decidiu.

    Ninguém aceita a própria proposta, e a recusa é nomeada: aceitar o que você
    mesmo escreveu é assinar sozinho um contrato de dois.
    """
    if not quem:
        return Desfecho(feito=False, razao=SEM_AUTOR)
    projeto = (
        Encomenda.objects.select_for_update()
        .filter(pk=encomenda_id, site_id=site_id)
        .first()
    )
    if projeto is None or projeto.status != Encomenda.Status.EM_NEGOCIACAO:
        return Desfecho(
            feito=False,
            razao=NAO_ESTA_EM_NEGOCIACAO,
            encomenda_em=projeto.status if projeto else "",
        )
    de_pe = proposta_de_pe(projeto)
    if de_pe is None:
        return Desfecho(
            feito=False, razao=SEM_PROPOSTA_DE_PE, encomenda_em=projeto.status
        )
    if de_pe.de_quem == de_quem:
        return Desfecho(feito=False, razao=NAO_E_A_SUA_VEZ, encomenda_em=projeto.status)

    de_pe.responder(Proposta.Resultado.ACEITA, em=agora)
    Acordo.objects.create(
        site_id=site_id,
        encomenda=projeto,
        proposta=de_pe,
        aluno_id=projeto.aluno_id,
        de_quem=de_quem,
        aceito_por=quem,
        aceito_em=agora,
    )
    for campo in Proposta.CAMPOS_QUE_O_ACORDO_CONGELA:
        setattr(projeto, f"acordo_{campo}", getattr(de_pe, campo))
    projeto.acordado_em = agora
    projeto.save(
        update_fields=[
            *(f"acordo_{campo}" for campo in Proposta.CAMPOS_QUE_O_ACORDO_CONGELA),
            "acordado_em",
            "atualizada_em",
        ]
    )
    projeto.mudar_status(
        Encomenda.Status.ACORDADA, ator_id=quem, motivo=MOTIVO_DO_ACORDO
    )
    return Desfecho(feito=True, encomenda_em=projeto.status)


@transaction.atomic
def desistir(encomenda_id, agora: datetime, *, site_id: str, de_quem: str) -> Desfecho:
    """Um lado sai da negociação antes do acordo. O destino depende de QUEM saiu.

    A mesma bifurcação do silêncio (§4.2), e pela mesma razão: o aluno que
    desiste devolve o projeto à pista, para o próximo; o cliente que desiste
    manda o projeto ao plantão, nunca ao próximo aluno ([INV-ENC-N7]).

    Desistir é gratuito ([INV-ENC-N5]): o aluno perde este projeto, e mais nada.
    A proposta de pé se fecha como `retirada` quando quem sai é quem a escreveu,
    e como `recusada` quando quem sai é o lado que devia respondê-la. As duas
    são pedra, e a diferença entre elas é o que a mediação vai ler depois.
    """
    projeto = (
        Encomenda.objects.select_for_update()
        .filter(pk=encomenda_id, site_id=site_id)
        .first()
    )
    if projeto is None or projeto.status != Encomenda.Status.EM_NEGOCIACAO:
        return Desfecho(
            feito=False,
            razao=NAO_ESTA_EM_NEGOCIACAO,
            encomenda_em=projeto.status if projeto else "",
        )
    de_pe = proposta_de_pe(projeto)
    if de_pe is None:
        return Desfecho(
            feito=False, razao=SEM_PROPOSTA_DE_PE, encomenda_em=projeto.status
        )

    de_pe.responder(
        (
            Proposta.Resultado.RETIRADA
            if de_pe.de_quem == de_quem
            else Proposta.Resultado.RECUSADA
        ),
        em=agora,
    )
    if de_quem == Proposta.DeQuem.ALUNO:
        devolver_a_pista(projeto, MOTIVO_DA_DESISTENCIA_DO_ALUNO)
    else:
        mandar_ao_plantao(projeto, MOTIVO_DA_DESISTENCIA_DO_CLIENTE)
    return Desfecho(feito=True, encomenda_em=projeto.status)


@transaction.atomic
def mudar_por_mediacao(
    encomenda_id,
    agora: datetime,
    *,
    site_id: str,
    quem: str,
    motivo: str,
    valor_cents: int | None = None,
    prazo_dias: int | None = None,
    entregaveis=None,
    correcoes_inclusas: int | None = None,
) -> Desfecho:
    """A única porta por onde o combinado muda depois de congelado ([INV-ENC-N3]).

    O projeto vai a `em_mediacao` ANTES da escrita, e não por arrumação: é a
    linha de `MudancaDeStatus` dessa transição que guarda o autor e o motivo, e
    é o estado `em_mediacao` que o gatilho `encomendas_o_acordo_e_pedra`
    reconhece como a exceção. Fora dela, o PostgreSQL recusa o `UPDATE` das
    quatro colunas, o que quer dizer que "só por mediação" não é uma frase num
    documento.

    Autor e motivo são obrigatórios. Uma mudança de acordo sem os dois é
    exatamente a mediação que ninguém consegue explicar seis meses depois, que é
    o que o §7 pede para não acontecer.
    """
    if not quem:
        return Desfecho(feito=False, razao=SEM_AUTOR)
    if not motivo:
        return Desfecho(feito=False, razao=SEM_MOTIVO)
    projeto = (
        Encomenda.objects.select_for_update()
        .filter(pk=encomenda_id, site_id=site_id)
        .first()
    )
    if projeto is None or projeto.acordado_em is None:
        return Desfecho(
            feito=False,
            razao=SEM_ACORDO,
            encomenda_em=projeto.status if projeto else "",
        )
    if projeto.status != Encomenda.Status.EM_MEDIACAO:
        projeto.mudar_status(Encomenda.Status.EM_MEDIACAO, ator_id=quem, motivo=motivo)

    novos = {
        "acordo_valor_cents": valor_cents,
        "acordo_prazo_dias": prazo_dias,
        "acordo_entregaveis": entregaveis,
        "acordo_correcoes_inclusas": correcoes_inclusas,
    }
    mudados = [campo for campo, valor in novos.items() if valor is not None]
    for campo in mudados:
        setattr(projeto, campo, novos[campo])
    if mudados:
        projeto.save(update_fields=[*mudados, "atualizada_em"])
    return Desfecho(feito=True, encomenda_em=projeto.status)


# ---------------------------------------------------------------------------
# O CAIXA E A PRODUÇÃO: [INV-ENC-N4] e [INV-ENC-N8]
# ---------------------------------------------------------------------------


@transaction.atomic
def confirmar_pagamento_pela_escola(
    encomenda_id, agora: datetime, *, site_id: str, quem: str
) -> Desfecho:
    """O plantão registra "pago pela escola", com autor e data. Sem linha de cobrança.

    A trava de 22/08/2026 continua de pé e o mantenedor a reafirmou em
    04/09/2026: *"só a escola por enquanto"*. Então não há checkout aqui, não há
    Mercado Pago e não há webhook: o que existe é o registro humano que o
    [INV-ENC-N4] mede, e o banco já exige que ele venha com autor e data
    (`confirmacao_de_pagamento_tem_autor_e_data`) e só para a origem `escola`
    (`confirmacao_pelo_plantao_so_para_a_escola`).

    **O caixa mudou de lugar, e não de dono** (§5). Até 04/09/2026 pagar era a
    porta de entrada da encomenda, porque o preço vinha da tabela; com a
    negociação, o valor só existe depois do Acordo, e por isso a passagem por
    `aguardando_pagamento` acontece agora, entre o acordo e a produção. Ela é
    uma transição de verdade, com linha de histórico, e não um estado saltado:
    quando houver checkout, é nela que o projeto vai esperar.
    """
    if not quem:
        return Desfecho(feito=False, razao=SEM_AUTOR)
    projeto = (
        Encomenda.objects.select_for_update()
        .filter(pk=encomenda_id, site_id=site_id)
        .first()
    )
    if projeto is None or projeto.status != Encomenda.Status.ACORDADA:
        return Desfecho(
            feito=False,
            razao=SEM_ACORDO,
            encomenda_em=projeto.status if projeto else "",
        )
    projeto.mudar_status(
        Encomenda.Status.AGUARDANDO_PAGAMENTO, ator_id=quem, motivo=MOTIVO_DO_CAIXA
    )
    projeto.confirmacao_de_pagamento = Encomenda.Confirmacao.PLANTAO
    projeto.pagamento_confirmado_em = agora
    projeto.pagamento_confirmado_por = quem
    projeto.save(
        update_fields=[
            "confirmacao_de_pagamento",
            "pagamento_confirmado_em",
            "pagamento_confirmado_por",
            "atualizada_em",
        ]
    )
    return Desfecho(feito=True, encomenda_em=projeto.status)


@transaction.atomic
def comecar_a_producao(encomenda_id, agora: datetime, *, site_id: str) -> Desfecho:
    """[INV-ENC-N4]: nenhuma produção começa sem Acordo E pagamento confirmado com autor.

    As duas perguntas são feitas separadas e recusadas com nomes diferentes, de
    propósito: "falta o acordo" e "falta o pagamento" mandam o plantão para
    lugares diferentes, e uma recusa só faria as duas parecerem a mesma coisa.

    **O PRAZO COMEÇA AQUI, E NÃO NO ACORDO** ([INV-ENC-N8]). Entre o Acordo e a
    confirmação há uma espera que não é do aluno: hoje é o plantão registrando
    "pago pela escola", amanhã será o webhook. Se um deles demorasse três dias,
    um prazo negociado de sete viraria quatro, e o aluno seria cobrado por um
    atraso que ele não causou. O marco é `pagamento_confirmado_em`, e não
    `agora`: quem começa a produção pode ser uma passada do tique, minutos
    depois, e um prazo que dependesse de quando o processo rodou não seria
    prazo.

    O prazo prometido ao cliente é o de produção mais o dia de revisão (lei
    §6.6), e o banco recusa a promessa anterior ao trabalho
    (`prazo_prometido_nunca_antes_do_de_producao`).

    **"Registrada COM AUTOR" é exigência, e não conveniência.** O banco aceita
    a confirmação por `webhook` com data e sem autor, porque webhook não tem
    pessoa atrás; a produção, não. Enquanto a única origem for `escola`, quem
    confirma é o plantão e o autor existe sempre. No dia em que a célula de
    pagamentos confirmar de verdade, afrouxar esta linha é uma DECISÃO a reabrir
    com o mantenedor, e não um detalhe de implementação.

    Este gesto substitui o [INV-ENC-D13] na ordem dos fatos, e não na
    substância: a confirmação com autor continua exigida, e agora o Acordo
    também. O código D13 fica aposentado, e nunca é reutilizado.
    """
    projeto = (
        Encomenda.objects.select_for_update()
        .filter(pk=encomenda_id, site_id=site_id)
        .first()
    )
    if projeto is None:
        return Desfecho(feito=False, razao=SEM_ACORDO)
    if (
        projeto.acordado_em is None
        or not Acordo.objects.filter(encomenda=projeto).exists()
    ):
        return Desfecho(feito=False, razao=SEM_ACORDO, encomenda_em=projeto.status)
    if (
        not projeto.confirmacao_de_pagamento
        or projeto.pagamento_confirmado_em is None
        or not projeto.pagamento_confirmado_por
        or projeto.status != Encomenda.Status.AGUARDANDO_PAGAMENTO
    ):
        return Desfecho(
            feito=False, razao=SEM_PAGAMENTO_CONFIRMADO, encomenda_em=projeto.status
        )

    dias_de_revisao = Parametro.inteiro_vigente(
        "dias_de_revisao_no_prazo_prometido", agora, site_id=site_id
    )
    projeto.prazo_producao_ate = projeto.pagamento_confirmado_em + timedelta(
        days=projeto.acordo_prazo_dias
    )
    projeto.prazo_prometido_ate = projeto.prazo_producao_ate + timedelta(
        days=dias_de_revisao
    )
    projeto.save(
        update_fields=["prazo_producao_ate", "prazo_prometido_ate", "atualizada_em"]
    )
    projeto.mudar_status(
        Encomenda.Status.EM_PRODUCAO, motivo=MOTIVO_DO_COMECO_DA_PRODUCAO
    )
    return Desfecho(feito=True, encomenda_em=projeto.status)
