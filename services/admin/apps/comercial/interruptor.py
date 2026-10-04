"""O interruptor da equipe comercial e o escopo por quiz, guardados no banco.

Antes, ligar a equipe pedia editar `COMERCIAL_AGENTES` no env da VPS. Agora a
tela `/admin/crm/agentes/` liga e desliga, e o que a tela grava manda:

* sem linha no banco, vale o comportamento antigo do ambiente
  (`COMERCIAL_AGENTES=desligado` continua desligando);
* com linha, vale a linha (`ligada` verdadeiro ou falso). Uma linha que só
  guardou o escopo, sem nunca ter ligado ou desligado, deixa `ligada` vazio e o
  ambiente continua mandando.

Uma linha por instalação (a chave é sempre 1). O escopo é a lista de quizzes em
que a equipe atua; vazia quer dizer todos.
"""

from __future__ import annotations

import os

from django.db import models
from django.utils import timezone

PK = 1
LIMITE_DE_QUIZZES = 100


class ConfiguracaoComercial(models.Model):
    ligada = models.BooleanField(null=True, blank=True, default=None)
    quizzes = models.JSONField(default=list, blank=True)
    ligada_por = models.CharField(max_length=200, blank=True, default="")
    ligada_em = models.DateTimeField(null=True, blank=True)
    escopo_por = models.CharField(max_length=200, blank=True, default="")
    escopo_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "comercial_configuracaocomercial"

    def __str__(self) -> str:  # pragma: no cover - conveniência de shell
        return f"equipe comercial: {self.ligada} / quizzes {self.quizzes}"


def configuracao() -> ConfiguracaoComercial | None:
    return ConfiguracaoComercial.objects.filter(pk=PK).first()


def _do_ambiente() -> bool:
    return os.environ.get("COMERCIAL_AGENTES", "").strip().lower() != "desligado"


def ligada() -> bool:
    """A linha manda; sem linha (ou sem decisão nela), manda o ambiente."""
    linha = configuracao()
    if linha is None or linha.ligada is None:
        return _do_ambiente()
    return bool(linha.ligada)


def origem() -> str:
    """De onde vem o estado de agora: `tela` ou `ambiente`."""
    linha = configuracao()
    return "tela" if linha is not None and linha.ligada is not None else "ambiente"


def definir_ligada(valor: bool, quem: str) -> ConfiguracaoComercial:
    linha, _ = ConfiguracaoComercial.objects.get_or_create(pk=PK)
    linha.ligada = bool(valor)
    linha.ligada_por = (quem or "")[:200]
    linha.ligada_em = timezone.now()
    linha.save(update_fields=["ligada", "ligada_por", "ligada_em"])
    return linha


def escopo() -> list[str]:
    """Os quizzes em que a equipe atua. Lista vazia: todos."""
    linha = configuracao()
    bruto = linha.quizzes if linha is not None else []
    return [s for s in bruto if isinstance(s, str) and s] if isinstance(bruto, list) else []


def definir_escopo(slugs, quem: str) -> ConfiguracaoComercial:
    limpos = list(dict.fromkeys(str(s).strip()[:120] for s in slugs if str(s).strip()))[:LIMITE_DE_QUIZZES]
    linha, _ = ConfiguracaoComercial.objects.get_or_create(pk=PK)
    linha.quizzes = limpos
    linha.escopo_por = (quem or "")[:200]
    linha.escopo_em = timezone.now()
    linha.save(update_fields=["quizzes", "escopo_por", "escopo_em"])
    return linha


def quiz_no_escopo(slug: str) -> bool:
    lista = escopo()
    return not lista or (slug or "").strip() in lista
