"""Consulta somente os marcos indispensáveis da cópia privada do reinício."""

import gzip
import hashlib
import json
from functools import lru_cache

from django.utils.dateparse import parse_datetime

from .bonus_faixas import SLUGS
from .models import BackupDoReinicioDasFaixas

CHAVE = "reinicio-autorizado-20261011"
ORDENS_POR_SLUG = {"bonus-faixa-" + slug: ordem for ordem, slug in SLUGS.items()}


@lru_cache(maxsize=4)
def _extrair(backup_id, sha256):
    backup = BackupDoReinicioDasFaixas.objects.get(pk=backup_id, sha256=sha256)
    conteudo = bytes(backup.conteudo)
    if hashlib.sha256(conteudo).hexdigest() != sha256:
        raise ValueError("A cópia privada do reinício falhou na conferência.")
    pessoas = {}
    for linha in json.loads(gzip.decompress(conteudo)):
        campos = linha.get("fields") or {}
        pessoa = campos.get("pessoa")
        if pessoa is None:
            continue
        historico = pessoas.setdefault(str(pessoa), {"bonus": {}, "faixas": set(), "conclusoes": set()})
        modelo = linha.get("model", "").lower()
        if modelo == "gamificacao.lancamentodexp":
            ordem = ORDENS_POR_SLUG.get(campos.get("regra_slug"))
            if ordem and campos.get("status") == "definitivo" and int(campos.get("pontos") or 0) > 0:
                historico["bonus"].setdefault(ordem, {
                    "pontos": int(campos["pontos"]),
                    "criado_em": parse_datetime(campos.get("criado_em") or ""),
                })
        elif modelo == "gamificacao.faixadoaluno":
            historico["faixas"].add((campos.get("ordem"), campos.get("origem")))
        elif modelo == "gamificacao.registrodajornada":
            if campos.get("acao") == "conclusao":
                historico["conclusoes"].add((campos.get("dados") or {}).get("passo"))
    return pessoas


def marcos_anteriores(pessoa_id, site_id):
    referencia = BackupDoReinicioDasFaixas.objects.filter(
        site_id=site_id, chave=CHAVE, aplicado_em__isnull=False,
    ).values("id", "sha256").first()
    if not referencia:
        return {"bonus": {}, "faixas": set(), "conclusoes": set()}
    return _extrair(referencia["id"], referencia["sha256"]).get(
        str(pessoa_id), {"bonus": {}, "faixas": set(), "conclusoes": set()}
    )
