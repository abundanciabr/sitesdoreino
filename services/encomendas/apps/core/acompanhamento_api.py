"""Prática e encomendas de uma pessoa, para a ficha administrativa."""

import logging
import os

from django.db import DatabaseError
from ninja import Router
from ninja.errors import HttpError

from apps.encomendas.models import (
    Encomenda, Oferta, PedidoMarketplace, PerfilProfissional,
    ReservaDoMural,
)
try:
    from apps.encomendas.models import ParticipacaoSandbox
except ImportError:
    ParticipacaoSandbox = None

logger = logging.getLogger(__name__)
router = Router()


def _data(valor):
    return valor.isoformat() if valor else None


@router.get("/acompanhamento/{site_id}/{pessoa_id}")
def acompanhamento(request, site_id: str, pessoa_id: str):
    # O bearer de leitura geral também atende outros pares. A ficha pessoal
    # pertence ao token já provisionado para o Admin.
    token_admin = (os.environ.get("TOKENS_ACEITOS_ADMIN") or "").strip()
    if not token_admin or request.auth != token_admin:
        raise HttpError(403, "consulta reservada ao Admin")
    try:
        perfis = PerfilProfissional.objects.filter(site_id=site_id, pessoa_id=pessoa_id).values("id")
        projetos = ParticipacaoSandbox.objects.filter(
            site_id=site_id, pessoa_id=pessoa_id, projeto__site_id=site_id,
        ).select_related("projeto").order_by("-aceite_em") if ParticipacaoSandbox else []
        encomendas = Encomenda.objects.filter(
            site_id=site_id, aluno_id__in=perfis,
        ).order_by("-criada_em")
        pedidos = PedidoMarketplace.objects.filter(
            site_id=site_id, aluno_id__in=perfis,
        ).order_by("-criado_em")
        ofertas = Oferta.objects.filter(
            site_id=site_id, aluno_id__in=perfis, encomenda__site_id=site_id,
        )
        reservas = ReservaDoMural.objects.filter(
            site_id=site_id, aluno_id__in=perfis, encomenda__site_id=site_id,
        )
        return {
            "fonte": "encomendas", "site_id": site_id, "pessoa_id": pessoa_id,
            "projetos_disponiveis": ParticipacaoSandbox is not None,
            "projetos": [
                {"id": str(p.id), "projeto_id": str(p.projeto_id), "titulo": p.projeto.titulo,
                 "estado": p.status, "aceite_em": _data(p.aceite_em),
                 "prazo_ate": _data(p.prazo_ate), "aprovado_em": _data(p.aprovado_em)}
                for p in projetos
            ],
            "encomendas": [
                {"id": str(e.id), "origem": e.origem, "titulo": e.get_cartao_display(),
                 "estado": e.status, "criado_em": _data(e.criada_em),
                 "prazo_ate": _data(e.prazo_producao_ate)}
                for e in encomendas
            ] + [
                {"id": str(p.id), "origem": "marketplace", "titulo": p.titulo,
                 "estado": p.status, "criado_em": _data(p.criado_em),
                 "prazo_ate": _data(p.producao_prazo_ate)}
                for p in pedidos
            ],
            "participacoes": [
                {"tipo": "oferta", "id": str(o.id), "encomenda_id": str(o.encomenda_id),
                 "estado": o.resultado, "em": _data(o.oferecida_em), "prazo_ate": _data(o.expira_em)}
                for o in ofertas
            ] + [
                {"tipo": "reserva", "id": str(r.id), "encomenda_id": str(r.encomenda_id),
                 "estado": r.resultado, "em": _data(r.pegada_em), "prazo_ate": _data(r.expira_em)}
                for r in reservas
            ],
        }
    except DatabaseError as erro:
        logger.warning("acompanhamento de encomendas indisponível: %s", erro)
        raise HttpError(503, "fonte de encomendas indisponível") from erro
