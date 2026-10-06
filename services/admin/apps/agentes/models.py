"""Os robôs pessoais da equipe: quem é cada robô, o que ele conversou, o que
executou no servidor e o que entregou.

Plano-mestre dos robôs (01/10/2026), §10. Quatro coisas separadas, de
propósito:

* **identidade do robô** (`RoboPessoal`): persiste; trocar o modelo não cria
  outro robô;
* **responsável humano** (`RoboPessoal.membro`): a pessoa da equipe dona do
  robô, cujas permissões o robô usa;
* **modelo** (`Execucao.modelo`, `Consumo.modelo`): o que respondeu naquela
  execução, conferido na conta (`Conexao`);
* **executor** (`Execucao.trabalhador`): o processo do servidor que pegou a
  execução. O navegador só pede e acompanha.

As tarefas continuam na tabela da equipe (`core.Tarefa`); aqui só se guarda o
NÚMERO da tarefa (`tarefa_id`), para que esta parte possa virar uma célula
própria sem levar a tabela da equipe junto.
"""

from __future__ import annotations

from django.db import models
from django.db.models import Q

from .modelos_comerciais import MaterialComercial, TrechoComercial  # noqa: F401


class RoboPessoal(models.Model):
    """O robô de UMA pessoa da equipe. Nasce no primeiro acesso dela."""

    class Situacao(models.TextChoices):
        ATIVO = "ativo", "Ativo"
        PAUSADO = "pausado", "Pausado"

    membro = models.OneToOneField(
        "core.MembroDaEquipe", on_delete=models.PROTECT, related_name="robo"
    )
    nome = models.CharField(max_length=120)
    responsabilidades = models.TextField(blank=True, default="")
    instrucoes = models.TextField(blank=True, default="")
    versao_das_instrucoes = models.PositiveIntegerField(default=1)
    situacao = models.CharField(
        max_length=20, choices=Situacao.choices, default=Situacao.ATIVO
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    alterado_em = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:  # pragma: no cover - conveniência de shell
        return self.nome


class Conversa(models.Model):
    """A conversa do membro com o robô. Uma por robô no primeiro lote."""

    robo = models.ForeignKey(
        RoboPessoal, on_delete=models.PROTECT, related_name="conversas"
    )
    titulo = models.CharField(max_length=200, blank=True, default="")
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)


class Execucao(models.Model):
    """Um trabalho do robô no servidor, do pedido ao fim.

    O navegador cria a linha e vai embora; o executor do servidor
    (`executor.py`) pega a linha com um prazo de posse (`ocupada_ate`),
    renova a posse enquanto trabalha e guarda o ponto de retomada em
    `estado`. Se o processo cair, a posse vence e outro trabalhador retoma
    do ponto guardado.
    """

    class Tipo(models.TextChoices):
        CONVERSA = "conversa", "Resposta na conversa"
        PANORAMA = "panorama_semanal", "Panorama semanal"
        CONFERENCIA_QUIZ = "conferencia_quiz", "Conferência dos links do quiz"
        LEITURA_QUIZ = "leitura_quiz", "Leitura dos números do quiz"
        CONHECIMENTO = "conhecimento", "Leitura dos documentos para o mapa de conhecimento"
        SUPER_EQUIPE = "super_equipe", "Equipe de especialistas técnicos"

    class Situacao(models.TextChoices):
        NA_FILA = "na_fila", "Na fila"
        EXECUTANDO = "executando", "Executando"
        AGUARDANDO_INFORMACAO = "aguardando_informacao", "Aguardando informação"
        AGUARDANDO_DEPENDENCIA = "aguardando_dependencia", "Aguardando dependência"
        AGUARDANDO_AUTORIZACAO = "aguardando_autorizacao", "Aguardando autorização"
        PAUSADA = "pausada", "Pausada"
        CONCLUIDA = "concluida", "Concluída"
        FALHOU = "falhou", "Falhou"
        CANCELADA = "cancelada", "Cancelada"

    ABERTAS = (
        Situacao.NA_FILA,
        Situacao.EXECUTANDO,
        Situacao.AGUARDANDO_INFORMACAO,
        Situacao.AGUARDANDO_DEPENDENCIA,
        Situacao.AGUARDANDO_AUTORIZACAO,
        Situacao.PAUSADA,
    )
    ESPERANDO = (
        Situacao.AGUARDANDO_INFORMACAO,
        Situacao.AGUARDANDO_DEPENDENCIA,
        Situacao.AGUARDANDO_AUTORIZACAO,
        Situacao.PAUSADA,
    )

    robo = models.ForeignKey(
        RoboPessoal, on_delete=models.PROTECT, related_name="execucoes"
    )
    tipo = models.CharField(max_length=30, choices=Tipo.choices)
    origem = models.CharField(max_length=30, blank=True, default="")
    # Quem pediu, para agir com a identidade e o acesso DELE também em
    # segundo plano: o número da pessoa e o texto que a tela mostra.
    pedido_por_membro_id = models.IntegerField(null=True, blank=True)
    pedido_por = models.CharField(max_length=200, blank=True, default="")
    conversa = models.ForeignKey(
        Conversa,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="execucoes",
    )
    tarefa_id = models.IntegerField(null=True, blank=True, db_index=True)
    pedido = models.TextField(blank=True, default="")
    # Pedido repetido (duplo clique, reenvio do formulário, evento entregue
    # duas vezes) acha a execução que já existe em vez de criar outra.
    chave_de_repeticao = models.CharField(
        max_length=120, null=True, blank=True, unique=True
    )
    modelo = models.CharField(max_length=60, blank=True, default="")

    situacao = models.CharField(
        max_length=30, choices=Situacao.choices, default=Situacao.NA_FILA
    )
    motivo = models.TextField(blank=True, default="")
    etapa_atual = models.CharField(max_length=200, blank=True, default="")
    progresso = models.PositiveSmallIntegerField(default=0)
    estado = models.JSONField(default=dict, blank=True)
    resultado = models.TextField(blank=True, default="")
    tentativas = models.PositiveIntegerField(default=0)

    trabalhador = models.CharField(max_length=120, blank=True, default="")
    ocupada_ate = models.DateTimeField(null=True, blank=True)
    batimento_em = models.DateTimeField(null=True, blank=True)
    nao_antes_de = models.DateTimeField(null=True, blank=True)
    cancelar_pedido_em = models.DateTimeField(null=True, blank=True)

    criada_em = models.DateTimeField(auto_now_add=True)
    iniciada_em = models.DateTimeField(null=True, blank=True)
    terminada_em = models.DateTimeField(null=True, blank=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-criada_em"]
        indexes = [
            models.Index(fields=["situacao", "criada_em"], name="agentes_execucao_fila_idx")
        ]

    @property
    def aberta(self) -> bool:
        return self.situacao in self.ABERTAS

    @property
    def esperando(self) -> bool:
        return self.situacao in self.ESPERANDO

    @property
    def duracao(self) -> str:
        """Do pedido ao fim, em palavras curtas ("6 s", "3 min")."""
        if self.terminada_em is None:
            return ""
        return tempo_em_palavras((self.terminada_em - self.criada_em).total_seconds())


def tempo_em_palavras(segundos: float) -> str:
    segundos = max(0, round(segundos))
    if segundos < 120:
        return f"{segundos} s"
    minutos = round(segundos / 60)
    if minutos < 120:
        return f"{minutos} min"
    return f"{minutos // 60} h {minutos % 60} min"


class RegistroDaExecucao(models.Model):
    """Cada passo e cada troca de situação, com data e motivo."""

    execucao = models.ForeignKey(
        Execucao, on_delete=models.CASCADE, related_name="registros"
    )
    momento = models.DateTimeField(auto_now_add=True)
    situacao = models.CharField(max_length=30, blank=True, default="")
    texto = models.TextField()

    class Meta:
        ordering = ["momento", "id"]


class Mensagem(models.Model):
    class Papel(models.TextChoices):
        MEMBRO = "membro", "Pessoa"
        ROBO = "robo", "Robô"
        AVISO = "aviso", "Aviso do sistema"

    conversa = models.ForeignKey(
        Conversa, on_delete=models.CASCADE, related_name="mensagens"
    )
    papel = models.CharField(max_length=10, choices=Papel.choices)
    texto = models.TextField()
    autor = models.CharField(max_length=200, blank=True, default="")
    chave_de_envio = models.CharField(max_length=64, blank=True, default="")
    execucao = models.ForeignKey(
        Execucao,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mensagens",
    )
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["criada_em", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["conversa", "chave_de_envio"],
                condition=~Q(chave_de_envio=""),
                name="mensagem_enviada_uma_vez",
            )
        ]


class ChamadaDeFerramenta(models.Model):
    """Uma ação que o modelo pediu e o sistema executou (ou recusou).

    `call_id` é o identificador que o modelo deu ao pedido: o mesmo pedido,
    visto de novo numa retomada, acha esta linha e devolve o resultado
    guardado em vez de executar duas vezes.
    """

    class Situacao(models.TextChoices):
        PEDIDA = "pedida", "Pedida"
        FEITA = "feita", "Feita"
        RECUSADA = "recusada", "Recusada"
        FALHOU = "falhou", "Falhou"

    execucao = models.ForeignKey(
        Execucao, on_delete=models.CASCADE, related_name="chamadas"
    )
    call_id = models.CharField(max_length=120)
    nome = models.CharField(max_length=80)
    argumentos = models.JSONField(default=dict, blank=True)
    resultado = models.JSONField(default=dict, blank=True)
    situacao = models.CharField(
        max_length=20, choices=Situacao.choices, default=Situacao.PEDIDA
    )
    criada_em = models.DateTimeField(auto_now_add=True)
    terminada_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["criada_em", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["execucao", "call_id"], name="uma_chamada_por_pedido"
            )
        ]


class Entrega(models.Model):
    """O que o robô produziu, salvo no site e ligado à tarefa.

    A pessoa abre a entrega com o crachá dela (`/equipe/robo/entregas/<n>`),
    não numa área só de administrador. Entrega parcial diz o que falta em
    `pendencias`; a mesma entrega ganha versão nova quando a pendência sai.
    """

    robo = models.ForeignKey(
        RoboPessoal, on_delete=models.PROTECT, related_name="entregas"
    )
    execucao = models.ForeignKey(
        Execucao,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="entregas",
    )
    tarefa_id = models.IntegerField(null=True, blank=True, db_index=True)
    tipo = models.CharField(max_length=30, blank=True, default="")
    titulo = models.CharField(max_length=200)
    conteudo = models.TextField()
    parcial = models.BooleanField(default=False)
    pendencias = models.JSONField(default=list, blank=True)
    versao = models.PositiveIntegerField(default=1)
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-criada_em"]


class AutorizacaoDeGasto(models.Model):
    """O teto de gasto com modelos que o mantenedor autorizou.

    O executor confere o teto ANTES de cada chamada paga, somando o gasto do
    mês e o pior caso da chamada. Sem autorização ativa, nada pago sai.
    """

    descricao = models.CharField(max_length=200)
    destino = models.CharField(max_length=20, default="equipe")
    teto_mensal_usd = models.DecimalField(max_digits=10, decimal_places=2)
    fonte = models.TextField()
    ativa = models.BooleanField(default=True)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criada_em"]


class Consumo(models.Model):
    """Uma chamada paga ao modelo: tokens e custo estimado em dólar.

    Chamada cujo resultado ficou desconhecido (caiu a conexão no meio) entra
    com o PIOR caso, marcada `desconhecido`: a conta do teto não pode
    esquecer um gasto que talvez tenha acontecido.
    """

    execucao = models.ForeignKey(
        Execucao,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="consumos",
    )
    robo = models.ForeignKey(
        RoboPessoal,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="consumos",
    )
    autorizacao = models.ForeignKey(
        AutorizacaoDeGasto,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="consumos",
    )
    modelo = models.CharField(max_length=60)
    origem = models.CharField(max_length=20, default="equipe")
    resposta_id = models.CharField(max_length=120, blank=True, default="")
    tokens_entrada = models.PositiveIntegerField(default=0)
    tokens_entrada_em_cache = models.PositiveIntegerField(default=0)
    tokens_saida = models.PositiveIntegerField(default=0)
    custo_estimado_usd = models.DecimalField(max_digits=12, decimal_places=6)
    desconhecido = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]


class RoboDosAlunos(models.Model):
    """Assistente da escola para alunos, independente dos robôs da equipe."""

    nome = models.CharField(max_length=120, default="Robô dos alunos")
    modelo = models.CharField(max_length=60, default="gpt-6-luna")
    instrucoes = models.TextField(blank=True, default="")
    ativo = models.BooleanField(default=False)
    autorizacao = models.ForeignKey(
        AutorizacaoDeGasto, null=True, blank=True, on_delete=models.PROTECT
    )
    alterado_em = models.DateTimeField(auto_now=True)


class Conexao(models.Model):
    """A conexão com o provedor do modelo.

    A chave fica CIFRADA no banco (`segredo.py`), nunca em texto, nunca no
    prompt, nunca no log; a tela mostra só os quatro últimos caracteres.
    `OPENAI_API_KEY` no ambiente, quando existir, vale por cima desta.
    """

    class Situacao(models.TextChoices):
        SEM_CHAVE = "sem_chave", "Sem chave"
        A_CONFERIR = "a_conferir", "A conferir"
        CONFERIDA = "conferida", "Conferida"
        RECUSADA = "recusada", "Recusada pela conta"
        FALHOU = "falhou", "Não deu para conferir"

    provedor = models.CharField(max_length=30, unique=True, default="openai")
    segredo_cifrado = models.TextField(blank=True, default="")
    final_da_chave = models.CharField(max_length=8, blank=True, default="")
    situacao = models.CharField(
        max_length=20, choices=Situacao.choices, default=Situacao.SEM_CHAVE
    )
    detalhe = models.TextField(blank=True, default="")
    modelo_rapido = models.CharField(max_length=60, default="gpt-6-luna")
    modelo_forte = models.CharField(max_length=60, default="gpt-6-sol")
    modelos_disponiveis = models.JSONField(default=list, blank=True)
    conferida_em = models.DateTimeField(null=True, blank=True)
    alterada_por = models.CharField(max_length=200, blank=True, default="")
    alterada_em = models.DateTimeField(auto_now=True)


class FonteDoConhecimento(models.Model):
    """Um documento do site já lido para o mapa de conhecimento
    (`conhecimento.py`). A `impressao` é o resumo do texto lido: documento que
    não mudou não é lido de novo, e não gasta de novo."""

    chave = models.CharField(max_length=120, unique=True)
    titulo = models.CharField(max_length=200)
    endereco = models.CharField(max_length=300, blank=True, default="")
    publica = models.BooleanField(default=False)
    impressao = models.CharField(max_length=64)
    lida_em = models.DateTimeField(auto_now=True)


class EntidadeDoConhecimento(models.Model):
    """Uma coisa que um documento cita: pessoa, curso, oferta, sistema..."""

    fonte = models.ForeignKey(
        FonteDoConhecimento, on_delete=models.CASCADE, related_name="entidades"
    )
    nome = models.CharField(max_length=200)
    tipo = models.CharField(max_length=40)
    resumo = models.CharField(max_length=500, blank=True, default="")


class LigacaoDoConhecimento(models.Model):
    """Uma ligação que um documento afirma entre duas coisas, com o trecho
    que a sustenta: é o que deixa o robô dizer de onde tirou a resposta."""

    fonte = models.ForeignKey(
        FonteDoConhecimento, on_delete=models.CASCADE, related_name="ligacoes"
    )
    origem = models.CharField(max_length=200)
    relacao = models.CharField(max_length=80)
    destino = models.CharField(max_length=200)
    evidencia = models.CharField(max_length=400, blank=True, default="")
