"""Recebimentos existentes: projeção somente de leitura para o admin."""
import hashlib
import hmac
import os
from datetime import date

from django.http import HttpResponse
from ninja import Router
from ninja.errors import HttpError

from apps.gamificacao.models import RecebimentoDeclarado
from .sessao import site_atual

router = Router()


def autorizar(request, site_id):
    token = (os.environ.get("TOKENS_ACEITOS_ADMIN") or "").strip()
    if not token or not hmac.compare_digest(str(request.auth or ""), token):
        raise HttpError(403, "Consulta reservada ao Admin")
    site = site_atual()
    if not site:
        raise HttpError(503, "Site indisponível")
    if site_id != site:
        raise HttpError(404, "Site não encontrado")


def registros(site_id):
    return RecebimentoDeclarado.objects.filter(
        site_id=site_id, fora_da_progressao=False, estado="confirmado",
        print_bytes__isnull=False,
    ).exclude(print_sha256="").select_related("pessoa").defer("print_bytes")


def projetar(registro):
    # Nenhum e-mail, CPF, conta, chave ou JSON bruto da leitura é projetado.
    nome = registro.pessoa.nome_exibido.strip()
    nome = nome.split()[0] if nome and "@" not in nome else "Aluno"
    return {
        "id": registro.pk, "nome": nome,
        "trabalho": registro.referencia_trabalho,
        "origem": registro.origem,
        "valor_cents": registro.valor_cents,
        "moeda_original": registro.moeda_original,
        "valor_original_cents": registro.valor_original_cents,
        "recebido_em": registro.recebido_em.isoformat(),
        "analisada_em": registro.analisada_em.isoformat() if registro.analisada_em else None,
        "revisao": registro.revisao,
        "leitura_status": registro.leitura.get("status", "") if isinstance(registro.leitura, dict) else "",
    }


@router.get("/ganhos-admin/{site_id}", operation_id="listAdminEarningsPreview")
def listar(request, response: HttpResponse, site_id: str, de: str = "", ate: str = "", pagina: int = 1):
    autorizar(request, site_id)
    if pagina < 1:
        raise HttpError(400, "Página inválida")
    consulta = registros(site_id)
    try:
        inicio = date.fromisoformat(de) if de else None
        fim = date.fromisoformat(ate) if ate else None
    except ValueError:
        raise HttpError(400, "Período inválido") from None
    if inicio and fim and inicio > fim:
        raise HttpError(400, "Período inválido")
    if inicio:
        consulta = consulta.filter(recebido_em__gte=inicio)
    if fim:
        consulta = consulta.filter(recebido_em__lte=fim)
    total = consulta.count()
    itens = [projetar(r) for r in consulta.order_by("-recebido_em", "-pk")[(pagina-1)*12:pagina*12]]
    response["Cache-Control"] = "private, no-store"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return {"site_id": site_id, "total": total, "pagina": pagina, "itens": itens, "mais": pagina*12 < total}


@router.get("/ganhos-admin/{site_id}/{registro_id}", operation_id="getAdminEarningEvidence")
def detalhe(request, response: HttpResponse, site_id: str, registro_id: int):
    autorizar(request, site_id)
    registro = registros(site_id).filter(pk=registro_id).first()
    if not registro:
        raise HttpError(404, "Recebimento não encontrado")
    response["Cache-Control"] = "private, no-store"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return {"site_id": site_id, "item": projetar(registro)}


@router.get("/ganhos-admin/{site_id}/{registro_id}/print", operation_id="getAdminEarningPrivatePrint")
def imagem(request, site_id: str, registro_id: int):
    autorizar(request, site_id)
    registro = registros(site_id).filter(pk=registro_id).first()
    if not registro:
        raise HttpError(404, "Recebimento não encontrado")
    conteudo = bytes(registro.print_bytes or b"")
    if not conteudo or hashlib.sha256(conteudo).hexdigest() != registro.print_sha256:
        raise HttpError(409, "Print indisponível para conferência")
    resposta = HttpResponse(conteudo, content_type="image/png")
    resposta["Cache-Control"] = "private, no-store"
    resposta["X-Robots-Tag"] = "noindex, nofollow"
    resposta["X-Content-Type-Options"] = "nosniff"
    resposta["Content-Disposition"] = 'inline; filename="print-privado.png"'
    return resposta
