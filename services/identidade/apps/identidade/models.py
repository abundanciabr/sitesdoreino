# apps/identidade/models.py — a linha da pessoa (DECISAO-celula-de-identidade)
"""Camada de dados da célula `identidade`.

Uma tabela só, de propósito: esta célula responde "quem é", e mais nada.
A forma é a MESMA que a `Identidade` da Caixa tinha (EVO-01 §3) — foi de lá
que este desenho veio, e é para cá que a responsabilidade mudou de casa.

**O e-mail do SITE vive aqui e em nenhum outro lugar.** As células que
precisam dele para AUTORIZAR (a Caixa confere matrícula e staff) o recebem
pela resposta completa da API interna, sob token do par com o degrau a mais
(`TOKENS_COMPLETOS_*`) — nunca lendo este banco (Lei 3). O que as células
guardam do lado delas é snapshot próprio, casado por e-mail — snapshots são
sagrados (Virtude da Lei 3), e é isso que fez a mudança de casa custar zero
migração de dado em produção.
"""

import secrets

import uuid

from django.db import models


def cunhar_id() -> str:
    """Cunha o identificador opaco de uma `Identidade`.

    Texto, nunca UUID — decisão do EVO-01 §3, mantida aqui: a forma escolhida
    (`token_urlsafe`) deixa impossível um consumidor "reconhecer um UUID" e
    passar a tratá-lo como tal.
    """
    return secrets.token_urlsafe(16)


class Identidade(models.Model):
    """Quem é a pessoa, para o site inteiro — cunhada na primeira entrada.

    O Google prova QUEM É (e-mail verificado); nenhuma matrícula é conferida
    NA PORTA do site — quem decide SE PODE alguma coisa é a célula dona do
    recurso, na hora do recurso (a Caixa confere matrícula na participação).
    Reconhecer não é autorizar (DECISAO-onde-mora-a-sessao §4).
    """

    id = models.CharField(
        primary_key=True, max_length=64, default=cunhar_id, editable=False
    )
    # `unique` no e-mail (e não no par com `provedor`): a mesma pessoa entrando
    # amanhã por outro provedor — um código, por exemplo — precisa RECUPERAR
    # esta identidade, não cunhar uma segunda (EVO-01 §3).
    email = models.EmailField(unique=True)
    provedor = models.CharField(max_length=20, default="google")
    nome_exibido = models.CharField(max_length=120, blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:  # pragma: no cover - conveniência de admin/shell
        return self.nome_exibido or self.email


class OutboxEvent(models.Model):
    """Uma linha por fato que esta célula afirma ao resto da plataforma.

    Nasceu em 31/08/2026, junto com a VOZ desta célula: até então ela era muda
    — cunhava a `Identidade` e não contava a ninguém. Por isso o pedido mais
    óbvio do mantenedor, *"após o cadastro, mandar boas-vindas"*, não tinha o
    que escutar (`PLANO-SEQUENCIAS-DE-MENSAGENS` §2).

    O padrão é copiado da `alunos` — nunca o arquivo, e nunca por import
    cruzado (Lei 7): um relay diferente por célula significaria N modos de
    falha diferentes para o mesmo problema.

    `payload` guarda **só o campo `data`** do envelope. O envelope inteiro é
    montado pelo relay, no instante da publicação: guardar o envelope pronto
    duplicaria em JSON o que já são colunas, e as duas cópias envelheceriam
    separadas.
    """

    event_id = models.UUIDField(default=uuid.uuid4, unique=True)
    event = models.CharField(max_length=100)
    version = models.PositiveSmallIntegerField(default=1)
    payload = models.JSONField()  # SÓ o campo `data` do envelope
    occurred_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)
    # As chaves que este evento acrescenta ao ENVELOPE (o nível de cima), e não
    # ao `data`. Vazio hoje: `identidade.pessoa-cadastrada` não tem ator (quem
    # se cadastra não "faz isto a alguém"). O campo existe porque o relay é
    # burro de propósito — quem emite, que conhece o próprio contrato, é quem
    # declara o que vai no envelope.
    envelope_extra = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            # O caminho quente do relay é um só: "o que ainda não publiquei, na
            # ordem em que aconteceu".
            models.Index(fields=["published_at", "id"], name="idt_outbox_pendentes"),
        ]

    def __str__(self) -> str:  # pragma: no cover - conveniência de shell
        return f"{self.event}#{self.event_id}"
