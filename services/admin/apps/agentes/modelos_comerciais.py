"""O conhecimento comercial que os agentes consultam (`conhecimento_comercial.py`).

Mora num arquivo à parte e entra em `models.py` por um import só, para não
disputar o mesmo trecho com quem mexe nos robôs. O `db_table` vem escrito
porque a aplicação unificada só reescreve as tabelas das classes de
`models.py`: com ele, a tabela tem o mesmo nome nos dois jeitos de rodar.

* `MaterialComercial`: a marca que o administrador põe num documento do site
  dizendo "isto é material comercial (ou um depoimento) deste site". O
  documento continua sendo o mesmo `core.Documento`; aqui só se guarda o nome
  dele, como `FonteDoConhecimento` faz.
* `TrechoComercial`: um pedaço do índice comercial de UM site, com a fonte
  (tipo + id), o produto/oferta a que se refere e a vigência. Preço e
  condições NUNCA entram aqui: são consultados ao vivo.
"""

from __future__ import annotations

from django.db import models


class MaterialComercial(models.Model):
    """Um documento do site marcado como material comercial ou depoimento de
    um site. Depoimento só entra no índice com `utilizavel` (autorização de uso)."""

    class Tipo(models.TextChoices):
        MATERIAL = "material", "Material comercial"
        DEPOIMENTO = "depoimento", "Depoimento"

    documento_nome = models.CharField(max_length=80)
    site_id = models.CharField(max_length=64)
    site_host = models.CharField(max_length=200, blank=True, default="")
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.MATERIAL)
    produto = models.CharField(max_length=255, blank=True, default="")
    oferta = models.CharField(max_length=255, blank=True, default="")
    utilizavel = models.BooleanField(default=False)
    marcado_por = models.CharField(max_length=200, blank=True, default="")
    alterado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "agentes_materialcomercial"
        constraints = [
            models.UniqueConstraint(
                fields=["documento_nome", "site_id"], name="uma_marca_comercial_por_documento_e_site"
            )
        ]


class TrechoComercial(models.Model):
    """Um trecho do índice comercial de um site. A `fonte` é a mesma
    `FonteDoConhecimento` do mapa (chave `comercial:<site>:<tipo>:<id>`): a
    impressão dela decide se a fonte mudou, e apagar a fonte apaga os trechos."""

    fonte = models.ForeignKey(
        "agentes.FonteDoConhecimento", on_delete=models.CASCADE, related_name="trechos_comerciais"
    )
    site_id = models.CharField(max_length=64, db_index=True)
    site_host = models.CharField(max_length=200, blank=True, default="")
    tipo = models.CharField(max_length=20)
    ref = models.CharField(max_length=255)
    produto_ref = models.CharField(max_length=64, blank=True, default="")
    produto_nome = models.CharField(max_length=255, blank=True, default="")
    oferta_ref = models.CharField(max_length=255, blank=True, default="")
    titulo = models.CharField(max_length=200)
    texto = models.TextField()
    texto_normal = models.TextField()
    ordem = models.PositiveIntegerField(default=0)
    publico = models.BooleanField(default=True)
    endereco = models.CharField(max_length=300, blank=True, default="")
    vigente_desde = models.DateTimeField(null=True, blank=True)
    conferido_em = models.DateTimeField()

    class Meta:
        db_table = "agentes_trechocomercial"
        ordering = ["fonte_id", "ordem"]
        indexes = [models.Index(fields=["site_id", "tipo"], name="trecho_comercial_site_tipo")]
