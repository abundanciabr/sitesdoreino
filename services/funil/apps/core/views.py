import json
import logging
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from django import forms
from django.conf import settings
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import render
from django.utils.html import format_html
from django.views.decorators.http import (
    require_http_methods,
    require_POST,
    require_safe,
)
from django.views.static import serve as serve_do_django

from apps.core.clients import (
    SEM_RESPOSTA,
    AlunosClient,
    CatalogoClient,
    IdentidadeClient,
    LeadsClient,
    NotificacoesClient,
)
from apps.core import sorteio, telemetria, ver_como
from apps.core.middleware import limpar_cache_de_avisos
from apps.core.visitante import COOKIE, id_valido
from apps.core.notificacoes import (
    TIPOS_POR_ASSUNTO,
    avisos_para_tela,
    buscar_avisos,
    links_para_o_celular,
    marcar_aviso,
    marcar_todos,
)
from apps.core.enderecos import (
    url_de_entrada,
    url_de_entrada_por_senha,
    url_dos_avisos,
)
from apps.i18n import catalogo as cat
from apps.i18n.idiomas import caminho_publico, direcao, tag_bcp47

logger = logging.getLogger("funil.oferta")

# Ordem fixa: é a ordem da query string do link do checkout.
CHAVES_UTM = ("utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content")

# Páginas públicas localizadas do site, listadas no sitemap.
PAGINAS_PUBLICAS = ("/", "/cadastro")


def _utm_da_requisicao(request) -> dict:
    return {chave: valor for chave in CHAVES_UTM if (valor := request.GET.get(chave))}


# Atribuição do quiz: versão, formato, segmento, origem, mídia, campanha,
# criativo, a tentativa opaca (qa) e o quiz (qz). Seguem o mesmo caminho das UTMs
# (link do checkout). Só passam valores de até 100 caracteres: letras, números, espaço e . : + / - _.
CHAVES_QUIZ = ("v", "fmt", "seg", "src", "med", "cpg", "ctv", "qa", "qz")
_VALOR_DE_ATRIBUICAO = re.compile(r"[\w .:+/-]{1,100}")


def _atribuicao_da_requisicao(request) -> dict:
    """UTMs + parâmetros do quiz, na ordem fixa, para o link do checkout."""
    quiz = {
        chave: valor
        for chave in CHAVES_QUIZ
        if (valor := request.GET.get(chave)) and _VALOR_DE_ATRIBUICAO.fullmatch(valor)
    }
    return {**_utm_da_requisicao(request), **quiz}


@require_safe
def healthz(request):
    return JsonResponse({"status": "ok"})


@require_safe
def verificacao_do_google(request):
    """Verificação do Google Search Console: texto fixo, sem prefixo de idioma."""
    return HttpResponse(
        "google-site-verification: google0e78b54775677e95.html",
        content_type="text/plain",
    )


def servir_estatico(request, path):
    """Serve os estáticos a partir do diretório-fonte; rota sem prefixo de idioma."""
    if getattr(request, "idioma", None) is not None:
        raise Http404("estático não tem prefixo de idioma")
    return serve_do_django(request, path, document_root=settings.STATICFILES_DIRS[0])


@require_safe
def landing(request):
    """A raiz do site: a home nos sites com idioma registrado, e a vitrine da
    oferta padrão (com UTM no link do checkout) nos demais."""
    if getattr(request, "idioma", None):
        return render(request, "funil/landing_i18n.html")

    site = request.site
    slug = site.get("default_offer_slug")
    if not slug:
        raise Http404("site sem oferta padrão configurada")

    oferta = CatalogoClient().obter_oferta(site["id"], slug)
    if oferta is None:
        raise Http404("oferta padrão não encontrada neste site")

    utm = _utm_da_requisicao(request)
    query = urlencode(_atribuicao_da_requisicao(request))
    url_checkout = f"/checkout/{slug}/" + (f"?{query}" if query else "")

    return render(
        request,
        "funil/landing.html",
        {
            "site": site,
            "oferta": oferta,
            "preco_formatado": f"{oferta['price_cents'] / 100:.2f}".replace(".", ","),
            "url_checkout": url_checkout,
            "utm": utm,
        },
    )


#: O apelido da página de vendas dentro de cada site.
SLUG_DA_PAGINA_DE_OFERTA = "oferta"
SLUG_DA_FLP = "flp-0"

#: Slots que a página desenha em lugar próprio, fora do corpo corrido da seção.
SLOTS_COM_LUGAR_PROPRIO = (
    "headline",
    "imagem",
    "cta_texto",
    "cta_destino",
    "prova",
    "assinatura",
)

#: Slots de corpo que abrem a seção; os demais parágrafos vêm depois, em
#: ordem alfabética.
SLOTS_QUE_ABREM_O_CORPO = ("subheadline", "texto")


def _e_item_de_lista(slot: str) -> bool:
    """`vilao_2` e `recusa_5` são itens de lista (nome_N); `texto` é parágrafo."""
    prefixo, _, sufixo = slot.rpartition("_")
    return bool(prefixo) and sufixo.isdigit()


def _bloco_da_secao(secao) -> dict | None:
    """Converte uma seção da API no bloco do template; `None` sem slot preenchido."""
    if not isinstance(secao, dict):
        return None
    nome = secao.get("nome")
    slots = secao.get("slots")
    if not isinstance(nome, str) or not isinstance(slots, dict):
        return None

    preenchidos = {
        chave: valor.strip()
        for chave, valor in slots.items()
        if isinstance(valor, str) and valor.strip()
    }
    if not preenchidos:
        return None

    corridos = sorted(
        (
            chave
            for chave in preenchidos
            if chave not in SLOTS_COM_LUGAR_PROPRIO and not _e_item_de_lista(chave)
        ),
        key=lambda chave: (
            (
                SLOTS_QUE_ABREM_O_CORPO.index(chave)
                if chave in SLOTS_QUE_ABREM_O_CORPO
                else len(SLOTS_QUE_ABREM_O_CORPO)
            ),
            chave,
        ),
    )
    numerados = sorted(
        (chave for chave in preenchidos if _e_item_de_lista(chave)),
        key=lambda chave: (chave.rpartition("_")[0], int(chave.rpartition("_")[2])),
    )
    return {
        "nome": nome,
        "headline": preenchidos.get("headline", ""),
        "imagem": preenchidos.get("imagem", ""),
        "cta_texto": preenchidos.get("cta_texto", ""),
        "cta_destino": preenchidos.get("cta_destino", ""),
        "prova": preenchidos.get("prova", ""),
        "assinatura": preenchidos.get("assinatura", ""),
        "paragrafos": [preenchidos[chave] for chave in corridos],
        "itens": [preenchidos[chave] for chave in numerados],
        # De que slot veio cada parágrafo e cada item, na mesma ordem.
        "slots_dos_paragrafos": corridos,
        "slots_dos_itens": numerados,
        "slots": preenchidos,
    }


def _bloco_vazio_da_oferta() -> dict:
    """O cartão da oferta quando ainda não há copy nenhuma para ele."""
    return {
        "nome": "oferta",
        "headline": "",
        "imagem": "",
        "cta_texto": "",
        "cta_destino": "",
        "prova": "",
        "assinatura": "",
        "paragrafos": [],
        "itens": [],
        "slots": {},
    }


@require_safe
def pagina_de_oferta(request, slug=SLUG_DA_PAGINA_DE_OFERTA):
    """`/oferta`: seções do catálogo e preço da oferta; 404 se a página não
    existe e 503 com `Retry-After` se o catálogo não responde."""
    site = request.site
    catalogo = CatalogoClient()
    pagina = catalogo.obter_pagina(site["id"], slug)

    if pagina is SEM_RESPOSTA:
        resposta = render(
            request,
            "funil/oferta.html",
            {"site": site, "catalogo_mudo": True},
            status=503,
        )
        # Pede nova tentativa em 30 segundos.
        resposta["Retry-After"] = "30"
        return resposta
    if pagina is None:
        pagina_inexistente = True
        return render(
            request,
            "funil/oferta.html",
            {"site": site, "pagina_inexistente": pagina_inexistente},
            status=404,
        )

    blocos = [
        bloco
        for bloco in (_bloco_da_secao(secao) for secao in pagina["secoes"])
        if bloco is not None
    ]
    braco = _braco_na_tela(request, pagina, blocos)

    offer_slug = pagina.get("offer_slug") or ""
    oferta = None
    if offer_slug:
        try:
            oferta = catalogo.obter_oferta(site["id"], offer_slug)
        except httpx.HTTPError:
            # A oferta é só um cartão: sem ela a página segue sem preço.
            oferta = None

    # O cartão da oferta aparece sempre que há oferta, mesmo sem copy escrita.
    if oferta and not any(bloco["nome"] == "oferta" for bloco in blocos):
        blocos.append(_bloco_vazio_da_oferta())

    for bloco in blocos:
        bloco["cta_medido"] = _cta_medido(bloco, offer_slug if oferta else "")
    contexto_telemetria = (
        telemetria.contexto_da_pagina(
            site["id"],
            pagina,
            [bloco["nome"] for bloco in blocos],
            [
                (bloco["nome"], "cta_texto", bloco["cta_medido"])
                for bloco in blocos
                if bloco["cta_medido"]
            ],
            braco,
        )
        if blocos
        else ""
    )

    query = urlencode(_atribuicao_da_requisicao(request))
    template = (
        "funil/desafio_apple.html"
        if slug == "desafio-como-ganhar-em-dolar-com-roblox"
        and request.get_host().split(":")[0].lower() == "meshcraft.top"
        else "funil/oferta.html"
    )
    resposta = render(
        request,
        template,
        {
            "site": site,
            "blocos": blocos,
            "contexto_telemetria": contexto_telemetria,
            "oferta": oferta,
            "preco_formatado": (
                f"{oferta['price_cents'] // 100:,}".replace(",", ".")
                + f",{oferta['price_cents'] % 100:02d}" if oferta else ""
            ),
            "url_checkout": (
                f"/checkout/{offer_slug}/" + (f"?{query}" if query else "")
                if oferta
                else ""
            ),
        },
    )
    if braco:
        # Cache compartilhado serviria o braço de uma pessoa a outra.
        resposta["Cache-Control"] = "private, no-store"
    _medir_visita(request, pagina, offer_slug, braco)
    return resposta


@require_safe
def pagina_de_oferta_roblox(request, slug):
    """As ofertas Roblox pertencem ao catálogo do Meshcraft."""
    if request.get_host().split(":")[0].lower() != "meshcraft.top":
        raise Http404("página disponível apenas em meshcraft.top")
    return pagina_de_oferta(request, slug=slug)



@require_safe
def pagina_de_oferta_blender(request):
    """Novo endereço público; preserva a identidade da oferta e das matrículas."""
    if request.get_host().split(":")[0].lower() != "meshcraft.top":
        raise Http404("página disponível apenas em meshcraft.top")
    return pagina_de_oferta(request, slug="desafio-como-ganhar-em-dolar-com-roblox")


def _braco_na_tela(request, pagina: dict, blocos: list) -> dict:
    """Sorteia o braço do visitante e põe o texto dele no slot em teste.
    Devolve `{experimento_id, variante_id}`, ou `{}` se não há experimento."""
    experimento = pagina.get("experimento_ativo")
    variante = sorteio.sortear(experimento, getattr(request, "id_do_visitante", ""))
    if variante is None:
        return {}
    secao, slot = experimento["secao"], experimento["slot"]
    posicao = next(
        (i for i, bloco in enumerate(blocos) if bloco["nome"] == secao), None
    )
    bloco = (
        None
        if posicao is None
        else _bloco_da_secao(
            {
                "nome": secao,
                "slots": {**blocos[posicao]["slots"], slot: variante["valor"]},
            }
        )
    )
    if bloco is None or slot not in bloco["slots"]:
        logger.error(
            "oferta: o experimento %s testa %s.%s, que esta página não desenha; "
            "a página segue como foi publicada, sem experimento",
            experimento["id"],
            secao,
            slot,
        )
        return {}

    bloco["marca"] = {
        "slot": slot,
        "paragrafo": _posicao(bloco["slots_dos_paragrafos"], slot),
        "item": _posicao(bloco["slots_dos_itens"], slot),
        "atributos": format_html(
            ' data-experimento-id="{}" data-variante-id="{}"',
            experimento["id"],
            variante["variante_id"],
        ),
    }
    blocos[posicao] = bloco
    return {"experimento_id": experimento["id"], "variante_id": variante["variante_id"]}


def _posicao(slots: list, slot: str) -> int | None:
    return slots.index(slot) if slot in slots else None


def _destino_interno(destino: str) -> bool:
    """Âncora desta página ou caminho deste host; nunca outro domínio."""
    return destino.startswith("#") or (
        destino.startswith("/") and not destino.startswith(("//", "/\\"))
    )


def _cta_medido(bloco: dict, offer_slug: str) -> str:
    """Destino do botão da seção medido pela telemetria (sem UTM), ou vazio."""
    if bloco["nome"] == "oferta":
        return f"/checkout/{offer_slug}/" if offer_slug else ""
    if bloco["nome"] == "cubo" and bloco["cta_texto"]:
        destino = bloco["cta_destino"] or "#a-oferta"
        return destino if _destino_interno(destino) else ""
    return ""


def _destino_da_flp(destino: str, request) -> str:
    """Aceita âncora, caminho interno ou HTTPS e leva a atribuição ao destino."""
    destino = destino.strip()
    try:
        partes = urlsplit(destino)
    except ValueError:
        return ""
    if destino.startswith("#") and not partes.scheme:
        return destino
    if not (
        (partes.scheme == "https" and partes.netloc)
        or (not partes.scheme and not partes.netloc and destino.startswith("/"))
    ) or destino.startswith("//"):
        return ""
    parametros = dict(parse_qsl(partes.query, keep_blank_values=True))
    for chave, valor in _atribuicao_da_requisicao(request).items():
        parametros.setdefault(chave, valor)
    return urlunsplit(partes._replace(query=urlencode(parametros)))


@require_safe
def pagina_flp(request):
    """Mostra somente a versão publicada de `flp-0` do site do Host."""
    pagina = CatalogoClient().obter_pagina(request.site["id"], SLUG_DA_FLP)
    if pagina is None:
        return render(
            request,
            "funil/flp.html",
            {"site": request.site, "sem_publicacao": True},
            status=404,
        )
    if (
        pagina is SEM_RESPOSTA
        or pagina.get("slug") != SLUG_DA_FLP
        or pagina.get("tipo") != "flp"
    ):
        resposta = render(
            request,
            "funil/flp.html",
            {"site": request.site, "catalogo_mudo": True},
            status=503,
        )
        resposta["Retry-After"] = "30"
        return resposta

    blocos = []
    for secao in pagina["secoes"]:
        bloco = _bloco_da_secao(secao)
        if bloco is not None:
            bloco["cta_url"] = _destino_da_flp(bloco["cta_destino"], request)
            blocos.append(bloco)
    if not blocos:
        resposta = render(
            request,
            "funil/flp.html",
            {"site": request.site, "catalogo_mudo": True},
            status=503,
        )
        resposta["Retry-After"] = "30"
        return resposta
    resposta = render(
        request, "funil/flp.html", {"site": request.site, "blocos": blocos}
    )
    _medir_visita(request, pagina, pagina.get("offer_slug") or "", {})
    return resposta


def _medir_visita(request, pagina: dict, offer_slug: str, braco: dict) -> None:
    """Publica `funil.pagina-vista.v1` sem derrubar nem atrasar a página.
    Leva só ids e versão da página, nunca o texto; campo sem valor fica fora."""
    dados = {
        # `site_id` dentro de `data`: a recepção da `metricas` o lê daqui.
        "site_id": request.site["id"],
        "visitor_id": getattr(request, "id_do_visitante", ""),
        "pagina_slug": pagina["slug"],
        "pagina_version": pagina["version"],
        "offer_slug": offer_slug,
        **braco,
    }
    referrer = request.META.get("HTTP_REFERER", "")
    if referrer:
        dados["referrer"] = referrer
    utm = telemetria.utm_sem_prefixo(request.GET)
    if utm:
        dados["utm"] = utm
    dispositivo = telemetria.dispositivo_do_agente(
        request.META.get("HTTP_USER_AGENT", "")
    )
    if dispositivo:
        dados["dispositivo"] = dispositivo
    telemetria.publicar("funil.pagina-vista", 1, dados)


class FormularioDeCadastro(forms.Form):
    """Valida o pedido de entrada (nome, e-mail, WhatsApp e senha); as duas
    senhas são conferidas na view `cadastro`."""

    name = forms.CharField(max_length=200)
    email = forms.EmailField()
    whatsapp = forms.CharField(max_length=32)
    senha = forms.CharField(min_length=8, widget=forms.PasswordInput)
    confirmar_senha = forms.CharField(min_length=8, widget=forms.PasswordInput)


# HEAD junto com GET: `require_http_methods` não o inclui por padrão.
@require_http_methods(["GET", "HEAD", "POST"])
def cadastro(request):
    """Pedido de entrada de quem não tem conta do Google: cria a pré-matrícula na
    célula `alunos` (site do Host) e grava a senha na `identidade`."""
    if getattr(request, "idioma", None) is None:
        # Site fora do registro i18n não tem cadastro.
        raise Http404("cadastro só existe em site registrado no i18n")

    sucesso, ja_matriculado, erro_envio, status = False, False, False, 200
    # Flag própria: a mensagem sai do catálogo de tradução, no template.
    senhas_diferentes = False
    if request.method == "POST":
        form = FormularioDeCadastro(request.POST)
        if form.is_valid():
            senhas_diferentes = (
                form.cleaned_data["senha"] != form.cleaned_data["confirmar_senha"]
            )
        if form.is_valid() and not senhas_diferentes:
            resultado = AlunosClient().criar_pre_matricula(
                site_id=request.site["id"],  # do Host, não do payload
                email=form.cleaned_data["email"],
                nome_completo=form.cleaned_data["name"],
                whatsapp=form.cleaned_data["whatsapp"],
            )
            if resultado == AlunosClient.RESULTADO_NA_FILA:
                # A senha só é gravada se o pedido entrou na fila; se falhar,
                # o pedido conta como não enviado.
                senha_ok = (
                    IdentidadeClient().definir_senha(
                        email=form.cleaned_data["email"],
                        senha=form.cleaned_data["senha"],
                        nome=form.cleaned_data["name"],
                        site_id=request.site["id"],
                    )
                    == IdentidadeClient.RESULTADO_SENHA_OK
                )
                if senha_ok:
                    sucesso = True
                    form = FormularioDeCadastro()  # sucesso limpa o formulário
                else:
                    erro_envio, status = True, 502
            elif resultado == AlunosClient.RESULTADO_JA_TEM_MATRICULA:
                # O pedido chegou, mas esta pessoa já está na plataforma.
                ja_matriculado = True
            else:
                # Falha: 502 com a página e o que a pessoa digitou.
                erro_envio, status = True, 502
    else:
        form = FormularioDeCadastro()

    return render(
        request,
        "funil/cadastro.html",
        {
            "form": form,
            "sucesso": sucesso,
            "ja_matriculado": ja_matriculado,
            "erro_envio": erro_envio,
            "senhas_diferentes": senhas_diferentes,
        },
        status=status,
    )


def destino_local(cru: str | None, padrao: str) -> str:
    """Só caminho local deste site; qualquer endereço de fora devolve `padrao`."""
    if not cru or not cru.startswith("/") or cru.startswith("//"):
        return padrao
    if "\\" in cru or any(ord(c) < 0x20 for c in cru):
        return padrao
    return cru


# Chaves de recusa aceitas em `?erro=`; qualquer outra é ignorada.
CHAVES_DE_RECUSA = {
    "interrompida",
    "nao-confere",
    "nao-configurada",
    "google-indisponivel",
    "email-nao-verificado",
    # Recusas de /entrar/senha; "senha-invalida" vale para e-mail sem conta e
    # para senha errada.
    "senha-invalida",
    "muitas-tentativas",
}


@require_safe
def entrar(request):
    """Tela de entrada: botão do Google, formulário de senha e a mensagem de `?erro=`.
    Não abre sessão; o `?next=` diz à `identidade` aonde devolver a pessoa."""
    if getattr(request, "idioma", None) is None:
        # Site fora do registro i18n não tem esta página.
        raise Http404("login só existe em site registrado no i18n")
    erro = request.GET.get("erro") or ""
    if erro not in CHAVES_DE_RECUSA:
        erro = ""
    # Volta para a página de onde veio (`?next=`); sem ele, para a home do idioma.
    home = caminho_publico(request.i18n, request.idioma, "/")
    destino = destino_local(request.GET.get("next"), home)
    # O `site` viaja junto com o `next`, para a `identidade` anunciar de qual
    # site a pessoa entrou.
    entrada = f"{url_de_entrada()}?" + urlencode(
        {"next": destino, "site": request.site["id"]}
    )
    # Token de CSRF do formulário de senha; sem ele o template não o desenha.
    token_de_senha = IdentidadeClient().emitir_token_de_senha()
    return render(
        request,
        "funil/login.html",
        {
            "url_de_entrada": entrada,
            "url_de_entrada_por_senha": url_de_entrada_por_senha(),
            "erro": erro,
            "destino": destino,
            "token_de_senha": token_de_senha,
        },
    )


def _login_para(request):
    destino = caminho_publico(request.i18n, request.idioma, "/login")
    return HttpResponseRedirect(f"{destino}?{urlencode({'next': request.path})}")


@require_safe
def notificacoes(request):
    if getattr(request, "idioma", None) is None:
        raise Http404("notificações só existem em site registrado no i18n")
    ator = getattr(request, "ator", None)
    if not ator or not ator.id:
        return _login_para(request)
    itens = buscar_avisos(ator.id, request.site["id"])
    if itens is None:
        return render(
            request,
            "funil/notificacoes.html",
            {"falha": True, "avisos": []},
            status=503,
        )
    avisos = avisos_para_tela(itens, ator.id, request.site["id"], request.idioma)
    return render(
        request,
        "funil/notificacoes.html",
        {
            "falha": False,
            "avisos": avisos,
            "nao_lidos": sum(1 for aviso in avisos if not aviso["lido_em"]),
        },
    )


@require_POST
def marcar_notificacao_lida(request, aviso_id):
    if getattr(request, "idioma", None) is None:
        raise Http404("notificações só existem em site registrado no i18n")
    ator = getattr(request, "ator", None)
    if not ator or not ator.id:
        return _login_para(request)
    resultado = marcar_aviso(ator.id, request.site["id"], aviso_id)
    if resultado is False:
        raise Http404("aviso inexistente, ou de outra pessoa")
    if resultado is None:
        return render(
            request,
            "funil/notificacoes.html",
            {"falha": True, "avisos": []},
            status=503,
        )
    limpar_cache_de_avisos()
    return HttpResponseRedirect(
        caminho_publico(request.i18n, request.idioma, "/notificacoes")
    )


@require_POST
def marcar_todas_notificacoes_lidas(request):
    if getattr(request, "idioma", None) is None:
        raise Http404("notificações só existem em site registrado no i18n")
    ator = getattr(request, "ator", None)
    if not ator or not ator.id:
        return _login_para(request)
    if marcar_todos(ator.id, request.site["id"]) is None:
        return render(
            request,
            "funil/notificacoes.html",
            {"falha": True, "avisos": []},
            status=503,
        )
    limpar_cache_de_avisos()
    return HttpResponseRedirect(
        caminho_publico(request.i18n, request.idioma, "/notificacoes")
    )


@require_safe
def sitemap_xml(request):
    """Sitemap do site: URLs absolutas no host canônico, só dos idiomas indexáveis;
    404 em site monolíngue."""
    if getattr(request, "idioma", None) is not None or request.path != "/sitemap.xml":
        # Rota de máquina: sem prefixo de idioma.
        raise Http404("sitemap não tem prefixo de idioma")
    cfg = getattr(request, "i18n", None)
    if cfg is None:
        raise Http404("site sem sitemap")
    host = request.site["host"]

    urls = [
        # O caminho sai do caminho_publico, que sabe se o idioma leva prefixo.
        f"https://{host}{caminho_publico(cfg, codigo, pagina)}"
        for codigo, definicao in cfg["idiomas"].items()
        if definicao["indexavel"]  # idiomas noindex ficam fora
        for pagina in PAGINAS_PUBLICAS
    ]
    linhas = "\n".join(f"  <url><loc>{u}</loc></url>" for u in urls)
    corpo = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{linhas}\n"
        "</urlset>\n"
    )
    return HttpResponse(corpo, content_type="application/xml")


# O resumo do Meshcraft para IAs (04/10/2026). O texto mora num arquivo ao lado
# desta view para ser editado sem mexer em código.
TEXTO_PARA_IAS = Path(__file__).resolve().parent / "llms.txt"


@require_safe
def llms_txt(request):
    """`/llms.txt`: o resumo da escola que as IAs procuram na raiz do site.
    Só no meshcraft.top, e sem prefixo de idioma."""
    if getattr(request, "idioma", None) is not None or request.path != "/llms.txt":
        raise Http404("llms.txt não tem prefixo de idioma")
    if request.site["host"] != "meshcraft.top":
        raise Http404("o resumo para IAs é só do meshcraft.top")
    return HttpResponse(
        TEXTO_PARA_IAS.read_text(encoding="utf-8"),
        content_type="text/plain; charset=utf-8",
    )


# Áreas de conta e de compra: nada nelas serve a um buscador.
FECHADO_PARA_ROBOS = ("/admin/", "/api/", "/checkout/", "/notificacoes", "/ver-como")


@require_safe
def robots_txt(request):
    """`/robots.txt`: libera os buscadores, fecha as áreas de conta e aponta o
    sitemap (e, no meshcraft.top, o resumo para IAs); 404 em site monolíngue."""
    if getattr(request, "idioma", None) is not None or request.path != "/robots.txt":
        raise Http404("robots.txt não tem prefixo de idioma")
    if getattr(request, "i18n", None) is None:
        raise Http404("site sem robots.txt")
    host = request.site["host"]
    linhas = []
    if host == "meshcraft.top":
        linhas.append(f"# Resumo do site para IAs: https://{host}/llms.txt")
    linhas.append("User-agent: *")
    linhas.extend(f"Disallow: {caminho}" for caminho in FECHADO_PARA_ROBOS)
    linhas.extend(["", f"Sitemap: https://{host}/sitemap.xml"])
    return HttpResponse("\n".join(linhas) + "\n", content_type="text/plain; charset=utf-8")


# O app instalável na tela do celular: manifesto e service worker, na raiz do site.
COR_DO_APP = "#16a34a"
FUNDO_DO_APP = "#f7f7f8"
ICONES_DO_APP = [
    {
        "src": "/static/funil/pwa/icone-192.png",
        "sizes": "192x192",
        "type": "image/png",
        "purpose": "any",
    },
    {
        "src": "/static/funil/pwa/icone-512.png",
        "sizes": "512x512",
        "type": "image/png",
        "purpose": "any",
    },
    # Variante `maskable`, que o Android recorta na forma do aparelho.
    {
        "src": "/static/funil/pwa/icone-maskable-512.png",
        "sizes": "512x512",
        "type": "image/png",
        "purpose": "maskable",
    },
]


@require_safe
def manifesto_do_app(request):
    """`/manifest.webmanifest`: manifesto do app instalado; 404 fora do registro i18n.
    O `start_url` usa o idioma de `?idioma=`; código desconhecido cai no padrão."""
    if getattr(request, "idioma", None) is not None:
        raise Http404("manifesto não tem prefixo de idioma")
    cfg = getattr(request, "i18n", None)
    if cfg is None:
        raise Http404("site sem app instalável")

    pedido = request.GET.get("idioma") or ""
    codigo = pedido if pedido in cfg["idiomas"] else cfg["default"]
    nome = request.site["name"]

    return JsonResponse(
        {
            "name": nome,
            "short_name": nome,
            "lang": tag_bcp47(codigo),
            "dir": direcao(codigo),
            "start_url": caminho_publico(cfg, codigo, "/"),
            # O escopo é o site inteiro, para links internos abrirem dentro do app.
            "scope": "/",
            "display": "standalone",
            "orientation": "portrait",
            "background_color": FUNDO_DO_APP,
            "theme_color": COR_DO_APP,
            "icons": ICONES_DO_APP,
        },
        content_type="application/manifest+json",
        json_dumps_params={"ensure_ascii": False},
    )


@require_safe
def service_worker(request):
    """`/sw.js`: o `static/funil/sw.js` servido da raiz, com os textos dos avisos
    no idioma de `?idioma=`."""
    if getattr(request, "idioma", None) is not None:
        raise Http404("service worker não tem prefixo de idioma")

    # O idioma vem da query (rota sem prefixo); código desconhecido usa o idioma fonte.
    idioma = request.GET.get("idioma") or ""
    if idioma not in cat.IDIOMAS_BASE:
        idioma = cat.IDIOMA_FONTE

    textos = {
        assunto: {
            "titulo": cat.t(f"avisos.js.{chave}_titulo", idioma),
            "corpo": cat.t(f"avisos.js.{chave}_corpo", idioma),
        }
        for assunto, chave in TIPOS_POR_ASSUNTO.items()
    }
    configuracao = {
        # Página aberta ao tocar na notificação.
        "caminho": url_dos_avisos(),
        "links": links_para_o_celular(),
        "textos": textos,
        "generico": {
            "titulo": cat.t("avisos.js.generico_titulo", idioma),
            "corpo": cat.t("avisos.js.generico_corpo", idioma),
        },
    }
    arquivo = Path(settings.STATICFILES_DIRS[0]) / "funil" / "sw.js"
    corpo = (
        "// Injetado por apps/core/views.py::service_worker — os textos do\n"
        "// aviso no idioma de quem instalou. O arquivo abaixo é\n"
        "// static/funil/sw.js, palavra por palavra.\n"
        f"self.AVISOS_DO_SITE = {json.dumps(configuracao, ensure_ascii=False)};\n"
        + arquivo.read_text(encoding="utf-8")
    )
    resposta = HttpResponse(corpo, content_type="text/javascript")
    resposta["Service-Worker-Allowed"] = "/"
    resposta["Cache-Control"] = "no-cache"
    return resposta


# Ligar e desligar os avisos no celular: o navegador manda a inscrição do
# aparelho para cá e o servidor a repassa à `notificacoes`.
TETOS_DA_INSCRICAO = {"endpoint": 2048, "p256dh": 256, "auth": 64}


def _inscricao_do_corpo(request) -> dict:
    """Lê e confere as três partes da inscrição do aparelho, dentro dos tetos."""
    try:
        corpo = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError("payload inválido")
    if not isinstance(corpo, dict):
        raise ValueError("payload inválido")
    inscricao = {}
    for campo, teto in TETOS_DA_INSCRICAO.items():
        valor = corpo.get(campo)
        if not isinstance(valor, str) or not valor.strip() or len(valor) > teto:
            raise ValueError(f"{campo} ausente ou inválido")
        inscricao[campo] = valor.strip()
    return inscricao


@require_POST
def ligar_avisos(request):
    """Registra o aparelho da pessoa na `notificacoes`; exige login (401 sem ele)."""
    if getattr(request, "idioma", None) is None:
        raise Http404("avisos só existem em site registrado no i18n")
    ator = getattr(request, "ator", None)
    if not ator or not ator.id:
        return JsonResponse({"erro": "é preciso entrar primeiro"}, status=401)
    try:
        inscricao = _inscricao_do_corpo(request)
    except ValueError as erro:
        return JsonResponse({"erro": str(erro)}, status=422)

    ligado = NotificacoesClient().inscrever_aparelho(
        destinatario_id=ator.id, site_id=request.site["id"], inscricao=inscricao
    )
    # 502 quando a caixa não confirmou, para a tela poder dizer "tente de novo".
    return JsonResponse({"ligado": ligado}, status=200 if ligado else 502)


@require_POST
def desligar_avisos(request):
    """Remove o aparelho (pelo `endpoint`) dos avisos; não exige login."""
    if getattr(request, "idioma", None) is None:
        raise Http404("avisos só existem em site registrado no i18n")
    try:
        corpo = json.loads(request.body or b"{}")
        endpoint = corpo.get("endpoint") if isinstance(corpo, dict) else None
        if not isinstance(endpoint, str) or not endpoint.strip():
            raise ValueError
        endpoint = endpoint.strip()
        if len(endpoint) > TETOS_DA_INSCRICAO["endpoint"]:
            raise ValueError
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return JsonResponse({"erro": "endpoint ausente ou inválido"}, status=422)

    desligado = NotificacoesClient().esquecer_aparelho(
        site_id=request.site["id"], endpoint=endpoint
    )
    return JsonResponse({"desligado": desligado}, status=200 if desligado else 502)


@require_POST
def capturar_lead(request):
    """Recebe o formulário e repassa o lead à `leads` com o `site_id` do site,
    nunca do payload."""
    try:
        corpo = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return HttpResponseBadRequest("payload inválido")

    email = corpo.get("email")
    if not email:
        return JsonResponse({"erro": "email obrigatório"}, status=422)

    payload = {
        "site_id": request.site["id"],
        "email": email,
        "name": corpo.get("name") or "",
        "phone": corpo.get("phone") or "",
        "source": corpo.get("source") or "funil",
        "utm": corpo.get("utm") or {},
    }
    resultado = LeadsClient().upsert_lead(payload)
    _medir_lead(request, corpo.get("contexto"), resultado)
    return JsonResponse(resultado, status=200)


def _medir_lead(request, token, resultado) -> None:
    """Publica `funil.lead-capturado` quando o lead nasceu numa página medida."""
    contexto = telemetria.ler_contexto(token, request.site["id"])
    lead_id = resultado.get("lead_id") if isinstance(resultado, dict) else None
    visitante = id_valido(request.COOKIES.get(COOKIE, ""))
    if not (contexto and isinstance(lead_id, str) and lead_id and visitante):
        return
    telemetria.publicar(
        "funil.lead-capturado",
        1,
        {
            "site_id": request.site["id"],
            "visitor_id": visitante,
            "pagina_slug": contexto["p"],
            "pagina_version": contexto["v"],
            "lead_id": lead_id,
            **telemetria.braco_do_contexto(contexto),
        },
        event_id=telemetria.id_do_fato(
            contexto["c"], visitante, "lead-capturado", lead_id
        ),
    )


#: Tamanho máximo, em bytes, do corpo de um fato do navegador.
TETO_DO_FATO_DO_NAVEGADOR = 2048

#: Campos aceitos em cada fato; o `visitor_id` vem do cookie, não do corpo.
CAMPOS_DO_FATO = {
    "secao-vista": {"contexto", "evento", "secao"},
    "cta-clicado": {"contexto", "evento", "secao", "slot", "destino"},
}


@require_POST
def telemetria_do_navegador(request):
    """`POST /telemetria`: registra seção vista e clique no botão. O corpo JSON
    traz o `contexto` assinado, o `evento` e seus campos; responde 204 ou 400."""
    if len(request.body) > TETO_DO_FATO_DO_NAVEGADOR:
        return HttpResponseBadRequest("fato grande demais")
    try:
        corpo = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return HttpResponseBadRequest("o corpo não é JSON")
    evento = corpo.get("evento") if isinstance(corpo, dict) else None
    campos = CAMPOS_DO_FATO.get(evento) if isinstance(evento, str) else None
    if campos is None or set(corpo) != campos:
        return HttpResponseBadRequest(
            "fato desconhecido ou com campos fora do contrato"
        )

    contexto = telemetria.ler_contexto(corpo["contexto"], request.site["id"])
    if contexto is None:
        return HttpResponseBadRequest("contexto que esta página não assinou")
    if evento == "secao-vista":
        partes = [corpo["secao"]]
        aceito = corpo["secao"] in contexto["e"]
    else:
        partes = [corpo["secao"], corpo["slot"], corpo["destino"]]
        aceito = partes in contexto["b"]
    if not aceito:
        return HttpResponseBadRequest("seção ou botão que esta página não desenhou")

    visitante = id_valido(request.COOKIES.get(COOKIE, ""))
    if visitante:
        dados = {
            "site_id": request.site["id"],
            "visitor_id": visitante,
            "pagina_slug": contexto["p"],
            "pagina_version": contexto["v"],
            "secao": corpo["secao"],
            **telemetria.braco_do_contexto(contexto),
        }
        if evento == "cta-clicado":
            dados["slot"] = corpo["slot"]
            dados["destino"] = corpo["destino"]
        telemetria.publicar(
            f"funil.{evento}",
            1,
            dados,
            event_id=telemetria.id_do_fato(contexto["c"], visitante, evento, *partes),
        )
    return HttpResponse(status=204)


@require_http_methods(["GET", "POST"])
def ver_como_view(request):
    """Tela para a equipe ver o site como outro papel; grava a escolha em cookie.
    404 para quem não é da equipe; o cookie só muda a exibição, não a sessão."""
    if getattr(request, "idioma", None) is None:
        raise Http404("ver-como só existe em site registrado no i18n")
    ator = getattr(request, "ator", None)
    if not ator or ator.papel != ver_como.PAPEL_DE_EQUIPE:
        raise Http404("ver-como é da equipe")

    if request.method == "POST":
        escolha = ver_como.disfarce_valido(request.POST.get("como", ""))
        destino = HttpResponseRedirect(
            caminho_publico(request.i18n, request.idioma, "/")
        )
        if escolha:
            destino.set_cookie(
                ver_como.COOKIE,
                escolha,
                # Sem `max_age`: o disfarce acaba quando o navegador fecha.
                httponly=True,
                samesite="Lax",
                secure=request.is_secure(),
            )
        else:
            # Valor fora da lista também remove o disfarce.
            destino.delete_cookie(ver_como.COOKIE)
        return destino

    return render(
        request,
        "funil/ver_como.html",
        {"disfarces": ver_como.DISFARCES, "atual": ator.ver_como},
    )
