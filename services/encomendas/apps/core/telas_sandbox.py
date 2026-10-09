"""Telas da prática da escola; cada leitura é limitada ao site e à pessoa."""

from __future__ import annotations

import hashlib
import logging
import uuid
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import quote

from django.http import FileResponse, Http404, HttpResponseRedirect
from django.conf import settings
from django.core.exceptions import ValidationError
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.core import sessao, telas_marketplace
from apps.core.selecionar_marketplace import _matriculas_ativas
from apps.encomendas import sandbox, catalogo_curso
from apps.encomendas.models import (ArquivoSandbox, EntregaSandbox, MensagemSandbox,
                                    AjusteSandbox, MovimentoMeshcoin, ParticipacaoSandbox,
                                    ProjetoSandbox)

logger = logging.getLogger(__name__)

CATEGORIAS = catalogo_curso.CATEGORIAS


ILUSTRACOES = {
    'prop-espada', 'fuzil-assalto', 'pistola-estilizada', 'mascote-3d', 'pet-fantasia',
    'cabelo-curto', 'cabelo-longo', 'bone-estilizado', 'chapeu-fantasia',
    'personagem-conceito', 'personagem-robo',
}


@require_GET
def ilustracao_projeto(request, slug):
    if slug not in ILUSTRACOES and slug not in catalogo_curso.ARQUIVOS_ILUSTRACOES and slug != 'guia-visual':
        raise Http404
    caminho = Path(settings.BASE_DIR) / 'static' / 'sandbox' / 'ilustracoes' / (slug + '.png')
    if not caminho.is_file():
        raise Http404
    resposta = FileResponse(caminho.open('rb'), content_type='image/png')
    resposta['Cache-Control'] = 'public, max-age=604800'
    return resposta


@require_GET
def arte_catalogo(request):
    caminho = Path(settings.BASE_DIR) / "static" / "sandbox" / "categorias-referencia.png"
    return FileResponse(caminho.open("rb"), content_type="image/png")


def _login(request):
    destino = request.get_full_path()
    return HttpResponseRedirect("/login?next=" + quote(destino, safe=""))


def _entrada(request):
    pessoa = sessao.quem_e(request)
    if not pessoa:
        return None, None
    try:
        return sessao.site_desta_instalacao(), pessoa
    except sessao.ConfiguracaoAusente:
        raise Http404


def _email_da_conta(request, pessoa):
    """Consulta o e-mail da identidade apenas nesta requisição, sem persistir."""
    base = sessao.exigir("IDENTIDADE_API_URL").rstrip("/")
    token = sessao.exigir("IDENTIDADE_API_TOKEN")
    resposta = sessao._pedir("identidade", "GET", base + "/sessao/completa",
                            headers={"Authorization": f"Bearer {token}",
                                     "Cookie": request.META.get("HTTP_COOKIE", "")})
    corpo = sessao._corpo_de(resposta, "identidade")
    if not corpo.get("autenticado") or corpo.get("id") != pessoa:
        raise sessao.VizinhaIndisponivel("sessão completa incompatível")
    email = (corpo.get("email") or "").strip()
    if not email:
        raise sessao.VizinhaIndisponivel("sessão completa sem e-mail")
    return email


def _aluno_atual(request, pessoa, site):
    email = _email_da_conta(request, pessoa)
    if sessao.categoria_na_escola(email) != sessao.CATEGORIA_DE_ALUNO:
        return False
    matriculas = _matriculas_ativas(site)
    if matriculas is None:
        raise sessao.VizinhaIndisponivel("não foi possível consultar as matrículas do site")
    return any(isinstance(linha, dict) and linha.get("site_id") == site
               and str(linha.get("email", "")).casefold() == email.casefold()
               for linha in matriculas)


def _falha(request, texto, status=400, papel="aluno"):
    return render(request, "sandbox/aviso.html",
                  {"texto": texto, "papel": papel, "titulo": "Confira este passo"}, status=status)


def _voltar(nome, *args, recado=""):
    destino = reverse(nome, args=args)
    if recado:
        destino += "?recado=" + quote(recado)
    return HttpResponseRedirect(destino)


def _equipe(request):
    site, pessoa = _entrada(request)
    if not pessoa:
        return None, None
    telas_marketplace._equipe(request)
    return site, pessoa


def _trabalho(request, participacao_id):
    site, pessoa = _entrada(request)
    if not pessoa:
        return None, None, None
    participacao = ParticipacaoSandbox.objects.filter(pk=participacao_id, site_id=site).select_related("projeto").first()
    if not participacao:
        raise Http404
    if participacao.pessoa_id == pessoa:
        return participacao, pessoa, "aluno"
    try:
        telas_marketplace._equipe(request)
    except Http404:
        raise Http404
    return participacao, pessoa, "equipe"


@require_GET
def catalogo(request):
    site, pessoa = _entrada(request)
    if not pessoa:
        return _login(request)
    try:
        _, _ = telas_marketplace._equipe(request)
        papel = "equipe"
    except Http404:
        papel = "aluno"
    trabalhos = list(ParticipacaoSandbox.objects.filter(site_id=site, pessoa_id=pessoa)
                    .select_related("projeto").order_by("-aceite_em"))
    if papel == "aluno":
        try:
            aluno_atual = _aluno_atual(request, pessoa, site)
        except (sessao.VizinhaIndisponivel, sessao.ConfiguracaoAusente):
            if not trabalhos:
                return _falha(request, "Não foi possível consultar a escola agora. Tente novamente.", 503)
            aluno_atual = False
        if not aluno_atual and not trabalhos:
            raise Http404
    else:
        aluno_atual = False
    categoria = request.GET.get("categoria", "espadas_objetos")
    if categoria not in catalogo_curso.CHAVES_CATEGORIAS:
        raise Http404
    projetos = list(ProjetoSandbox.objects.filter(site_id=site, ativo=True,
                    categoria=categoria).order_by("titulo"))
    categorias = [{"chave": chave, "titulo": titulo, "descricao": descricao,
                   "arte": arte, "selecionada": chave == categoria}
                  for chave, titulo, descricao, arte in CATEGORIAS]
    selecionada = next(c for c in categorias if c["selecionada"])
    trabalho_ativo = next((trabalho for trabalho in trabalhos if trabalho.status != "aprovado"), None)
    for projeto in projetos:
        projeto.do_curso = projeto.slug in catalogo_curso.SLUGS
        projeto.tem_ilustracao = projeto.slug in ILUSTRACOES
        projeto.pronto = (bool(projeto.briefing.strip())
                          and bool(projeto.criterios.strip()) and bool(projeto.entregaveis))
    return render(request, "sandbox/catalogo.html", {
        "papel": papel, "projetos": projetos, "trabalhos": trabalhos,
        "categorias": categorias, "selecionada": selecionada,
        "trabalho_ativo": trabalho_ativo,
        "aluno_atual": aluno_atual, "saldo": sandbox.saldo(site_id=site, pessoa_id=pessoa),
        "historico": sandbox.historico(site_id=site, pessoa_id=pessoa),
        "recado": request.GET.get("recado", ""),
    })


@require_GET
def confirmar_projeto(request, projeto_id):
    site, pessoa = _entrada(request)
    if not pessoa:
        return _login(request)
    projeto = ProjetoSandbox.objects.filter(pk=projeto_id, site_id=site, ativo=True,
                                            categoria__in=ProjetoSandbox.Categoria.values).first()
    if projeto is None:
        raise Http404
    try:
        aluno = _aluno_atual(request, pessoa, site)
        if not aluno:
            _equipe(request)
    except (sessao.VizinhaIndisponivel, sessao.ConfiguracaoAusente):
        return _falha(request, "Não foi possível confirmar sua matrícula agora. Tente novamente.", 503)
    projeto.do_curso = projeto.slug in catalogo_curso.SLUGS
    projeto.livre = projeto.do_curso and projeto.categoria == "livre"
    ativo = ParticipacaoSandbox.objects.filter(site_id=site, pessoa_id=pessoa,
                    status__in=['em_producao', 'em_ajuste', 'entregue']).first()
    return render(request, 'sandbox/confirmar.html', {
        'projeto': projeto, 'termos_simulacao': ('Prática educacional sem pagamento. Concluir o Sandbox concede a faixa Azul e 10.000 XP, uma vez por aluno.' if projeto.do_curso else sandbox.TERMOS_SIMULACAO),
        'aluno_atual': aluno, 'trabalho_ativo': ativo,
        'papel': 'aluno' if aluno else 'equipe',
    })


@require_POST
def aceitar(request, projeto_id):
    site, pessoa = _entrada(request)
    if not pessoa:
        return _login(request)
    if not ProjetoSandbox.objects.filter(pk=projeto_id, site_id=site, ativo=True).exists():
        raise Http404
    try:
        if not _aluno_atual(request, pessoa, site):
            raise Http404
    except (sessao.VizinhaIndisponivel, sessao.ConfiguracaoAusente):
        return _falha(request, "Não foi possível confirmar sua matrícula agora. Tente novamente.", 503)
    if request.POST.get("aceito_termos") != "sim":
        return _falha(request, "Leia os termos e marque o aceite para começar.")
    try:
        prazo_horas = int(request.POST.get('prazo_horas', '0'))
        if prazo_horas not in (24, 48, 72):
            raise sandbox.ErroSandbox("Escolha um prazo de 24h, 48h ou 72h na confirmação.")
        participacao = sandbox.aceitar(site_id=site, pessoa_id=pessoa, projeto_id=projeto_id,
                                       prazo_horas=prazo_horas, item_livre=request.POST.get("item_livre", ""),
                                       descricao_livre=request.POST.get("descricao_livre", ""))
    except (ValueError, sandbox.ErroSandbox) as erro:
        return _falha(request, str(erro))
    return _voltar("sandbox_trabalho", participacao.pk, recado="Trabalho iniciado.")


@require_GET
def trabalho(request, participacao_id):
    participacao, _, papel = _trabalho(request, participacao_id)
    if participacao is None:
        return _login(request)
    sandbox.registrar_atrasos(site_id=participacao.site_id)
    participacao.refresh_from_db()
    return render(request, "sandbox/trabalho.html", {
        "papel": papel, "trabalho": participacao, "agora": timezone.now(),
        "mensagens": MensagemSandbox.objects.filter(participacao=participacao).order_by("criada_em"),
        "arquivos": ArquivoSandbox.objects.filter(participacao=participacao).select_related("entrega").order_by("-criado_em"),
        "entregas": EntregaSandbox.objects.filter(participacao=participacao).order_by("-versao"),
        "ajustes": AjusteSandbox.objects.filter(participacao=participacao).order_by("-criado_em"),
        "respostas_pendentes": participacao.respostasandbox_set.exclude(estado='concluida'),
        "recado": request.GET.get("recado", ""),
    })


@require_POST
def mensagem(request, participacao_id):
    trabalho, pessoa, papel = _trabalho(request, participacao_id)
    if trabalho is None:
        return _login(request)
    texto = request.POST.get("texto", "").strip()
    try:
        fala = sandbox.mensagem(site_id=trabalho.site_id, participacao_id=trabalho.pk,
                         ator_id=pessoa, papel=papel, texto=texto)
    except (ValueError, sandbox.ErroSandbox) as erro:
        return _falha(request, str(erro), papel=papel)
    if papel == "aluno":
        from apps.core.ia_sandbox import enfileirar
        destino = request.POST.get('destino', 'ia')
        if destino not in ('ia', 'cliente', 'ambos'):
            destino = 'ia'
        for interlocutor in (('ia', 'cliente') if destino == 'ambos' else (destino,)):
            enfileirar(trabalho, 'mensagem:' + str(fala.pk), interlocutor)
    return _voltar("sandbox_trabalho", trabalho.pk)


@require_POST
def enviar_arquivo(request, participacao_id):
    trabalho, pessoa, papel = _trabalho(request, participacao_id)
    if trabalho is None:
        return _login(request)
    if papel != "aluno" or trabalho.status == "aprovado":
        raise Http404
    recebido = request.FILES.get("arquivo")
    if not recebido:
        return _falha(request, "Escolha um arquivo.")
    chave = uuid.uuid4().hex
    caminho = telas_marketplace._pasta_privada() / chave
    resumo = hashlib.sha256()
    tamanho = 0
    try:
        with caminho.open("xb") as destino:
            for bloco in recebido.chunks():
                destino.write(bloco)
                resumo.update(bloco)
                tamanho += len(bloco)
        ArquivoSandbox.objects.create(
            site_id=trabalho.site_id, participacao=trabalho, nome=Path(str(recebido.name).replace("\\", "/")).name[:255],
            chave=chave, sha256=resumo.hexdigest(), tamanho=tamanho,
            mime=(recebido.content_type or "application/octet-stream")[:120])
    except Exception:
        caminho.unlink(missing_ok=True)
        raise
    return _voltar("sandbox_trabalho", trabalho.pk, recado="Arquivo guardado. Inclua-o na próxima entrega.")


@require_GET
def baixar_arquivo(request, arquivo_id):
    site, pessoa = _entrada(request)
    if not pessoa:
        return _login(request)
    arquivo = ArquivoSandbox.objects.filter(pk=arquivo_id, participacao__site_id=site).select_related("participacao").first()
    if not arquivo:
        raise Http404
    if arquivo.participacao.pessoa_id != pessoa:
        telas_marketplace._equipe(request)
    if not arquivo.chave or Path(arquivo.chave).name != arquivo.chave:
        raise Http404
    caminho = telas_marketplace._pasta_privada() / arquivo.chave
    if not caminho.is_file():
        raise Http404
    resposta = FileResponse(caminho.open("rb"), as_attachment=True, filename=arquivo.nome,
                            content_type="application/octet-stream")
    resposta["X-Content-Type-Options"] = "nosniff"
    resposta["Cache-Control"] = "private, no-store"
    return resposta


@require_POST
def entregar(request, participacao_id):
    trabalho, pessoa, papel = _trabalho(request, participacao_id)
    if trabalho is None:
        return _login(request)
    if papel != "aluno":
        raise Http404
    try:
        arquivos = [uuid.UUID(chave) for chave in request.POST.getlist("arquivos")]
        sandbox.entregar(site_id=trabalho.site_id, participacao_id=trabalho.pk,
                         pessoa_id=pessoa, comentario=request.POST.get("comentario", "").strip(),
                         arquivos=arquivos)
    except (ValueError, sandbox.ErroSandbox) as erro:
        return _falha(request, str(erro))
    return _voltar("sandbox_trabalho", trabalho.pk, recado="Nova versão enviada à escola.")


@require_POST
def avaliar(request, participacao_id, acao):
    trabalho, pessoa, papel = _trabalho(request, participacao_id)
    if trabalho is None:
        return _login(request)
    if papel != "equipe":
        raise Http404
    try:
        if acao == "ajuste":
            sandbox.pedir_ajuste(site_id=trabalho.site_id, participacao_id=trabalho.pk,
                                 autor_id=pessoa, texto=request.POST.get("texto", "").strip())
            recado = "Ajuste enviado."
        elif acao == "aprovar":
            sandbox.aprovar(site_id=trabalho.site_id, participacao_id=trabalho.pk,
                            aprovador_id=pessoa)
            recado = "Entrega aprovada."
        else:
            raise Http404
    except (ValueError, sandbox.ErroSandbox) as erro:
        return _falha(request, str(erro), papel=papel)
    return _voltar("sandbox_trabalho", trabalho.pk, recado=recado)


@require_GET
def escola(request):
    site, pessoa = _equipe(request)
    if not pessoa:
        return _login(request)
    sandbox.registrar_atrasos(site_id=site)
    return render(request, "sandbox/escola.html", {
        "papel": "equipe", "projetos": ProjetoSandbox.objects.filter(site_id=site).order_by("titulo"),
        "categorias": ProjetoSandbox.Categoria.choices,
        "trabalhos": ParticipacaoSandbox.objects.filter(site_id=site).select_related("projeto").order_by("-aceite_em"),
        "movimentos": MovimentoMeshcoin.objects.filter(site_id=site).select_related("participacao__projeto").order_by("-criado_em"),
        "recado": request.GET.get("recado", ""),
    })


def _lista(texto):
    return [linha.strip() for linha in texto.splitlines() if linha.strip()]


def _opcional_inteiro(texto):
    if not texto.strip():
        return None
    valor = int(texto)
    if valor < 0:
        raise ValueError("Use número não negativo.")
    return valor


@require_POST
def salvar_projeto(request, projeto_id=None):
    site, pessoa = _equipe(request)
    if not pessoa:
        return _login(request)
    projeto = (ProjetoSandbox.objects.filter(pk=projeto_id, site_id=site).first()
               if projeto_id else ProjetoSandbox(site_id=site))
    if projeto is None:
        raise Http404
    try:
        titulo = request.POST.get("titulo", "").strip()
        slug = request.POST.get("slug", "").strip()
        if not titulo or not slug:
            raise ValueError("Informe título e identificador do projeto.")
        recompensa = request.POST.get("recompensa", "").strip().replace(",", ".")
        recompensa = Decimal(recompensa) if recompensa else None
        if recompensa is not None and (not recompensa.is_finite() or recompensa < 0):
            raise ValueError("Confira a recompensa em Meshcoins.")
        projeto.titulo = titulo
        categoria = request.POST.get("categoria", "")
        if categoria not in catalogo_curso.CHAVES_CATEGORIAS:
            raise ValueError("Escolha uma categoria de prática.")
        projeto.categoria = categoria
        projeto.slug = slug
        projeto.briefing = request.POST.get("briefing", "").strip()
        projeto.referencias = _lista(request.POST.get("referencias", ""))
        projeto.entregaveis = _lista(request.POST.get("entregaveis", ""))
        projeto.criterios = request.POST.get("criterios", "").strip()
        projeto.prazo_dias = _opcional_inteiro(request.POST.get("prazo_dias", ""))
        projeto.ajustes_previstos = _opcional_inteiro(request.POST.get("ajustes_previstos", ""))
        if "recompensa" in request.POST:
            projeto.recompensa = recompensa
        projeto.ativo = request.POST.get("ativo") == "sim"
        projeto.full_clean()
        projeto.save()
    except (ValueError, InvalidOperation, ValidationError) as erro:
        return _falha(request, str(erro), papel="equipe")
    return _voltar("sandbox_escola", recado="Projeto salvo.")


@require_POST
def repetir_analise(request, participacao_id, entrega_id):
    trabalho, _, papel = _trabalho(request, participacao_id)
    if trabalho is None:
        return _login(request)
    entrega = EntregaSandbox.objects.filter(pk=entrega_id, participacao=trabalho).first()
    if not entrega:
        raise Http404
    from apps.encomendas.analises_sandbox import repetir
    repetir(entrega)
    return _voltar('sandbox_trabalho', trabalho.pk, recado='Nova tentativa solicitada para esta versão.')


@require_GET
def previa_analise(request, arquivo_id, nome):
    arquivo = ArquivoSandbox.objects.filter(pk=arquivo_id).select_related('participacao').first()
    if not arquivo:
        raise Http404
    trabalho, _, _ = _trabalho(request, arquivo.participacao_id)
    if trabalho is None:
        return _login(request)
    import re
    if not re.fullmatch('[a-f0-9]{24}(?:-(?:frontal|lateral|perspectiva))?\\.png', nome):
        raise Http404
    from apps.encomendas.analises_sandbox import pasta
    from apps.encomendas.sandbox_models import AnaliseArquivoSandbox
    analise = AnaliseArquivoSandbox.objects.filter(arquivo=arquivo, estado='concluida').first()
    if not analise:
        raise Http404
    caminho = pasta() / analise.chave_cache / 'previas' / nome
    if not caminho.is_file():
        raise Http404
    response = FileResponse(caminho.open('rb'), content_type='image/png')
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
