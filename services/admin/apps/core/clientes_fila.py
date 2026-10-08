"""Painel dos clientes da fila remunerada, servido pelo Admin e pela célula dona."""

import os
from decimal import Decimal, InvalidOperation
from urllib.parse import quote

import httpx
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST


class EncomendasIndisponiveis(Exception):
    pass


class ClientesFilaClient:
    BASE = "/clientes-fila"

    def pedir(self, metodo, caminho="", *, dados=None, escrita=False):
        base = (os.environ.get("ENCOMENDAS_API_URL") or "").strip().rstrip("/")
        nome_token = "ENCOMENDAS_API_TOKEN_ESCRITA" if escrita else "ENCOMENDAS_API_TOKEN"
        token = (os.environ.get(nome_token) or "").strip()
        if not base or not token:
            raise EncomendasIndisponiveis
        try:
            resposta = httpx.request(
                metodo, base + self.BASE + caminho,
                headers={"Authorization": f"Bearer {token}"}, json=dados, timeout=5.0,
            )
        except httpx.HTTPError as erro:
            raise EncomendasIndisponiveis from erro
        if resposta.status_code == 404:
            raise Http404
        if resposta.status_code not in (200, 201):
            raise EncomendasIndisponiveis
        try:
            return resposta.json()
        except ValueError as erro:
            raise EncomendasIndisponiveis from erro

    def acesso(self, pessoa_id):
        return self.pedir("GET", "/acesso/" + quote(str(pessoa_id), safe=""))

    def lista(self):
        return self.pedir("GET")

    def detalhe(self, slug, *, pessoa_id="", administrativo=False):
        caminho = "/" + quote(slug, safe="")
        if pessoa_id:
            caminho += "?pessoa_id=" + quote(str(pessoa_id), safe="")
        if administrativo:
            caminho += ("&" if pessoa_id else "?") + "administrativo=1"
        return self.pedir("GET", caminho)

    def vincular(self, slug, email):
        return self.pedir("POST", "/" + quote(slug, safe="") + "/vincular", dados={"email": email, "administrativo": True}, escrita=True)

    def pedido(self, slug, dados, pedido_id=None):
        caminho = "/" + quote(slug, safe="") + "/pedidos"
        if pedido_id:
            caminho += "/" + quote(str(pedido_id), safe="")
        return self.pedir("POST", caminho, dados=dados, escrita=True)


def _admin(request):
    return bool(getattr(request, "admin", None))


def _cliente_do_caminho(request, slug):
    if _admin(request):
        return "", True
    cliente = getattr(request, "cliente_fila", None)
    if not isinstance(cliente, dict) or cliente.get("slug") != slug:
        raise Http404
    return str(cliente.get("pessoa_id") or ""), False


def _detalhe(request, slug, *, erro=""):
    pessoa_id, administrativo = _cliente_do_caminho(request, slug)
    try:
        dados = ClientesFilaClient().detalhe(slug, pessoa_id=pessoa_id, administrativo=administrativo)
    except EncomendasIndisponiveis:
        return render(request, "admin/clientes_fila_indisponivel.html", status=503)
    if not isinstance(dados, dict):
        return render(request, "admin/clientes_fila_indisponivel.html", status=503)
    situacao = request.GET.get("situacao", "todos")
    conjuntos = {
        "abertos": {"rascunho", "aguardando_pagamento", "na_fila", "oferecido"},
        "em_andamento": {"em_producao", "entregue", "em_ajuste", "mediacao"},
        "finalizados": {"aprovado"},
    }
    pedidos = dados.get("pedidos") or []
    for pedido in pedidos:
        pedido["descricao_form"] = pedido.get("descricao") or ""
        pedido["referencias_form"] = "\n".join(pedido.get("referencias") or [])
        pedido["entregaveis_form"] = "\n".join(pedido.get("entregaveis") or [])
        pedido["valor_reais_form"] = f"{int(pedido.get('valor_cents') or 0) / 100:.2f}".replace(".", ",")
    if situacao in conjuntos:
        dados["pedidos"] = [p for p in pedidos if p.get("status") in conjuntos[situacao]]
    return render(request, "admin/cliente_fila.html", {
        "cliente": dados, "administrativo": administrativo, "erro": erro,
        "situacao": situacao,
        "mensagem": request.GET.get("mensagem", ""),
    })


@require_GET
def clientes_fila(request):
    if not _admin(request):
        raise Http404
    try:
        dados = ClientesFilaClient().lista()
    except EncomendasIndisponiveis:
        return render(request, "admin/clientes_fila_indisponivel.html", status=503)
    clientes = dados if isinstance(dados, list) else dados.get("clientes", [])
    return render(request, "admin/clientes_fila.html", {"clientes": clientes})


@require_GET
def cliente_fila(request, slug):
    return _detalhe(request, slug)


@require_POST
def vincular_cliente_fila(request, slug):
    if not _admin(request):
        raise Http404
    email = (request.POST.get("email") or "").strip()
    if "@" not in email or len(email) > 254:
        return _detalhe(request, slug, erro="Informe o e-mail da conta deste cliente.")
    try:
        ClientesFilaClient().vincular(slug, email)
    except EncomendasIndisponiveis:
        return _detalhe(request, slug, erro="Não foi possível vincular a conta agora.")
    return HttpResponseRedirect(reverse("cliente_fila", args=[slug]) + "?mensagem=Conta vinculada")


@require_POST
def salvar_pedido_cliente_fila(request, slug, pedido_id=None):
    pessoa_id, administrativo = _cliente_do_caminho(request, slug)
    titulo = (request.POST.get("titulo") or "").strip()
    categoria = (request.POST.get("categoria") or "").strip()
    briefing = (request.POST.get("briefing") or "").strip()
    categorias = {"espadas_objetos", "pets", "cabelos", "chapeus", "personagens"}
    try:
        valor_reais = Decimal((request.POST.get("valor_reais") or "").strip().replace(",", "."))
        if not valor_reais.is_finite() or valor_reais.as_tuple().exponent < -2:
            raise InvalidOperation
        valor_cents = int(valor_reais * 100)
    except (InvalidOperation, ValueError):
        valor_cents = 0
    entregaveis = (request.POST.get("entregaveis") or "").strip()
    if not titulo or not briefing or not entregaveis or categoria not in categorias or valor_cents < 1:
        return _detalhe(request, slug, erro="Preencha título, categoria, descrição, entregáveis e valor.")
    dados = {
        "titulo": titulo, "categoria": categoria, "briefing": briefing,
        "referencias": (request.POST.get("referencias") or "").strip(),
        "entregaveis": entregaveis,
        "valor_cents": valor_cents, "quantidade": 1, "prazo_horas": 48,
        "pessoa_id": pessoa_id, "administrativo": administrativo,
    }
    try:
        ClientesFilaClient().pedido(slug, dados, pedido_id=pedido_id)
    except EncomendasIndisponiveis:
        return _detalhe(request, slug, erro="Não foi possível salvar o pedido agora.")
    return HttpResponseRedirect(reverse("cliente_fila", args=[slug]) + "?mensagem=Pedido salvo")


@require_POST
def orientar_pedido_cliente_fila(request, slug, pedido_id):
    pessoa_id, administrativo = _cliente_do_caminho(request, slug)
    observacoes = (request.POST.get("observacoes_cliente") or "").strip()
    if not observacoes:
        return _detalhe(request, slug, erro="Escreva a orientação para o aluno.")
    try:
        ClientesFilaClient().pedido(slug, {
            "observacoes_cliente": observacoes,
            "pessoa_id": pessoa_id, "administrativo": administrativo,
        }, pedido_id=pedido_id)
    except EncomendasIndisponiveis:
        return _detalhe(request, slug, erro="Não foi possível enviar a orientação agora.")
    return HttpResponseRedirect(reverse("cliente_fila", args=[slug]) + "?mensagem=Orientação enviada")

