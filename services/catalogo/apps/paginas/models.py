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
  natureza dele.

Publicar é congelar o rascunho numa versão nova. Consequência aceita da
imutabilidade: apagar uma página que já publicou é recusado, porque apagá-la
levaria as versões junto.
"""

import uuid

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
    de conjunto, e a trava pareceria existir sem existir (`armadilhas/023`).
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
            kwargs["secoes"] = normalizar_secoes(kwargs["secoes"])
        return super().update(**kwargs)


class Page(models.Model):
    """A identidade estável de uma página. [INV-P11] slug única POR site."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(
        "sites.Site", on_delete=models.CASCADE, related_name="paginas"
    )
    slug = models.SlugField(max_length=255)
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

    def save(self, *args, **kwargs):
        criando = self._state.adding
        super().save(*args, **kwargs)
        if criando:
            # Toda página nasce com um rascunho, ainda que vazio: sem isso,
            # "página sem rascunho" seria um segundo estado a tratar em cada
            # leitura, e `atualizado_em` não teria valor honesto para devolver.
            PageDraft.objects.create(page=self)

    @property
    def ultima_versao(self):
        """A versão publicada que está no ar, ou `None` se nunca publicou."""
        return self.versoes.order_by("-version").first()

    def publicar(self):
        """Congela o rascunho numa versão nova e devolve essa versão.

        Rascunho vazio levanta `RascunhoVazio`: publicar uma página em branco
        poria no ar um endereço público sem nada dentro.
        """
        rascunho = self.rascunho
        if not rascunho.secoes:
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
        self.secoes = normalizar_secoes(self.secoes)
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
        self.secoes = normalizar_secoes(self.secoes)
        return super().save(*args, **kwargs)
