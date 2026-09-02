"""O motor: inscrever, agendar, reavaliar a condição, desistir, e a varredura.

Lei: `docs/decisoes/PLANO-SEQUENCIAS-DE-MENSAGENS.md` §2 (as três capacidades que
não existiam), §5 (o modelo e os cinco carimbos de tempo) e §9 (os riscos, que
são a lista de testes deste arquivo).

A DECISÃO QUE ESTE ARQUIVO PRECISOU TOMAR, E QUE O PLANO NÃO TOMA
------------------------------------------------------------------
Este é o degrau 4 da escada, e a entrega visível dele é *"uma pessoa entra numa
jornada e o passo é AGENDADO"*. O envio de verdade é o degrau 5 (o sininho, pelo
`notificacao.devida.v1`) e o degrau 8 (o e-mail, que ainda nem sabe perguntar o
endereço à `identidade`).

Ou seja: aqui existe o momento em que a régua libera um passo e **nada tem para
onde entregá-lo**. E o vocabulário de `Entrega.resultado` é fechado — `enviada`,
`pulada`, `barrada_pela_regua`, `barrada_por_preferencia`. Gravar `enviada` para
um passo que ninguém entregou seria falso-verde escrito no banco, que é a
categoria de erro mais cara desta casa.

**A saída: o despacho é INJETADO, e sem despacho não nasce linha de entrega.**
`varrer(despachar=...)` recebe quem sabe entregar. O padrão é
`sem_despacho_ainda`, que devolve `False` e diz, no nome, o que está faltando.
Quando ele devolve `False`:

- **nenhuma `Entrega` é criada** (nada saiu, então nada se registra como saído);
- **a inscrição NÃO avança** — o passo continua devendo, e a passada seguinte o
  reencontra;
- a passada CONTA isso e devolve no relatório, para que a ausência de despacho
  seja um número visível e não um silêncio.

O degrau 5 passa o despachador de verdade, e nada mais aqui muda.

O CRONOGRAMA É ANCORADO, E ISSO RESPONDE A PERGUNTA DO §5
----------------------------------------------------------
`proximo_em = Inscricao.ancora_em + Passo.atraso` — **nunca** `agora + atraso`.
Se o passo 2 era para D+2 e a régua o empurrou para D+3, o passo 3 sai em D+5, e
não em D+6: **atraso da régua não empurra os passos seguintes.** Sem esta linha,
o comportamento seria decidido por acidente e viraria bug irreproduzível.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from django.db import IntegrityError, transaction
from django.utils import timezone

from . import condicoes, regua
from .models import Entrega, EstadoDoAluno, Inscricao, Jornada, JornadaVersao, Passo

# Teto de trabalho de UMA passada, como os relays da casa já fazem. Ele limita o
# trabalho da varredura, NÃO o volume do dia (§6.3): dez mil pessoas elegíveis
# continuam sendo dez mil envios ao longo das passadas. Ler o LOTE como proteção
# de volume é o conforto falso que faz ninguém construir a régua de capacidade
# que falta (TAR-079).
LOTE = 200

# Quem sabe entregar um passo num canal. Devolve True se ENTREGOU de verdade.
Despachante = Callable[[Inscricao, Passo, str], bool]


def sem_despacho_ainda(inscricao: Inscricao, passo: Passo, canal: str) -> bool:
    """O despachante padrão: não entrega nada, e diz isso.

    Não é um `pass` disfarçado: é a afirmação de que, no degrau 4, ninguém sabe
    entregar ainda. Devolver `False` faz o motor não gravar `enviada` e não
    avançar a inscrição — o passo continua devendo, que é a verdade.
    """
    return False


@dataclass
class Passada:
    """O relatório de uma varredura, para a passada ser auditável de fora."""

    examinadas: int = 0
    concluidas: int = 0
    puladas: int = 0
    barradas: int = 0
    entregues: int = 0
    sem_despacho: int = 0
    motivos: list[str] = field(default_factory=list)
    # O teto QUE ESTA PASSADA usou, e não a constante do módulo: `varrer` aceita
    # `lote=` e uma passada menor precisa saber dizer se encheu. Comparar com a
    # constante fazia a resposta ser sempre "não" para toda passada reduzida.
    lote: int = LOTE

    @property
    def esgotou_o_lote(self) -> bool:
        return self.examinadas >= self.lote


def _agora(momento: datetime | None) -> datetime:
    return momento if momento is not None else timezone.now()


def _versao_publicada(jornada: Jornada) -> JornadaVersao | None:
    """A versão em que uma inscrição NOVA entra: a última publicada.

    Rascunho não inscreve ninguém. E quem já entrou continua na versão dele — não
    por disciplina, mas porque a `Inscricao` aponta para a versão e a versão
    publicada é fisicamente imutável (gatilhos da migração `0001`).
    """
    return (
        jornada.versoes.filter(publicada_em__isnull=False).order_by("-numero").first()
    )


def inscrever(
    jornada: Jornada,
    *,
    destinatario_id: str,
    site_id: str,
    origem_event_id=None,
    momento: datetime | None = None,
) -> Inscricao | None:
    """Põe uma pessoa numa jornada. Devolve `None` quando não há onde inscrever.

    TRÊS CAMADAS DE IDEMPOTÊNCIA, e nenhuma substitui a outra:

    1. `origem_event_id` — o mesmo FATO nunca inscreve duas vezes, mesmo depois
       de o episódio anterior ter terminado. A trava parcial do banco sozinha não
       cobria este caso: ela só impede duas inscrições ANDANDO, e um evento
       reentregue meses depois abriria um episódio novo, legítimo pela trava e
       errado pelo fato.
    2. A trava parcial `uniq_inscricao_andando_por_jornada` — a rede do banco,
       que pega a corrida entre dois consumidores no mesmo instante.
    3. O dedup por `event_id` do `apps/eventos`, que é a camada de fora e nem
       chega aqui.

    A jornada `ativa=False` não inscreve ninguém: ligar uma sequência é decisão
    do mantenedor.
    """
    agora = _agora(momento)
    if not jornada.ativa:
        return None

    versao = _versao_publicada(jornada)
    if versao is None:
        return None

    if origem_event_id is not None:
        ja = Inscricao.objects.filter(
            jornada=jornada,
            destinatario_id=destinatario_id,
            site_id=site_id,
            origem_event_id=origem_event_id,
        ).first()
        if ja is not None:
            return ja

    primeiro = versao.passos.order_by("ordem").first()
    try:
        # O savepoint é obrigatório: um `IntegrityError` engolido sem ele
        # envenena a transação inteira e o erro seguinte fala de outra coisa
        # (`armadilhas/027` e `armadilhas/120`).
        with transaction.atomic():
            return Inscricao.objects.create(
                jornada_versao=versao,
                destinatario_id=destinatario_id,
                site_id=site_id,
                ancora_em=agora,
                proximo_em=agora + primeiro.atraso if primeiro else None,
                origem_event_id=origem_event_id,
                estado="andando",
            )
    except IntegrityError:
        # A trava parcial falou: já existe um episódio andando. Devolvê-lo é a
        # resposta certa — a corrida não é erro, é duas entregas do mesmo fato.
        return Inscricao.objects.filter(
            jornada=jornada,
            destinatario_id=destinatario_id,
            site_id=site_id,
            estado="andando",
        ).first()


def _proximo_passo(inscricao: Inscricao) -> Passo | None:
    return (
        inscricao.jornada_versao.passos.filter(ordem__gt=inscricao.passo_atual)
        .order_by("ordem")
        .first()
    )


def _projecao(inscricao: Inscricao) -> EstadoDoAluno | None:
    return EstadoDoAluno.objects.filter(
        destinatario_id=inscricao.destinatario_id, site_id=inscricao.site_id
    ).first()


def avancar(inscricao: Inscricao, passo: Passo) -> Inscricao:
    """Fecha um passo e agenda o seguinte PELO CRONOGRAMA ANCORADO.

    A conta é `ancora_em + atraso_do_proximo`, e não `agora + atraso`. É esta
    linha que faz o passo 3 sair em D+5 mesmo com o passo 2 tendo saído em D+3
    por causa da régua.
    """
    inscricao.passo_atual = passo.ordem
    seguinte = _proximo_passo(inscricao)
    if seguinte is None:
        inscricao.estado = "concluida"
        inscricao.proximo_em = None
    else:
        inscricao.proximo_em = inscricao.ancora_em + seguinte.atraso
    inscricao.save(update_fields=["passo_atual", "estado", "proximo_em"])
    return inscricao


def _pular(inscricao: Inscricao, passo: Passo, motivo: str, agora: datetime) -> None:
    """O passo deixou de fazer sentido: registra POR CANAL e segue a jornada.

    Registrar o pulo é o ponto: sem ele, "por que o aluno X não recebeu?" cai no
    silêncio, e o §5 é explícito em que essa pergunta precisa de resposta.
    """
    for canal in passo.canais:
        Entrega.objects.update_or_create(
            inscricao=inscricao,
            passo=passo,
            canal=canal,
            defaults={
                "previsto_para": inscricao.ancora_em + passo.atraso,
                "resultado": "pulada",
                "motivo": motivo,
                "enviado_em": None,
            },
        )
    avancar(inscricao, passo)


def candidatas(agora: datetime):
    """Quem está andando e já passou da hora, na ordem de desempate da régua.

    A ordem vem de `regua.ORDEM_DE_DESEMPATE`, chamada e não copiada: quando duas
    jornadas disputam a vaga do dia, ganha a inscrição mais antiga, e duas
    implementações da mesma ordem divergem no primeiro dia em que alguém mexer
    numa delas.
    """
    consulta = Inscricao.objects.filter(estado="andando", proximo_em__lte=agora)
    return consulta.order_by(
        *(campo.removeprefix("inscricao__") for campo in regua.ORDEM_DE_DESEMPATE)
    )


def varrer(
    *,
    momento: datetime | None = None,
    lote: int = LOTE,
    despachar: Despachante = sem_despacho_ainda,
) -> Passada:
    """Uma passada da varredura. Decide, registra e agenda — não envia sozinha.

    A condição é reavaliada AQUI, no instante do envio, e nunca no da inscrição:
    é a diferença entre uma sequência que sabe desistir e uma que manda "sentimos
    sua falta" para quem voltou ontem.
    """
    agora = _agora(momento)
    passada = Passada(lote=lote)

    for inscricao in candidatas(agora)[:lote]:
        passada.examinadas += 1
        passo = _proximo_passo(inscricao)

        if passo is None:
            inscricao.estado = "concluida"
            inscricao.proximo_em = None
            inscricao.save(update_fields=["estado", "proximo_em"])
            passada.concluidas += 1
            continue

        try:
            vale = condicoes.avaliar(passo.condicao_slug, _projecao(inscricao), agora)
        except condicoes.CondicaoDesconhecida:
            # Fail-closed: slug que ninguém reconhece PULA o passo. Um erro de
            # digitação não pode virar mensagem enviada a quem não devia recebê-la.
            _pular(
                inscricao, passo, f"condicao desconhecida: {passo.condicao_slug}", agora
            )
            passada.puladas += 1
            passada.motivos.append(f"condicao desconhecida: {passo.condicao_slug}")
            continue

        if not vale:
            _pular(
                inscricao,
                passo,
                f"a condicao {passo.condicao_slug} nao vale mais",
                agora,
            )
            passada.puladas += 1
            continue

        previsto = inscricao.ancora_em + passo.atraso
        entregou_algum = False
        adiar_para: datetime | None = None
        # A TERCEIRA COISA QUE PODE ACONTECER, e não tê-la nomeada era o defeito.
        # "Nada saiu" tinha duas causas indistinguíveis no código: a pessoa
        # RECUSOU (preferência — decisão dela, definitiva) e o despacho FALHOU
        # (Redis fora, carta não emitida — transitório). A primeira deve seguir a
        # jornada; a segunda deve ser retentada. Tratar as duas como a segunda
        # prendia quem silenciou, para sempre (ver o desfecho lá embaixo).
        falhou_o_despacho = False

        for canal in passo.canais:
            veredito = regua.avaliar(
                destinatario_id=inscricao.destinatario_id,
                site_id=inscricao.site_id,
                canal=canal,
                classe=passo.classe,
                momento=agora,
                # QUAL mensagem está sendo avaliada. Sem isto o teto conta a
                # própria: o sino sai, e o e-mail do mesmo passo bate na linha
                # que o sino acabou de gravar.
                mensagem=(inscricao.pk, passo.pk),
            )
            if veredito.barrada:
                regua.registrar(
                    veredito,
                    inscricao=inscricao,
                    passo=passo,
                    canal=canal,
                    previsto_para=previsto,
                    momento=agora,
                )
                passada.barradas += 1
                if veredito.reagendar_para is not None:
                    adiar_para = (
                        veredito.reagendar_para
                        if adiar_para is None
                        else min(adiar_para, veredito.reagendar_para)
                    )
                continue

            # O DESPACHO E O REGISTRO VIVEM OU MORREM JUNTOS. Sem esta
            # transação comum, a carta chega ao sininho e a linha de `Entrega`
            # que diz "saiu" pode não ser gravada — e a passada seguinte manda
            # tudo de novo, com um `event_id` novo que a dedup do sininho não
            # tem como pegar. É também ela que satisfaz o `emitir()` da outbox,
            # que RECUSA gravar fora de transação.
            with transaction.atomic():
                if not despachar(inscricao, passo, canal):
                    # NADA saiu: nada se registra como saído. O passo continua
                    # devendo, e a passada seguinte o reencontra.
                    passada.sem_despacho += 1
                    falhou_o_despacho = True
                    continue

                regua.registrar(
                    veredito,
                    inscricao=inscricao,
                    passo=passo,
                    canal=canal,
                    previsto_para=previsto,
                    momento=agora,
                )
            passada.entregues += 1
            entregou_algum = True

        if entregou_algum:
            avancar(inscricao, passo)
        elif adiar_para is not None:
            # Barrado NÃO se perde: a inscrição espera a próxima janela válida, e
            # o passo continua sendo o mesmo.
            inscricao.proximo_em = adiar_para
            inscricao.save(update_fields=["proximo_em"])
        elif falhou_o_despacho:
            # Transitório: o relógio NÃO anda, o passo continua devendo, e a
            # passada seguinte tenta de novo. É o comportamento que já existia, e
            # aqui ele fica escrito em vez de ser o que sobra.
            pass
        else:
            # RECUSA DEFINITIVA — todo canal deste passo foi barrado por
            # preferência, e a régua barra preferência SEM reagendar de
            # propósito: "silenciado é silenciado, remarcar seria insistir".
            #
            # Sem este desfecho, "não reagenda" virava "reexamina e rebarra de
            # cinco em cinco minutos, para sempre": `proximo_em` não andava, o
            # estado ficava `andando`, e a inscrição nunca terminava. Medido em
            # 02/09/2026 — 11 dias de varredura com `passo_atual=0`.
            #
            # E o estrago não parava nela. `candidatas()` ordena pela inscrição
            # mais antiga e a passada leva as primeiras `lote`: as presas são
            # sempre as mais velhas e sempre estão na hora, então ocupavam a
            # frente da fila permanentemente. Encenado com `lote=3` e 3 presas,
            # o aluno novo foi atendido ZERO vezes em 14 passadas, sem erro
            # nenhum. Em produção o lote é 200.
            #
            # Seguir a jornada é o que respeita a intenção da régua: não insiste
            # naquele passo, e não sequestra a pessoa dentro da sequência. As
            # linhas de `Entrega` já ficaram gravadas como
            # `barrada_por_preferencia`, então a pergunta "por que ele não
            # recebeu?" continua com resposta.
            avancar(inscricao, passo)

    return passada


# ---------------------------------------------------------------------------
# A PROJEÇÃO — calculada, nunca fonte da verdade
# ---------------------------------------------------------------------------


def registrar_atividade(
    destinatario_id: str,
    site_id: str,
    *,
    momento: datetime | None = None,
    aula: bool = False,
    post: bool = False,
) -> EstadoDoAluno:
    """Atualiza a projeção do aluno. Quem a alimenta são EVENTOS, não consultas.

    A autoridade sobre cada fato continua na célula de origem: esta tabela é uma
    cópia operacional para a varredura não multiplicar idas à rede (§5). Ligar
    esta função aos eventos das outras células é trabalho do degrau seguinte —
    aqui ela existe e é testada, e é por ela que as condições leem.
    """
    agora = _agora(momento)
    estado, _ = EstadoDoAluno.objects.get_or_create(
        destinatario_id=destinatario_id, site_id=site_id
    )
    estado.ultima_atividade_em = agora
    if aula:
        estado.ultima_aula_em = agora
    if post:
        estado.ultimo_post_em = agora
    estado.save()
    return estado
