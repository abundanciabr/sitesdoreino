# apps/paginas/models.py
"""A estrutura de uma página: identidade, versão publicada e rascunho.

Três tabelas, e a diferença entre elas é o que precisa ficar claro para quem
chegar:

- **`Page`** é a identidade estável da página (este site, esta slug). Ela não
  guarda conteúdo nenhum: o conteúdo tem versão, e a identidade não.
- **`PageVersion`** é o que foi publicado, e é imutável, exatamente como o
  `Evento` da célula `metricas`. Página publicada que alguém pode reescrever
  não é publicação, é rascunho com endereço público. A trava é dupla de
  propósito, porque a do ORM não alcança um `UPDATE` digitado num console e a
  do banco não explica nada a quem está programando.
- **`PageDraft`** é onde se escreve, um por página, e é mutável: essa é a
  natureza dele. Ele nasce na primeira gravação, e não junto com a página,
  porque o contrato distingue "nunca foi editada" (404) de "tem um texto pela
  metade" (200), e criar um rascunho vazio de véspera apagaria essa diferença.

Publicar é congelar o rascunho numa versão nova. Consequência aceita da
imutabilidade: apagar uma página que já publicou é recusado, porque apagá-la
levaria as versões junto.
"""

import math
import uuid
from statistics import NormalDist

from django.core.exceptions import ValidationError
from django.db import models

from apps.paginas.vocabulario import normalizar_secoes


class VersaoPublicadaImutavel(Exception):
    """Tentativa de alterar ou apagar uma página já publicada."""


class RascunhoVazio(Exception):
    """Tentativa de publicar uma página que não tem nada escrito."""


RECADO_IMUTAVEL = (
    "versão publicada não se edita: publique uma versão nova, gravando o "
    "rascunho e chamando publicar (constituicoes/AGENTS.catalogo.md, a oferta "
    "publicada segue a mesma regra)"
)


class PageVersionQuerySet(models.QuerySet):
    """O caminho de conjunto também é fechado.

    Sem isto, `PageVersion.objects.filter(...).update(...)` passaria direto
    pelo `save()` sobrescrito, porque o ORM não chama `save()` numa atualização
    de conjunto, e a trava pareceria existir sem existir.
    """

    def update(self, **kwargs):
        raise VersaoPublicadaImutavel(RECADO_IMUTAVEL)

    def delete(self):
        raise VersaoPublicadaImutavel(RECADO_IMUTAVEL)


class PageDraftQuerySet(models.QuerySet):
    """O rascunho é mutável, mas a forma dele continua sendo conferida.

    Mesmo motivo do guarda acima e do `SiteQuerySet.update()`: este é um
    caminho de escrita que não passa pelo `save()`, e sem esta linha o banco
    aceitaria um rascunho fora do vocabulário pela porta dos fundos.
    """

    def update(self, **kwargs):
        if "secoes" in kwargs:
            tipos = set(self.values_list("page__tipo", flat=True))
            if len(tipos) > 1:
                raise ValidationError(
                    "rascunhos de tipos diferentes não recebem as mesmas seções. "
                    "Filtre por tipo e grave cada conjunto separadamente."
                )
            kwargs["secoes"] = normalizar_secoes(
                kwargs["secoes"], next(iter(tipos), "oferta")
            )
        return super().update(**kwargs)


class Page(models.Model):
    """A identidade estável de uma página. [INV-P11] slug única POR site."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(
        "sites.Site", on_delete=models.CASCADE, related_name="paginas"
    )
    slug = models.SlugField(max_length=255)
    tipo = models.CharField(
        max_length=6,
        choices=[("oferta", "Oferta"), ("flp", "FLP")],
        default="oferta",
        db_default="oferta",
    )
    #: A oferta que esta página vende, quando ela vende alguma. Opcional porque
    #: nem toda página é de venda. `PROTECT` pela mesma razão de `Offer.product`:
    #: sumir com a oferta por baixo de uma página é decisão, não efeito colateral.
    offer = models.ForeignKey(
        "ofertas.Offer",
        on_delete=models.PROTECT,
        related_name="paginas",
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site", "slug"], name="pagina_unica_por_site"
            )
        ]

    def __str__(self) -> str:
        return f"{self.site_id}:{self.slug}"

    @property
    def ultima_versao(self):
        """A versão publicada que está no ar, ou `None` se nunca publicou."""
        return self.versoes.order_by("-version").first()

    def publicar(self):
        """Congela o rascunho numa versão nova e devolve essa versão.

        Rascunho vazio levanta `RascunhoVazio`: publicar uma página em branco
        poria no ar um endereço público sem nada dentro.
        """
        rascunho = PageDraft.objects.filter(page=self).first()
        if rascunho is None or not rascunho.secoes:
            raise RascunhoVazio(
                "não há rascunho para publicar nesta página. Grave as seções no "
                "rascunho e publique de novo"
            )

        ultima = self.ultima_versao
        versao = PageVersion.objects.create(
            page=self,
            version=(ultima.version if ultima else 0) + 1,
            secoes=rascunho.secoes,
        )
        rascunho.base_version = versao.version
        rascunho.save()
        return versao


class PageVersion(models.Model):
    """Uma publicação da página, congelada. Não se edita, não se apaga."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name="versoes")
    #: Cresce de um em um e nunca é reescrito, como o `version` da `Offer`.
    version = models.PositiveIntegerField()
    secoes = models.JSONField(default=list)
    published_at = models.DateTimeField(auto_now_add=True)

    objects = PageVersionQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["page", "version"], name="versao_unica_por_pagina"
            )
        ]
        ordering = ["-version"]

    def __str__(self) -> str:
        return f"{self.page} v{self.version}"

    def save(self, *args, **kwargs):
        # `_state.adding`, e não `pk is None`: a chave é um UUID com valor
        # padrão, então ela já existe antes do primeiro `save()` e não serve
        # para distinguir criação de reescrita.
        if not self._state.adding:
            raise VersaoPublicadaImutavel(RECADO_IMUTAVEL)
        self.secoes = normalizar_secoes(self.secoes, self.page.tipo)
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise VersaoPublicadaImutavel(RECADO_IMUTAVEL)


class PageDraft(models.Model):
    """O que está sendo escrito. Um por página, e mutável."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    page = models.OneToOneField(Page, on_delete=models.CASCADE, related_name="rascunho")
    secoes = models.JSONField(default=list, blank=True)
    #: A versão publicada de que este rascunho partiu. Zero enquanto a página
    #: nunca publicou, e é assim que quem edita sabe se está mexendo no que já
    #: está no ar ou escrevendo a primeira vez.
    base_version = models.PositiveIntegerField(default=0)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = PageDraftQuerySet.as_manager()

    def __str__(self) -> str:
        return f"rascunho de {self.page}"

    def save(self, *args, **kwargs):
        self.secoes = normalizar_secoes(self.secoes, self.page.tipo)
        return super().save(*args, **kwargs)


class VarianteCongelada(Exception):
    """Tentativa de alterar ou apagar uma variante de experimento que já saiu do rascunho."""


RECADO_VARIANTE_CONGELADA = (
    "variante de experimento que já saiu do rascunho não se edita nem se apaga: "
    "o texto dela é o que os visitantes viram e o que os eventos do funil citam. "
    "Para testar outro texto, encerre este experimento e crie um novo"
)


#: Alfa 0,05 bicaudal e poder 0,8, os da conta que decidiu o primeiro
#: experimento.
Z_ALFA = NormalDist().inv_cdf(1 - 0.05 / 2)
Z_PODER = NormalDist().inv_cdf(0.80)


def amostra_por_braco(taxa_base: float, mde: float) -> int:
    """Visitantes expostos por braço para enxergar `mde` sobre `taxa_base`.

    A fórmula da DECISAO §3 (duas proporções, variância agrupada sob a nula),
    com uma diferença: lá o efeito é relativo (`lift`), aqui `mde` é ABSOLUTO,
    em pontos de proporção (0,02 é "de 10% para 12%").
    """
    tratado = taxa_base + mde
    media = (taxa_base + tratado) / 2
    termo_nulo = Z_ALFA * math.sqrt(2 * media * (1 - media))
    termo_alt = Z_PODER * math.sqrt(
        taxa_base * (1 - taxa_base) + tratado * (1 - tratado)
    )
    return math.ceil(((termo_nulo + termo_alt) / mde) ** 2)


class ExperimentoQuerySet(models.QuerySet):
    """Apagar em conjunto também respeita o que já foi ao ar."""

    def delete(self):
        if self.exclude(estado=Experimento.RASCUNHO).exists():
            raise VarianteCongelada(RECADO_VARIANTE_CONGELADA)
        return super().delete()


class Experimento(models.Model):
    """O teste de um slot de uma página: uma hipótese, as variantes e o horizonte.

    O horizonte é fixo e decidido antes de começar (`taxa_base`, `mde`,
    `n_por_braco_planejado`, `dias_planejados`), porque olhar o resultado todo
    dia e parar quando ele agrada fabrica vencedor por acaso. Não há pausa:
    pausar e retomar misturaria no braço `b` quem viu `a` durante a pausa, e
    retomar é criar um experimento novo.

    Um só `ativo` por página, garantido pelo banco: duas ativações ao mesmo
    tempo terminam com uma aceita e a outra recusada, nunca com duas no ar.
    """

    RASCUNHO = "rascunho"
    ATIVO = "ativo"
    ENCERRADO = "encerrado"

    #: As transições válidas. Repetir a transição que já aconteceu não passa
    #: por aqui: é idempotente e responde o estado atual sem mudar nada.
    TRANSICOES = {RASCUNHO: {ATIVO, ENCERRADO}, ATIVO: {ENCERRADO}, ENCERRADO: set()}

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    page = models.ForeignKey(
        Page, on_delete=models.PROTECT, related_name="experimentos"
    )
    secao = models.CharField(max_length=32)
    slot = models.CharField(max_length=32)
    hipotese = models.TextField()
    metrica_principal = models.CharField(max_length=100)
    taxa_base = models.FloatField()
    mde = models.FloatField()
    n_por_braco_planejado = models.PositiveIntegerField()
    dias_planejados = models.PositiveIntegerField()
    estado = models.CharField(
        max_length=9,
        choices=[(RASCUNHO, "Rascunho"), (ATIVO, "Ativo"), (ENCERRADO, "Encerrado")],
        default=RASCUNHO,
    )
    decisao = models.CharField(
        max_length=8,
        choices=[
            ("promover", "Promover"),
            ("reverter", "Reverter"),
            ("encerrar", "Encerrar"),
        ],
        blank=True,
    )
    vencedora = models.CharField(max_length=32, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    iniciado_em = models.DateTimeField(null=True, blank=True)
    encerrado_em = models.DateTimeField(null=True, blank=True)

    objects = ExperimentoQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["page"],
                condition=models.Q(estado="ativo"),
                name="um_experimento_ativo_por_pagina",
            )
        ]
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return f"{self.page} {self.secao}.{self.slot} ({self.estado})"

    def delete(self, *args, **kwargs):
        # Apagar o experimento levaria as variantes junto pela cascata, que não
        # passa pelo `delete()` de cada uma: a trava delas precisa estar aqui.
        if self.estado != self.RASCUNHO:
            raise VarianteCongelada(RECADO_VARIANTE_CONGELADA)
        return super().delete(*args, **kwargs)


class VarianteQuerySet(models.QuerySet):
    """O caminho de conjunto também confere o estado do experimento.

    Sem isto, `Variante.objects.filter(...).update(...)` passaria direto pelo
    `save()` sobrescrito, e a trava pareceria existir sem
    existir.
    """

    def _recusa_se_congelada(self):
        if self.exclude(experimento__estado=Experimento.RASCUNHO).exists():
            raise VarianteCongelada(RECADO_VARIANTE_CONGELADA)

    def update(self, **kwargs):
        self._recusa_se_congelada()
        return super().update(**kwargs)

    def delete(self):
        self._recusa_se_congelada()
        return super().delete()


class Variante(models.Model):
    """Um braço do experimento: a chave curta, o peso e o texto congelado do slot.

    O texto é snapshot, e não referência à página: a página pode ser publicada
    de novo durante o experimento, e o que cada visitante viu precisa continuar
    sendo o que está aqui.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    experimento = models.ForeignKey(
        Experimento, on_delete=models.CASCADE, related_name="variantes"
    )
    variante_id = models.CharField(max_length=32)
    #: Pontos-base: as variantes de um experimento somam 10000.
    peso = models.PositiveIntegerField()
    valor = models.TextField()

    objects = VarianteQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["experimento", "variante_id"],
                name="variante_unica_por_experimento",
            )
        ]
        ordering = ["variante_id"]

    def __str__(self) -> str:
        return f"{self.experimento_id}:{self.variante_id}"

    def _congelada(self) -> bool:
        estado = (
            Experimento.objects.filter(pk=self.experimento_id)
            .values_list("estado", flat=True)
            .first()
        )
        return estado not in (None, Experimento.RASCUNHO)

    def save(self, *args, **kwargs):
        if self._congelada():
            raise VarianteCongelada(RECADO_VARIANTE_CONGELADA)
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self._congelada():
            raise VarianteCongelada(RECADO_VARIANTE_CONGELADA)
        return super().delete(*args, **kwargs)
