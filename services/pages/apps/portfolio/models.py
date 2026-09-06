"""As quatro tabelas do portfólio do aluno, e a fronteira que elas defendem.

Lei: `docs/changespecs/CS-PAGES-0001.md` (critérios AC-02, AC-06, AC-07 e
AC-13), `docs/decisoes/PLANO-PORTFOLIO-DO-ALUNO.md` (§4 a casa, §5 a escada,
§7 o que ninguém pode inventar) e `constituicoes/AGENTS.pages.md` (os
invariantes desta célula). Este é o degrau 02 da escada.

**Não há tela, não há porta de máquina, não há evento e não há contrato.** Eles
são os degraus 06, 03 e 12. O que existe aqui é a fundação, e nela três coisas
que o resto vai poder tratar como verdade:

1. **Nenhuma chave estrangeira sai do banco desta célula** (critério AC-02).
   O id do aluno e o id do site são texto OPACO: quem sabe quem é a pessoa é a
   `identidade`, quem sabe se ela tem matrícula é a `alunos`, e o banco daqui
   não enxerga o das outras (Lei 2, Muralha 2).
2. **A marcação da lista de conferência mora no BANCO, por aluno.** Nunca em
   `request.session` (o [INV-P12] proíbe, e `armadilhas/143` conta o preço) e
   nunca no navegador: o AC-06 exige que a marcação atravesse APARELHOS, e
   sessão não atravessa.
3. **O isolamento por aluno é uma porta só, e ela é o `do_aluno` destes
   gerenciadores** (critério AC-07). Toda tela dos degraus 07, 08, 10 e 13 lê
   por ele. Guarda: `tests/test_isolamento_por_aluno.py`, provado por mutação.

POR QUE NENHUMA TABELA FILHA GUARDA `site_id` NEM `aluno_id`
------------------------------------------------------------
A fronteira de site (Lei 9 / [INV-P11]) e a fronteira de aluno moram no
`Portfolio`, e SÓ nele. `Peca`, `ItemDeConferencia` e `EstadoDoAluno` chegam às
duas pela chave estrangeira local.

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
- **O estado do link (quebrado, conferido) e o semáforo da peça.** São os
  degraus 08 e 10, que os calculam de respostas objetivas que ainda não existem.
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
    """

    portfolio = models.ForeignKey(
        Portfolio, on_delete=models.CASCADE, related_name="pecas"
    )

    link = models.URLField(max_length=500)
    legenda = models.CharField(max_length=200, blank=True, default="")
    ordem = models.PositiveIntegerField()
    destaque = models.BooleanField(default=False)

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
