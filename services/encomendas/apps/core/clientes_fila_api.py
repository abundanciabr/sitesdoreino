"""Página interna de clientes: par Admin com a célula de encomendas."""

import hmac
import os
from uuid import UUID
from django.views.decorators.debug import sensitive_variables

from ninja import Router, Body
from ninja.errors import HttpError

from apps.core import sessao
from apps.core.auth import exigir_grau_de_escrita
from apps.encomendas import fila_real, saques_fila
from apps.encomendas.marketplace import ErroMarketplace

router = Router()


def _admin(request, escrita=False):
    chaves = [os.environ.get('TOKENS_ACEITOS_ADMIN', ''), os.environ.get('TOKENS_ESCRITA_ADMIN', '')]
    if not any(c and hmac.compare_digest(str(request.auth or ''), c) for c in chaves):
        raise HttpError(403, 'Consulta reservada à página interna de clientes.')
    if escrita:
        exigir_grau_de_escrita(request)
    try:
        return sessao.site_desta_instalacao()
    except sessao.ConfiguracaoAusente:
        raise HttpError(503, 'A escola está indisponível agora.')


def _executar(funcao, **kwargs):
    try:
        return funcao(**kwargs)
    except ErroMarketplace as erro:
        raise HttpError(400, str(erro))


@router.get('/clientes-fila')
def lista(request):
    site = _admin(request)
    return {'clientes': fila_real.lista_clientes(site_id=site)}


@router.get('/clientes-fila/saques-manuais')
def saques_manuais(request):
    site = _admin(request)
    return _executar(saques_fila.listar_admin, site_id=site)


@router.post('/clientes-fila/saques-manuais/{saque_id}/pago')
@sensitive_variables('payload')
def pagar_saque_manual(request, saque_id: UUID, payload: dict = Body(...)):
    site = _admin(request, escrita=True)
    if payload.get('administrativo') is not True:
        raise HttpError(403, 'Somente a administração registra o Pix manual.')
    return _executar(saques_fila.confirmar, site_id=site, saque_id=saque_id,
        ator_id=str(payload.get('ator_id') or ''), dados=payload)


@router.get('/clientes-fila/acesso/{pessoa_id}')
def acesso(request, pessoa_id: str):
    site = _admin(request)
    cliente = fila_real.cliente_da_pessoa(site_id=site, pessoa_id=pessoa_id)
    if not cliente:
        raise HttpError(404, 'Cliente não autorizado.')
    return {'slug': cliente.slug, 'nome': cliente.nome, 'pessoa_id': cliente.pessoa_id, 'ativo': cliente.ativo}


@router.get('/clientes-fila/{slug}')
def detalhe(request, slug: str, pessoa_id: str = '', administrativo: bool = False):
    site = _admin(request)
    return _executar(fila_real.detalhe_cliente, site_id=site, slug=slug,
        pessoa_id=pessoa_id, administrativo=administrativo)


@router.post('/clientes-fila/{slug}/vincular')
def vincular(request, slug: str, payload: dict = Body(...)):
    site = _admin(request, escrita=True)
    if not payload.get('administrativo'):
        raise HttpError(403, 'Somente a administração vincula contas.')
    email = str(payload.get('email') or '').strip()
    if not email or len(email) > 254 or '@' not in email:
        raise HttpError(400, 'Informe o e-mail da conta existente.')
    try:
        pessoa_id = sessao.pessoa_por_email(email)
    except (sessao.VizinhaIndisponivel, sessao.ConfiguracaoAusente):
        raise HttpError(503, 'Não foi possível consultar a conta agora.')
    return _executar(fila_real.vincular_cliente, site_id=site, slug=slug, pessoa_id=pessoa_id)


@router.post('/clientes-fila/{slug}/pedidos')
def criar(request, slug: str, payload: dict = Body(...)):
    site = _admin(request, escrita=True)
    pedido = _executar(fila_real.criar_pedido, site_id=site, slug=slug,
        pessoa_id=str(payload.get('pessoa_id') or ''), dados=payload,
        administrativo=payload.get('administrativo') is True)
    return fila_real.dados_pedido(pedido)


@router.get('/clientes-fila/{slug}/pedidos/{pedido_id}')
def pedido(request, slug: str, pedido_id: UUID, pessoa_id: str = '', administrativo: bool = False):
    site = _admin(request)
    detalhe = _executar(fila_real.detalhe_cliente, site_id=site, slug=slug,
        pessoa_id=pessoa_id, administrativo=administrativo)
    item = next((p for p in detalhe['pedidos'] if p['id'] == str(pedido_id)), None)
    if not item:
        raise HttpError(404, 'Pedido não encontrado.')
    # Formulário recebe texto; a persistência conserva campos estruturados.
    item['briefing_dados'] = item['briefing']
    item['briefing'] = item['descricao']
    item['referencias'] = '\n'.join(item['referencias']) if isinstance(item['referencias'], list) else item['referencias']
    item['entregaveis'] = '\n'.join(item['entregaveis'])
    return item


@router.post('/clientes-fila/{slug}/pedidos/{pedido_id}')
def editar(request, slug: str, pedido_id: UUID, payload: dict = Body(...)):
    site = _admin(request, escrita=True)
    pedido = _executar(fila_real.editar_pedido, site_id=site, slug=slug, pedido_id=pedido_id,
        pessoa_id=str(payload.get('pessoa_id') or ''), dados=payload,
        administrativo=payload.get('administrativo') is True)
    return fila_real.dados_pedido(pedido)
