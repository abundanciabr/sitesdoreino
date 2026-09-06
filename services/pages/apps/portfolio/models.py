"""As tabelas do portfólio do aluno, e a fronteira que elas defendem.

Lei: `docs/changespecs/CS-PAGES-0001.md` (critérios AC-02, AC-06, AC-07 e
AC-13), `docs/decisoes/PLANO-PORTFOLIO-DO-ALUNO.md` (§4 a casa, §5 a escada,
§7 o que ninguém pode inventar) e `constituicoes/AGENTS.pages.md` (os
invariantes desta célula). Este é o degrau 02 da escada.

Cinco delas são DO ALUNO (o portfólio, a peça, o item de conferência, o estado
e o pedido de conferência do degrau 11) e duas são o CATÁLOGO da escola, no fim
do arquivo. Este arquivo nasceu no degrau 02, com a fundação, e nela três coisas
que o resto pôde tratar como verdade:

1. **Nenhuma chave estrangeira sai do banco desta célula** (critério AC-02).
   O id do aluno e o id do site são texto OPACO: quem sabe quem é a pessoa é a
   `identidade`, quem sabe se ela tem matrícula é a `alunos`, e o banco daqui
   não enxerga o das outras (Lei 2, Muralha 2).
2. **A marcação da lista de conferência mora no BANCO, por aluno.** Nunca em
   `request.session` (o [INV-P12] proíbe, e `armadilhas/143` conta o preço) e
   nunca no navegador: o AC-06 exige que a marcação atravesse APARELHOS, e
   sessão não atravessa.
3. **O isolamento por aluno é uma porta só, e ela é o `do_aluno` destes
   gerenciadores** (critério AC-07). Toda tela dos degraus 07, 08, 10, 11 e 13
   lê por ele. Guarda: `tests/test_isolamento_por_aluno.py`, provado por mutação.

POR QUE NENHUMA TABELA FILHA GUARDA `site_id` NEM `aluno_id`
------------------------------------------------------------
A fronteira de site (Lei 9 / [INV-P11]) e a fronteira de aluno moram no
`Portfolio`, e SÓ nele. `Peca`, `ItemDeConferencia`, `EstadoDoAluno` e
`PedidoDeConferencia` chegam às duas pela chave estrangeira local.

A alternativa era copiar as colunas para cada filha, e ela tem preço conhecido:
coluna denormalizada pode MENTIR, e quando mente derruba justamente a trava que
existia para impedir o vazamento. Curar isso exigiria chave estrangeira composta
escrita em `RunSQL`, porque o Django não a sabe escrever (`armadilhas/274`).
Aqui a doença nem nasce: não existe segunda cópia para divergir.

O QUE ESTE ARQUIVO NÃO GUARDA, DE PROPÓSITO
-------------------------------------------
- **Nota, estrela, ranking ou voto** em portfólio ou em peça. Proibido por
  escrito (plano §7), e a ausência é decisão, não esquecimento.
- **Arquivo de imagem.** A foto entra por LINK colado, decisão do mantenedor de
  01/09/2026 (plano §6.2). O campo de uma imagem hospedada por nós cabe no mesmo
  modelo no dia em que ele pedir o degrau 09, e é isso que mantém a porta de
  volta barata sem construí-la agora.
- **O SEMÁFORO em si.** As três colunas de resposta do aluno moram aqui (degrau
  10), mas a cor e a lista do que falta são CALCULADAS a cada abertura de tela,
  em `apps/portfolio/semaforo.py`. Guardar a cor numa coluna criaria uma segunda
  verdade capaz de discordar das respostas que a produziram, no primeiro dia em
  que a escola corrigisse uma regra.
- **E-mail, telefone e nome do aluno.** A página pública não os expõe (AC-14), e
  a forma mais simples de nunca expor um dado é não o guardar.
- **O NOME das cinco etapas.** A lei fixa que são cinco (AC-06); quem escreve o
  texto delas é a escola, no editor de documentos do admin (degrau 16, plano
  §6.4). Nomear as etapas aqui seria inventar produto num PR que não tem como
  prová-lo, e o texto ficaria em duas casas.
"""

from django.db import models

# As cinco etapas do roteiro da Prancheta (AC-06). Guardamos o NÚMERO da etapa,
# não o nome: o número é lei desta obra, o nome é texto da escola e mora no
# editor de documentos (degrau 16). O banco recusa qualquer valor fora da faixa.
PRIMEIRA_ETAPA = 1
ULTIMA_ETAPA = 5


def id_da_plataforma() -> models.CharField:
    """Um id OPACO de outra célula: o aluno, o monitor que confere.

    Nunca chave estrangeira (a tabela é de outra célula, com outro banco e outro
    papel) e nunca e-mail (o e-mail muda de dono). Vazio significa "ainda não
    sei", e é por isso que ele é `blank=True, default=""` em vez de
    `null=True`: duas formas de "não sei" na mesma coluna é a origem de metade
    das consultas erradas.
    """
    return models.CharField(max_length=64, blank=True, default="")


class EstadoDoLink(models.TextChoices):
    """O que a escola sabe sobre o endereço de uma peça. Critérios AC-08 e AC-09.

    **Três respostas, e a terceira é a que costuma faltar.** Duas dizem o que a
    escola SABE; a terceira diz que ela não sabe. Misturar a terceira com a
    segunda seria acusar a obra do aluno de estar quebrada toda vez que a nossa
    própria rede tossisse, e quem decide o que fazer com cada uma é quem chama
    (`apps/portfolio/conferencia_do_link.py` explica a assimetria por extenso).

    Mora no MÓDULO, e não dentro de `Peca`, por uma razão de linguagem e não de
    gosto: o corpo de uma `class Meta` aninhada não enxerga os nomes do corpo da
    classe que a contém, e as duas restrições abaixo precisam destes valores.

    O rótulo é o que o aluno lê na tela, então ele sai em frase inteira e sem
    travessão (lei do `ci/travessao.py`).
    """

    RESPONDENDO = "respondendo", "O endereço abriu na última conferência"
    QUEBRADO = "quebrado", "O endereço parou de abrir"
    NAO_CONFERIDO = "nao_conferido", "A escola ainda não conseguiu conferir"


class TipoDeModelo(models.TextChoices):
    """De que tipo é a peça. As palavras são da PROFESSORA, não invenção daqui.

    Ela escreveu a lista na etapa 1 do roteiro (`roteiro_da_escola.py`): *"armas,
    carros, cabelos, acessórios, animais e outros"*. Este é o mesmo conjunto,
    numa forma que o banco sabe contar, porque prosa não se conta.

    **Vazio significa "o aluno ainda não respondeu"**, e é por isso que a coluna
    é `blank=True, default=""` em vez de `null=True`: duas formas de "não sei"
    na mesma coluna é a origem de metade das consultas erradas, e esta casa já
    tomou essa decisão uma vez em `id_da_plataforma`.
    """

    ARMAS = "armas", "Armas"
    CARROS = "carros", "Carros"
    CABELOS = "cabelos", "Cabelos"
    ACESSORIOS = "acessorios", "Acessórios"
    ANIMAIS = "animais", "Animais"
    OUTRO = "outro", "Outro tipo que o curso ensina"


class Acabamento(models.TextChoices):
    """High poly ou variação mais simples. Regra 3 da professora, nas palavras dela.

    *"O ideal é que sejam high poly... Você também pode criar algumas variações
    mais simples"*. São essas duas respostas, e não uma escala: escala em peça de
    aluno viraria nota, e nota é proibida por escrito (plano §7).
    """

    HIGH_POLY = "high_poly", "High poly, mais detalhada"
    MAIS_SIMPLES = "mais_simples", "Uma variação mais simples"


class ParecidaComAAula(models.TextChoices):
    """A peça se parece com o modelo feito na aula? Regra 4 da professora.

    **É o ALUNO quem responde, e a máquina não opina.** Nada aqui tenta descobrir
    de onde a peça veio nem se parece com coisa nenhuma: detecção desse tipo é
    proibida na obra (plano §7), e a única fonte desta coluna é a resposta que a
    pessoa deu na tela.

    Duas respostas escritas, e não um `BooleanField(null=True)`, pelo mesmo
    motivo das duas de cima: com o booleano, "ainda não respondi" e "não se
    parece" ficariam a um engano de distância uma da outra.
    """

    NAO = "nao", "Não se parece com o modelo da aula"
    SIM = "sim", "Se parece com o modelo da aula"


class PortfolioQuerySet(models.QuerySet):
    """A porta de leitura por aluno. É esta linha que o AC-07 mede."""

    def do_aluno(self, *, site_id: str, aluno_id: str) -> "PortfolioQuerySet":
        return self.filter(site_id=site_id, aluno_id=aluno_id)


class DoPortfolioQuerySet(models.QuerySet):
    """O mesmo isolamento para quem pendura no portfólio.

    A travessia é pela chave estrangeira, e não por uma cópia do id do aluno:
    filha nenhuma guarda `aluno_id`, então não há como a resposta discordar do
    dono da linha.
    """

    def do_aluno(self, *, site_id: str, aluno_id: str) -> "DoPortfolioQuerySet":
        return self.filter(portfolio__site_id=site_id, portfolio__aluno_id=aluno_id)


class Portfolio(models.Model):
    """Um por aluno por site: a identidade do portfólio e o estado da vitrine.

    **A vitrine é opt-in e nasce DESLIGADA** (`vitrine_publicada=False`), e o
    padrão é a lei: `/estudio/<apelido>` só existe se o aluno ligar, e
    despublicar tira a página do ar imediatamente (AC-13). Por isso o banco não
    admite os meios-termos que uma tela distraída produziria: publicada sem
    apelido (endereço que não existe) e publicada sem data (selo e vitrine sem
    saber desde quando).

    **O apelido é o endereço que o aluno manda ao cliente no chat**, então ele
    obedece à forma de endereço web e é único DENTRO do site: dois sites podem
    ter o mesmo apelido sem se ver, que é a Lei 9 em uma linha.
    """

    site_id = models.CharField(max_length=64, db_index=True)
    aluno_id = models.CharField(max_length=64, db_index=True)

    apelido = models.CharField(max_length=48, blank=True, default="")
    vitrine_publicada = models.BooleanField(default=False)
    publicada_em = models.DateTimeField(null=True, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = PortfolioQuerySet.as_manager()

    class Meta:
        verbose_name = "portfólio"
        verbose_name_plural = "portfólios"
        constraints = [
            models.UniqueConstraint(
                fields=["site_id", "aluno_id"],
                name="um_portfolio_por_aluno_por_site",
            ),
            # Único por SITE, e só quando existe: o apelido vazio é o estado
            # normal de quem nunca ligou a vitrine, e uma unicidade sem a
            # condição deixaria o segundo aluno sem apelido sem conseguir
            # nascer.
            models.UniqueConstraint(
                fields=["site_id", "apelido"],
                condition=~models.Q(apelido=""),
                name="um_apelido_por_site",
            ),
            models.CheckConstraint(
                condition=models.Q(apelido="")
                | models.Q(apelido__regex=r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$"),
                name="apelido_e_endereco_web",
            ),
            # Publicada exige apelido E data; despublicada não tem data. As duas
            # direções na mesma restrição, porque metade dela deixaria passar
            # exatamente o caso que a outra metade proíbe.
            models.CheckConstraint(
                condition=(
                    models.Q(
                        vitrine_publicada=True,
                        publicada_em__isnull=False,
                    )
                    & ~models.Q(apelido="")
                )
                | models.Q(vitrine_publicada=False, publicada_em__isnull=True),
                name="vitrine_publicada_tem_apelido_e_data",
            ),
        ]

    def __str__(self) -> str:
        return f"portfólio de {self.aluno_id} em {self.site_id}"


class Peca(models.Model):
    """Uma obra do aluno: o link colado, a legenda, a ordem e o destaque.

    **O link é colado, e o arquivo nunca sobe para cá** (plano §6.2). O aluno
    aponta para o render que já está no Drive, no ArtStation ou onde ele guarda.

    **A ordem é a que o aluno escolheu**, e é ela que a vitrine (AC-13) e o
    dossiê em PDF (AC-16) seguem. A unicidade dela é `DEFERRED` de propósito:
    reordenar duas peças é uma troca, e uma restrição imediata recusaria o passo
    do meio da troca, obrigando a tela do degrau 08 a inventar posições
    temporárias.

    **O ESTADO DO LINK é o preço do link colado, escrito em três colunas**
    (plano §6.2, critérios AC-08 e AC-09). O mantenedor escolheu o link em vez
    do arquivo no nosso disco, informado de que link de aluno quebra e de que a
    escola não consegue consertar do lado de lá. Estas colunas são a mitigação
    que o plano prometeu em troca: a Prancheta confere o endereço quando ele é
    colado, volta a conferir de tempos em tempos, e MARCA o que parou de abrir.

    **Marcar nunca é apagar.** A obra do aluno só sai daqui quando ele mandar
    (critério AC-09), e é por isso que o estado é uma coluna e não uma exclusão:
    apagar peça de aluno por causa de uma medição de rede é a falha que não tem
    volta. Guarda: `tests/test_pecas_por_link.py`, provado por mutação.
    """

    portfolio = models.ForeignKey(
        Portfolio, on_delete=models.CASCADE, related_name="pecas"
    )

    link = models.URLField(max_length=500)
    legenda = models.CharField(max_length=200, blank=True, default="")
    ordem = models.PositiveIntegerField()
    destaque = models.BooleanField(default=False)

    estado_do_link = models.CharField(
        max_length=16,
        choices=EstadoDoLink.choices,
        default=EstadoDoLink.NAO_CONFERIDO,
    )
    conferido_em = models.DateTimeField(null=True, blank=True)
    # Desde QUANDO está quebrado, e é coluna separada de propósito:
    # `conferido_em` anda a cada varredura, então ela nunca conseguiria
    # responder "quebrou hoje" ou "quebrou no mês passado", que é justamente a
    # diferença que muda o que o aluno faz a respeito.
    quebrado_desde = models.DateTimeField(null=True, blank=True)

    # AS RESPOSTAS OBJETIVAS DO ALUNO SOBRE ESTA PEÇA (degrau 10, critério
    # AC-10). Cada uma responde a UMA regra que a professora escreveu, e o
    # semáforo é calculado só delas.
    #
    # **Vazio é "ainda não respondi", e é o estado em que toda peça nasce**,
    # inclusive as que já estavam guardadas antes deste degrau. A peça antiga
    # não vira peça errada por causa de uma pergunta que ninguém tinha feito a
    # ela: ela aparece com o que falta, que é exatamente o que a tela promete.
    #
    # **Nenhuma delas é nota, estrela ou classificação** (plano §7). Elas são a
    # resposta da pessoa a uma pergunta de sim ou não, e o que a tela faz com
    # elas é dizer o que ainda falta marcar, nunca quanto a obra vale.
    tipo = models.CharField(
        max_length=16, choices=TipoDeModelo.choices, blank=True, default=""
    )
    acabamento = models.CharField(
        max_length=16, choices=Acabamento.choices, blank=True, default=""
    )
    parecida_com_a_aula = models.CharField(
        max_length=8, choices=ParecidaComAAula.choices, blank=True, default=""
    )

    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    objects = DoPortfolioQuerySet.as_manager()

    class Meta:
        verbose_name = "peça"
        verbose_name_plural = "peças"
        constraints = [
            models.UniqueConstraint(
                fields=["portfolio", "ordem"],
                name="uma_peca_por_posicao",
                deferrable=models.Deferrable.DEFERRED,
            ),
            models.CheckConstraint(
                condition=models.Q(ordem__gte=1),
                name="a_ordem_comeca_em_um",
            ),
            models.CheckConstraint(
                condition=~models.Q(link=""),
                name="a_peca_tem_link",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    estado_do_link__in=[valor for valor, _ in EstadoDoLink.choices]
                ),
                name="o_estado_do_link_e_um_dos_tres",
            ),
            # A data da quebra anda junto com a quebra, nas duas direções: peça
            # quebrada sem data não diz desde quando, e data sem quebra é a
            # sobra de uma volta ao normal que ninguém limpou. Metade desta
            # restrição deixaria passar exatamente o caso que a outra proíbe.
            models.CheckConstraint(
                condition=models.Q(
                    estado_do_link=EstadoDoLink.QUEBRADO,
                    quebrado_desde__isnull=False,
                )
                | (
                    ~models.Q(estado_do_link=EstadoDoLink.QUEBRADO)
                    & models.Q(quebrado_desde__isnull=True)
                ),
                name="a_quebra_e_a_data_dela_andam_juntas",
            ),
            # Cada resposta é uma das que a escola escreveu, ou o vazio de quem
            # ainda não respondeu. Sem estas três, um POST com valor inventado
            # gravaria uma resposta que nenhuma tela sabe desenhar, e o semáforo
            # passaria a contar uma pergunta que a professora nunca fez.
            models.CheckConstraint(
                condition=models.Q(
                    tipo__in=[""] + [valor for valor, _ in TipoDeModelo.choices]
                ),
                name="o_tipo_da_peca_e_um_dos_da_escola",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    acabamento__in=[""] + [valor for valor, _ in Acabamento.choices]
                ),
                name="o_acabamento_da_peca_e_um_dos_dois",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    parecida_com_a_aula__in=[""]
                    + [valor for valor, _ in ParecidaComAAula.choices]
                ),
                name="a_semelhanca_com_a_aula_e_sim_ou_nao",
            ),
        ]

    def __str__(self) -> str:
        return self.legenda or self.link


class ItemDeConferencia(models.Model):
    """A marcação do aluno num item da lista de conferência, no banco, por aluno.

    **É este modelo que faz o AC-06 ser possível:** o aluno marca no celular,
    abre no computador e encontra a marcação no lugar. Guardar isso em
    `request.session` funcionaria em dev, passaria em teste de unidade,
    reprovaria o próprio AC-06 (sessão não atravessa aparelho) e deslogaria a
    plataforma inteira em produção, porque quem assina o cookie do site é a
    `identidade` ([INV-P12], `armadilhas/143`).

    **O que mora aqui é a MARCAÇÃO, não o texto do item.** A `chave` é o nome
    estável do item dentro da etapa; o texto que o aluno lê vem do guia da
    escola (degrau 07, lido do banco, e degrau 16, escrito no editor de
    documentos). Copiar o texto para cá criaria uma segunda verdade que ninguém
    mantém, e o dia em que a professora corrigisse uma linha o aluno veria a
    antiga.

    **Desmarcar não apaga a linha**, apaga a marca: o par `marcado` e
    `marcado_em` anda junto, e o banco recusa a data sem a marca e a marca sem a
    data.
    """

    portfolio = models.ForeignKey(
        Portfolio, on_delete=models.CASCADE, related_name="itens_de_conferencia"
    )

    etapa = models.PositiveSmallIntegerField()
    chave = models.CharField(max_length=64)
    marcado = models.BooleanField(default=False)
    marcado_em = models.DateTimeField(null=True, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = DoPortfolioQuerySet.as_manager()

    class Meta:
        verbose_name = "item de conferência"
        verbose_name_plural = "itens de conferência"
        constraints = [
            models.UniqueConstraint(
                fields=["portfolio", "chave"],
                name="uma_marcacao_por_item_por_portfolio",
            ),
            models.CheckConstraint(
                condition=models.Q(etapa__gte=PRIMEIRA_ETAPA, etapa__lte=ULTIMA_ETAPA),
                name="o_item_esta_numa_das_cinco_etapas",
            ),
            models.CheckConstraint(
                condition=~models.Q(chave=""),
                name="o_item_tem_chave",
            ),
            models.CheckConstraint(
                condition=models.Q(marcado=True, marcado_em__isnull=False)
                | models.Q(marcado=False, marcado_em__isnull=True),
                name="a_marca_e_a_data_andam_juntas",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.chave} (etapa {self.etapa})"


class EstadoDoAluno(models.Model):
    """Onde o aluno está no roteiro, e o selo da escola quando ele vier.

    Um por portfólio, e a chave é o portfólio de propósito: repetir aqui o
    `site_id` e o `aluno_id` criaria uma segunda verdade capaz de divergir do
    dono da linha (`armadilhas/274`).

    **O selo vale para o que o monitor VIU no dia** (plano §6.2), então ele
    guarda data e autor, e o banco exige os dois juntos: selo com data e sem
    quem conferiu é um selo que ninguém assinou. A conferência em si é o degrau
    11 e o selo é o 12; o que existe aqui é a coluna que eles vão preencher.
    """

    portfolio = models.OneToOneField(
        Portfolio, on_delete=models.CASCADE, related_name="estado"
    )

    etapa_atual = models.PositiveSmallIntegerField(default=PRIMEIRA_ETAPA)
    selo_conferido_em = models.DateTimeField(null=True, blank=True)
    selo_conferido_por = id_da_plataforma()

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = DoPortfolioQuerySet.as_manager()

    class Meta:
        verbose_name = "estado do aluno"
        verbose_name_plural = "estados dos alunos"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    etapa_atual__gte=PRIMEIRA_ETAPA, etapa_atual__lte=ULTIMA_ETAPA
                ),
                name="a_etapa_atual_e_uma_das_cinco",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    selo_conferido_em__isnull=True, selo_conferido_por=""
                )
                | (
                    models.Q(selo_conferido_em__isnull=False)
                    & ~models.Q(selo_conferido_por="")
                ),
                name="o_selo_tem_data_e_quem_conferiu",
            ),
        ]

    def __str__(self) -> str:
        return f"etapa {self.etapa_atual} de {self.portfolio.aluno_id}"


# ---------------------------------------------------------------------------
# O VOCABULÁRIO DO PEDIDO DE CONFERÊNCIA (degrau 11, critério AC-11)
# ---------------------------------------------------------------------------
# As duas listas moram no MÓDULO, e não dentro de `PedidoDeConferencia`, pela
# mesma razão de linguagem que já pôs `EstadoDoLink` aqui em cima: o corpo de
# uma `class Meta` aninhada não enxerga os nomes do corpo da classe que a
# contém, e as restrições do pedido precisam destes valores.


class EstadoDoPedido(models.TextChoices):
    """Onde está o pedido. Três estados, e nenhum deles se chama "recusado".

    **"Em análise" tem nome de espera, e o nome é a decisão.** Um primeiro
    estado chamado "pendente" ensinaria o aluno a se sentir recusado nos cinco
    dias em que ninguém fez nada de errado. E "recusado" não existe nesta
    lista: devolver não é dizer não, é dizer o que falta.

    O rótulo é o que o aluno lê na tela, então ele sai em frase inteira e sem
    travessão (lei do `ci/travessao.py`).
    """

    EM_ANALISE = "em_analise", "A escola está olhando o seu portfólio"
    ACEITO = "aceito", "A escola conferiu o seu portfólio"
    DEVOLVIDO = "devolvido", "A escola devolveu com o que falta"


class MotivoDaDevolucao(models.TextChoices):
    """As frases que a equipe escolhe ao devolver. Cada uma diz o que fazer.

    Elas saem das quatro regras que a professora escreveu no roteiro
    (`apps/portfolio/roteiro_da_escola.py`), mais o caso prático de a
    equipe não conseguir abrir uma peça. São o que o ALUNO lê, então elas
    são frases inteiras, em português, e sem travessão (lei do
    `ci/travessao.py`, que mede o rótulo de todo `TextChoices` de célula).

    **Nenhuma delas é uma opinião sobre a obra.** Cada uma aponta uma regra
    objetiva do roteiro e o que falta para cumpri-la, que é a diferença
    entre um processo e uma humilhação.
    """

    POUCOS_TIPOS = (
        "poucos_tipos",
        "Faltam tipos de modelo: a escola pede pelo menos 3 tipos "
        "diferentes entre os que o curso ensina.",
    )
    POUCAS_PECAS = (
        "poucas_pecas",
        "Faltam peças: a escola pede pelo menos 3 de cada tipo que você "
        "escolheu, o que dá 9 no mínimo.",
    )
    POUCO_HIGH_POLY = (
        "pouco_high_poly",
        "A maioria das peças ainda não está em high poly, que é o que a "
        "escola pede para impressionar o cliente.",
    )
    PARECIDA_COM_A_AULA = (
        "parecida_com_a_aula",
        "Há peças parecidas demais com o modelo feito na aula. Troque por "
        "criações suas.",
    )
    PECA_QUE_NAO_ABRE = (
        "peca_que_nao_abre",
        "A escola não conseguiu abrir o endereço de alguma peça. Guarde a "
        "peça de novo com o endereço atual dela.",
    )


class PedidoDeConferencia(models.Model):
    """O aluno pede que a escola olhe o portfólio dele, e o relógio começa a correr.

    Este é o degrau 11 da escada (critério AC-11), e o desenho é COPIADO do
    molde vivo da fila de marcos (`services/gamificacao`, tela
    `/conquistas/interno`): mesmos três estados, mesmo prazo em dias úteis,
    mesma devolução com motivo de lista fechada. Copia-se o PADRÃO entre
    células, nunca o código (Lei 3), e copiar um desenho que gente de verdade
    já usou vale mais que inventar um segundo jeito de fazer a mesma coisa.

    **A DEVOLUÇÃO EXIGE MOTIVO, e essa é metade do critério AC-11.** Devolver
    sem dizer por quê é o que faz um aluno desistir: ele fica sabendo que não
    foi, e não fica sabendo o que fazer. O banco recusa a linha devolvida sem
    motivo, e o motivo é uma das frases que a escola escreveu, nunca texto
    livre. Texto livre vira crítica pessoal, que é exatamente o que a lista
    fechada existe para impedir.

    **O SELO NÃO MORA AQUI.** Aceitar fecha o pedido e nada mais: o selo
    "conferido pela escola", o evento e a carta no sininho são o degrau 12, e
    a coluna que os guarda já existe em `EstadoDoAluno`. Escrever o selo aqui
    poria a mesma verdade em dois degraus e faria este PR entregar um critério
    que ele não tem como provar.

    O QUE ESTE MODELO NÃO GUARDA, E É DECISÃO
    -----------------------------------------
    - **A prova que o aluno manda.** Na fila de marcos ela existe porque o
      marco acontece FORA do site; aqui a prova é o portfólio, que já está
      neste banco e que a equipe abre na tela. Um campo de texto ao lado seria
      uma segunda descrição da mesma obra, livre para discordar dela.
    - **Contador de devoluções e escalada para adulto.** Na fila de marcos eles
      são o anti-anel, e existem porque um COLEGA pode devolver lá. Aqui quem
      devolve é só a equipe da escola, então não há anel para desfazer.
    - **Nota, estrela ou classificação.** Proibidas por escrito (plano §7). O
      resultado de uma conferência é aceito ou devolvido com o que falta, e
      nunca um número sobre a obra de alguém.

    **A porta do isolamento é a mesma de todo o resto** (`do_aluno`, critério
    AC-07): o pedido chega ao aluno e ao site pela chave estrangeira do
    portfólio, e nenhuma cópia de `aluno_id` mora aqui para divergir dele.
    """

    portfolio = models.ForeignKey(
        Portfolio, on_delete=models.CASCADE, related_name="pedidos_de_conferencia"
    )

    estado = models.CharField(
        max_length=10,
        choices=EstadoDoPedido.choices,
        default=EstadoDoPedido.EM_ANALISE,
    )
    # QUANDO A ESCOLA PROMETEU RESPONDER, e a coluna é obrigatória: fila sem
    # prazo é fila que envelhece calada, e o aluno não tem como saber se
    # esperar mais um dia é normal ou se ele foi esquecido.
    prazo_ate = models.DateTimeField()

    motivo_da_devolucao = models.CharField(
        max_length=24, choices=MotivoDaDevolucao.choices, blank=True, default=""
    )
    respondido_em = models.DateTimeField(null=True, blank=True)
    respondido_por = id_da_plataforma()

    criado_em = models.DateTimeField(auto_now_add=True)

    objects = DoPortfolioQuerySet.as_manager()

    class Meta:
        verbose_name = "pedido de conferência"
        verbose_name_plural = "pedidos de conferência"
        # A ORDEM DA FILA É REGRA, e ela mora aqui para a tela não poder
        # discordar: o prazo mais curto em cima. Ordenar por data de criação
        # mostraria o pedido mais VELHO primeiro, que não é o mais urgente
        # quando dois prazos diferentes convivem na mesma fila.
        ordering = ["prazo_ate", "criado_em"]
        constraints = [
            # UM pedido esperando por portfólio. Sem esta chave, dois cliques
            # no mesmo botão (ou duas abas abertas) poriam o mesmo portfólio
            # duas vezes na fila que uma PESSOA olha, e o prazo viraria ficção.
            # Parcial de propósito: pedido respondido é história, e o aluno
            # pode pedir de novo depois de arrumar o que faltava.
            models.UniqueConstraint(
                fields=["portfolio"],
                condition=models.Q(estado="em_analise"),
                name="um_pedido_de_conferencia_em_analise_por_portfolio",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    estado__in=[valor for valor, _ in EstadoDoPedido.choices]
                ),
                name="o_estado_do_pedido_e_um_dos_tres",
            ),
            # O MOTIVO ANDA JUNTO COM A DEVOLUÇÃO, nas duas direções: devolvido
            # sem motivo é o aluno travado sem saber o que fazer, e motivo sem
            # devolução é a sobra de uma resposta que alguém trocou depois.
            # Metade desta restrição deixaria passar o caso que a outra proíbe.
            models.CheckConstraint(
                condition=(
                    models.Q(estado="devolvido") & ~models.Q(motivo_da_devolucao="")
                )
                | (~models.Q(estado="devolvido") & models.Q(motivo_da_devolucao="")),
                name="a_devolucao_tem_motivo",
            ),
            # E o motivo é um dos que a escola escreveu. A tela recusa cedo e
            # com uma frase; esta linha recusa por último e sem frase nenhuma,
            # que é o mesmo par que a `Peca` já usa nas respostas do aluno.
            models.CheckConstraint(
                condition=models.Q(
                    motivo_da_devolucao__in=[""]
                    + [valor for valor, _ in MotivoDaDevolucao.choices]
                ),
                name="o_motivo_da_devolucao_e_um_dos_da_escola",
            ),
            # TODA RESPOSTA TEM DATA E TEM NOME. Sem os dois, a auditoria de
            # uma conferência contestada não teria o que responder meses
            # depois, e é a mesma exigência que o selo já faz de si mesmo em
            # `EstadoDoAluno`.
            models.CheckConstraint(
                condition=models.Q(
                    estado="em_analise",
                    respondido_em__isnull=True,
                    respondido_por="",
                )
                | (
                    ~models.Q(estado="em_analise")
                    & models.Q(respondido_em__isnull=False)
                    & ~models.Q(respondido_por="")
                ),
                name="a_resposta_tem_data_e_quem_respondeu",
            ),
        ]

    def __str__(self) -> str:
        return f"conferência de {self.portfolio.aluno_id}: {self.estado}"


# ===========================================================================
# O ROTEIRO DA ESCOLA: o que a Prancheta MOSTRA, e que não é de aluno nenhum
# ===========================================================================
# As duas tabelas abaixo nasceram no degrau 07 e guardam o CATÁLOGO: as cinco
# etapas e os itens de conferência que a escola escreveu. As quatro tabelas de
# cima guardam o que é DO ALUNO.
#
# A divisão é a que faz o critério AC-06 ser barato: o aluno marca uma `chave`,
# e o texto daquela chave pode ser corrigido pela escola sem tocar em nenhuma
# marcação. Copiar o texto para dentro da marcação criaria a segunda verdade
# que o degrau 02 recusou linha a linha.
#
# NEM `site_id` NEM `aluno_id` MORAM AQUI, e é decisão: o roteiro é o guia do
# curso, o mesmo para todo mundo que estuda nesta instalação. Uma cópia por
# aluno seria o texto da escola replicado em cada portfólio, envelhecendo em
# silêncio a partir da primeira correção.
#
# O TEXTO NÃO SE ESCREVE AQUI. Ele mora em `apps/portfolio/roteiro_da_escola.py`
# (marcado `ci:texto-publicado`, portanto medido pelo portão do travessão) e é
# plantado por migração. Este arquivo guarda a FORMA; aquele guarda a palavra.


class EtapaDoRoteiro(models.Model):
    """Uma das cinco etapas do roteiro. São cinco por lei (critério AC-06).

    O banco recusa a sexta, e recusa a etapa zero, pela mesma faixa que
    `ItemDeConferencia` e `EstadoDoAluno` já obedecem: as três precisam
    concordar sobre o que é uma etapa, e a única forma de garantir isso é a
    mesma restrição escrita nas três.
    """

    numero = models.PositiveSmallIntegerField(unique=True)
    titulo = models.CharField(max_length=120)
    resumo = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "etapa do roteiro"
        verbose_name_plural = "etapas do roteiro"
        ordering = ["numero"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    numero__gte=PRIMEIRA_ETAPA, numero__lte=ULTIMA_ETAPA
                ),
                name="a_etapa_do_roteiro_e_uma_das_cinco",
            ),
            models.CheckConstraint(
                condition=~models.Q(titulo=""),
                name="a_etapa_do_roteiro_tem_titulo",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.numero}. {self.titulo}"


class ItemDoRoteiro(models.Model):
    """Um item da lista de conferência: a frase que o aluno marca.

    **A `chave` é o que liga este catálogo à marcação do aluno**
    (`ItemDeConferencia.chave`), e ela é única na instalação inteira, não só
    dentro da etapa. Duas etapas com a mesma chave dariam duas frases diferentes
    para a mesma marcação, e a tela mostraria a marca no lugar errado sem nada
    reclamar.

    **Ela nunca muda.** Corrigir o texto é corrigir `texto`; trocar a chave
    apagaria a marcação de todos os alunos em silêncio.
    """

    etapa = models.ForeignKey(
        EtapaDoRoteiro, on_delete=models.CASCADE, related_name="itens"
    )

    chave = models.CharField(max_length=64, unique=True)
    texto = models.CharField(max_length=300)
    ordem = models.PositiveSmallIntegerField()

    class Meta:
        verbose_name = "item do roteiro"
        verbose_name_plural = "itens do roteiro"
        ordering = ["etapa__numero", "ordem"]
        constraints = [
            models.UniqueConstraint(
                fields=["etapa", "ordem"],
                name="um_item_do_roteiro_por_posicao_na_etapa",
            ),
            models.CheckConstraint(
                condition=~models.Q(chave=""),
                name="o_item_do_roteiro_tem_chave",
            ),
            models.CheckConstraint(
                condition=~models.Q(texto=""),
                name="o_item_do_roteiro_tem_texto",
            ),
        ]

    def __str__(self) -> str:
        return self.texto
