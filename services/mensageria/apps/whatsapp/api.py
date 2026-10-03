"""Operação interna para o painel autenticado do mantenedor."""
from ninja import Router, Schema
from ninja.errors import HttpError

from apps.core.auth import tokens_de_publicacao

from .models import ConfiguracaoWhatsApp, MensagemWhatsApp
from .service import conectar, enviar_mensagem, estado_da_conexao, mascarar_telefone, reconciliar_mensagem

router = Router()


class ConfigEntrada(Schema):
    instancia: str
    transporte: str = "WHATSAPP-BAILEYS"
    ativo: bool = True


class EnvioEntrada(Schema):
    destinatario: str
    corpo: str
    referencia: str


class ReconciliacaoEntrada(Schema):
    origem: str
    referencia: str
    provider_id: str


class ConexaoEntrada(Schema):
    renovar: bool = False


def _site(site_id: str) -> str:
    site_id = site_id.strip()
    if not site_id or len(site_id) > 100:
        raise HttpError(422, "site_id invalido")
    return site_id


def _escrita(request):
    if request.auth not in tokens_de_publicacao():
        raise HttpError(403, "acesso de escrita negado")


def _resumo(msg: MensagemWhatsApp) -> dict:
    return {
        "id": msg.pk, "origem": msg.origem, "referencia": msg.referencia,
        "status": msg.status, "provider_id": msg.provider_id,
        "numero_mascarado": mascarar_telefone(msg.destinatario),
        "erro": msg.erro, "criado_em": msg.criado_em.isoformat(),
    }


@router.get("/{site_id}")
def consultar(request, site_id: str):
    site_id = _site(site_id)
    config = ConfiguracaoWhatsApp.objects.filter(site_id=site_id).first()
    mensagens = MensagemWhatsApp.objects.filter(site_id=site_id).order_by("-id")[:50]
    return {
        "configuracao": ({"site_id": site_id, "instancia": config.instancia,
                           "transporte": config.transporte, "ativo": config.ativo}
                          if config else None),
        "conexao": estado_da_conexao(site_id),
        "mensagens": [_resumo(msg) for msg in mensagens],
    }


@router.post("/{site_id}/config")
def configurar(request, site_id: str, dados: ConfigEntrada):
    _escrita(request)
    site_id = _site(site_id)
    instancia = dados.instancia.strip()
    if not instancia or len(instancia) > 100 or "/" in instancia:
        raise HttpError(422, "instancia invalida")
    if dados.transporte != "WHATSAPP-BAILEYS":
        raise HttpError(422, "transporte ainda nao disponivel neste site")
    if ConfiguracaoWhatsApp.objects.filter(instancia=instancia).exclude(site_id=site_id).exists():
        raise HttpError(409, "instancia ja pertence a outro site")
    anterior = ConfiguracaoWhatsApp.objects.filter(site_id=site_id).first()
    if (anterior and anterior.instancia != instancia and
            MensagemWhatsApp.objects.filter(site_id=site_id).exists()):
        raise HttpError(409, "esta instancia ja tem historico; reconecte a mesma instancia")
    config, _ = ConfiguracaoWhatsApp.objects.update_or_create(
        site_id=site_id, defaults={"instancia": instancia, "transporte": dados.transporte, "ativo": dados.ativo},
    )
    return {"site_id": config.site_id, "instancia": config.instancia,
            "transporte": config.transporte, "ativo": config.ativo}


@router.post("/{site_id}/connect")
def conectar_pelo_painel(request, site_id: str, dados: ConexaoEntrada = None):
    _escrita(request)
    return conectar(_site(site_id), renovar=bool(dados and dados.renovar))


@router.post("/{site_id}/send")
def envio_manual(request, site_id: str, dados: EnvioEntrada):
    _escrita(request)
    if not dados.referencia.strip():
        raise HttpError(422, "referencia obrigatoria")
    msg = enviar_mensagem(site_id=_site(site_id), destinatario=dados.destinatario,
                          corpo=dados.corpo, origem="manual", referencia=dados.referencia)
    return _resumo(msg)


@router.post("/{site_id}/reconcile")
def reconciliar(request, site_id: str, dados: ReconciliacaoEntrada):
    _escrita(request)
    try:
        msg = reconciliar_mensagem(site_id=_site(site_id), origem=dados.origem,
                                   referencia=dados.referencia, provider_id=dados.provider_id)
    except MensagemWhatsApp.DoesNotExist:
        raise HttpError(404, "mensagem nao encontrada")
    except ValueError as exc:
        raise HttpError(409, str(exc))
    return _resumo(msg)
