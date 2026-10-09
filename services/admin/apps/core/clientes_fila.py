"""Painel dos clientes da fila remunerada, servido pelo Admin e pela célula dona."""

import os
from datetime import datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import quote

import httpx
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables


class EncomendasIndisponiveis(Exception):
    pass


class EncomendasRecusaram(EncomendasIndisponiveis):
    pass


class ClientesFilaClient:
    BASE = "/clientes-fila"

    @sensitive_variables('dados', 'resposta', 'token')
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
        if resposta.status_code in (400, 409, 422):
            raise EncomendasRecusaram
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

    def saques_manuais(self):
        return self.pedir("GET", "/saques-manuais")

    def confirmar_saque_manual(self, saque_id, dados):
        return self.pedir(
            "POST", "/saques-manuais/" + quote(str(saque_id), safe="") + "/pago",
            dados=dados, escrita=True,
        )


def _admin(request):
    return bool(getattr(request, "admin", None))


def _admin_humano(request):
    admin = getattr(request, "admin", None) or {}
    return bool(admin and admin.get("id") != "conta-do-robo" and not admin.get("equipe_apenas"))


def _cpf_valido(cpf):
    if len(cpf) != 11 or len(set(cpf)) == 1:
        return False
    digitos = [int(c) for c in cpf]
    for tamanho in (9, 10):
        soma = sum(d * (tamanho + 1 - i) for i, d in enumerate(digitos[:tamanho]))
        verificador = (soma * 10) % 11
        if verificador == 10:
            verificador = 0
        if digitos[tamanho] != verificador:
            return False
    return True


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
        "situacao": situacao, "catalogo_curso": dados.get("catalogo_curso", {}),
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
    categorias = {"espadas_objetos", "pets", "cabelos", "chapeus", "personagens", "carros", "roupas", "livre"}
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
        "projeto_curso": (request.POST.get("projeto_curso") or "").strip(),
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


def _saques(request, *, erro="", status=200):
    if not _admin_humano(request):
        raise Http404
    try:
        dados = ClientesFilaClient().saques_manuais()
    except EncomendasIndisponiveis:
        return render(request, "admin/clientes_fila_indisponivel.html", status=503)
    saques = dados.get("saques", []) if isinstance(dados, dict) else []
    for saque in saques:
        for campo in ("solicitado_em", "pago_em"):
            if isinstance(saque.get(campo), str):
                try:
                    saque[campo] = datetime.fromisoformat(saque[campo])
                except ValueError:
                    saque[campo] = None
    resposta = render(request, "admin/saques_fila.html", {
        "saques": saques, "erro": erro,
        "mensagem": request.GET.get("mensagem", ""),
    }, status=status)
    resposta["Cache-Control"] = "private, no-store"
    resposta["Vary"] = "Cookie"
    return resposta


@require_GET
def saques_fila(request):
    return _saques(request)


@require_POST
@sensitive_post_parameters('pagador_cpf')
@sensitive_variables('cpf')
def saque_fila_pago(request, saque_id):
    if not _admin_humano(request):
        raise Http404
    referencia = (request.POST.get("referencia_pix") or "").strip()
    nome = (request.POST.get("pagador_nome") or "").strip()
    cpf = "".join(c for c in (request.POST.get("pagador_cpf") or "") if c.isdigit())
    email = (request.POST.get("pagador_email") or "").strip()
    if not referencia or len(nome.split()) < 2 or not _cpf_valido(cpf) or "@" not in email or len(email) > 254:
        return _saques(request, erro="Informe a referência do Pix e nome completo, CPF e e-mail de quem pagou.", status=400)
    ator_id = str(request.admin.get("id") or "")
    if not ator_id:
        return _saques(request, erro="Não foi possível identificar o administrador.", status=400)
    try:
        ClientesFilaClient().confirmar_saque_manual(saque_id, {
            "administrativo": True, "ator_id": ator_id,
            "referencia_pix": referencia, "pagador_nome": nome,
            "pagador_cpf": cpf, "pagador_email": email,
        })
    except EncomendasRecusaram:
        return _saques(request, erro="Registro recusado. Confira a referência e a situação do saque.", status=400)
    except EncomendasIndisponiveis:
        return _saques(request, erro="A Fila do Dólar não respondeu. Confira antes de tentar registrar novamente.", status=503)
    return HttpResponseRedirect(reverse("saques_fila") + "?mensagem=Pix registrado")

