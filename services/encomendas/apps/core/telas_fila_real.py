"""Telas da fila remunerada, com conversa humana e orientação privada."""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from urllib.parse import quote

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.core import plantao
from apps.core.telas_marketplace import _entrada
from apps.encomendas import fila_real, marketplace
from apps.encomendas.models import (
    ArquivoMarketplace, CasoConversaFila, EntregaMarketplace, MensagemMarketplace,
)

ErroFilaReal = fila_real.ErroMarketplace


CATEGORIAS = (
    ("espadas_objetos", "Espadas e objetos", "espadas", "prop-espada"),
    ("pets", "Pets", "pets", "pet-fantasia"),
    ("cabelos", "Cabelos", "cabelos", "cabelo-curto"),
    ("chapeus", "Chapéus", "chapeus", "chapeu-fantasia"),
    ("personagens", "Personagens", "personagens", "personagem-conceito"),
)


def _moeda(centavos):
    return "R$ {:,.2f}".format(centavos / 100).replace(",", "X").replace(".", ",").replace("X", ".")


def _aviso(request, mensagem, status=400):
    return render(request, "fila_real_aviso.html", {"mensagem": mensagem}, status=status)


def _voltar(nome, *args, recado=""):
    destino = reverse(nome, args=args)
    if recado:
        destino += "?recado=" + quote(recado)
    return HttpResponseRedirect(destino)


def _papel(site, pessoa):
    if plantao.e_do_plantao(pessoa):
        return "equipe"
    if fila_real.cliente_da_pessoa(site_id=site, pessoa_id=pessoa):
        return "cliente"
    if marketplace.acesso_aluno(site_id=site, pessoa_id=pessoa):
        return "aluno"
    raise Http404


def _pedido(site, pessoa, pedido_id):
    try:
        return fila_real.pedido_acessivel(site_id=site, pessoa_id=pessoa, pedido_id=pedido_id)
    except (ValueError, fila_real.ErroFilaReal):
        raise Http404


def _apresentar(pedido):
    pedido.valor_exibido = _moeda(pedido.valor_cents)
    pedido.resumo = (pedido.briefing or {}).get("observacoes", "")
    pedido.referencias_exibidas = (pedido.briefing or {}).get("referencias", [])
    pedido.entregaveis_exibidos = (pedido.briefing or {}).get("entregaveis", [])
    pedido.ilustracao = next((arte for chave, _, _, arte in CATEGORIAS if chave == pedido.categoria), "prop-espada")
    return pedido


@require_GET
def catalogo(request):
    site, pessoa = _entrada(request)
    papel = _papel(site, pessoa)
    if papel == "cliente":
        cliente = fila_real.cliente_da_pessoa(site_id=site, pessoa_id=pessoa)
        if cliente is None:
            raise Http404
        return HttpResponseRedirect("/admin/clientes/" + quote(cliente.slug) + "/")
    categoria = request.GET.get("categoria", "espadas_objetos")
    if categoria not in {item[0] for item in CATEGORIAS}:
        raise Http404
    dados = fila_real.catalogo(site_id=site, pessoa_id=pessoa, categoria=categoria)
    pedidos = [_apresentar(p) for p in dados["pedidos"]]
    trabalhos = [_apresentar(p) for p in dados["trabalhos"]]
    categorias = [{"chave": chave, "titulo": titulo, "arte": arte, "selecionada": chave == categoria}
                  for chave, titulo, arte, _ in CATEGORIAS]
    return render(request, "fila_real_catalogo.html", {
        "pedidos": pedidos, "trabalhos": trabalhos, "categorias": categorias,
        "trabalho_ativo": dados.get("trabalho_ativo"), "recado": request.GET.get("recado", ""),
        "papel": papel,
    })


@require_GET
def confirmar(request, pedido_id):
    site, pessoa = _entrada(request)
    if _papel(site, pessoa) != "aluno":
        raise Http404
    dados = fila_real.catalogo(site_id=site, pessoa_id=pessoa, categoria=None)
    pedido = next((p for p in dados["pedidos"] if p.pk == pedido_id), None)
    if pedido is None:
        raise Http404
    return render(request, "fila_real_confirmar.html", {"pedido": _apresentar(pedido)})


@require_POST
def aceitar(request, pedido_id):
    site, pessoa = _entrada(request)
    if _papel(site, pessoa) != "aluno":
        raise Http404
    if request.POST.get("aceito_termos") != "sim":
        return _aviso(request, "Leia e aceite as condições deste trabalho.")
    try:
        pedido = fila_real.aceitar(site_id=site, pessoa_id=pessoa, pedido_id=pedido_id)
    except (ValueError, fila_real.ErroFilaReal) as erro:
        return _aviso(request, str(erro))
    return _voltar("fila_real_trabalho", pedido.pk, recado="Trabalho iniciado. O prazo de 48 horas começou.")


@require_GET
def trabalho(request, pedido_id):
    site, pessoa = _entrada(request)
    pedido, papel = _pedido(site, pessoa, pedido_id)
    if papel == "aluno" and (not pedido.aluno_id or pedido.aluno.pessoa_id != pessoa):
        return _voltar("fila_real_confirmar", pedido_id)
    _apresentar(pedido)
    mensagens = MensagemMarketplace.objects.filter(pedido=pedido).order_by("criada_em", "pk")
    arquivos = ArquivoMarketplace.objects.filter(pedido=pedido).order_by("criado_em", "pk")
    entregas = list(EntregaMarketplace.objects.filter(pedido=pedido).order_by("criada_em", "pk"))
    try:
        from apps.encomendas.models import OrientacaoPrivadaFila
        orientacoes = OrientacaoPrivadaFila.objects.filter(pedido=pedido, pessoa_id=pessoa).order_by("criada_em", "pk")
    except ImportError:
        orientacoes = []
    return render(request, "fila_real_trabalho.html", {
        "pedido": pedido, "papel": papel, "mensagens": mensagens, "arquivos": arquivos,
        "entregas": entregas, "ultima_entrega": entregas[-1] if entregas else None,
        "orientacoes": orientacoes, "agora": timezone.now(),
        "perguntas_pendentes": list(CasoConversaFila.objects.filter(pedido=pedido, resposta__isnull=True)
                                  .select_related("pergunta").order_by("criada_em")[:30]) if papel == "cliente" else [],
        "recado": request.GET.get("recado", ""),
    })


@require_POST
def mensagem(request, pedido_id):
    site, pessoa = _entrada(request)
    _pedido(site, pessoa, pedido_id)
    try:
        responde_a = request.POST.get("responde_a", "").strip()
        fila_real.registrar_mensagem(site_id=site, pessoa_id=pessoa, pedido_id=pedido_id,
                                    texto=request.POST.get("texto", "").strip(),
                                    responde_a=uuid.UUID(responde_a) if responde_a else None)
    except (ValueError, fila_real.ErroFilaReal) as erro:
        return _aviso(request, str(erro))
    return _voltar("fila_real_trabalho", pedido_id)


@require_POST
def orientar(request, pedido_id):
    site, pessoa = _entrada(request)
    pedido, papel = _pedido(site, pessoa, pedido_id)
    if papel not in {"aluno", "cliente"}:
        raise Http404
    pergunta = request.POST.get("pergunta", "").strip()
    if not pergunta or len(pergunta) > 4000:
        return _aviso(request, "Escreva uma pergunta de até 4.000 caracteres.")
    from apps.core.ia_fila_real import orientar_privadamente
    orientar_privadamente(pedido, pessoa, papel, pergunta)
    return _voltar("fila_real_trabalho", pedido_id)


def _pasta_privada():
    pasta = Path(getattr(settings, "MARKETPLACE_UPLOAD_ROOT", Path(settings.BASE_DIR) / "marketplace_uploads"))
    pasta.mkdir(mode=0o700, parents=True, exist_ok=True)
    return pasta


@require_POST
def arquivo(request, pedido_id):
    site, pessoa = _entrada(request)
    _, papel = _pedido(site, pessoa, pedido_id)
    if papel not in {"aluno", "cliente"}:
        raise Http404
    recebido = request.FILES.get("arquivo")
    if recebido is None:
        return _aviso(request, "Escolha um arquivo.")
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
        fila_real.adicionar_arquivo(site_id=site, pessoa_id=pessoa, pedido_id=pedido_id,
            nome=str(recebido.name).replace("\\", "/").split("/")[-1], chave=chave,
            sha256=resumo.hexdigest(), tamanho_bytes=tamanho,
            tipo_mime=recebido.content_type or "", papel="referencia" if papel == "cliente" else "final")
    except (ValueError, fila_real.ErroFilaReal) as erro:
        caminho.unlink(missing_ok=True)
        return _aviso(request, str(erro))
    except Exception:
        caminho.unlink(missing_ok=True)
        raise
    return _voltar("fila_real_trabalho", pedido_id, recado="Arquivo guardado.")


@require_GET
def baixar(request, arquivo_id):
    site, pessoa = _entrada(request)
    try:
        arquivo = fila_real.arquivo_acessivel(site_id=site, pessoa_id=pessoa, arquivo_id=arquivo_id)
    except (ValueError, fila_real.ErroFilaReal):
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
    site, pessoa = _entrada(request)
    pedido, papel = _pedido(site, pessoa, pedido_id)
    if papel != "aluno":
        raise Http404
    try:
        ids = [uuid.UUID(valor) for valor in request.POST.getlist("arquivos")]
        fila_real.entregar(site_id=site, pessoa_id=pessoa, pedido_id=pedido.pk,
                          comentario=request.POST.get("comentario", ""), arquivos_ids=ids)
    except (ValueError, fila_real.ErroFilaReal) as erro:
        return _aviso(request, str(erro))
    return _voltar("fila_real_trabalho", pedido_id, recado="Entrega enviada ao cliente.")


@require_POST
def avaliar(request, pedido_id, acao):
    site, pessoa = _entrada(request)
    pedido, papel = _pedido(site, pessoa, pedido_id)
    if papel != "cliente":
        raise Http404
    try:
        entrega_id = uuid.UUID(request.POST.get("entrega_id", ""))
        if acao == "aprovar":
            fila_real.aprovar(site_id=site, pessoa_id=pessoa, pedido_id=pedido.pk, entrega_id=entrega_id)
            recado = "Entrega aprovada. Acompanhe a liberação do saque."
        elif acao == "ajuste":
            fila_real.pedir_ajuste(site_id=site, pessoa_id=pessoa, pedido_id=pedido.pk,
                                  entrega_id=entrega_id, texto=request.POST.get("texto", ""))
            recado = "Pedido de ajuste enviado ao aluno."
        else:
            raise Http404
    except (ValueError, fila_real.ErroFilaReal) as erro:
        return _aviso(request, str(erro))
    return _voltar("fila_real_trabalho", pedido_id, recado=recado)
