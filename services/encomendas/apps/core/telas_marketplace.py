"""Telas do marketplace, sempre atrás da sessão e das autorizações por site."""

from __future__ import annotations

import uuid
import hashlib
import json
import base64
from decimal import Decimal, InvalidOperation
from pathlib import Path
from types import SimpleNamespace

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import FileResponse, Http404, HttpResponseRedirect, JsonResponse, QueryDict
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.core import plantao, sessao
from apps.core.selecionar_marketplace import alunos_para_selecao, preparar_perfil_sem_titulo
from apps.encomendas import marketplace as negocio
from apps.encomendas.models import PerfilProfissional
from apps.encomendas.models import (
    ArquivoMarketplace, AutorizacaoMarketplaceAluno,
    AutorizacaoMarketplaceCliente, EntregaMarketplace, FaseMarketplace,
    MensagemMarketplace, OfertaMarketplace, PedidoMarketplace, RecebivelMarketplace,
    RecargaMarketplace, SaqueMarketplace,
)


CATEGORIAS = (
    ("espadas_objetos", "Espadas e objetos", "Armas, itens e objetos de jogo"),
    ("pets", "Pets", "Animais e criaturas"),
    ("cabelos", "Cabelos", "Penteados e estilos"),
    ("chapeus", "Chapéus", "Chapéus e itens de cabeça"),
    ("personagens", "Personagens", "Avatares e personagens"),
)
NOMES_LEGADOS = {"acessorios": "Acessórios", "animacoes": "Animações"}
ENTREGAVEIS = (
    ("modelo_fbx", "Modelo em FBX"), ("arquivo_fonte", "Arquivo editável"),
    ("texturas", "Texturas"), ("previa", "Prévia"),
    ("rig", "Rig"),
)
PAGAMENTO_STATUS = {
    "absent": "Ainda não iniciado", "created": "Aguardando confirmação",
    "pending": "Aguardando confirmação", "approved": "Confirmado",
    "captured": "Confirmado", "denied": "Não confirmado",
    "failed": "Não confirmado", "canceled": "Cancelado",
    "expired": "Vencido", "rejected": "Não confirmado",
    "refunded": "Estornado", "partially_refunded": "Parcialmente estornado",
    "charged_back": "Contestado", "cancelled": "Cancelado",
    "indisponivel": "Indisponível no momento",
}


def _entrada(request):
    pessoa = sessao.quem_e(request)
    try:
        site = sessao.site_desta_instalacao()
    except sessao.ConfiguracaoAusente:
        site = None
    if not pessoa or not site:
        raise Http404
    return site, pessoa


def _equipe(request):
    site, pessoa = _entrada(request)
    if not plantao.e_do_plantao(pessoa):
        raise Http404
    return site, pessoa


def _cliente(request):
    site, pessoa = _entrada(request)
    if not negocio.acesso_cliente(site_id=site, cliente_id=pessoa):
        raise Http404
    return site, pessoa


def _aluno(request):
    site, pessoa = _entrada(request)
    if not negocio.acesso_aluno(site_id=site, pessoa_id=pessoa):
        raise Http404
    return site, pessoa


def _papel(request, pedido):
    site, pessoa = _entrada(request)
    if pedido.site_id != site:
        raise Http404
    if plantao.e_do_plantao(pessoa):
        return site, pessoa, "equipe"
    if pedido.cliente_id == pessoa and negocio.acesso_cliente(site_id=site, cliente_id=pessoa):
        return site, pessoa, "cliente"
    if (pedido.aluno_id and pedido.aluno.pessoa_id == pessoa
            and negocio.acesso_aluno(site_id=site, pessoa_id=pessoa)):
        return site, pessoa, "aluno"
    if (negocio.acesso_aluno(site_id=site, pessoa_id=pessoa)
            and OfertaMarketplace.objects.filter(pedido=pedido, aluno__pessoa_id=pessoa,
                                                  status="pendente").exists()):
        return site, pessoa, "aluno"
    raise Http404


def _pedido(pedido_id, site):
    return PedidoMarketplace.objects.filter(pk=pedido_id, site_id=site).select_related("aluno").first()


def _voltar(nome, *args, recado=""):
    destino = reverse(nome, args=args)
    if recado:
        destino += "?recado=" + recado
    return HttpResponseRedirect(destino)


def _falha(request, texto, *, status=400):
    return render(request, "marketplace/aviso.html", {"titulo": "Confira este passo", "texto": texto}, status=status)


def _contexto(request, papel, **extra):
    return {"papel": papel, "recado": request.GET.get("recado", ""), **extra}


def _dados(request):
    categoria = request.POST.get("categoria", "espadas_objetos")
    if categoria not in {chave for chave, _, _ in CATEGORIAS}:
        raise negocio.ErroMarketplace("Escolha uma das cinco categorias disponíveis.")
    entregue = request.POST.getlist("entregaveis")
    def inteiro(chave, padrao=0):
        try:
            valor = request.POST.get(chave, padrao)
            return int(valor) if str(valor).strip() else padrao
        except (TypeError, ValueError):
            raise negocio.ErroMarketplace("Confira os números do pedido.")
    modelos = inteiro("modelos", 1)
    if modelos < 1 or modelos > 1000:
        raise negocio.ErroMarketplace("Confira a quantidade de modelos.")
    valor_texto = request.POST.get("valor_reais")
    if valor_texto is None:
        valor_cents = inteiro("valor_cents")
    elif not valor_texto.strip():
        valor_cents = 0
    else:
        try:
            valor = Decimal(valor_texto.strip().replace(",", "."))
            if not valor.is_finite():
                raise InvalidOperation
        except (InvalidOperation, TypeError):
            raise negocio.ErroMarketplace("Confira o valor total oferecido.")
        if valor <= 0 or valor.as_tuple().exponent < -2:
            raise negocio.ErroMarketplace("Escreva o valor em reais e centavos.")
        valor_cents = int(valor * 100)
    return {
        "cartao": request.POST.get("cartao", "item_simples"),
        "categoria": categoria,
        "titulo": request.POST.get("titulo", "").strip(),
        "quantidade": inteiro("quantidade", 1),
        "modelos": [f"Modelo {indice}" for indice in range(1, modelos + 1)],
        "variacoes": inteiro("variacoes"),
        "destino": request.POST.get("destino", "").strip(),
        "plataforma": request.POST.get("plataforma", "").strip(),
        "estilo": request.POST.get("estilo", "").strip(),
        "observacoes": request.POST.get("observacoes", "").strip(),
        "entregaveis": entregue,
        "ajustes_inclusos": inteiro("ajustes"),
        "valor_cents": valor_cents,
        "prazo_quantidade": inteiro("prazo_quantidade"),
        "prazo_unidade": request.POST.get("prazo_unidade", "dias_corridos"),
    }


def _formatar_valor(pedido):
    pedido.valor_exibido = f"R$ {pedido.valor_cents // 100:,}".replace(",", ".") + f",{pedido.valor_cents % 100:02d}"
    pedido.valor_formulario = f"{pedido.valor_cents // 100},{pedido.valor_cents % 100:02d}"
    pedido.categoria_exibida = next((nome for chave, nome, _ in CATEGORIAS if chave == pedido.categoria),
                                    NOMES_LEGADOS.get(pedido.categoria, pedido.categoria))
    nomes = dict(ENTREGAVEIS)
    pedido.entregaveis_exibidos = [nomes.get(chave, chave) for chave in (pedido.briefing or {}).get("entregaveis", [])]
    return pedido


def _imagem_pix(pix: dict) -> str:
    try:
        imagem = base64.b64decode(pix.get("qr_code_base64") or "", validate=True)
        if imagem.startswith(b"\x89PNG\r\n\x1a\n") and len(imagem) <= 256_000:
            return "data:image/png;base64," + base64.b64encode(imagem).decode("ascii")
    except (ValueError, TypeError, base64.binascii.Error):
        pass
    return ""


@require_GET
def escola(request):
    site, _ = _equipe(request)
    from apps.core.financeiro_marketplace import situacao_do_ambiente
    from apps.core import carteira_marketplace
    fase = FaseMarketplace.objects.filter(site_id=site).first()
    pedidos = list(PedidoMarketplace.objects.filter(site_id=site).order_by("-criado_em")[:100])
    alunos = alunos_para_selecao(site_id=site, perfis=list(
        PerfilProfissional.objects.filter(site_id=site).select_related("pessoa").order_by("pessoa_id")[:200]
    ))
    autorizados_alunos = set(AutorizacaoMarketplaceAluno.objects.filter(site_id=site, ativa=True).values_list("pessoa_id", flat=True))
    autorizados_clientes = list(AutorizacaoMarketplaceCliente.objects.filter(site_id=site).order_by("cliente_id"))
    for aluno in alunos:
        aluno.marketplace_autorizado = aluno.pessoa_id in autorizados_alunos
    saques = []
    try:
        saques = carteira_marketplace.saques_da_escola(site_id=site)
        for saque in saques:
            saque["creditos"] = saque["amount_cents"] // 100
    except (carteira_marketplace.PagamentoIndisponivel, carteira_marketplace.PagamentoDivergente):
        pass
    return render(request, "marketplace/escola.html", _contexto(request, "equipe", fase=fase,
        pedidos=pedidos, alunos=alunos, clientes=autorizados_clientes, saques=saques,
        pagamentos=situacao_do_ambiente(),
        fila=PedidoMarketplace.objects.filter(site_id=site, status="na_fila").count(),
        producao=PedidoMarketplace.objects.filter(site_id=site, status="em_producao").count(),
        entregues=PedidoMarketplace.objects.filter(site_id=site, status="aprovado").count()))


@require_POST
def autorizar(request, tipo):
    site, operador = _equipe(request)
    pessoa_id = request.POST.get("pessoa_id", "").strip()
    if tipo == "cliente" and request.POST.get("email", "").strip():
        email_cliente = request.POST["email"].strip()
        if len(email_cliente) > 254 or "@" not in email_cliente:
            return _falha(request, "Confira o e-mail da conta do cliente.")
        try:
            pessoa_id = sessao.pessoa_por_email(email_cliente) or ""
        except (sessao.VizinhaIndisponivel, sessao.ConfiguracaoAusente):
            return _falha(request, "Não foi possível consultar a conta do cliente agora. Tente novamente.", status=503)
        if not pessoa_id:
            return _falha(request, "Não encontramos uma conta com este e-mail no site.")
    if not pessoa_id or len(pessoa_id) > 200:
        return _falha(request, "Informe a pessoa cadastrada no site.")
    if tipo == "aluno":
        if (request.POST.get("ativa") == "sim"
                and not PerfilProfissional.objects.filter(site_id=site, pessoa_id=pessoa_id).exists()):
            email = request.POST.get("email", "").strip()
            alunos = alunos_para_selecao(site_id=site, perfis=list(
                PerfilProfissional.objects.filter(site_id=site).select_related("pessoa")[:200]
            ))
            selecionado = next((aluno for aluno in alunos if aluno.pessoa_id == pessoa_id
                               and aluno.email == email and aluno.matricula_situacao == "Ativa"), None)
            if not selecionado:
                return _falha(request, "Este aluno não consta na lista atual da escola.")
            try:
                preparar_perfil_sem_titulo(site_id=site, pessoa_id=pessoa_id, email=email)
            except (ValueError, sessao.VizinhaIndisponivel, sessao.ConfiguracaoAusente):
                return _falha(request, "Não foi possível conferir a matrícula e a conta deste aluno agora.", status=503)
    elif tipo == "cliente":
        pass
    else:
        raise Http404
    try:
        if tipo == "aluno":
            negocio.autorizar_aluno(site_id=site, pessoa_id=pessoa_id,
                                    ativa=request.POST.get("ativa") == "sim", quem=operador)
        else:
            negocio.autorizar_cliente(site_id=site, cliente_id=pessoa_id,
                                      ativa=request.POST.get("ativa") == "sim", quem=operador)
    except negocio.ErroMarketplace as erro:
        return _falha(request, str(erro))
    return _voltar("marketplace_escola", recado="Autorização atualizada.")


@require_POST
def alterar_fase(request, tipo):
    site, operador = _equipe(request)
    liberar = request.POST.get("liberar") == "sim"
    if tipo == "alunos":
        negocio.configurar_fase(site_id=site, quem=operador, alunos_liberados=liberar)
    elif tipo == "clientes":
        negocio.configurar_fase(site_id=site, quem=operador, clientes_liberados=liberar)
    else:
        raise Http404
    return _voltar("marketplace_escola", recado="Fase atualizada.")


@require_GET
def cliente(request):
    site, pessoa = _cliente(request)
    pedidos = [_formatar_valor(p) for p in PedidoMarketplace.objects.filter(site_id=site, cliente_id=pessoa).order_by("-criado_em")]
    from apps.core import carteira_marketplace
    carteira = None
    recarga = RecargaMarketplace.objects.filter(site_id=site, cliente_id=pessoa).order_by("-criada_em").first()
    if recarga:
        recarga.creditos = recarga.valor_cents // 100
    cobranca_recarga = None
    try:
        if recarga and recarga.charge_id:
            cobranca_recarga = carteira_marketplace.consultar_recarga(
                site_id=site, cliente_id=pessoa, charge_id=recarga.charge_id,
            )
        carteira = carteira_marketplace.saldo(site_id=site, pessoa_id=pessoa, tipo="client")
    except (carteira_marketplace.PagamentoIndisponivel, carteira_marketplace.PagamentoDivergente):
        pass
    return render(request, "marketplace/cliente.html", _contexto(request, "cliente", pedidos=pedidos,
        categorias=CATEGORIAS, carteira=carteira, recarga=recarga,
        cobranca_recarga=cobranca_recarga,
        recarga_chave=recarga.pk if recarga and not recarga.charge_id else uuid.uuid4(),
        pix_imagem_recarga=_imagem_pix((cobranca_recarga or {}).get("pix") or {}),
        recarga_status=PAGAMENTO_STATUS.get((cobranca_recarga or {}).get("status"), "Em verificação")))


@require_POST
def recarregar(request):
    site, pessoa = _cliente(request)
    from apps.core import carteira_marketplace
    try:
        creditos = int(request.POST.get("creditos", "0"))
        if creditos < 1:
            raise ValueError()
        email = request.POST.get("email", "").strip()
        validate_email(email)
        nome = request.POST.get("nome", "").strip()
        cpf = request.POST.get("cpf", "").strip()
        recarga, _ = RecargaMarketplace.objects.get_or_create(
            pk=uuid.UUID(request.POST["chave"]), defaults={
                "site_id": site, "cliente_id": pessoa, "valor_cents": creditos * 100,
            },
        )
        if (recarga.site_id, recarga.cliente_id, recarga.valor_cents) != (site, pessoa, creditos * 100):
            raise ValueError()
        if recarga.charge_id:
            carteira_marketplace.consultar_recarga(
                site_id=site, cliente_id=pessoa, charge_id=recarga.charge_id,
            )
        else:
            resultado = carteira_marketplace.iniciar_recarga(
                site_id=site, cliente_id=pessoa, valor_cents=recarga.valor_cents,
                chave_idempotencia=str(recarga.pk), email=email, nome=nome, cpf=cpf,
            )
            recarga.charge_id = str(resultado["id"])
            recarga.save(update_fields=["charge_id"])
    except (ValueError, KeyError, ValidationError,
            carteira_marketplace.PagamentoDivergente) as erro:
        return _falha(request, "Confira os créditos, nome completo, CPF e e-mail do pagador.")
    except carteira_marketplace.PagamentoIndisponivel:
        return _voltar("marketplace_cliente", recado="A recarga ainda não foi confirmada. Confira a situação antes de tentar outra vez.")
    return _voltar("marketplace_cliente", recado="Código Pix gerado. Pague e acompanhe a confirmação nesta página.")


@require_GET
def novo(request):
    _cliente(request)
    categoria = request.GET.get("categoria", "espadas_objetos")
    if categoria not in {x[0] for x in CATEGORIAS}:
        categoria = CATEGORIAS[0][0]
    return render(request, "marketplace/editar.html", _contexto(request, "cliente", categorias=CATEGORIAS,
        entregaveis=ENTREGAVEIS, categoria=categoria, pedido=None))


@require_GET
def editar(request, pedido_id):
    site, pessoa = _cliente(request)
    pedido = _pedido(pedido_id, site)
    if not pedido or pedido.cliente_id != pessoa or pedido.status != "rascunho":
        raise Http404
    return render(request, "marketplace/editar.html", _contexto(request, "cliente", categorias=CATEGORIAS,
        entregaveis=ENTREGAVEIS, pedido=_formatar_valor(pedido), categoria=pedido.categoria,
        referencias=ArquivoMarketplace.objects.filter(pedido=pedido, papel="referencia").order_by("criado_em")))


@require_POST
def salvar(request, pedido_id=None):
    site, pessoa = _cliente(request)
    if pedido_id is None and request.POST.get("pedido_id"):
        try:
            pedido_id = uuid.UUID(request.POST["pedido_id"])
        except ValueError:
            raise Http404
    if pedido_id:
        pedido = _pedido(pedido_id, site)
        if not pedido or pedido.cliente_id != pessoa or pedido.status != "rascunho":
            raise Http404
    try:
        pedido = negocio.salvar_rascunho(site_id=site, cliente_id=pessoa, dados=_dados(request), pedido_id=pedido_id)
    except (ValueError, negocio.ErroMarketplace) as erro:
        return _falha(request, str(erro))
    return _voltar("marketplace_editar", pedido.pk, recado="Rascunho salvo.")


@require_POST
def autosave(request):
    site, pessoa = _cliente(request)
    try:
        corpo = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"erro": "Não foi possível salvar agora."}, status=400)
    if not isinstance(corpo, dict):
        return JsonResponse({"erro": "Dados do pedido inválidos."}, status=400)
    pedido_id = corpo.get("pedido_id") or None
    if pedido_id:
        try:
            pedido_id = uuid.UUID(str(pedido_id))
        except ValueError:
            raise Http404
        pedido = _pedido(pedido_id, site)
        if not pedido or pedido.cliente_id != pessoa or pedido.status != "rascunho":
            raise Http404
    campos = QueryDict(mutable=True)
    for chave, valor in corpo.items():
        if chave in {"pedido_id", "entregaveis"}:
            continue
        if isinstance(valor, (str, int)):
            campos[chave] = str(valor)
    campos.setlist("entregaveis", [str(v) for v in corpo.get("entregaveis", []) if isinstance(v, str)])
    try:
        pedido = negocio.salvar_rascunho(site_id=site, cliente_id=pessoa,
                                         dados=_dados(SimpleNamespace(POST=campos)), pedido_id=pedido_id)
    except (ValueError, negocio.ErroMarketplace) as erro:
        return JsonResponse({"erro": str(erro)}, status=400)
    return JsonResponse({"pedido_id": str(pedido.pk), "versao": pedido.versao,
                         "editar_url": reverse("marketplace_editar", args=[pedido.pk])})


@require_POST
def repetir(request, pedido_id):
    site, pessoa = _cliente(request)
    pedido = _pedido(pedido_id, site)
    if not pedido or pedido.cliente_id != pessoa:
        raise Http404
    try:
        copia = negocio.repetir_pedido(site_id=site, cliente_id=pessoa, pedido_id=pedido_id)
    except (ValueError, negocio.ErroMarketplace) as erro:
        return _falha(request, str(erro))
    return _voltar("marketplace_editar", copia.pk)


@require_POST
def publicar(request, pedido_id):
    site, pessoa = _cliente(request)
    pedido = _pedido(pedido_id, site)
    if not pedido or pedido.cliente_id != pessoa:
        raise Http404
    try:
        negocio.publicar_pedido(site_id=site, cliente_id=pessoa, pedido_id=pedido_id,
                                versao=int(request.POST.get("versao", "0")))
    except (ValueError, negocio.ErroMarketplace) as erro:
        return _falha(request, str(erro))
    return _voltar("marketplace_pedido", pedido_id, recado="Pedido publicado. Confira o pagamento.")


@require_GET
def pedido(request, pedido_id):
    site, _ = _entrada(request)
    projeto = _pedido(pedido_id, site)
    if not projeto:
        raise Http404
    _, pessoa, papel = _papel(request, projeto)
    arquivos = list(ArquivoMarketplace.objects.filter(pedido=projeto).order_by("criado_em"))
    entregas = list(EntregaMarketplace.objects.filter(pedido=projeto).order_by("-versao"))
    mensagens = list(MensagemMarketplace.objects.filter(pedido=projeto).order_by("criada_em"))
    ofertas = list(OfertaMarketplace.objects.filter(pedido=projeto, aluno__pessoa_id=pessoa).order_by("-oferecida_em")) if papel == "aluno" else []
    recebivel = RecebivelMarketplace.objects.filter(pedido=projeto).first()
    cobranca = None
    carteira = None
    if papel == "cliente" and projeto.status == "aguardando_pagamento":
        from apps.core import carteira_marketplace
        try:
            carteira = carteira_marketplace.saldo(site_id=site, pessoa_id=pessoa, tipo="client")
        except (carteira_marketplace.PagamentoIndisponivel, carteira_marketplace.PagamentoDivergente):
            pass
    if papel in {"cliente", "equipe"} and not projeto.pagamento_referencia.startswith("wallet-spend:"):
        from apps.core import financeiro_marketplace
        try:
            cobranca = financeiro_marketplace.consultar_cobranca(projeto)
        except Exception:
            cobranca = {"status": "indisponivel"}
        # A consulta pode confirmar o Pix e mover o pedido para a fila.
        projeto.refresh_from_db()
    pix_imagem = _imagem_pix((cobranca or {}).get("pix") or {}) if papel == "cliente" else ""
    return render(request, "marketplace/pedido.html", _contexto(request, papel, pedido=_formatar_valor(projeto),
        arquivos=arquivos, entregas=entregas, mensagens=mensagens, ofertas=ofertas,
        recebivel=recebivel, cobranca=cobranca, pix_imagem=pix_imagem, carteira=carteira,
        cobranca_status=PAGAMENTO_STATUS.get((cobranca or {}).get("status"), "Em verificação"),
        agora=timezone.now()))


@require_GET
def pedido_cliente(request, pedido_id):
    site, pessoa = _cliente(request)
    projeto = _pedido(pedido_id, site)
    if not projeto or projeto.cliente_id != pessoa:
        raise Http404
    return pedido(request, pedido_id)


@require_POST
def comprar_com_creditos(request, pedido_id):
    site, pessoa = _cliente(request)
    projeto = _pedido(pedido_id, site)
    if not projeto or projeto.cliente_id != pessoa:
        raise Http404
    from apps.core import carteira_marketplace
    if projeto.pagamento_referencia == f"wallet-spend:{projeto.pk}":
        return _voltar("marketplace_pedido", pedido_id, recado="A compra com créditos já foi registrada.")
    try:
        carteira_marketplace.usar_creditos(projeto)
        negocio.confirmar_pagamento(
            site_id=site, pedido_id=pedido_id, versao=projeto.versao,
            valor_cents=projeto.valor_cents, moeda=projeto.moeda,
            ambiente=projeto.ambiente, referencia=f"wallet-spend:{projeto.pk}",
        )
    except (carteira_marketplace.PagamentoIndisponivel,
            carteira_marketplace.PagamentoDivergente, negocio.ErroMarketplace):
        return _falha(request, "Não foi possível usar os créditos agora. Confira o saldo e tente novamente.", status=503)
    return _voltar("marketplace_pedido", pedido_id, recado="Créditos usados. Seu pedido entrou na fila.")


@require_POST
def cobrar(request, pedido_id):
    site, pessoa = _cliente(request)
    projeto = _pedido(pedido_id, site)
    if not projeto or projeto.cliente_id != pessoa:
        raise Http404
    return _falha(request, "Compre créditos na carteira do cliente e use-os neste pedido.")


@require_POST
def confirmar_paypal(request, pedido_id):
    site, pessoa = _cliente(request)
    projeto = _pedido(pedido_id, site)
    if not projeto or projeto.cliente_id != pessoa:
        raise Http404
    from apps.core import financeiro_marketplace
    try:
        financeiro_marketplace.consultar_cobranca(projeto, capturar_paypal=True)
    except Exception:
        return _falha(request, "O PayPal ainda não confirmou este pagamento. Confira novamente mais tarde.", status=503)
    return _voltar("marketplace_pedido", pedido_id, recado="Situação do pagamento atualizada.")


@require_GET
def retorno_paypal(request, pedido_id):
    site, pessoa = _cliente(request)
    projeto = _pedido(pedido_id, site)
    if not projeto or projeto.cliente_id != pessoa:
        raise Http404
    return _voltar("marketplace_pedido", pedido_id,
                   recado="Confira o pagamento PayPal nesta página.")


@require_GET
def fila(request):
    site, pessoa = _aluno(request)
    from apps.core import carteira_marketplace
    perfil = PerfilProfissional.objects.filter(site_id=site, pessoa_id=pessoa).first()
    ofertas = OfertaMarketplace.objects.filter(pedido__site_id=site, aluno=perfil).select_related("pedido").order_by("-oferecida_em") if perfil else []
    trabalhos = PedidoMarketplace.objects.filter(site_id=site, aluno=perfil).exclude(status="rascunho").order_by("-criado_em") if perfil else []
    carteira = None
    try:
        carteira = carteira_marketplace.extrato_aluno(site_id=site, aluno_id=pessoa)
        for saque in carteira.get("withdrawals", []):
            saque["creditos"] = saque["amount_cents"] // 100
    except (carteira_marketplace.PagamentoIndisponivel, carteira_marketplace.PagamentoDivergente):
        pass
    saque_pendente = SaqueMarketplace.objects.filter(
        site_id=site, aluno_id=pessoa, registrado_no_ledger=False,
    ).order_by("-solicitado_em").first()
    if saque_pendente:
        saque_pendente.creditos = saque_pendente.valor_cents // 100
    return render(request, "marketplace/fila.html", _contexto(request, "aluno", perfil=perfil,
        ofertas=ofertas, trabalhos=trabalhos, carteira=carteira,
        saque_pendente=saque_pendente, saque_chave=uuid.uuid4()))


@require_POST
def sacar(request):
    site, pessoa = _aluno(request)
    from apps.core import carteira_marketplace
    try:
        creditos = int(request.POST.get("creditos", "0"))
        if creditos < 50:
            raise ValueError()
        saque_id = request.POST.get("saque_id")
        if saque_id:
            saque = SaqueMarketplace.objects.get(
                pk=uuid.UUID(saque_id), site_id=site, aluno_id=pessoa,
                valor_cents=creditos * 100,
            )
        else:
            saque, _ = SaqueMarketplace.objects.get_or_create(
                id=uuid.UUID(request.POST["chave"]), defaults={
                    "site_id": site, "aluno_id": pessoa, "valor_cents": creditos * 100,
                },
            )
            if (saque.site_id, saque.aluno_id, saque.valor_cents) != (site, pessoa, creditos * 100):
                raise ValueError()
        resultado = carteira_marketplace.solicitar_saque(
            site_id=site, aluno_id=pessoa, valor_cents=saque.valor_cents,
            chave_idempotencia=str(saque.pk),
        )
        saque.registrado_no_ledger = True
        saque.save(update_fields=["registrado_no_ledger"])
    except (ValueError, KeyError, SaqueMarketplace.DoesNotExist,
            carteira_marketplace.PagamentoDivergente):
        return _falha(request, "O saque exige pelo menos 50 créditos disponíveis.")
    except carteira_marketplace.PagamentoIndisponivel:
        return _voltar("marketplace_fila", recado="A solicitação ainda está em verificação. Confira antes de pedir outra vez.")
    return _voltar("marketplace_fila", recado="Saque solicitado. A transferência ainda não foi confirmada.")


@require_POST
def disponibilidade(request):
    site, pessoa = _aluno(request)
    perfil = PerfilProfissional.objects.filter(site_id=site, pessoa_id=pessoa).first()
    if not perfil:
        raise Http404
    from apps.encomendas import gestos
    resultado = (gestos.religar(perfil.pk, timezone.now(), site_id=site)
                 if request.POST.get("acao") == "disponivel" else gestos.pausar(perfil.pk, site_id=site))
    return _voltar("marketplace_fila", recado="Disponibilidade atualizada." if resultado.feito else "Não foi possível mudar a disponibilidade agora.")


@require_POST
def responder_oferta(request, oferta_id, acao):
    site, pessoa = _aluno(request)
    oferta = OfertaMarketplace.objects.filter(pk=oferta_id, pedido__site_id=site,
        aluno__pessoa_id=pessoa).select_related("pedido").first()
    if not oferta:
        raise Http404
    try:
        if acao == "aceitar":
            negocio.aceitar_oferta(site_id=site, pessoa_id=pessoa, oferta_id=oferta_id)
        elif acao == "passar":
            negocio.passar_oferta(site_id=site, pessoa_id=pessoa, oferta_id=oferta_id,
                                  motivo=request.POST.get("motivo", ""))
        else:
            raise Http404
    except (ValueError, negocio.ErroMarketplace) as erro:
        return _falha(request, str(erro))
    return _voltar("marketplace_pedido", oferta.pedido_id)


@require_POST
def mensagem(request, pedido_id):
    site, _ = _entrada(request)
    projeto = _pedido(pedido_id, site)
    if not projeto:
        raise Http404
    _, pessoa, papel = _papel(request, projeto)
    texto = request.POST.get("texto", "").strip()
    if not texto:
        return _falha(request, "Escreva sua mensagem.")
    try:
        negocio.registrar_mensagem(site_id=site, pedido_id=pedido_id, ator_id=pessoa,
            papel=papel, texto=texto, entrega_id=request.POST.get("entrega_id") or None)
    except (ValueError, negocio.ErroMarketplace) as erro:
        return _falha(request, str(erro))
    return _voltar("marketplace_pedido", pedido_id)


def _pasta_privada():
    pasta = Path(getattr(settings, "MARKETPLACE_UPLOAD_ROOT", Path(settings.BASE_DIR) / "marketplace_uploads"))
    pasta.mkdir(mode=0o700, parents=True, exist_ok=True)
    return pasta


@require_POST
def enviar_arquivo(request, pedido_id):
    site, _ = _entrada(request)
    projeto = _pedido(pedido_id, site)
    if not projeto:
        raise Http404
    _, pessoa, papel_ator = _papel(request, projeto)
    papel = request.POST.get("papel", "")
    if papel not in {"referencia", "final", "previa"} or (papel_ator == "cliente" and papel != "referencia") or (papel_ator == "aluno" and papel == "referencia"):
        raise Http404
    recebido = request.FILES.get("arquivo")
    if not recebido:
        return _falha(request, "Escolha um arquivo.")
    chave = uuid.uuid4().hex
    caminho = _pasta_privada() / chave
    try:
        resumo = hashlib.sha256()
        tamanho = 0
        with caminho.open("xb") as destino:
            for bloco in recebido.chunks():
                destino.write(bloco)
                resumo.update(bloco)
                tamanho += len(bloco)
        negocio.adicionar_arquivo(site_id=site, pedido_id=pedido_id, ator_id=pessoa,
            papel=papel, nome=str(recebido.name).replace("\\", "/").split("/")[-1], chave=chave,
            legenda=request.POST.get("legenda", "").strip(), tamanho_bytes=tamanho,
            tipo_mime=recebido.content_type or "", sha256=resumo.hexdigest(),
            versao_exportacao=request.POST.get("versao_exportacao", "").strip(),
            ator_papel=papel_ator)
    except (ValueError, negocio.ErroMarketplace) as erro:
        caminho.unlink(missing_ok=True)
        return _falha(request, str(erro))
    except Exception:
        caminho.unlink(missing_ok=True)
        raise
    return _voltar("marketplace_pedido", pedido_id, recado="Arquivo recebido.")


@require_GET
def baixar_arquivo(request, arquivo_id):
    site, pessoa = _entrada(request)
    arquivo = ArquivoMarketplace.objects.filter(pk=arquivo_id, site_id=site).select_related("pedido").first()
    if not arquivo:
        raise Http404
    _, _, papel = _papel(request, arquivo.pedido)
    try:
        negocio.arquivo_autorizado(site_id=site, arquivo_id=arquivo_id, ator_id=pessoa, papel=papel)
    except (ValueError, negocio.ErroMarketplace):
        raise Http404
    chave = arquivo.chave
    if not chave or Path(chave).name != chave:
        raise Http404
    caminho = _pasta_privada() / chave
    if not caminho.is_file():
        raise Http404
    resposta = FileResponse(caminho.open("rb"), as_attachment=True, filename=arquivo.nome)
    resposta["X-Content-Type-Options"] = "nosniff"
    resposta["Cache-Control"] = "private, no-store"
    return resposta


@require_POST
def entregar(request, pedido_id):
    site, pessoa = _aluno(request)
    projeto = _pedido(pedido_id, site)
    if not projeto or not projeto.aluno_id or projeto.aluno.pessoa_id != pessoa:
        raise Http404
    try:
        ids = [uuid.UUID(x) for x in request.POST.getlist("arquivos")]
        negocio.enviar_entrega(site_id=site, pedido_id=pedido_id, pessoa_id=pessoa,
            arquivos_ids=ids, comentario=request.POST.get("comentario", ""))
    except (ValueError, negocio.ErroMarketplace) as erro:
        return _falha(request, str(erro))
    return _voltar("marketplace_pedido", pedido_id, recado="Entrega enviada.")


@require_POST
def avaliar(request, pedido_id, acao):
    site, pessoa = _cliente(request)
    projeto = _pedido(pedido_id, site)
    if not projeto or projeto.cliente_id != pessoa:
        raise Http404
    try:
        entrega_id = uuid.UUID(request.POST.get("entrega_id", ""))
        if acao == "aprovar":
            negocio.aprovar_entrega(site_id=site, pedido_id=pedido_id, cliente_id=pessoa,
                                    entrega_id=entrega_id)
        elif acao == "ajuste":
            negocio.pedir_ajuste(site_id=site, pedido_id=pedido_id, cliente_id=pessoa,
                entrega_id=entrega_id, texto=request.POST.get("texto", ""))
        else:
            raise Http404
    except (ValueError, negocio.ErroMarketplace) as erro:
        return _falha(request, str(erro))
    return _voltar("marketplace_pedido", pedido_id)
