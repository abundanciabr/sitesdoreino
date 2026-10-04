"""A equipe comercial de agentes: o que ela tem a fazer, o que decidiu e com
que estratégia.

Plano do CRM com agentes (03/10/2026). Três registros, de propósito
separados:

* **trabalho** (`TrabalhoComercial`): uma tarefa do coordenador — analisar um
  lead, abordá-lo, atender uma mensagem, acompanhar um pagamento ou analisar
  resultados. Tem posse com prazo e ponto de retomada, como as execuções dos
  robôs da equipe (`apps/agentes/executor.py`), e uma chave de idempotência:
  o mesmo evento entregue duas vezes acha o mesmo trabalho;
* **decisão** (`DecisaoComercial`): cada ferramenta que o agente pediu, com o
  contexto usado, a entrada, a saída, a versão da estratégia, o resultado e o
  custo. O `call_id` é a identidade da execução: a retomada acha a decisão já
  tomada e devolve o resultado guardado, sem repetir mensagem, link ou pedido;
* **estratégia** (`EstrategiaComercial`): as instruções de cada papel, em
  versões. Uma ativa por papel; a anterior fica guardada para voltar.

Os fatos (contato, oportunidade, conversa, pedido, pagamento) continuam nas
células donas deles. Aqui só se guarda a REFERÊNCIA a eles.
"""

from __future__ import annotations

from django.db import models
from django.db.models import Q


class EstrategiaComercial(models.Model):
    """As instruções de um papel numa versão. Mudar a estratégia é criar outra
    versão; a conversa já feita guarda a versão que usou."""

    class Papel(models.TextChoices):
        ANALISTA = "analista", "Analista do lead"
        ABORDAGEM = "abordagem", "Abordagem"
        ATENDIMENTO = "atendimento", "Atendimento e negociação"
        RESULTADOS = "resultados", "Análise de resultados"

    class Situacao(models.TextChoices):
        PROPOSTA = "proposta", "Proposta"
        ATIVA = "ativa", "Ativa"
        ARQUIVADA = "arquivada", "Arquivada"

    papel = models.CharField(max_length=20, choices=Papel.choices)
    versao = models.PositiveIntegerField()
    instrucoes = models.TextField()
    ativa = models.BooleanField(default=False)
    situacao = models.CharField(
        max_length=20, choices=Situacao.choices, default=Situacao.PROPOSTA
    )
    criada_por = models.CharField(max_length=200, blank=True, default="")
    motivo = models.TextField(blank=True, default="")
    origem = models.CharField(max_length=20, blank=True, default="")
    anterior = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="seguintes"
    )
    evidencias = models.JSONField(default=dict, blank=True)
    historico = models.JSONField(default=list, blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)
    ativada_em = models.DateTimeField(null=True, blank=True)
    desativada_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["papel", "-versao"]
        constraints = [
            models.UniqueConstraint(fields=["papel", "versao"], name="estrategia_versao_unica"),
            models.UniqueConstraint(
                fields=["papel"], condition=Q(ativa=True), name="uma_estrategia_ativa_por_papel"
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover - conveniência de shell
        return f"{self.get_papel_display()} v{self.versao}"


class TrabalhoComercial(models.Model):
    class Tipo(models.TextChoices):
        ANALISAR_LEAD = "analisar_lead", "Analisar o lead"
        ABORDAR = "abordar", "Abordar o lead"
        ATENDER_MENSAGEM = "atender_mensagem", "Atender mensagem"
        ACOMPANHAR_PAGAMENTO = "acompanhar_pagamento", "Acompanhar pagamento"
        ANALISAR_RESULTADOS = "analisar_resultados", "Analisar resultados"
        REANALISAR_PERFIL = "reanalisar_perfil", "Atualizar o perfil"
        RECUPERAR_COMPRA = "recuperar_compra", "Recuperar compra"
        REGISTRAR_ESTORNO = "registrar_estorno", "Registrar estorno"

    class Estado(models.TextChoices):
        NA_FILA = "na_fila", "Na fila"
        EXECUTANDO = "executando", "Executando"
        AGUARDANDO_DEPENDENCIA = "aguardando_dependencia", "Aguardando serviço"
        AGUARDANDO_AUTORIZACAO = "aguardando_autorizacao", "Aguardando teto de gasto"
        ENVIO_INCERTO = "envio_incerto", "Envio sem confirmação"
        CONCLUIDO = "concluido", "Concluído"
        ENCERRADO = "encerrado", "Encerrado sem precisar agir"
        FALHOU = "falhou", "Falhou"
        CANCELADO = "cancelado", "Cancelado"

    ABERTOS = (
        Estado.NA_FILA,
        Estado.EXECUTANDO,
        Estado.AGUARDANDO_DEPENDENCIA,
        Estado.AGUARDANDO_AUTORIZACAO,
        Estado.ENVIO_INCERTO,
    )
    # Quem detém a resposta da conversa: um por vez (a restrição abaixo).
    TRAVAM_A_CONVERSA = (Estado.EXECUTANDO, Estado.ENVIO_INCERTO)

    tipo = models.CharField(max_length=30, choices=Tipo.choices)
    papel = models.CharField(max_length=20, blank=True, default="")
    origem = models.CharField(max_length=30, blank=True, default="")
    evento_id = models.CharField(max_length=120, blank=True, default="")

    site_id = models.CharField(max_length=80, blank=True, default="", db_index=True)
    contato_id = models.CharField(max_length=80, blank=True, default="", db_index=True)
    oportunidade_id = models.CharField(max_length=80, blank=True, default="", db_index=True)
    conversa_id = models.CharField(max_length=120, blank=True, default="")
    pedido_id = models.CharField(max_length=120, blank=True, default="", db_index=True)
    # A trava: trabalhos com a mesma chave (a conversa, ou o lead quando ainda
    # não há conversa) não respondem ao mesmo tempo.
    chave_da_conversa = models.CharField(max_length=200, blank=True, default="", db_index=True)
    chave_idempotencia = models.CharField(max_length=200, unique=True)
    anterior = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="seguintes"
    )

    estado = models.CharField(max_length=30, choices=Estado.choices, default=Estado.NA_FILA)
    motivo = models.TextField(blank=True, default="")
    entrada = models.JSONField(default=dict, blank=True)
    # O ponto de retomada: os itens já trocados com o modelo e as rodadas.
    retomada = models.JSONField(default=dict, blank=True)
    resultado = models.JSONField(default=dict, blank=True)
    resumo = models.TextField(blank=True, default="")
    teste = models.BooleanField(default=False)
    modelo = models.CharField(max_length=60, blank=True, default="")
    custo_usd = models.DecimalField(max_digits=12, decimal_places=6, default=0)

    tentativas = models.PositiveIntegerField(default=0)
    trabalhador = models.CharField(max_length=120, blank=True, default="")
    ocupado_ate = models.DateTimeField(null=True, blank=True)
    batimento_em = models.DateTimeField(null=True, blank=True)
    nao_antes_de = models.DateTimeField(null=True, blank=True)
    encerrar_pedido_em = models.DateTimeField(null=True, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    iniciado_em = models.DateTimeField(null=True, blank=True)
    terminado_em = models.DateTimeField(null=True, blank=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-criado_em", "-id"]
        indexes = [
            models.Index(fields=["estado", "criado_em"], name="comercial_trabalho_fila_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["chave_da_conversa"],
                condition=Q(estado__in=["executando", "envio_incerto"]) & ~Q(chave_da_conversa=""),
                name="uma_resposta_por_conversa",
            )
        ]

    @property
    def aberto(self) -> bool:
        return self.estado in self.ABERTOS


class DecisaoComercial(models.Model):
    """Uma ação pedida pelo agente (ou a decisão final dele) e o que ela deu."""

    class Resultado(models.TextChoices):
        PENDENTE = "pendente", "Saindo"
        FEITO = "feito", "Feito"
        RECUSADO = "recusado", "Recusado"
        INDISPONIVEL = "indisponivel", "Capacidade indisponível"
        INCERTO = "incerto", "Sem confirmação"
        DECIDIDO = "decidido", "Decidido"

    trabalho = models.ForeignKey(
        TrabalhoComercial, on_delete=models.CASCADE, related_name="decisoes"
    )
    papel = models.CharField(max_length=20, blank=True, default="")
    estrategia = models.ForeignKey(
        EstrategiaComercial, null=True, blank=True, on_delete=models.PROTECT, related_name="decisoes"
    )
    versao_estrategia = models.PositiveIntegerField(null=True, blank=True)
    call_id = models.CharField(max_length=120)
    acao = models.CharField(max_length=60, blank=True, default="")
    ferramenta = models.CharField(max_length=80, blank=True, default="")
    contexto_usado = models.JSONField(default=dict, blank=True)
    entrada = models.JSONField(default=dict, blank=True)
    saida = models.JSONField(default=dict, blank=True)
    resultado = models.CharField(max_length=20, choices=Resultado.choices)
    chave_idempotencia = models.CharField(max_length=80, blank=True, default="")
    custo_usd = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    consumo = models.ForeignKey(
        "agentes.Consumo", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    criada_em = models.DateTimeField(auto_now_add=True)
    terminada_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["criada_em", "id"]
        constraints = [
            models.UniqueConstraint(fields=["trabalho", "call_id"], name="uma_decisao_por_chamada")
        ]


class EventoComercial(models.Model):
    """Um evento da plataforma que o coordenador já tratou. Reentrega do mesmo
    `event_id` não cria nada de novo. Guarda só referências, nunca dados
    pessoais: o fato mora na célula que o publicou."""

    event_id = models.CharField(max_length=120, unique=True)
    nome = models.CharField(max_length=80)
    site_id = models.CharField(max_length=80, blank=True, default="")
    oportunidade_ref = models.CharField(max_length=80, blank=True, default="", db_index=True)
    pedido_id = models.CharField(max_length=120, blank=True, default="", db_index=True)
    recebido_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recebido_em"]


# O teste entre duas versões de estratégia mora em experimentos.py (ver o módulo).
from .experimentos import ExperimentoEstrategia  # noqa: E402,F401
# O interruptor da equipe e o escopo por quiz (uma linha por instalação).
from .interruptor import ConfiguracaoComercial  # noqa: E402,F401

# O grupo de comparação (leads que ficam sem o agente) mora em comparacao.py (ver o módulo).
from .comparacao import ConfiguracaoDaComparacao, MarcaDeComparacao  # noqa: E402,F401
