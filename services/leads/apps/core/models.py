# apps/core/models.py  # [RECEITA:R4 v1]
import uuid

from django.db import models


class Lead(models.Model):
    """Uma pessoa, dentro de UM site. A mesma pessoa (mesmo e-mail) em sites
    diferentes é registrada como leads distintos — upsert é por (site_id, email)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site_id = models.CharField(max_length=100)
    email = models.EmailField()
    name = models.CharField(max_length=200, blank=True, default="")
    phone = models.CharField(max_length=50, blank=True, default="")
    source = models.CharField(max_length=100, blank=True, default="")
    utm = models.JSONField(default=dict, blank=True)
    tags = models.JSONField(default=list, blank=True)
    consent = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site_id", "email"], name="uniq_lead_site_email"
            ),
        ]


class TimelineEvent(models.Model):
    """Histórico da pessoa, por site. Nunca é apagado — upsert e reprocessamento
    de evento só acrescentam entrada, nunca removem as existentes."""

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="timeline")
    event = models.CharField(max_length=100)  # ex.: "quiz.completado", "lead.upsert"
    event_id = models.UUIDField(null=True, blank=True)  # ausente para upsert via API
    payload = models.JSONField()
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["lead", "occurred_at"])]


class EventoProcessado(models.Model):
    """[INV-leads-idempotencia] a unicidade É o guarda: reentrega do mesmo
    event_id não roda o handler pela segunda vez."""

    event_id = models.UUIDField(unique=True)
    processed_at = models.DateTimeField(auto_now_add=True)


class FatoDePagamentoProcessado(models.Model):
    """[INV-leads-dedup-entre-versoes] o mesmo pagamento pode chegar como
    `pagamento.aprovado`/`pagamento.recusado` na v1 e depois na v2 (RITOS.md
    §3: o v1 continua no ar até o último consumidor migrar). `event_id` não
    serve de guarda aqui — cada entrega tem o seu, mesmo quando é o MESMO
    fato relatado duas vezes. A unicidade É o guarda: (`evento`, `site_id`,
    `chave`) derivados de `x-ponte-do-v1` de cada contrato (ver
    `apps.core.handlers._chave_pagamento_aprovado` e `_chave_pagamento_recusado`)
    identificam o fato, não a entrega, e a segunda tentativa de gravar a
    mesma linha esbarra na constraint.

    `site_id` entra na IDENTIDADE, não só na leitura: sem ele, um
    aviso com o site errado (bug do publicador, ou mensagem injetada no
    stream) gravaria a identidade do fato verdadeiro sem produzir efeito
    nenhum de menção nele, e o aviso legítimo que chegasse depois seria
    descartado como duplicado. O pagamento aconteceria e a timeline do site
    certo nunca receberia nada, para sempre, sem erro em lugar nenhum. Ver
    `tests/test_inv_leads_dedup_entre_versoes.py`, testes com sufixo
    `_inv_p11`."""

    evento = models.CharField(max_length=40)
    site_id = models.CharField(max_length=100)
    chave = models.CharField(max_length=200)
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["evento", "site_id", "chave"],
                name="uniq_fato_pagamento_por_site",
            ),
        ]


class ReversaoDePagamento(models.Model):
    """Reversão por compra; guarda o fato mesmo se a aprovação chegar depois."""

    site_id = models.CharField(max_length=100)
    order_id = models.CharField(max_length=200)
    event_id = models.UUIDField()
    payload = models.JSONField()
    registrada_na_timeline = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site_id", "order_id"], name="uniq_reversao_site_pedido"
            ),
        ]


class Oportunidade(models.Model):
    """O acompanhamento comercial humano de UMA pessoa já conhecida da casa.

    A situação não é coluna: é derivada de `desfecho_encerrada_em`. Duas colunas
    dizendo a mesma coisa é uma que pode mentir — o contrato declara `aberta` e
    `encerrada` como variantes disjuntas, e aqui só existe um fato para consultar.
    """

    ETAPAS_ABERTAS = ("nova", "qualificada", "proposta", "negociacao")
    ETAPAS_ENCERRADAS = ("ganha", "perdida", "desqualificada")
    TIPOS_DE_FONTE = ("captura", "quiz", "pedido", "pagamento", "timeline_lead")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey(
        Lead, on_delete=models.PROTECT, related_name="oportunidades"
    )
    etapa = models.CharField(max_length=20)
    titular_id = models.CharField(max_length=100)
    fonte_tipo = models.CharField(max_length=20)
    fonte_referencia_id = models.CharField(max_length=200)
    passo_descricao = models.TextField()
    passo_executar_ate = models.DateTimeField()
    passo_evidencia_esperada = models.TextField()
    desfecho_resultado = models.CharField(max_length=20, blank=True, default="")
    desfecho_motivo = models.TextField(blank=True, default="")
    desfecho_evidencia = models.TextField(blank=True, default="")
    desfecho_encerrada_em = models.DateTimeField(null=True, blank=True)
    # Acompanhamento do dia a dia, escrito pelo agente ou pela pessoa da
    # equipe. Próximo passo e prazo são `passo_descricao` e
    # `passo_executar_ate`; aqui fica o resto do que o quadro mostra.
    ATENDIDO_POR = ("agente", "pessoa")
    atendido_por_tipo = models.CharField(max_length=10, blank=True, default="")
    atendido_por_nome = models.CharField(max_length=200, blank=True, default="")
    ultimo_contato_em = models.DateTimeField(null=True, blank=True)
    objecao_principal = models.TextField(blank=True, default="")
    aguardando_resposta = models.BooleanField(default=False)
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["titular_id", "-criada_em"]),
            models.Index(fields=["lead", "-criada_em"]),
        ]

    @property
    def encerrada(self) -> bool:
        return self.desfecho_encerrada_em is not None


class RegistroHistoricoOportunidade(models.Model):
    """Histórico humano da oportunidade. Nasce imutável e morre imutável.

    A garantia não é combinada: `save()` recusa o segundo save da mesma linha e
    `delete()` recusa sempre. O contrato promete que a API não expõe alteração
    nem remoção; sem estas duas recusas, a promessa valeria só enquanto ninguém
    escrevesse a linha de código que a quebra.
    """

    TIPOS = (
        "nota",
        "contato",
        "etapa_alterada",
        "transferencia_solicitada",
        "transferencia_aceita",
        "transferencia_recusada",
        "encerramento",
        "reabertura",
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    oportunidade = models.ForeignKey(
        Oportunidade, on_delete=models.PROTECT, related_name="historico"
    )
    registrado_em = models.DateTimeField(auto_now_add=True)
    autor_id = models.CharField(max_length=100)
    tipo = models.CharField(max_length=30)
    descricao = models.TextField()
    evidencia = models.TextField(blank=True, default="")

    class Meta:
        indexes = [models.Index(fields=["oportunidade", "registrado_em"])]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError(
                "registro de histórico é imutável: crie um registro novo em vez "
                "de alterar este"
            )
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError(
            "registro de histórico não é removível: o histórico da oportunidade "
            "é a memória do acompanhamento"
        )


class TransferenciaResponsabilidade(models.Model):
    """Passagem de bastão entre comerciais, com aceite do novo titular.

    A unicidade parcial É o guarda do 409: enquanto houver uma pendente, o banco
    recusa a segunda. Sem ela, duas chamadas simultâneas abririam duas pendências
    e a segunda aceita trocaria o titular de novo, sem ninguém ter pedido.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    oportunidade = models.ForeignKey(
        Oportunidade, on_delete=models.PROTECT, related_name="transferencias"
    )
    de_titular_id = models.CharField(max_length=100)
    para_titular_id = models.CharField(max_length=100)
    motivo = models.TextField()
    estado = models.CharField(max_length=10, default="pendente")
    solicitada_em = models.DateTimeField(auto_now_add=True)
    concluida_em = models.DateTimeField(null=True, blank=True)
    motivo_recusa = models.TextField(blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["oportunidade"],
                condition=models.Q(estado="pendente"),
                name="uniq_transferencia_pendente_por_oportunidade",
            ),
        ]


class QuizDoLead(models.Model):
    """O quiz que a pessoa respondeu, com as perguntas e respostas legíveis.

    Uma linha por tentativa: a captura parcial abre a linha e o quiz completo
    a conclui, sem criar outra. As respostas chegam prontas do quiz (texto da
    pergunta e das opções), para a ficha e o agente lerem sem perguntar a
    outra célula.
    """

    SITUACOES = ("parcial", "completo")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="quizzes")
    quiz_slug = models.CharField(max_length=100)
    sessao = models.CharField(max_length=100, blank=True, default="")
    submissao_id = models.CharField(max_length=100, blank=True, default="")
    versao = models.CharField(max_length=100, blank=True, default="")
    situacao = models.CharField(max_length=10, default="parcial")
    respostas = models.JSONField(default=list, blank=True)
    resultado = models.CharField(max_length=100, blank=True, default="")
    pontuacao = models.IntegerField(null=True, blank=True)
    utm = models.JSONField(default=dict, blank=True)
    campanha = models.CharField(max_length=200, blank=True, default="")
    ultimo_event_id = models.UUIDField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    completado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["lead", "-atualizado_em"])]
        constraints = [
            models.UniqueConstraint(
                fields=["lead", "quiz_slug", "sessao"],
                condition=~models.Q(sessao=""),
                name="uniq_quiz_do_lead_por_sessao",
            ),
        ]


class PerfilDoLead(models.Model):
    """Uma versão do perfil comercial da pessoa, escrita pelo analista.

    Cada análise acrescenta uma versão; a vigente é a de maior número. As
    anteriores ficam como histórico e não mudam.
    """

    PRIORIDADES = ("alta", "media", "baixa")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="perfis")
    versao = models.PositiveIntegerField()
    resumo = models.TextField(blank=True, default="")
    conteudo = models.JSONField(default=dict, blank=True)
    prioridade = models.CharField(max_length=10, blank=True, default="")
    prioridade_explicacao = models.TextField(blank=True, default="")
    oferta_indicada = models.JSONField(null=True, blank=True)
    analisado_em = models.DateTimeField()
    analisado_por = models.CharField(max_length=200, blank=True, default="")
    versao_estrategia = models.CharField(max_length=100, blank=True, default="")
    registrado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["lead", "versao"], name="uniq_perfil_do_lead_versao"
            ),
        ]
        indexes = [models.Index(fields=["lead", "-versao"])]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("versão de perfil não muda: grave uma versão nova")
        return super().save(*args, **kwargs)
