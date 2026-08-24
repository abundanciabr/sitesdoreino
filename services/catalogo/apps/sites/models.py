# apps/sites/models.py  # [RECEITA:R7 v1]
import re
import uuid

from django.core.exceptions import ValidationError
from django.db import models

# BCP 47 na forma que aparece na URL: minúscula, com hífen (en, pt-br, es).
# A tag canônica (pt-BR, para <html lang>/hreflang) DERIVA desta — guardar as
# duas seria deixá-las divergir em silêncio (PLANO-I18N D5).
CODIGO_DE_IDIOMA = re.compile(r"^[a-z]{2}(-[a-z]{2})?$")


def normalizar_idiomas(default_language, languages):
    """Normaliza e VALIDA a declaração de idiomas de um site — fail-closed.

    Fonte ÚNICA da regra de coerência: chamada pelo `Site.save()`, pelo
    `SiteQuerySet.update()` e pelo `infra/sincronizar_sites.py` (a última
    barreira antes do banco de produção). Regra escrita duas vezes é regra
    que diverge.

    Devolve `(default_language, languages)` na forma canônica: código em
    minúsculas e `indexable` sempre explícito — assim o dado guardado não
    depende de ninguém lembrar do default do contrato, e a comparação de
    convergência do sincronizador é um `!=` honesto.

    Levanta `ValidationError` em qualquer incoerência. Site monolíngue (o caso
    de hoje) é `("", [])` e continua passando intocado por aqui.
    """
    padrao = (default_language or "").strip().lower()

    if not languages:
        languages = []
    if not isinstance(languages, list):
        raise ValidationError(
            "languages precisa ser uma lista de objetos {code, indexable}."
        )

    normalizados = []
    vistos = set()
    for item in languages:
        if not isinstance(item, dict):
            raise ValidationError(
                f"cada idioma precisa ser um objeto {{code, indexable}}, veio {item!r}."
            )
        bruto = item.get("code")
        if not isinstance(bruto, str) or not bruto.strip():
            raise ValidationError(f"idioma sem 'code': {item!r}.")
        code = bruto.strip().lower()
        if not CODIGO_DE_IDIOMA.match(code):
            raise ValidationError(
                f"código de idioma inválido: {bruto!r} — esperado BCP 47 minúsculo, "
                f"como 'en', 'pt-br', 'es'."
            )
        if code in vistos:
            raise ValidationError(f"código de idioma duplicado: {code!r}.")
        vistos.add(code)

        indexable = item.get("indexable", True)
        if not isinstance(indexable, bool):
            raise ValidationError(
                f"'indexable' de {code!r} precisa ser true/false, veio {indexable!r}."
            )
        normalizados.append({"code": code, "indexable": indexable})

    if not normalizados:
        # Monolíngue é a AUSÊNCIA dos dois (contrato: "ausente ⇒ monolíngue").
        # Idioma padrão sem idioma nenhum é o mesmo tipo de torto que o inverso.
        if padrao:
            raise ValidationError(
                f"default_language {padrao!r} declarado sem 'languages' — site sem "
                f"idiomas é monolíngue e não tem idioma padrão."
            )
        return "", []

    if not padrao:
        raise ValidationError(
            f"site com idiomas {sorted(vistos)} precisa de default_language."
        )
    if padrao not in vistos:
        raise ValidationError(
            f"default_language {padrao!r} não está entre os idiomas declarados "
            f"{sorted(vistos)}."
        )
    return padrao, normalizados


class SiteQuerySet(models.QuerySet):
    """[ARMADILHAS §4.4] `QuerySet.update()` NÃO passa por `Model.save()`: sem
    este guarda a coerência de idioma teria um caminho de escrita sem validação
    nenhuma, e o banco aceitaria um site torto pela porta dos fundos."""

    def update(self, **kwargs):
        toca = {"default_language", "languages"} & set(kwargs)
        if toca:
            if len(toca) == 1:
                raise ValidationError(
                    "update() que toca idioma precisa declarar default_language E "
                    "languages juntos: a coerência é do par, e linha a linha o "
                    "guarda não teria o outro campo para conferir."
                )
            kwargs["default_language"], kwargs["languages"] = normalizar_idiomas(
                kwargs["default_language"], kwargs["languages"]
            )
        return super().update(**kwargs)


class Site(models.Model):
    """Registro canônico do multissítio (Lei 9). Host não cadastrado nunca
    resolve para um site — é 404 em quem consome (INV-P11)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    host = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    active = models.BooleanField(default=True)
    theme = models.JSONField(default=dict, blank=True)
    default_offer_slug = models.CharField(max_length=255, blank=True, default="")
    # Idioma é DADO do site (PLANO-I18N D3, CONV-SITE), não arquivo de célula.
    # JSONField pelo mesmo motivo de `theme`: a lista é lida inteira junto com o
    # site e ninguém filtra site POR idioma — assim o décimo idioma é um
    # elemento a mais na lista, nunca uma migration.
    default_language = models.CharField(max_length=16, blank=True, default="")
    languages = models.JSONField(default=list, blank=True)

    objects = SiteQuerySet.as_manager()

    def save(self, *args, **kwargs):
        self.host = self.host.lower()
        self.default_language, self.languages = normalizar_idiomas(
            self.default_language, self.languages
        )
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.host
