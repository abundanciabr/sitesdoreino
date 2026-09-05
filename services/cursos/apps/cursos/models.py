"""O conteúdo do curso como DADO (o curso, os blocos, as aulas, as peças, as
pausas e os instrumentos) e, desde o degrau 1.8, AS PESSOAS E O PROGRESSO
(`Pessoa`, `Progresso`, `RegistroDePausa`).

Lei: `docs/decisoes/PLANO-CELULA-CURSOS.md` §4 (o modelo) e §9 (os invariantes
[INV-CUR-C1], [INV-CUR-C2] e os três da porta, [INV-CUR-P1..P3]). Degraus 1.2
(TAR-147) e 1.8 (TAR-154) da escada (§10). Molde de código:
`services/encomendas/apps/encomendas/models.py` e, para o espelho de pessoa,
`services/forum/apps/forum/models.py`.

Não há `Envio` nem `Laudo` aqui: são os degraus 2.1 e 2.2. As REGRAS do
progresso (que porta abre, e quando) não moram neste arquivo: moram em
`apps/cursos/progresso.py`, e é lá que o [INV-CUR-P2] é imposto.

O TEXTO DAS AULAS NUNCA ENTRA POR ARQUIVO
-----------------------------------------
Este repositório é público e o curso é obra não lançada do mantenedor
(`armadilhas/331`). Toda tabela daqui nasce VAZIA de texto: a migração cria o
esquema e não roda código ([INV-CUR-C2], guarda em
`tests/test_inv_c2_conteudo_so_pela_porta.py`), e o `semear_esqueleto` grava só
o que já está na lei (números, ordens, letras, os nomes canônicos dos
instrumentos). O pedido de cada aula, as 16 peças, as pausas, a escala e os
descritores de cada instrumento entram pela tela do Admin (degrau 1.5) pela porta
de máquina (degrau 1.3).

A FRONTEIRA DE SITE MORA NO `Curso`
------------------------------------
`site_id` (Lei 9 / [INV-P11]) fica no `Curso`, e só nele: bloco, aula, peça e
pausa pertencem a um curso, e é por ele que se pergunta de que site são. O
`Instrumento` é de plataforma inteira, de propósito: os 13 cartões são os mesmos
em toda escola.

UNICIDADE QUE ATRAVESSA CHAVE ESTRANGEIRA
-----------------------------------------
`Aula.curso` é redundante com `Aula.bloco.curso`, e existe porque
`Unique(curso, numero)` precisa de uma coluna LOCAL (`UniqueConstraint` não faz
`JOIN`). Coluna redundante pode mentir, e quando mente quem cai é a unicidade
que ela sustenta. Quem impede o par incoerente é a chave estrangeira COMPOSTA
`(bloco_id, curso_id) -> cursos_bloco (id, curso_id)`, escrita na migração
`0001`, que vale para o ORM, para `queryset.update()` e para `psql`
(`armadilhas/274`). Nunca um `save()`.
"""

from django.db import models

# Os 34 números de aula, na ordem em que o aluno os encontra: "E00" a "E32" e a
# bônus "EB". É o vocabulário fechado da coluna `Aula.numero`, e o banco recusa
# qualquer outro.
NUMEROS_DE_AULA = tuple(f"E{n:02d}" for n in range(33)) + ("EB",)

# As 12 letras de bloco, A a L. A ordem do bloco (1 a 12) e a letra dizem a mesma
# coisa por dois nomes, e o plano §4 pede as duas colunas.
LETRAS_DE_BLOCO = tuple("ABCDEFGHIJKL")


def id_do_site() -> models.CharField:
    """O campo de fronteira de site: texto opaco de 64, como todo id que atravessa
    fronteira nesta plataforma, nunca `UUIDField` (molde: `encomendas`)."""
    return models.CharField(max_length=64, db_index=True)


# ---------------------------------------------------------------------------
# 1. O CURSO
# ---------------------------------------------------------------------------


class Curso(models.Model):
    """Um curso por site no lançamento (plano §4). O slug do lançamento é `meshcraft`."""

    class Estado(models.TextChoices):
        RASCUNHO = "rascunho", "Rascunho"
        PUBLICADO = "publicado", "Publicado"

    site_id = id_do_site()
    slug = models.SlugField(max_length=64)
    nome = models.CharField(max_length=120)
    estado = models.CharField(
        max_length=10, choices=Estado.choices, default=Estado.RASCUNHO
    )
    versao = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site_id", "slug"], name="um_curso_por_slug_por_site"
            ),
            models.CheckConstraint(
                condition=models.Q(estado__in=["rascunho", "publicado"]),
                name="estado_de_curso_no_vocabulario_fechado",
            ),
            models.CheckConstraint(
                condition=models.Q(versao__gte=1), name="versao_de_curso_comeca_em_1"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.slug}@{self.site_id} v{self.versao} ({self.estado})"


# ---------------------------------------------------------------------------
# 2. O BLOCO: 12 por curso, A a L, em três partes
# ---------------------------------------------------------------------------


class Bloco(models.Model):
    """Um dos 12 blocos do curso. `nome` e `boss_titulo` nascem vazios: são
    conteúdo, e conteúdo entra pela tela (`armadilhas/331`)."""

    curso = models.ForeignKey(Curso, related_name="blocos", on_delete=models.PROTECT)
    ordem = models.PositiveSmallIntegerField()
    letra = models.CharField(max_length=1)
    parte = models.PositiveSmallIntegerField()
    nome = models.CharField(max_length=120, blank=True, default="")
    boss_titulo = models.CharField(max_length=120, blank=True, default="")

    class Meta:
        ordering = ["curso", "ordem"]
        constraints = [
            models.UniqueConstraint(
                fields=["curso", "ordem"], name="uma_ordem_por_bloco_por_curso"
            ),
            models.UniqueConstraint(
                fields=["curso", "letra"], name="uma_letra_por_bloco_por_curso"
            ),
            # O par referenciável pela chave estrangeira composta da `Aula`.
            # Parece redundante (o `id` já é único), e é essa aparência que faz
            # alguém apagá-lo um dia, derrubando a guarda sem que nada pareça
            # errado (`armadilhas/274`).
            models.UniqueConstraint(
                fields=["id", "curso"], name="uniq_bloco_id_com_curso"
            ),
            models.CheckConstraint(
                condition=models.Q(ordem__gte=1, ordem__lte=12),
                name="ordem_de_bloco_entre_1_e_12",
            ),
            models.CheckConstraint(
                condition=models.Q(letra__in=list(LETRAS_DE_BLOCO)),
                name="letra_de_bloco_entre_a_e_l",
            ),
            models.CheckConstraint(
                condition=models.Q(parte__in=[1, 2, 3]),
                name="parte_de_bloco_e_1_2_ou_3",
            ),
        ]

    def __str__(self) -> str:
        return f"Bloco {self.letra} (parte {self.parte})"


# ---------------------------------------------------------------------------
# 3. O INSTRUMENTO: os 13 cartões de avaliação, de plataforma inteira
# ---------------------------------------------------------------------------


class Instrumento(models.Model):
    """Um dos 13 instrumentos de avaliação (plano §4).

    Só `slug`, `nome_canonico` e `cartao` nascem semeados
    (`semear_esqueleto`). A escala, os mínimos, a seção do padrão e os
    descritores 5/3/1 entram pela tela. **Avaliação em andamento guarda a versão
    em que começou** (P04): mudar o instrumento é `versao` nova, e o laudo
    (degrau 2.2) grava `instrumento_versao`.
    """

    slug = models.SlugField(max_length=40, unique=True)
    nome_canonico = models.CharField(max_length=120)
    cartao = models.PositiveSmallIntegerField(unique=True)
    escala = models.JSONField(default=dict, blank=True)
    minimo_exercicio = models.CharField(max_length=200, blank=True, default="")
    minimo_contrato = models.CharField(max_length=200, blank=True, default="")
    secao_do_padrao = models.CharField(max_length=120, blank=True, default="")
    descritores = models.JSONField(default=dict, blank=True)
    versao = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["cartao"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(cartao__gte=1, cartao__lte=13),
                name="cartao_de_instrumento_entre_1_e_13",
            ),
            models.CheckConstraint(
                condition=models.Q(versao__gte=1),
                name="versao_de_instrumento_comeca_em_1",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.cartao}. {self.nome_canonico}"


# ---------------------------------------------------------------------------
# 4. A AULA: a encomenda, com o pedido, o cliente e o checkpoint
# ---------------------------------------------------------------------------


class Aula(models.Model):
    """Uma encomenda do curso: "E00" a "E32" e a bônus "EB".

    `pedido`, `cliente`, `minimo`, `aceito_quando`, `quiz` e `video_url` nascem
    vazios e entram pela tela. `aceito_quando` é a lista de critérios que vira o
    formulário do checkpoint; `quiz` é a lista de `{pergunta, resposta_modelo}`.
    """

    class Estado(models.TextChoices):
        RASCUNHO = "rascunho", "Rascunho"
        PUBLICADA = "publicada", "Publicada"

    curso = models.ForeignKey(Curso, related_name="aulas", on_delete=models.PROTECT)
    bloco = models.ForeignKey(Bloco, related_name="aulas", on_delete=models.PROTECT)
    ordem = models.PositiveSmallIntegerField()
    numero = models.CharField(max_length=3)
    titulo_exibido = models.CharField(max_length=120)
    pedido = models.TextField(blank=True, default="")
    cliente = models.CharField(max_length=120, blank=True, default="")
    instrumento = models.ForeignKey(
        Instrumento,
        related_name="aulas",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    minimo = models.CharField(max_length=200, blank=True, default="")
    aceito_quando = models.JSONField(default=list, blank=True)
    quiz = models.JSONField(default=list, blank=True)
    video_url = models.URLField(max_length=500, blank=True, default="")
    e_boss = models.BooleanField(default=False)
    banca_nivel = models.PositiveSmallIntegerField(null=True, blank=True)
    estado = models.CharField(
        max_length=10, choices=Estado.choices, default=Estado.RASCUNHO
    )
    versao = models.PositiveIntegerField(default=1)
    publicada_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["curso", "ordem"]
        constraints = [
            models.UniqueConstraint(
                fields=["curso", "ordem"], name="uma_ordem_por_aula_por_curso"
            ),
            models.UniqueConstraint(
                fields=["curso", "numero"], name="um_numero_por_aula_por_curso"
            ),
            models.CheckConstraint(
                condition=models.Q(numero__in=list(NUMEROS_DE_AULA)),
                name="numero_de_aula_no_vocabulario_fechado",
            ),
            models.CheckConstraint(
                condition=models.Q(banca_nivel__isnull=True)
                | models.Q(banca_nivel__in=[1, 2, 3]),
                name="banca_nivel_e_1_2_3_ou_nulo",
            ),
            models.CheckConstraint(
                condition=models.Q(estado__in=["rascunho", "publicada"]),
                name="estado_de_aula_no_vocabulario_fechado",
            ),
            models.CheckConstraint(
                condition=models.Q(versao__gte=1), name="versao_de_aula_comeca_em_1"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.numero} {self.titulo_exibido}"


# ---------------------------------------------------------------------------
# 5. A PEÇA: as 16 da anatomia, na ordem canônica, mais duas internas
# ---------------------------------------------------------------------------


class TipoDePeca(models.TextChoices):
    """As 16 peças da anatomia, declaradas NA ORDEM CANÔNICA, e as duas internas.

    Mora no módulo, e não dentro de `Peca`, porque o corpo de uma `class Meta`
    aninhada não enxerga os nomes da classe que a contém, e a restrição do
    banco precisa deste vocabulário. `Peca.Tipo` é este mesmo objeto.
    """

    PEDIDO = "pedido", "O pedido"
    EM_JOGO = "em_jogo", "O que está em jogo"
    VOCE_VAI_CONSEGUIR = "voce_vai_conseguir", "Você vai conseguir"
    RECALL = "recall", "Recall"
    PAR_DE_COMPARACAO = "par_de_comparacao", "Par de comparação"
    ERRO_PRODUTIVO = "erro_produtivo", "Erro produtivo"
    EU_FACO = "eu_faco", "Eu faço"
    NOS_FAZEMOS = "nos_fazemos", "Nós fazemos"
    VOCE_FAZ = "voce_faz", "Você faz"
    DRILLS = "drills", "Drills"
    ERROS_CLASSICOS = "erros_classicos", "Erros clássicos"
    REGRA_DO_PADRAO = "regra_do_padrao", "Regra do padrão"
    CRITICA_DE_ATELIER = "critica_de_atelier", "Crítica de ateliê"
    CHECKPOINT = "checkpoint", "Checkpoint"
    PAGINA_DO_PORTFOLIO = "pagina_do_portfolio", "Página do portfólio"
    DICIONARIO_CARTAO_RESPOSTAS = (
        "dicionario_cartao_respostas",
        "Dicionário, cartão e respostas",
    )
    ROTEIRO = "roteiro", "Roteiro da aula (interno)"
    GUIA_DO_MENTOR = "guia_do_mentor", "Guia do mentor (interno)"


class Peca(models.Model):
    """Uma peça de uma aula, em Markdown (renderizado por `documentos.para_html`).

    `ORDEM_CANONICA` é a ordem em que a tela mostra as 16 peças ao aluno e em
    que o verificador (`checkLesson`, degrau 1.6) confere se estão todas. Mora
    aqui, como tupla, para a tela e o verificador lerem dela e nunca de uma
    segunda lista. `TIPOS_INTERNOS` o aluno nunca vê.
    """

    Tipo = TipoDePeca

    ORDEM_CANONICA: tuple[str, ...] = (
        Tipo.PEDIDO,
        Tipo.EM_JOGO,
        Tipo.VOCE_VAI_CONSEGUIR,
        Tipo.RECALL,
        Tipo.PAR_DE_COMPARACAO,
        Tipo.ERRO_PRODUTIVO,
        Tipo.EU_FACO,
        Tipo.NOS_FAZEMOS,
        Tipo.VOCE_FAZ,
        Tipo.DRILLS,
        Tipo.ERROS_CLASSICOS,
        Tipo.REGRA_DO_PADRAO,
        Tipo.CRITICA_DE_ATELIER,
        Tipo.CHECKPOINT,
        Tipo.PAGINA_DO_PORTFOLIO,
        Tipo.DICIONARIO_CARTAO_RESPOSTAS,
    )
    TIPOS_INTERNOS: tuple[str, ...] = (Tipo.ROTEIRO, Tipo.GUIA_DO_MENTOR)

    aula = models.ForeignKey(Aula, related_name="pecas", on_delete=models.PROTECT)
    tipo = models.CharField(max_length=30, choices=Tipo.choices)
    texto = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["aula", "id"]
        verbose_name = "peça"
        verbose_name_plural = "peças"
        constraints = [
            models.UniqueConstraint(
                fields=["aula", "tipo"], name="uma_peca_por_tipo_por_aula"
            ),
            models.CheckConstraint(
                condition=models.Q(tipo__in=TipoDePeca.values),
                name="tipo_de_peca_no_vocabulario_fechado",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.aula_id}: {self.tipo}"


# ---------------------------------------------------------------------------
# 6. A PAUSA: o vídeo para, o aluno registra, e só então o checkpoint abre
# ---------------------------------------------------------------------------


class Pausa(models.Model):
    """Uma pausa do vídeo de uma aula, no segundo `segundo`.

    `pede` é o que o aluno registra; `campos` (JSON) são os mínimos do registro.
    O formulário do checkpoint fica fechado até todas as pausas da aula terem
    registro ([INV-CUR-P3], degrau 1.8).
    """

    class Tipo(models.TextChoices):
        ERRO_PRODUTIVO = "erro_produtivo", "Erro produtivo"
        FACA_AGORA = "faca_agora", "Faça agora"
        CERIMONIA = "cerimonia", "Cerimônia"

    aula = models.ForeignKey(Aula, related_name="pausas", on_delete=models.PROTECT)
    ordem = models.PositiveSmallIntegerField()
    segundo = models.PositiveIntegerField()
    tipo = models.CharField(max_length=14, choices=Tipo.choices)
    pede = models.TextField(blank=True, default="")
    campos = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["aula", "ordem"]
        constraints = [
            models.UniqueConstraint(
                fields=["aula", "ordem"], name="uma_ordem_por_pausa_por_aula"
            ),
            models.CheckConstraint(
                condition=models.Q(
                    tipo__in=["erro_produtivo", "faca_agora", "cerimonia"]
                ),
                name="tipo_de_pausa_no_vocabulario_fechado",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.aula_id} pausa {self.ordem} aos {self.segundo}s ({self.tipo})"


# ---------------------------------------------------------------------------
# 7. A PESSOA: espelho mínimo de quem a `identidade` reconheceu
# ---------------------------------------------------------------------------


class Pessoa(models.Model):
    """Quem já abriu a sala de aula, pelo id OPACO da plataforma.

    **Nunca e-mail** ([INV-CUR-S1]). A matrícula se pergunta à `alunos` a cada
    requisição, pelo e-mail que a `identidade` devolve e que esta célula usa e
    descarta na hora (`apps/core/sessao.py`); guardá-lo aqui seria o mesmo fato
    em dois lugares, e um deles apodreceria. `nome_exibido` é o único dado de
    exibição, e a tela só mostra o da própria pessoa ([INV-CUR-P1]).
    """

    id_da_plataforma = models.CharField(max_length=64, primary_key=True)
    nome_exibido = models.CharField(max_length=120, blank=True, default="")

    def __str__(self) -> str:
        return self.id_da_plataforma


# ---------------------------------------------------------------------------
# 8. O PROGRESSO: que porta esta pessoa tem aberta, e em que estado
# ---------------------------------------------------------------------------


class Progresso(models.Model):
    """A porta de UMA aula para UMA pessoa.

    Linha ausente é porta `trancada`: só se escreve quando algo acontece (a E00
    nasce `disponivel` na primeira visita; a aula N sai de `trancada` quando a
    N-1 conclui). `concluida` só entra por `progresso.concluir`, que EXIGE um
    laudo aberto ([INV-CUR-P2]); nenhuma tela nem porta grava esse valor.

    `cerimonia_pendente` e `laudo_lido` são os dois estados que a tentação
    poria em `request.session`, e que deslogariam a plataforma inteira
    (`armadilhas/143`, [INV-P12]). Moram aqui, no modelo.
    """

    class Estado(models.TextChoices):
        TRANCADA = "trancada", "Trancada"
        DISPONIVEL = "disponivel", "Disponível"
        EM_PRODUCAO = "em_producao", "Em produção"
        ENVIADA = "enviada", "Enviada"
        DEVOLVIDA = "devolvida", "Devolvida"
        CONCLUIDA = "concluida", "Concluída"

    pessoa = models.ForeignKey(
        Pessoa, related_name="progressos", on_delete=models.PROTECT
    )
    aula = models.ForeignKey(Aula, related_name="progressos", on_delete=models.PROTECT)
    estado = models.CharField(
        max_length=12, choices=Estado.choices, default=Estado.TRANCADA
    )
    autoavaliacao = models.JSONField(default=dict, blank=True)
    data_de_retorno = models.DateField(null=True, blank=True)
    concluida_em = models.DateTimeField(null=True, blank=True)
    cerimonia_pendente = models.BooleanField(default=False)
    laudo_lido = models.BooleanField(default=False)

    class Meta:
        ordering = ["pessoa", "aula"]
        constraints = [
            models.UniqueConstraint(
                fields=["pessoa", "aula"], name="um_progresso_por_pessoa_por_aula"
            ),
            models.CheckConstraint(
                condition=models.Q(
                    estado__in=[
                        "trancada",
                        "disponivel",
                        "em_producao",
                        "enviada",
                        "devolvida",
                        "concluida",
                    ]
                ),
                name="estado_de_progresso_no_vocabulario_fechado",
            ),
            # Concluída carrega a hora em que concluiu, e só ela carrega.
            models.CheckConstraint(
                condition=(
                    models.Q(estado="concluida", concluida_em__isnull=False)
                    | models.Q(concluida_em__isnull=True)
                    & ~models.Q(estado="concluida")
                ),
                name="concluida_em_so_quando_concluida",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.pessoa_id}: {self.aula_id} ({self.estado})"


# ---------------------------------------------------------------------------
# 9. O REGISTRO DE PAUSA: o vídeo parou, a pessoa escreveu
# ---------------------------------------------------------------------------


class RegistroDePausa(models.Model):
    """O que a pessoa registrou numa pausa do vídeo.

    `respostas` é `{campo: texto}`, um por item de `Pausa.campos`. Uma pausa,
    um registro, uma pessoa: registrar de novo não sobrescreve, e é isso que
    faz o [INV-CUR-P3] ("o checkpoint fica fechado até todas as pausas terem
    registro") ser contável em vez de adivinhado.
    """

    pessoa = models.ForeignKey(
        Pessoa, related_name="registros_de_pausa", on_delete=models.PROTECT
    )
    pausa = models.ForeignKey(Pausa, related_name="registros", on_delete=models.PROTECT)
    respostas = models.JSONField(default=dict, blank=True)
    registrado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["pessoa", "pausa"]
        constraints = [
            models.UniqueConstraint(
                fields=["pessoa", "pausa"], name="um_registro_por_pessoa_por_pausa"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.pessoa_id}: pausa {self.pausa_id}"
