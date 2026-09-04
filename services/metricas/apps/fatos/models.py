"""O evento imutável e a fila de eventos mortos (degrau 7.2).

`PLANO-PAINEL-DE-GESTAO.md` §6.2. Duas tabelas, e a diferença entre elas é a
única coisa que precisa ficar clara para quem chegar:

- **`Evento`** guarda o que a plataforma AFIRMA que aconteceu. É append-only:
  não se corrige, não se apaga. Correção é evento novo.
- **`EventoMorto`** guarda o que chegou e **não pôde ser afirmado**: corpo que
  não casa com o contrato, tipo desconhecido, data ilegível. Ele não conta em
  número nenhum; existe para ser inspecionado, tentado de novo ou descartado
  com motivo (Scale OS 1.2 §183), e para virar incidente no livro.

**Por que imutável, em uma frase:** um número derivado de fatos que alguém
pode reescrever não é medição, é opinião com casas decimais. A trava é dupla
de propósito — o ORM recusa e o banco recusa —, porque a trava do ORM não
alcança um `UPDATE` digitado num console e a do banco não explica nada a quem
está programando.
"""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from django.db import models

#: O fuso em que esta casa decide a que DIA um fato pertence. A `admin` usa o
#: mesmo (`placar.py::FUSO`), e as duas contas têm de concordar.
FUSO = ZoneInfo("America/Sao_Paulo")


class FatoImutavel(Exception):
    """Tentativa de alterar ou apagar um fato já gravado."""


class EventoQuerySet(models.QuerySet):
    """O caminho de conjunto também é fechado: `update()` e `delete()` recusam.

    Sem isto, `Evento.objects.filter(...).update(...)` passaria direto pelo
    `save()` sobrescrito — o ORM não chama `save()` numa atualização de
    conjunto, e a trava pareceria existir sem existir.
    """

    def update(self, **kwargs):
        raise FatoImutavel(
            "evento não se corrige: acrescente um evento novo que aponte para "
            "o anterior (AGENTS.metricas.md, invariante da imutabilidade)"
        )

    def delete(self):
        raise FatoImutavel(
            "evento não se apaga: o livro de fatos é append-only. Se o fato "
            "não devia ter sido afirmado, o que se grava é a correção"
        )


def dia_em_sao_paulo(instante: dt.datetime) -> dt.date:
    """O dia a que um instante pertence, em São Paulo.

    É a conversão que decide em qual mês uma pessoa entrou. 01h de UTC ainda é
    o dia anterior aqui; medir por UTC põe quem entrou às 22h do dia 30 no mês
    seguinte, sem erro em lugar nenhum (`armadilhas/099`).
    """
    if instante.tzinfo is None:
        raise ValueError("instante sem fuso: todo evento traz `occurred_at` com fuso")
    return instante.astimezone(FUSO).date()


class Evento(models.Model):
    """Um fato afirmado por uma célula, guardado como veio.

    O envelope é o canônico da casa (`contracts/eventos/*.json`): `event`,
    `version`, `event_id`, `occurred_at`, `data`. Os campos abaixo são esse
    envelope aberto em colunas — mais `dia`, que é derivado e existe para que
    contar por dia não custe uma conversão por linha em toda consulta.
    """

    #: `event_id` do envelope: a chave de idempotência. O mesmo fato reentregue
    #: pelo relay grava UMA vez, e é por este campo que a duplicata se recusa —
    #: nunca por comparação de conteúdo, que acharia iguais dois cadastros
    #: legítimos feitos no mesmo segundo.
    event_id = models.UUIDField(unique=True)

    #: `event` do envelope: "identidade.pessoa-cadastrada", "forum.topico-criado".
    tipo = models.CharField(max_length=120)

    #: `version` do envelope. Guardada porque o mesmo tipo pode ter dois
    #: formatos vivos ao mesmo tempo durante uma migração de contrato.
    versao = models.PositiveIntegerField()

    #: A célula que afirmou o fato, derivada do tipo (o que vem antes do ponto).
    #: Redundante de propósito: é por ela que se responde "quem parou de
    #: publicar?", e derivar isso com `LIKE` em toda consulta é caro e frágil.
    celula = models.CharField(max_length=60)

    #: `data.site_id`: a plataforma serve mais de um site (Lei 9).
    site_id = models.CharField(max_length=60)

    #: `occurred_at`: quando o fato aconteceu no mundo.
    ocorrido_em = models.DateTimeField()

    #: Quando ele chegou aqui. A distância entre os dois é o atraso do relay, e
    #: é o que a cobertura do degrau 7.11 vai medir.
    recebido_em = models.DateTimeField(auto_now_add=True)

    #: O dia de São Paulo de `ocorrido_em`, gravado no momento da recepção.
    dia = models.DateField()

    #: `data` inteiro, como veio. Guardar o corpo cru é o que permite responder
    #: amanhã uma pergunta que ninguém fez hoje.
    dados = models.JSONField()

    objects = EventoQuerySet.as_manager()

    class Meta:
        indexes = [
            models.Index(fields=["tipo", "dia"]),
            models.Index(fields=["dia"]),
            models.Index(fields=["celula", "recebido_em"]),
        ]
        ordering = ["-ocorrido_em"]

    def __str__(self) -> str:
        return f"{self.tipo} v{self.versao} em {self.dia}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise FatoImutavel(
                "evento não se corrige: acrescente um evento novo que aponte "
                "para o anterior (AGENTS.metricas.md, invariante da "
                "imutabilidade)"
            )
        if self.dia is None and self.ocorrido_em is not None:
            self.dia = dia_em_sao_paulo(self.ocorrido_em)
        if not self.celula and self.tipo:
            self.celula = self.tipo.split(".")[0]
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise FatoImutavel(
            "evento não se apaga: o livro de fatos é append-only. Se o fato "
            "não devia ter sido afirmado, o que se grava é a correção"
        )


class EventoMorto(models.Model):
    """O que chegou e não pôde ser afirmado.

    Fail-closed: evento inválido nunca é aceito pela metade. Meio fato gravado
    é pior que fato nenhum, porque o número resultante parece medido.

    Diferente do `Evento`, esta tabela É mutável — de propósito. Ela guarda o
    ESTADO de um problema em aberto (inspecionar, tentar de novo, descartar com
    motivo), e estado que muda é a natureza dela. O que nunca muda é o corpo
    cru: `corpo` só se escreve na criação.
    """

    class Estado(models.TextChoices):
        NOVO = "novo", "Novo"
        REPROCESSADO = "reprocessado", "Reprocessado"
        DESCARTADO = "descartado", "Descartado"

    #: O corpo exatamente como chegou, em texto. Texto e não JSON porque a
    #: causa mais comum de um evento morto é justamente não ser JSON válido.
    corpo = models.TextField()

    #: Por que não pôde ser afirmado, em português, para quem for inspecionar.
    motivo = models.TextField()

    #: O que se conseguiu ler do envelope antes de desistir. Podem ficar
    #: vazios, e é por isso que não são chave de nada.
    tipo_declarado = models.CharField(max_length=120, blank=True)
    event_id_declarado = models.CharField(max_length=80, blank=True)

    recebido_em = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(
        max_length=20, choices=Estado.choices, default=Estado.NOVO
    )

    #: Preenchidos quando alguém age. `decidido_por` é o id opaco de quem
    #: decidiu, nunca o e-mail.
    decidido_em = models.DateTimeField(null=True, blank=True)
    decidido_por = models.CharField(max_length=80, blank=True)
    motivo_da_decisao = models.TextField(blank=True)

    class Meta:
        indexes = [models.Index(fields=["estado", "recebido_em"])]
        ordering = ["-recebido_em"]

    def __str__(self) -> str:
        return f"morto: {self.tipo_declarado or 'sem tipo'} ({self.estado})"
