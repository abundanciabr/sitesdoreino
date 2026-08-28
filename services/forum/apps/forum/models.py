"""O modelo de dados do fórum — a fundação, e a peça que decide a reversibilidade.

Lei: `docs/decisoes/DECISAO-forum-da-escola.md` §4. Análise:
`docs/consultorias/forum-da-escola/VEREDITO.md`.

**A forma é deliberadamente comum: área → tópico → mensagem.** Não é falta de
imaginação — é o seguro que mantém aberta a porta de migrar para o Discourse se
a escola crescer muito (lei §4.2). Migrar de um esquema de fórum normal é
caminho batido, com ferramenta de importação pronta; migrar de um formato
inventado aqui não é. Foi a recomendação em que os dois consultores externos
concordaram.
"""

from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models


class Pessoa(models.Model):
    """O espelho local de quem participa — nunca a fonte da verdade.

    Quem sabe quem é a pessoa é a célula `identidade`; quem sabe se ela é aluna
    é a célula `alunos`. Esta tabela guarda só o mínimo para o fórum conseguir
    dizer "quem escreveu isto" sem uma chamada de rede por mensagem exibida.

    O padrão é o mesmo da Caixa de Sugestões (`services/sugestoes`), e a razão
    de não guardar mais que isto é a Lei 2: dado de outra célula copiado sem
    necessidade vira uma segunda verdade que ninguém mantém.
    """

    # O id OPACO da plataforma, como a `identidade` o devolve. É a chave de
    # ligação com o resto do site — nunca o e-mail, que muda de dono.
    id_da_plataforma = models.CharField(max_length=64, primary_key=True)
    # Guardado porque a `alunos` responde por E-MAIL (`getStudentStanding`), e
    # sem ele o fórum não conseguiria perguntar se a pessoa é aluna.
    email = models.EmailField(unique=True)
    nome_exibido = models.CharField(max_length=120, blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)
    vista_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "pessoas"

    def __str__(self) -> str:
        return self.nome_exibido or self.email


class Area(models.Model):
    """Uma seção do fórum. É AQUI que mora a regra de quem entra e quem escreve.

    **As permissões são DADO, não código** — recomendação do consultor 1, e a
    razão é o produto: o mantenedor decidiu áreas MISTAS (lei §5), umas
    públicas e indexáveis pelo Google, outras trancadas por curso ou turma.
    Escrever isso em `if` espalhado por views transformaria cada área nova numa
    entrega de código; como dado, uma área nova é uma linha.

    **Reconhecer não é autorizar:** a `identidade` diz quem é a pessoa; QUEM
    PODE é decidido aqui, fail-closed, conferindo estes campos
    (`DECISAO-forum-da-escola.md` §3).
    """

    class Visibilidade(models.TextChoices):
        # Visitante lê e o Google indexa. É a aposta de crescimento da escola:
        # dúvida respondida é porta de entrada gratuita e permanente.
        PUBLICA = "publica", "Pública — qualquer um lê"
        # Só quem tem matrícula válida (a `alunos` é quem responde isso).
        ALUNOS = "alunos", "Alunos — só quem comprou"
        # Trancada num curso específico, via `curso_id`.
        TURMA = "turma", "Turma — só quem está no curso"

    class QuemEscreve(models.TextChoices):
        # O caso padrão, e o mais seguro: escrever exige matrícula. Numa área
        # PÚBLICA isso é "visitante lê, aluno escreve" — o desenho que não abre
        # porta para spam.
        ALUNO = "aluno", "Alunos e acima"
        # Área de avisos: a escola fala, a turma lê.
        EQUIPE = "equipe", "Só professor ou administrador"
        # Existe para o dia em que o mantenedor decidir abrir — e está
        # documentado como o caso que EXIGE defesa anti-spam de verdade
        # (`DECISAO-forum-da-escola.md` §6.3, pergunta em aberto).
        CADASTRADO = "cadastrado", "Qualquer pessoa com login"

    slug = models.SlugField(max_length=60, unique=True)
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)
    ordem = models.PositiveIntegerField(default=0)
    ativa = models.BooleanField(default=True)

    visibilidade = models.CharField(
        max_length=10, choices=Visibilidade.choices, default=Visibilidade.ALUNOS
    )
    quem_escreve = models.CharField(
        max_length=12, choices=QuemEscreve.choices, default=QuemEscreve.ALUNO
    )
    # Opaco de propósito: o fórum não é dono do catálogo de cursos. Só faz
    # sentido com `visibilidade = TURMA`.
    curso_id = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        ordering = ["ordem", "nome"]
        constraints = [
            # Fail-closed por construção: área de turma SEM curso seria uma
            # área que ninguém consegue avaliar — e a tentação, na hora do
            # bug, é liberar. O banco recusa antes disso.
            models.CheckConstraint(
                condition=~models.Q(visibilidade="turma") | ~models.Q(curso_id=""),
                name="area_de_turma_exige_curso",
            ),
        ]

    def __str__(self) -> str:
        return self.nome


class Topico(models.Model):
    """Uma conversa. O que o Discourse chama de `topic`, e de propósito."""

    class Estado(models.TextChoices):
        PUBLICADO = "publicado", "Publicado"
        # A fila de aprovação (lei §4.6). Nasce como estado porque moderação
        # depois é moderação que não acontece.
        ESPERANDO = "esperando", "Esperando aprovação"
        # Some da lista, mas o histórico fica. Apagar de verdade é o que
        # impede reconstruir o que houve numa denúncia.
        REMOVIDO = "removido", "Removido pela moderação"

    area = models.ForeignKey(Area, related_name="topicos", on_delete=models.PROTECT)
    autor = models.ForeignKey(Pessoa, related_name="topicos", on_delete=models.PROTECT)
    titulo = models.CharField(max_length=180)
    criado_em = models.DateTimeField(auto_now_add=True)

    # A marca-d'água de leitura compara com ISTO, não com a data de cada
    # mensagem (ver `MarcaDeLeitura`). Atualizada a cada resposta nova.
    ultima_atividade_em = models.DateTimeField(auto_now_add=True, db_index=True)

    estado = models.CharField(
        max_length=10, choices=Estado.choices, default=Estado.PUBLICADO
    )
    fixado = models.BooleanField(default=False)
    trancado = models.BooleanField(default=False)

    # O selo de "resolvido" (lei §5): o professor — ou o próprio autor — aponta
    # a mensagem que respondeu a dúvida. É o que transforma o fórum em
    # patrimônio em vez de arquivo morto.
    resposta_aceita = models.OneToOneField(
        "Mensagem",
        null=True,
        blank=True,
        related_name="aceita_em",
        on_delete=models.SET_NULL,
    )

    class Meta:
        ordering = ["-fixado", "-ultima_atividade_em"]
        indexes = [
            # A consulta da tela de área: os tópicos publicados, os fixados no
            # topo, do mais recente para o mais antigo.
            models.Index(fields=["area", "estado", "-fixado", "-ultima_atividade_em"]),
        ]

    def __str__(self) -> str:
        return self.titulo


class Mensagem(models.Model):
    """Uma fala dentro de um tópico — a primeira é o corpo da pergunta."""

    topico = models.ForeignKey(
        Topico, related_name="mensagens", on_delete=models.CASCADE
    )
    autor = models.ForeignKey(
        Pessoa, related_name="mensagens", on_delete=models.PROTECT
    )
    texto = models.TextField()
    criado_em = models.DateTimeField(auto_now_add=True)
    editado_em = models.DateTimeField(null=True, blank=True)

    # Remoção é SUAVE: a linha continua, some da tela. Apagar de verdade
    # destruiria o contexto de uma denúncia justamente quando ele importa —
    # e o público desta escola é majoritariamente menor de idade.
    removida_em = models.DateTimeField(null=True, blank=True)

    # A BUSCA (lei §4.4). Coluna materializada e indexada, calculada na
    # ESCRITA — nunca na consulta. Calcular no `WHERE` funciona lindamente com
    # 500 mensagens e trava com 50 mil, e só se descobre em produção. É o único
    # item que é caro de instalar depois: vira migração na maior tabela do
    # sistema. Por isso nasce agora, com o resto vazio ao redor.
    busca = SearchVectorField(null=True, editable=False)

    class Meta:
        ordering = ["criado_em"]
        indexes = [
            GinIndex(fields=["busca"], name="forum_mensagem_busca_gin"),
            models.Index(fields=["topico", "criado_em"]),
        ]

    def __str__(self) -> str:
        return f"#{self.pk} em {self.topico_id}"


class MarcaDeLeitura(models.Model):
    """ "Li até aqui" — UMA linha por pessoa por área. Nunca por mensagem.

    **Este é o achado mais afiado da rodada de consultoria** (lei §4.3), e o
    motivo é aritmético: guardar uma linha por pessoa por mensagem lida faz,
    com 200 alunos e 20 mil mensagens, milhões de linhas para responder uma
    pergunta boba ("tem coisa nova?"). A lista de tópicos fica lenta e o
    conserto, depois, é uma migração na maior tabela do sistema.

    O desenho é o do Discourse: uma marca-d'água por área — tudo cuja última
    atividade seja anterior a `lido_ate` está lido — mais a pequena tabela de
    exceções (`TopicoLido`) para o que a pessoa leu DEPOIS da marca. Quando a
    marca avança, as exceções que ficaram para trás podem ser podadas.
    """

    pessoa = models.ForeignKey(Pessoa, related_name="marcas", on_delete=models.CASCADE)
    area = models.ForeignKey(Area, related_name="marcas", on_delete=models.CASCADE)
    lido_ate = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["pessoa", "area"], name="uma_marca_por_pessoa_por_area"
            ),
        ]


class TopicoLido(models.Model):
    """As exceções da marca-d'água: tópicos lidos DEPOIS dela.

    Pequena por construção — só vive entre a marca e o presente. É o que
    permite a marca ser uma linha só sem mentir sobre tópicos avulsos.
    """

    pessoa = models.ForeignKey(Pessoa, related_name="lidos", on_delete=models.CASCADE)
    topico = models.ForeignKey(Topico, related_name="lidos", on_delete=models.CASCADE)
    lido_em = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["pessoa", "topico"], name="uma_leitura_por_pessoa_por_topico"
            ),
        ]
