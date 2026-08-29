# apps/matriculas/models.py
from django.db import models

STATUS_ATIVA = "ativa"
STATUS_SUSPENSA = "suspensa"
STATUS_REEMBOLSADA = "reembolsada"
STATUS_AGUARDANDO = "aguardando"
STATUS_RECUSADA = "recusada"
# [GESTAO] Quem saiu da escola (28/08/2026). Estado NOVO, e nao um apelido para
# `reembolsada`: reembolso e sobre dinheiro devolvido, sair e sobre acesso.
STATUS_ENCERRADA = "encerrada"

# [GESTAO] `suspensa` SAIU desta lista em 28/08/2026
# (`docs/decisoes/DECISAO-gestao-de-alunos.md` §2), e a mudanca e deliberada:
# ela e o "acesso pausado pelo mantenedor", e um pause que deixa a pessoa
# entrar do mesmo jeito seria decoracao.
#
# `reembolsada` FICA, e isso NAO e descuido: e a decisao do mantenedor de
# 24/08/2026 — "quem ja foi aluno mantem a voz na Caixa" —, tomada sobre
# REEMBOLSO. Pausar e outra intencao; duas intencoes diferentes nao podem ter o
# mesmo efeito.
#
# Custo da migracao, MEDIDO e nao suposto: nenhuma linha de codigo em
# `services/` jamais atribuiu `suspensa` ou `reembolsada` (so a declaracao
# delas aqui), entao nao ha linha em producao que mude de comportamento.
STATUS_QUE_VALEM = (STATUS_ATIVA, STATUS_REEMBOLSADA)
STATUS_DA_FILA = (STATUS_AGUARDANDO, STATUS_RECUSADA)
# [GESTAO] Quem NAO tem acesso. Existe como lista propria — e nao como "tudo que
# nao esta em STATUS_QUE_VALEM" — porque a pergunta "este status da acesso?" tem
# de ser respondida uma vez, a mao, para cada status que nascer. Ate 28/08/2026
# os dois baldes eram QUE_VALEM e DA_FILA e cobriam o vocabulario inteiro; com
# `suspensa` saindo do acesso sem entrar na fila, apareceu um terceiro caso, e o
# guarda `test_status_novo_nasce_sem_acesso` passou a medir ESTA divisao.
STATUS_SEM_ACESSO = (
    STATUS_AGUARDANDO,
    STATUS_RECUSADA,
    STATUS_SUSPENSA,
    STATUS_ENCERRADA,
)

# [PRONTUARIO] Os estados que provam que esta pessoa JA TEVE ACESSO alguma vez
# (29/08/2026, `DECISAO-a-ficha-nao-se-apaga.md`). E o que responde "esta pessoa
# ja foi aluna?" quando ela aparece de novo na fila.
#
# HOJE ele tem exatamente os mesmos quatro nomes de `STATUS_DE_GESTAO`, e a
# duplicacao e DELIBERADA: as duas listas respondem perguntas diferentes ("o
# painel administra?" e "ja teve acesso?") e nada garante que continuem
# coincidindo. No dia em que nascer um estado administravel que nunca deu acesso
# — um "pre-matriculado pago", por exemplo —, quem reusou a lista do vizinho
# passa a mentir sobre a historia de uma pessoa, em silencio. Lista propria custa
# quatro linhas; a mentira custa uma decisao errada do mantenedor.
#
# Lista de PERMISSAO, como as outras: estado novo nasce FORA, e alguem precisa
# decidir se ele conta como "ja foi aluno".
STATUS_QUE_JA_DERAM_ACESSO = (
    STATUS_ATIVA,
    STATUS_REEMBOLSADA,
    STATUS_SUSPENSA,
    STATUS_ENCERRADA,
)

# [GESTAO] Os estados que o painel administra — tudo que ja passou da fila. Eixo
# DIFERENTE do acesso: `ativa` da acesso e e administravel; `aguardando` nao da
# acesso e nao e administravel por aqui. Lista de PERMISSAO: estado novo nasce
# fora dela.
STATUS_DE_GESTAO = (
    STATUS_ATIVA,
    STATUS_SUSPENSA,
    STATUS_ENCERRADA,
    STATUS_REEMBOLSADA,
)


class Matricula(models.Model):
    """Uma linha por matrícula — e, desde 27/08/2026, também uma linha por pessoa
    que PEDIU entrada e ainda espera (`docs/decisoes/DECISAO-fila-de-liberacao.md`).

    A fila de liberação é a própria matrícula num status novo, não uma tabela
    paralela: duas tabelas responderiam à mesma pergunta ("quem é aluno?") e
    discordariam no primeiro caso de borda — alguém na fila que depois compra
    pelo site. É a lei anti-duplicação do `CLAUDE.md`.
    """

    # Apelidos das constantes do módulo (o `X = X` lê a global e grava no
    # namespace da classe): o resto do código diz `Matricula.STATUS_ATIVA`, e o
    # `class Meta` lá embaixo precisa das globais — corpo de classe aninhada não
    # enxerga os atributos da classe de fora. Uma fonte só para cada string.
    STATUS_ATIVA = STATUS_ATIVA
    STATUS_SUSPENSA = STATUS_SUSPENSA
    STATUS_REEMBOLSADA = STATUS_REEMBOLSADA
    STATUS_AGUARDANDO = STATUS_AGUARDANDO
    STATUS_RECUSADA = STATUS_RECUSADA
    STATUS_ENCERRADA = STATUS_ENCERRADA

    # [FILA] Os status que VALEM como "esta pessoa é aluna". É uma lista de
    # PERMISSÃO, não de exclusão, e a diferença é a única coisa que separa esta
    # decisão de um vazamento de acesso: com `.exclude(aguardando, recusada)`,
    # todo status inventado no futuro nasceria DANDO acesso; com a permissão,
    # nasce sem — e alguém precisa decidir explicitamente. Os três de baixo
    # significam todos "comprou" (o mantenedor decidiu em 24/08/2026 que
    # `reembolsada` continua entrando: quem já foi aluno mantém a voz).
    STATUS_QUE_VALEM = STATUS_QUE_VALEM
    # [FILA] Os status da fila de liberação: ninguém aqui tem acesso a nada.
    STATUS_DA_FILA = STATUS_DA_FILA
    # [GESTAO] Quem nao tem acesso, e o que o painel administra.
    STATUS_SEM_ACESSO = STATUS_SEM_ACESSO
    STATUS_DE_GESTAO = STATUS_DE_GESTAO
    # [PRONTUARIO] "esta pessoa ja teve acesso alguma vez?"
    STATUS_QUE_JA_DERAM_ACESSO = STATUS_QUE_JA_DERAM_ACESSO

    STATUS_CHOICES = [
        (STATUS_ATIVA, "ativa"),
        (STATUS_SUSPENSA, "suspensa"),
        (STATUS_REEMBOLSADA, "reembolsada"),
        (STATUS_AGUARDANDO, "aguardando"),
        (STATUS_RECUSADA, "recusada"),
        (STATUS_ENCERRADA, "encerrada"),
    ]

    # [FILA] Quem entra na fila não pagou nada, então não existe pedido: a linha
    # nasce com `pre:<uuid>`. O prefixo é o que marca a PROVENIÊNCIA da linha
    # para sempre — sobrevive à liberação (a linha vira `ativa` e continua
    # `pre:`), e é por ele que `POST /pre-matriculas/{id}/decisao` sabe que está
    # decidindo sobre uma linha da fila e não sobre uma matrícula paga.
    # Guarda de que pedido real não pode começar assim: services.matricular().
    PREFIXO_DA_FILA = "pre:"

    site_id = models.CharField(max_length=64)  # [INV-P5] guarda o site_id do evento
    order_id = models.CharField(
        max_length=128, unique=True
    )  # [INV-P5] chave de idempotência
    product_id = models.CharField(max_length=64, blank=True, default="")
    email = models.EmailField()
    name = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_ATIVA
    )
    enrolled_at = models.DateTimeField(auto_now_add=True)

    # [FILA] PII: o WhatsApp mora aqui e SÓ `GET /pre-matriculas` (a porta do
    # painel) o devolve — nunca `GET /alunos/{email}/matriculas`, nunca evento.
    # Decidido nominalmente pelo mantenedor em 27/08/2026, com a alternativa (a
    # Caixa também poder ler) oferecida e recusada: cada peça a mais que guarda
    # um telefone é mais um lugar de onde ele pode vazar (lei §5).
    whatsapp = models.CharField(max_length=32, blank=True, default="")
    # [FILA] Pistas de CONFERÊNCIA, não dados de cadastro — servem para o
    # mantenedor achar a pessoa na lista dele, e por isso são opcionais.
    comprou_em = models.DateField(null=True, blank=True)
    turma = models.CharField(max_length=120, blank=True, default="")
    # [FILA] A auditoria de quem liberou quem.
    decidido_em = models.DateTimeField(null=True, blank=True)
    decidido_por = models.CharField(max_length=128, blank=True, default="")
    motivo_recusa = models.TextField(blank=True, default="")

    class Meta:
        indexes = [models.Index(fields=["email"])]
        constraints = [
            # [FILA] Idempotência de `POST /pre-matriculas` com MECANISMO, não com
            # disciplina: sem esta constraint, duas requisições simultâneas da
            # mesma pessoa passariam as duas pelo "já existe?" e virariam duas
            # linhas na fila. Parcial de propósito — cobre só os status da fila,
            # para não impedir que a mesma pessoa tenha várias matrículas pagas
            # no mesmo site (que é o normal: um curso cada).
            models.UniqueConstraint(
                fields=["site_id", "email"],
                condition=models.Q(status__in=STATUS_DA_FILA),
                name="matricula_unica_na_fila_por_site_e_email",
            )
        ]
