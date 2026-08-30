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
from django.contrib.postgres.search import SearchVector, SearchVectorField
from django.db import models

# ---------------------------------------------------------------------------
# A VOZ DA ESCOLA — como a instituição assina o que publica (TAR-020, 30/08/2026)
# ---------------------------------------------------------------------------
# O mandato do mantenedor, com as palavras dele: o fórum é semeado com as
# dúvidas reais dos alunos, já respondidas, e essas mensagens saem EM NOME DA
# ESCOLA. Nenhuma pode fingir ser de aluno, nem com nome inventado, nem com
# conta de mentira, nem com um rótulo genérico que sugira uma pessoa.
#
# Até aqui o modelo não sabia dizer isso: `autor` era obrigatório em tópico e em
# mensagem, então a única forma de a escola publicar seria criar uma `Pessoa` de
# mentira, ou seja, exatamente o proibido. A capacidade nasce agora.
NOME_DA_ESCOLA = "Meshcraft Academy"

# O rótulo que a tela mostra quando quem escreveu não pôs nome de exibição. Ele
# sugere UMA PESSOA, e por isso nunca pode sobrar para uma fala da instituição:
# seria o avatar genérico que o mantenedor recusou, escrito em palavra.
ALGUEM = "alguém"


def assinatura_de(autor, publicado_pela_escola: bool) -> str:
    """Quem a tela diz que falou. Uma regra só, para todas as telas.

    Se esta conta morasse no template, cada página resolveria a autoria por
    conta própria, e a primeira que esquecesse mostraria `alguém` no lugar do
    nome da escola. Duas expressões da mesma regra divergem no primeiro dia em
    que alguém mexer numa delas.
    """
    if publicado_pela_escola:
        return NOME_DA_ESCOLA
    return (autor.nome_exibido if autor else "") or ALGUEM


def _fala_de_pessoa_ou_da_escola(nome: str) -> models.CheckConstraint:
    """A restrição que impede as DUAS mentiras possíveis sobre quem falou.

    Ou existe uma pessoa por trás da fala, ou a fala é declaradamente da
    instituição. Nunca as duas juntas, nunca nenhuma das duas.

    **Por que no BANCO, e não só numa regra de aplicação.** É a mesma razão de
    `pagina_publica_so_a_escola_fala`, mais abaixo: regra que existe só em
    código é promessa. Bastaria um `update()` numa tela de administração futura,
    ou uma linha editada à mão no `psql` numa madrugada de incidente, para uma
    mensagem da escola ganhar autor de aluno (ou o contrário) sem ninguém saber.

    **E o campo explícito não é redundante com `autor IS NULL`.** Ele é o que
    torna a declaração DELIBERADA: sem ele a leitura seria "sem autor, logo é da
    escola", e um caminho de código que esquecesse o autor publicaria em nome da
    instituição por acidente. Com ele, o esquecimento é recusado pelo banco, que
    é o lado seguro do erro.
    """
    return models.CheckConstraint(
        condition=(
            models.Q(autor__isnull=False, publicado_pela_escola=False)
            | models.Q(autor__isnull=True, publicado_pela_escola=True)
        ),
        name=nome,
    )


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
        # Escrever exige matrícula. Numa área trancada isso é "aluno lê, aluno
        # escreve"; numa área PÚBLICA esta combinação passou a ser PROIBIDA em
        # 30/08/2026 — ver a restrição `pagina_publica_so_a_escola_fala`.
        ALUNO = "aluno", "Alunos e acima"
        # A escola fala, a turma lê. É o ÚNICO valor que uma área pública
        # aceita, e é por isso que virou o default (abaixo).
        EQUIPE = "equipe", "Só professor ou administrador"
        # Existe para o dia em que o mantenedor decidir abrir uma área
        # trancada a quem só tem cadastro. **Numa área pública ele é
        # impossível** — a restrição do banco recusa.
        CADASTRADO = "cadastrado", "Qualquer pessoa com login"

    slug = models.SlugField(max_length=60, unique=True)
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)
    ordem = models.PositiveIntegerField(default=0)
    ativa = models.BooleanField(default=True)

    visibilidade = models.CharField(
        max_length=10, choices=Visibilidade.choices, default=Visibilidade.ALUNOS
    )
    # O DEFAULT É O LADO FECHADO, e mudou em 30/08/2026: onde ninguém disse
    # quem escreve, quem escreve é a ESCOLA. Antes o default era `ALUNO`, e uma
    # área nascida sem o campo preenchido já vinha com a porta mais aberta que
    # a intenção de quem a criou — o oposto de fail-closed.
    quem_escreve = models.CharField(
        max_length=12, choices=QuemEscreve.choices, default=QuemEscreve.EQUIPE
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
            # ---------------------------------------------------------------
            # EM PÁGINA PÚBLICA, SÓ A ESCOLA FALA (mandato do mantenedor em
            # 30/08/2026 — registro `20260830-021`).
            # ---------------------------------------------------------------
            # A escola é de Roblox: o público é majoritariamente criança e
            # adolescente. A decisão dele, nas palavras do livro, foi *"menor
            # de idade não escreve em página pública"* — o que é aberto ao
            # Google e a estranhos passa a ser só a escola falando, e onde
            # aluno escreve, exige login. O preço, aceito por ele na mesma
            # escolha: o fórum sai do alcance de buscador.
            #
            # **Por que no BANCO, e não só numa função de permissão.** A
            # permissão também confere (`apps/core/permissoes.py`), e ela é o
            # que decide cada requisição. Mas uma regra que existe só em código
            # é uma promessa: basta um `Area.objects.update(visibilidade=...)`
            # numa tela de administração futura, ou uma linha editada à mão no
            # `psql` numa madrugada de incidente, para a combinação proibida
            # existir — e ninguém saber. Aqui ela não chega a existir: o
            # PostgreSQL recusa o INSERT e o UPDATE. É a `RETROSPECTIVA-FASE-D`
            # §2 (garantia declarada sem mecanismo apodrece) aplicada à decisão
            # que protege menores.
            models.CheckConstraint(
                condition=~models.Q(visibilidade="publica")
                | models.Q(quem_escreve="equipe"),
                name="pagina_publica_so_a_escola_fala",
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
    # NULO quando quem abriu a conversa foi a própria escola. Ver
    # `_fala_de_pessoa_ou_da_escola`: o nulo sozinho nunca basta.
    autor = models.ForeignKey(
        Pessoa, related_name="topicos", on_delete=models.PROTECT, null=True, blank=True
    )
    publicado_pela_escola = models.BooleanField(default=False)
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
        constraints = [_fala_de_pessoa_ou_da_escola("topico_de_pessoa_ou_da_escola")]

    @property
    def assinatura(self) -> str:
        """Quem a tela diz que abriu esta conversa."""
        return assinatura_de(self.autor, self.publicado_pela_escola)

    def __str__(self) -> str:
        return self.titulo


class Mensagem(models.Model):
    """Uma fala dentro de um tópico — a primeira é o corpo da pergunta."""

    topico = models.ForeignKey(
        Topico, related_name="mensagens", on_delete=models.CASCADE
    )
    # NULO quando quem falou foi a própria escola (ver
    # `_fala_de_pessoa_ou_da_escola`, no topo do arquivo).
    autor = models.ForeignKey(
        Pessoa,
        related_name="mensagens",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    publicado_pela_escola = models.BooleanField(default=False)
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
        constraints = [_fala_de_pessoa_ou_da_escola("mensagem_de_pessoa_ou_da_escola")]

    @property
    def assinatura(self) -> str:
        """Quem a tela diz que escreveu esta fala."""
        return assinatura_de(self.autor, self.publicado_pela_escola)

    def indexar_para_busca(self) -> None:
        """Preenche a coluna de BUSCA desta mensagem, na ESCRITA.

        Mora AQUI, e não em quem escreve, porque quem escreve são dois caminhos
        diferentes (a tela do aluno e a semeadura da escola) e um terceiro
        aparecerá. A cópia que ficasse para trás numa mudança de configuração de
        idioma deixaria um lote inteiro de mensagens invisível para a busca do
        site, e o defeito só apareceria quando alguém procurasse.

        `SearchVector` é expressão de BANCO: não há como atribuí-la a um atributo
        Python antes do `save()`. O caminho é um `update()` sobre a linha que
        acabou de nascer, uma ida a mais ao banco por mensagem escrita.
        """
        Mensagem.objects.filter(pk=self.pk).update(
            busca=SearchVector("texto", config="portuguese")
        )

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
