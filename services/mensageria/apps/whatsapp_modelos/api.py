"""Porta de máquina dos modelos aprovados: painel, sincronização e envio."""
from ninja import Router, Schema
from ninja.errors import HttpError

from apps.core.auth import tokens_de_publicacao

from . import cloud
from .models import EnvioDeModelo, ModeloWhatsApp
from .modelos import (definir_mapeamento, enviar_modelo, painel, resumo_de_envio, resumo_de_modelo,
                      sincronizar_modelos)

router = Router()


class EnvioEntrada(Schema):
    chave_idempotencia: str
    destinatario: str
    modelo: str
    idioma: str = ""
    variaveis: dict = {}
    origem: str = "abordagem"
    referencia: str = ""


class MapeamentoEntrada(Schema):
    mapeamento: dict


def _site(site_id: str) -> str:
    site_id = site_id.strip()
    if not site_id or len(site_id) > 100:
        raise HttpError(422, "site_id invalido")
    return site_id


def _escrita(request):
    if request.auth not in tokens_de_publicacao():
        raise HttpError(403, "acesso de escrita negado")


@router.post("/sincronizar")
def sincronizar(request):
    _escrita(request)
    if not cloud.configurado():
        return {"canal_oficial": "nao_ligado", "modelos": 0, "sumidos": 0, "erro": ""}
    try:
        resultado = sincronizar_modelos()
    except cloud.CloudRecusou as exc:
        return {"canal_oficial": "ligado", "modelos": 0, "sumidos": 0, "erro": str(exc)}
    except cloud.CloudSemResposta as exc:
        return {"canal_oficial": "ligado", "modelos": 0, "sumidos": 0, "erro": str(exc)}
    return {"canal_oficial": "ligado", "erro": "", **resultado}


@router.post("/modelos/{modelo_id}/mapeamento")
def mapear(request, modelo_id: int, dados: MapeamentoEntrada):
    _escrita(request)
    try:
        modelo = definir_mapeamento(modelo_id, dados.mapeamento)
    except ModeloWhatsApp.DoesNotExist:
        raise HttpError(404, "modelo nao encontrado")
    except ValueError as exc:
        raise HttpError(422, str(exc))
    return resumo_de_modelo(modelo)


@router.get("/{site_id}")
def consultar(request, site_id: str):
    return painel(_site(site_id))


@router.post("/{site_id}/enviar")
def enviar(request, site_id: str, dados: EnvioEntrada):
    _escrita(request)
    if not dados.chave_idempotencia.strip() or not dados.modelo.strip():
        raise HttpError(422, "chave_idempotencia e modelo sao obrigatorios")
    if dados.origem not in ("abordagem", "jornada", "manual"):
        raise HttpError(422, "origem invalida")
    envio = enviar_modelo(site_id=_site(site_id), chave_idempotencia=dados.chave_idempotencia,
                          destinatario=dados.destinatario, modelo=dados.modelo, idioma=dados.idioma,
                          variaveis=dados.variaveis, origem=dados.origem, referencia=dados.referencia)
    return resumo_de_envio(envio)


@router.get("/{site_id}/envios/{chave_idempotencia}")
def estado_do_envio(request, site_id: str, chave_idempotencia: str):
    envio = EnvioDeModelo.objects.filter(site_id=_site(site_id), chave_idempotencia=chave_idempotencia).first()
    if envio is None:
        raise HttpError(404, "envio nao encontrado")
    return resumo_de_envio(envio)
