# apps/gamificacao/cartas.py
"""As CARTAS DE CELEBRAÇÃO: onde a célula muda deixa de ser muda.

Até aqui a gamificação só ESCUTAVA. Ela contava pontos, subia níveis e não
dizia nada a ninguém: ganhar só acontecia se o aluno resolvesse abrir a tela por
conta própria. Este arquivo é o degrau 9 da escada
(`docs/decisoes/PLANO-CELULA-GAMIFICACAO.md` §6) — a voz.

Lei do assunto: `contracts/eventos/notificacao.devida.v1.json`, congelado no
Rito de Contrato de 26/08/2026 e ampliado com os quatro assuntos desta célula na
Sessão B de 30/08/2026, com o mantenedor presente. **Nada aqui inventa campo,
renomeia campo ou acrescenta campo "que seria útil"** — divergir do contrato é
parar e avisar, nunca editar `contracts/`.

AS QUATRO REGRAS QUE ESTE ARQUIVO EXISTE PARA CUMPRIR
------------------------------------------------------
1. **Só BOA NOTÍCIA vira carta.** Perder XP, regredir na Sequência ou ter uma
   marca estornada não gera aviso nenhum. Não é delicadeza: é a lei da célula
   (`DECISAO-gamificacao.md`), e a notificação de culpa está na lista do §
   "mecânicas proibidas". O mecanismo está no ponto de emissão — `motor.py` só
   chama daqui quando o nível SOBE — e o guarda que o prova é
   `tests/test_cartas_de_celebracao.py::test_perder_xp_nao_gera_carta`.
2. **A carta nasce DENTRO da transação do fato.** Fora dela, um rollback
   deixaria uma carta no fio para uma subida de nível que não aconteceu — o modo
   de falha mais caro que uma outbox existe para impedir. `emitir()` RECUSA a
   escrita fora de `atomic`, em vez de confiar que todo ponto de emissão futuro
   se lembre.
3. **Número e SLUG viajam; a FRASE nunca.** A escola serve três idiomas.
   Gravar "Você chegou ao nível 7, Modelador!" congela o idioma de quem gravou,
   e quem lê em espanhol recebe português para sempre — texto já gravado não se
   traduz depois (`DECISAO-notificacoes` §5.1). A frase nasce na LEITURA.
4. **Assunto fora do contrato não sai.** `carta_de_celebracao` recusa um assunto
   que o contrato não conheça. Um assunto inventado atravessaria o fio, seria
   gravado no sininho e só apareceria como aviso mudo na tela de alguém.

O QUE ESTE ARQUIVO **NÃO** DECIDE
----------------------------------
**Quando o aviso é MOSTRADO.** O plano diz, sobre notificações, *"só boas
notícias, máx 1/dia, nunca >20h"* (§ do `PLANO-CELULA-GAMIFICACAO.md`). A
primeira metade é regra do FATO e mora aqui. As outras duas são regra da
ENTREGA — quantas vezes por dia o sininho incomoda, e a que horas — e não podem
morar na origem: descartar a carta aqui apagaria o fato para sempre, e o aluno
não a veria nem no dia seguinte. Hoje **nenhuma camada as implementa**, e esta
ausência está declarada no registro do livro em vez de escondida num TODO.
"""

from __future__ import annotations

import uuid
from typing import Any

from django.db import transaction
from django.utils.text import slugify

from .models import OutboxEvent

# A CARTA ENDEREÇADA (Rito de Contrato de 26/08/2026): uma pessoa a avisar, um
# evento. O leque é feito na ORIGEM — a lista de quem sobe de nível nunca
# circula pela plataforma, e o tamanho do evento não cresce com a plateia.
NOTIFICACAO_DEVIDA = "notificacao.devida"

ASSUNTO_NIVEL = "gamificacao.nivel-alcancado"
ASSUNTO_CONQUISTA = "gamificacao.conquista-concedida"
ASSUNTO_MARCO = "gamificacao.marco-validado"
ASSUNTO_DESTAQUE = "gamificacao.destaque-da-semana"

# O vocabulário FECHADO desta célula, igual ao `enum` do contrato. Fechado e não
# aberto porque o `data` do evento é `additionalProperties: false` dos dois
# lados: um assunto a mais aqui é um assunto que o consumidor recusa.
ASSUNTOS = frozenset(
    {ASSUNTO_NIVEL, ASSUNTO_CONQUISTA, ASSUNTO_MARCO, ASSUNTO_DESTAQUE}
)


class EventoForaDaTransacao(Exception):
    """`emitir()` chamado sem transação aberta — o evento não seria transacional.

    Levantar aqui é a Lei 1 aplicada: em vez de confiar que todo ponto de
    emissão futuro se lembre do `atomic`, a própria função recusa a escrita. Um
    evento gravado em autocommit sobrevive ao rollback do fato que o justifica,
    e aí a plataforma inteira passa a acreditar em algo que não aconteceu.
    """


class AssuntoForaDoContrato(Exception):
    """Tentativa de emitir um assunto que o contrato congelado não conhece.

    Fail-CLOSED de propósito. O caminho contrário — deixar passar e ver no que
    dá — termina com a carta gravada no sininho de alguém e nenhuma tela sabendo
    o que fazer com ela: um aviso mudo, que ninguém consegue explicar nem apagar.
    """


def emitir(
    event: str,
    data: dict[str, Any],
    *,
    site_id: str,
    version: int = 1,
    envelope_extra: dict[str, Any] | None = None,
    event_id: uuid.UUID | None = None,
) -> OutboxEvent:
    """Grava o fato na outbox — SEMPRE dentro da transação do fato.

    Não publica nada: publicar é do relay (`tasks.py`), depois do commit. Essa
    separação É a outbox — escrever no Redis aqui dentro devolveria o problema
    que o padrão resolve (evento publicado, transação revertida).
    """
    if not transaction.get_connection().in_atomic_block:
        raise EventoForaDaTransacao(
            f"emitir({event!r}) foi chamado fora de transaction.atomic(). "
            "O evento tem de nascer na MESMA transação do fato que o justifica: "
            "sem isso, um rollback deixa a plataforma acreditando num fato que "
            "não aconteceu."
        )
    campos: dict[str, Any] = {
        "event": event,
        "version": version,
        "payload": data,
        "site_id": site_id,
        "envelope_extra": envelope_extra or {},
    }
    # `event_id` explícito é a exceção, não a regra: quem emite normalmente
    # deixa o default do model cunhar um. Ele existe porque a carta declara
    # `origem_event_id` DENTRO do `data`, e o valor precisa estar decidido antes
    # de o `data` ser montado — cunhar depois faria os dois discordarem, em
    # silêncio, e a rastreabilidade que o campo promete morreria na primeira
    # carta.
    if event_id is not None:
        campos["event_id"] = event_id
    return OutboxEvent.objects.create(**campos)


def carta_de_celebracao(
    *,
    site_id: str,
    destinatario_id: str,
    assunto: str,
    parametros: dict[str, Any],
    origem_event_id: str | None = None,
) -> OutboxEvent:
    """A carta de UMA celebração para UMA pessoa.

    É a única porta desta célula para o sininho, e é genérica de propósito: os
    quatro assuntos da Sessão B compartilham forma, e os três que ainda não têm
    fato para pendurar (medalha, marco e destaque da semana vêm nos degraus 12 e
    19 da escada) entram com uma chamada, sem contrato novo e sem código novo
    aqui.

    `origem_event_id` é o `event_id` do FATO que causou a celebração — o evento
    da Caixa ou do fórum que rendeu o XP, quando ele existe. **Quando não
    existe**, a carta usa o PRÓPRIO id, e isso não é remendo: é o que a
    `alunos` já faz na carta de liberação, e o campo continua cumprindo o que
    promete (de qualquer aviso se chega ao acontecimento que o causou). Sem
    fato anterior, o acontecimento é a própria carta — uma liberação de
    quarentena, por exemplo, é um relógio, não um clique de alguém.
    """
    if assunto not in ASSUNTOS:
        raise AssuntoForaDoContrato(
            f"{assunto!r} não é um dos assuntos que esta célula publica. "
            f"O contrato congelado conhece: {sorted(ASSUNTOS)}. Assunto novo "
            "entra por Rito de Contrato (RITOS §3), nunca por um dicionário "
            "aqui."
        )

    # UM identificador para a CELEBRAÇÃO, usado nos dois lugares quando não há
    # fato anterior. No dia em que uma celebração gerar N cartas (uma medalha de
    # obra coletiva, por exemplo), todas compartilharão este valor — que é
    # exatamente o que o campo promete no contrato.
    identificador = uuid.uuid4()

    return emitir(
        NOTIFICACAO_DEVIDA,
        {
            "site_id": site_id,
            "destinatario_id": destinatario_id,
            "assunto": assunto,
            "parametros": parametros,
            "origem_event_id": origem_event_id or str(identificador),
        },
        site_id=site_id,
        # `ator_id` é NULO nas cartas desta célula, e a ausência é a verdade:
        # ninguém "concedeu" um nível. Quem o alcançou foi a própria pessoa, e o
        # que disparou a conta foi um relógio ou um fato que ela mesma causou. O
        # contrato prevê `null` exatamente para os fatos sem gente por trás.
        envelope_extra={"ator_id": None},
        event_id=identificador,
    )


def carta_de_nivel(
    *,
    site_id: str,
    destinatario_id: str,
    nivel: int,
    titulo: str,
    origem_event_id: str | None = None,
) -> OutboxEvent:
    """Subiu de nível. A primeira das quatro cartas a ganhar fato de verdade.

    **O `titulo_slug` é DERIVADO do título, e a escolha é medida.** O contrato
    pede um slug; `NivelDefinicao` guarda `titulo` (e a forma feminina), sem
    coluna de slug. Havia dois caminhos: acrescentar a coluna, ou derivá-la aqui.
    A coluna é o desenho melhor no dia em que um título for RENOMEADO — mas ela
    exigiria uma migração de dados sobre linhas que já existem em produção
    (a economia foi semeada em 01/09/2026), e `semear_economia` é `get_or_create`,
    que de propósito não altera o que já está lá: a coluna nasceria vazia e a
    carta sairia com slug em branco, sem erro em lugar nenhum. É o mesmo erro que
    o conserto da regra `sugestao-implementada` quase cometeu em 31/08/2026, e o
    mesmo que deixou um travessão vivo no fórum depois de uma limpeza que se
    declarou completa: corrigir o semeador NÃO corrige a linha já semeada.

    Enquanto isso, o `nivel` — que viaja junto e é o campo obrigatório de
    verdade — é o que identifica o degrau sem ambiguidade. O slug acompanha para
    o sininho escolher o tom.
    """
    # Título vazio ou só com sinais gráficos deixaria `slugify` devolver "", e
    # uma string vazia PASSA no contrato (`type: string`) — seria um campo mudo
    # atravessando o fio sem nada reclamar. O número do degrau nunca é ambíguo,
    # então é dele que sai o slug de reserva.
    slug = slugify(titulo) or f"nivel-{int(nivel)}"
    return carta_de_celebracao(
        site_id=site_id,
        destinatario_id=destinatario_id,
        assunto=ASSUNTO_NIVEL,
        parametros={"nivel": int(nivel), "titulo_slug": slug},
        origem_event_id=origem_event_id,
    )
