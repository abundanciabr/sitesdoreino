"""A régua anti-chateação: UMA peça, por pessoa, atravessada por toda entrega.

Lei: `docs/decisoes/PLANO-SEQUENCIAS-DE-MENSAGENS.md` §6 (as três partes) e a
constituição da célula, §"A régua de quem recebe". O cenário que ela existe para
não repetir está em `docs/consultorias/sequencias-de-mensagens/VEREDITO.md` §1.6
e §1.7.

POR QUE UMA PEÇA SÓ, E NÃO UMA RÉGUA POR JORNADA
------------------------------------------------
Se cada jornada implementasse a própria régua, três jornadas somariam três
mensagens no mesmo dia, cada uma respeitando "1 por dia" isoladamente e o aluno
recebendo três. A pessoa é uma só; a régua também.

A ORDEM DAS BARREIRAS NÃO É ARBITRÁRIA, E INVERTÊ-LA JÁ QUEBROU UM CENÁRIO REAL
-------------------------------------------------------------------------------
**A classe decide ANTES de tudo.** A régua anterior isentava o transacional de
ser *silenciado* mas não do teto diário, e o resultado foi medido contra o texto:

    o aluno ganha uma medalha às 10h · às 18h a matrícula dele é liberada ·
    a régua BARRA o aviso da matrícula.

Mensagem de serviço barrada por uma de incentivo. Por isso `critica` e
`transacional` passam **POR FORA da régua inteira** — não só do teto. "Isento do
teto" não bastava: um aviso de senha também não espera janela de horário e não
some porque a pessoa silenciou incentivo.

O QUE ESTE MÓDULO NÃO É
-----------------------
Não é a régua de CAPACIDADE do §6.3. Esta aqui protege **a atenção de uma
pessoa**; ela não limita nada do lado de fora. Dez mil pessoas ficando elegíveis
às 9h continuam sendo dez mil envios, cada um respeitando "uma por dia"
perfeitamente — e é o provedor que degrada. Teto por minuto, backoff com jitter
e disjuntor são outra peça, e são a TAR-079.

Também não é o motor: aqui ninguém varre, ninguém inscreve e ninguém envia. Esta
peça DECIDE e, quando pedida, ESCREVE a decisão na `Entrega` (que é onde a
promessa "barrado não se perde" vira linha de banco).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta

from django.db import DatabaseError
from django.utils import timezone

from .models import Entrega, Inscricao, Preferencia
from .parametros import TETO_DE_CONTATO_POR_DIA

# ---------------------------------------------------------------------------
# AS CONSTANTES DA LEI, NUM LUGAR SÓ
# ---------------------------------------------------------------------------

# Passam por fora da régua INTEIRA: não esperam vaga, não esperam janela, e não
# somem porque alguém silenciou incentivo (§6.1).
CLASSES_FORA_DA_REGUA = frozenset({"critica", "transacional"})

# A janela tem hora de ABRIR e de fechar. O piso não é zelo: sem ele, "reagenda
# para a próxima janela válida" manda a mensagem às 6h da manhã, e a régua que
# existe para não incomodar teria acabado de incomodar (VEREDITO §1.7).
ABRE = time(8, 0)
FECHA = time(20, 0)

# Lei 4 do §3. Uma por dia, por pessoa. O NUMERO NAO MORA MAIS AQUI: ele e um
# parametro com dono declarado (`parametros.py`), porque o mantenedor pode
# querer outro e um numero solto no meio de um algoritmo nao diz de quem e a
# decisao. Continua sendo um `int` de propósito, e nao o objeto: quem lê a linha
# do teto lá embaixo precisa de "teto de 1 por dia" na tela, não de um dataclass.
TETO_POR_DIA = TETO_DE_CONTATO_POR_DIA.valor

# O desempate, e ele é do banco, não da sorte: quando duas jornadas disputam a
# vaga do dia, ganha a inscrição mais antiga. Sem ordem definida, o teste do teto
# não tem o que afirmar — e guarda que não pode afirmar é guarda decorativo.
# O `id` entra como segundo critério para a ordem ser TOTAL: dois `criada_em`
# iguais (mesmo lote, mesmo instante) empatariam de novo, e um empate que sobra
# é um teste que passa hoje e falha amanhã sem nada ter mudado.
ORDEM_DE_DESEMPATE = ("inscricao__criada_em", "inscricao__id")


@dataclass(frozen=True)
class Veredito:
    """O que a régua respondeu, e por quê.

    `motivo` nunca fica vazio quando a resposta é não: é ele que responde à
    pergunta "por que o aluno X não recebeu?" na tela do degrau 7 — e o §5 é
    explícito em que essa pergunta não pode cair no silêncio.
    """

    libera: bool
    resultado: str
    motivo: str
    reagendar_para: datetime | None = None

    @property
    def barrada(self) -> bool:
        return not self.libera


def _agora(momento: datetime | None) -> datetime:
    return momento if momento is not None else timezone.now()


def _limites_do_dia(momento: datetime) -> tuple[datetime, datetime]:
    """O começo e o fim do DIA DE SÃO PAULO que contém `momento`.

    Calculado explicitamente, e não por `enviado_em__date`: aquele atalho
    delega a conversão de fuso ao banco, e o dia da mensageria é o dia de São
    Paulo por lei (§3, lei 6; `armadilhas/099`). Com o fuso do Django cru, o
    envio das 22h cai no dia errado e NADA acusa.
    """
    dia = timezone.localdate(momento)
    fuso = timezone.get_current_timezone()
    inicio = timezone.make_aware(datetime.combine(dia, time.min), fuso)
    return inicio, inicio + timedelta(days=1)


def proxima_janela(momento: datetime) -> datetime:
    """O próximo instante em que a janela de silêncio está ABERTA.

    Antes das 8h, é hoje às 8h; das 8h às 20h, é agora mesmo; das 20h em diante,
    é amanhã às 8h.
    """
    local = timezone.localtime(momento)
    fuso = timezone.get_current_timezone()
    if local.time() < ABRE:
        return timezone.make_aware(datetime.combine(local.date(), ABRE), fuso)
    if local.time() < FECHA:
        return momento
    amanha = local.date() + timedelta(days=1)
    return timezone.make_aware(datetime.combine(amanha, ABRE), fuso)


def dentro_da_janela(momento: datetime) -> bool:
    return ABRE <= timezone.localtime(momento).time() < FECHA


def em_ordem_de_desempate(queryset):
    """A ordem em que as candidatas do dia devem ser avaliadas.

    Mora aqui, e não na varredura, porque o desempate É regra da régua: quem
    varre só precisa obedecer. Duas implementações da mesma ordem divergem no
    primeiro dia em que alguém mexer numa delas.
    """
    return queryset.order_by(*ORDEM_DE_DESEMPATE)


def _aceita(destinatario_id: str, site_id: str, canal: str, classe: str) -> bool:
    """A vontade da pessoa, por canal e por classe.

    AUSÊNCIA NÃO É RECUSA, e a distinção é a que separa esta função do
    fail-closed: quem nunca disse nada não silenciou nada, e tratar silêncio
    como recusa desligaria a plataforma inteira para todo mundo no primeiro dia.
    O fail-closed do §6.2 é sobre preferência **ilegível** (o banco fora, a linha
    corrompida), e ele mora em `avaliar`, que trata a EXCEÇÃO — não a ausência.
    """
    linha = Preferencia.objects.filter(
        destinatario_id=destinatario_id,
        site_id=site_id,
        canal=canal,
        classe=classe,
    ).first()
    return True if linha is None else linha.aceita


def _quantas_hoje(
    destinatario_id: str,
    site_id: str,
    momento: datetime,
    excluir: tuple[object, object] | None = None,
) -> int:
    """Quantas mensagens desta pessoa já SAÍRAM no dia de São Paulo de `momento`.

    O QUE ESTA CONTA ALCANÇA, E O QUE ELA NÃO ALCANÇA — dito porque a diferença
    é uma decisão, não um esquecimento: ela conta `Entrega`, que é tudo que sai
    pelo motor das jornadas. Ela NÃO conta o envio transacional antigo da célula
    (`EnvioRegistrado`, do `apps/eventos`), e não pode contar: ler aquela tabela
    é o critério de morte §10.7 do plano, que só permite a este app CRIAR a linha
    de `EnvioRegistrado`.

    E conta toda classe, inclusive as que passam por fora da régua. A régua
    protege a ATENÇÃO de uma pessoa, e atenção não distingue classe: uma
    mensagem de serviço recebida às 10h é uma mensagem recebida. O que a classe
    decide é que ela nunca é BARRADA — não que ela seja invisível.

    CONTA MENSAGENS, NÃO LINHAS DE ENTREGA, e a diferença é um defeito medido.
    `Passo.canais` é lista, e a `Entrega` tem uma linha POR CANAL — de propósito
    (VEREDITO §1.5). Contar linhas fazia o mesmo passo somar duas vezes: o sino
    saía, gravava `resultado="enviada"`, e o e-mail DAQUELE MESMO PASSO batia no
    teto que o sino acabara de gastar. Medido em 02/09/2026, com a mensagem que
    o mantenedor leria na tela: *"ja recebeu 1 hoje (teto de 1 por dia)"* — a
    régua parecendo funcionar enquanto engolia metade do aviso.

    A regra que resolve vem da constituição desta célula, não de gosto: *"um teto
    por canal seria um teto por caixa de entrada, e a pessoa é uma só"*. O
    inverso também vale, e é o que faltava escrever: uma mensagem em duas caixas
    continua sendo UMA mensagem para a atenção de quem lê.

    Daí as DUAS metades do conserto, e a segunda quase não veio. Contar
    `(inscricao, passo)` distintos não bastava: com teto 1, a linha do sino já
    valia 1, e o e-mail do mesmo passo continuava barrado por ela. O teto
    pergunta *"quantas OUTRAS mensagens esta pessoa já recebeu hoje?"* — a que
    está sendo avaliada agora não conta contra si mesma, e é isso que o
    `excluir=` faz. Medido: sem ele, o guarda dos dois canais continuava vermelho.
    """
    inicio, fim = _limites_do_dia(momento)
    return quantas_mensagens_entre(
        destinatario_id, site_id, inicio, fim, excluir=excluir
    )


def quantas_mensagens_entre(
    destinatario_id: str,
    site_id: str,
    inicio: datetime,
    fim: datetime,
    excluir: tuple[object, object] | None = None,
) -> int:
    """Quantas MENSAGENS desta pessoa sairam em `[inicio, fim)`.

    A conta inteira do teto diario mora aqui; `_quantas_hoje` so escolhe a
    janela. A extracao aconteceu no degrau 15 do painel de gestao, quando a fila
    de proxima acao precisou da MESMA conta numa janela de sete dias, e duas
    implementacoes da mesma contagem divergiriam no primeiro dia em que alguem
    mexesse numa delas, sem que nada acusasse (e o defeito medido de 02/09/2026,
    contar linha em vez de mensagem, viveria de novo numa das duas).

    Tudo que a docstring de `_quantas_hoje` explica sobre O QUE esta conta
    alcanca continua valendo palavra por palavra, porque e esta a conta.
    """
    consulta = Entrega.objects.filter(
        inscricao__destinatario_id=destinatario_id,
        inscricao__site_id=site_id,
        resultado="enviada",
        enviado_em__gte=inicio,
        enviado_em__lt=fim,
    )
    if excluir is not None:
        inscricao_id, passo_id = excluir
        consulta = consulta.exclude(inscricao_id=inscricao_id, passo_id=passo_id)
    return consulta.values("inscricao_id", "passo_id").distinct().count()


def avaliar(
    *,
    destinatario_id: str,
    site_id: str,
    canal: str,
    classe: str,
    momento: datetime | None = None,
    mensagem: tuple[object, object] | None = None,
) -> Veredito:
    """A régua inteira, na ordem que o §6.2 fixa.

    FAIL-CLOSED: qualquer falha em ler a preferência ou contar o dia vira "não
    envia", com o motivo gravado. Silêncio por dúvida, nunca mensagem por
    dúvida — a mesma escolha que a Caixa de Sugestões já fez com a lista de
    aprovadores, e é desenho, não defeito.
    """
    agora = _agora(momento)

    # 0. A CLASSE, ANTES DE TUDO. Note que isto vem antes até do try: uma
    #    mensagem crítica não pode ser barrada nem por uma falha da régua.
    if classe in CLASSES_FORA_DA_REGUA:
        return Veredito(
            libera=True,
            resultado="enviada",
            motivo=f"classe {classe} passa por fora da regua inteira",
        )

    try:
        # 1. A vontade da pessoa. Silenciou, barra — e NÃO reagenda: silenciado
        #    é silenciado, e remarcar para amanhã seria insistir.
        if not _aceita(destinatario_id, site_id, canal, classe):
            return Veredito(
                libera=False,
                resultado="barrada_por_preferencia",
                motivo=f"a pessoa silenciou {classe} no canal {canal}",
            )

        # 2. A janela, com hora de abrir E de fechar.
        if not dentro_da_janela(agora):
            proxima = proxima_janela(agora)
            hora = timezone.localtime(agora).strftime("%H:%M")
            return Veredito(
                libera=False,
                resultado="barrada_pela_regua",
                motivo=f"fora da janela ({hora}; vale das 08:00 as 20:00)",
                reagendar_para=proxima,
            )

        # 3. O teto do dia. Barrado NÃO se perde: vai para a próxima janela.
        ja_saiu = _quantas_hoje(destinatario_id, site_id, agora, excluir=mensagem)
        if ja_saiu >= TETO_POR_DIA:
            _, fim_do_dia = _limites_do_dia(agora)
            return Veredito(
                libera=False,
                resultado="barrada_pela_regua",
                motivo=f"ja recebeu {ja_saiu} hoje (teto de {TETO_POR_DIA} por dia)",
                reagendar_para=proxima_janela(fim_do_dia),
            )
    except DatabaseError as erro:
        # A régua não conseguiu se pronunciar. Isso é motivo para NÃO enviar, e
        # o motivo fica escrito: a tela do degrau 7 mostra "a régua não pôde
        # decidir", que é honesto, em vez de um silêncio sem explicação.
        return Veredito(
            libera=False,
            resultado="barrada_pela_regua",
            motivo=f"regua indisponivel, nao envio por duvida: {erro}",
            reagendar_para=proxima_janela(agora + timedelta(hours=1)),
        )

    return Veredito(libera=True, resultado="enviada", motivo="")


def registrar(
    veredito: Veredito,
    *,
    inscricao: Inscricao,
    passo,
    canal: str,
    previsto_para: datetime,
    momento: datetime | None = None,
) -> Entrega:
    """Materializa a decisão na `Entrega` — inclusive quando a decisão foi não.

    Guardar o que NÃO saiu é o ponto, não um detalhe: sem estas linhas, "por que
    o aluno X não recebeu no e-mail?" é silêncio, e o mantenedor fica olhando
    para ele. Uma linha por `(inscricao, passo, canal)`, como manda a trava do
    §5 — a mesma entrega reavaliada depois do reagendamento ATUALIZA a linha, e
    é por isso que este é um `update_or_create` e não um `create`.
    """
    agora = _agora(momento)
    entrega, _ = Entrega.objects.update_or_create(
        inscricao=inscricao,
        passo=passo,
        canal=canal,
        defaults={
            "previsto_para": previsto_para,
            "reagendado_para": veredito.reagendar_para,
            "enviado_em": agora if veredito.libera else None,
            "resultado": veredito.resultado,
            "motivo": veredito.motivo,
        },
    )
    return entrega
