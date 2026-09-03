import json
from pathlib import Path
from urllib.parse import urlencode

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
from django.views.decorators.http import (
    require_http_methods,
    require_POST,
    require_safe,
)
from django.views.static import serve as serve_do_django

from apps.core.clients import (
    AlunosClient,
    CatalogoClient,
    IdentidadeClient,
    LeadsClient,
    NotificacoesClient,
)
from apps.core import ver_como
from apps.core.enderecos import (
    url_de_entrada,
    url_de_entrada_por_senha,
    url_dos_avisos,
)
from apps.i18n import catalogo as cat
from apps.i18n.idiomas import caminho_publico, direcao, tag_bcp47

# Ordem fixa: é também a ordem em que a query string do link do checkout é
# montada — preservar isso torna o teste de UTM determinístico.
CHAVES_UTM = ("utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content")

# Páginas públicas localizadas da célula, para o sitemap (fase 2; a Receita
# R12 da fase 3 decide se isto vira registro por página).
PAGINAS_PUBLICAS = ("/", "/cadastro")


def _utm_da_requisicao(request) -> dict:
    return {chave: valor for chave in CHAVES_UTM if (valor := request.GET.get(chave))}


@require_safe
def healthz(request):
    return JsonResponse({"status": "ok"})


@require_safe
def verificacao_do_google(request):
    """`/google0e78b54775677e95.html` — verificação de propriedade do Google
    Search Console para meshcraft.top (31/08/2026). Rota de MÁQUINA como o
    /healthz: conteúdo fixo, sem Site e sem prefixo de idioma — o Google bate
    exatamente neste caminho, sem conhecer nem se importar com o catálogo de
    sites."""
    return HttpResponse(
        "google-site-verification: google0e78b54775677e95.html",
        content_type="text/plain",
    )


def servir_estatico(request, path):
    """Estáticos em produção. Sem esta rota o formulário da landing não existe.

    Com `DEBUG=0` o Django não serve estático por conta própria, e esta célula
    está SOZINHA atrás do Traefik: não há nginx, CDN nem router `/static` no
    gateway (o catch-all `PathPrefix(/)` manda tudo para cá). Resultado medido
    ao vivo em 24/08/2026: `/static/funil/api.js` respondia 404 nos dois
    domínios, as landings carregavam esse `<script>` mesmo assim, e a ilha
    Alpine quebrava no `api.post(...)` — em silêncio para o visitante. A célula
    checkout resolveu o MESMO problema assim em 22/08/2026 e está verde em
    produção desde então; aqui se copia o padrão, não o arquivo (Lei 7).

    Duas escolhas que parecem detalhe e são o fix:

    1. **Serve do diretório-FONTE (`STATICFILES_DIRS[0]`), nunca de
       `STATIC_ROOT`.** O `collectstatic --noinput || true` do Dockerfile falha
       em TODO build — não há `DJANGO_SECRET_KEY` em tempo de build e o
       `settings.py` é fail-hard — e o `|| true` engole o erro: a imagem sobe
       com `STATIC_ROOT` vazio. Servir de lá (o default do whitenoise, entre
       outros) manteria o 404 com a suíte inteira verde. O diretório-fonte
       está na imagem pelo `COPY . .`, e é o mesmo caminho em dev e em prod.
    2. **É rota de MÁQUINA e nunca se localiza (D6).** O resolver de idioma
       decapa o prefixo em `path_info` ANTES da resolução de URL, então sem
       esta guarda `/pt-br/static/funil/api.js` passaria a responder 200 —
       uma URL de máquina por idioma, conteúdo duplicado para robô e
       superfície nova para ninguém. Mesma guarda do `sitemap_xml` abaixo.
    """
    if getattr(request, "idioma", None) is not None:
        raise Http404("estático não tem prefixo de idioma")
    return serve_do_django(request, path, document_root=settings.STATICFILES_DIRS[0])


@require_safe
def landing(request):
    """A raiz do site — duas páginas diferentes, escolhidas pelo regime do site.

    **Site registrado no i18n (meshcraft.top): a HOME.** Decisão do mantenedor
    em 27/08/2026 — a raiz deixou de ser vitrine de oferta e virou porta: quem
    entrou vê o aviso de novidade e o caminho para a Caixa; quem não entrou vê
    o convite para entrar. O conteúdo inteiro sai do catálogo de tradução e da
    sessão, então **esta página não pergunta oferta nenhuma ao catálogo** — e
    é isso que a faz abrir num site sem `default_offer_slug`, onde ela
    respondia 404 até hoje. Um 404 na raiz por causa de um campo que a página
    não usa mais seria uma falha invisível para quem a abre.

    **Site NÃO registrado (os domínios monolíngues): a vitrine de sempre**
    ([RECEITA:R6 v1]) — lê a default_offer do site (R2, server-side) e monta o
    link do checkout preservando UTM na query string. Intocada, byte a byte
    (golden da fase 1): dois templates e dois caminhos, nunca um `if` dentro
    de um só.
    """
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
    query = urlencode(utm)
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


class FormularioDeCadastro(forms.Form):
    """Validação server-side da página de cadastro. As mensagens de erro são
    as do próprio Django — o activate() do resolver (fase 1) as localiza.

    `whatsapp` é OBRIGATÓRIO — ao contrário do antigo `phone` opcional da
    versão de captura de lead. Esta página deixou de ser "deixe seu contato
    para acompanhar novidades" e virou o pedido de entrada de quem não tem
    conta do Google (decisão do mantenedor, 31/08/2026): sem WhatsApp o
    mantenedor não tem como avisar a pessoa da decisão, e a porta
    `POST /pre-matriculas` da célula `alunos` já recusa o pedido por essa
    mesma razão (`nome_completo e whatsapp são obrigatórios`) — o form aqui só
    adianta a mesma regra, no idioma da página.

    `senha`/`confirmar_senha` (`DECISAO-login-por-senha.md`, também
    31/08/2026): a pessoa escolhe a senha JUNTO com o pedido de vaga, não
    numa etapa separada depois da aprovação — decisão do mantenedor. Mínimo
    de 8 caracteres, mesma régua que `AUTH_PASSWORD_VALIDATORS` já exige do
    lado da `identidade`; conferir aqui adianta o erro no idioma da página
    em vez de um 502 vindo de uma validação que só existe do outro lado.

    **A conferência "as duas senhas batem?" NÃO mora em `clean()`**: a
    mensagem de erro vem do catálogo de tradução (`apps.i18n.catalogo`, não
    do gettext do Django, que é o que localiza os erros DE CAMPO acima), e
    `clean()` não tem `request.idioma`. Quem faz essa conferência é a view
    `cadastro`, depois de `is_valid()`.
    """

    name = forms.CharField(max_length=200)
    email = forms.EmailField()
    whatsapp = forms.CharField(max_length=32)
    senha = forms.CharField(min_length=8, widget=forms.PasswordInput)
    confirmar_senha = forms.CharField(min_length=8, widget=forms.PasswordInput)


# HEAD junto com GET, sempre: `require_http_methods` NÃO o inclui de graça (o
# `require_safe` das views de leitura inclui, e foi por isso que esta escapou do
# conserto de 25/08). Um HEAD nesta página respondia 405 — e ela está no
# sitemap, então quem a chama assim é justamente robô de busca e
# pré-visualizador de link. Medido em produção depois do deploy do PR #158.
@require_http_methods(["GET", "HEAD", "POST"])
def cadastro(request):
    """O pedido de entrada de quem não tem conta do Google.

    Até 31/08/2026 esta página era captura de lead ("deixe seu nome e e-mail
    para acompanhar as novidades") — um site de notícias, não uma escola.
    Decisão do mantenedor nessa data: quem não tem Google (a ÚNICA porta de
    login do site, `DECISAO-celula-de-identidade.md`) ainda precisa de um
    jeito de virar aluno, e o jeito é este formulário entrar DIRETO na mesma
    fila "Aguardando aprovação" que o admin já gerencia em
    `/admin/escola/alunos/` — a mesma porta `POST /pre-matriculas` que o
    cadastro à mão do admin e o pedido de entrada da Caixa (para quem já
    logou com o Google) usam. Nenhum contrato novo: um terceiro consumidor do
    mesmo endpoint congelado (`AlunosClient.criar_pre_matricula`).

    O form posta para a PRÓPRIA URL prefixada (decisão da maestro sobre a
    pendência 1 do PR #87): o resolver decapa o prefixo, esta view recebe e
    repassa à célula alunos server-side, com `site_id` do Host (INV-P11) —
    nunca do payload.

    Desde o D1 revisto (25/08/2026) o caminho nu `/cadastro` **é** a página em
    inglês, e o POST dele chega aqui normalmente. Na matriz antiga ele morria
    404 antes desta view — o caminho nu era um 302 para `/en/cadastro`, e
    redirecionar um POST converteria o método em GET e descartaria o corpo em
    silêncio, então recusar era o menos pior. Sem redirecionamento no meio, o
    problema deixou de existir."""
    if getattr(request, "idioma", None) is None:
        # Site fora do registro i18n não tem cadastro — 404, o mesmo que o
        # caminho respondia antes desta fase (rota inexistente).
        raise Http404("cadastro só existe em site registrado no i18n")

    sucesso, ja_matriculado, erro_envio, status = False, False, False, 200
    # [LOGIN-POR-SENHA] Flag própria, não `form.add_error()`: a mensagem sai
    # do catálogo de tradução via `{% t %}` NO TEMPLATE (mesmo padrão de
    # `sucesso`/`ja_matriculado`/`erro_envio` logo abaixo) — não em Python,
    # onde o validador do i18n não veria a chave sendo usada (ela só conta
    # como "usada" dentro de um `{% t %}` real num arquivo de template).
    senhas_diferentes = False
    if request.method == "POST":
        form = FormularioDeCadastro(request.POST)
        if form.is_valid():
            senhas_diferentes = (
                form.cleaned_data["senha"] != form.cleaned_data["confirmar_senha"]
            )
        if form.is_valid() and not senhas_diferentes:
            resultado = AlunosClient().criar_pre_matricula(
                site_id=request.site["id"],  # [INV-P11] do Host, não do payload
                email=form.cleaned_data["email"],
                nome_completo=form.cleaned_data["name"],
                whatsapp=form.cleaned_data["whatsapp"],
            )
            if resultado == AlunosClient.RESULTADO_NA_FILA:
                # A senha só é gravada quando o pedido de vaga deu certo — uma
                # senha "órfã" para um e-mail que nunca entrou na fila não
                # serviria a ninguém. Fail-CLOSED aqui (decisão do
                # mantenedor, DECISAO-login-por-senha.md §1.3): se a senha
                # não puder ser gravada, o pedido inteiro é tratado como não
                # enviado — reenviar é seguro, `entrar_na_fila` do lado da
                # alunos é idempotente por e-mail.
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
                # Não é erro de envio (ARMADILHAS §4.9 é sobre falha de rede):
                # o pedido chegou, só que esta pessoa já está na plataforma. A
                # tela explica em vez de repetir "cadastro recebido" para
                # quem talvez precise é só entrar com o Google.
                ja_matriculado = True
            else:
                # Falha fechada e honesta (ARMADILHAS §4.9): nada de 200 com
                # cara de sucesso — 502 com a página e o que a pessoa digitou.
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


# O vocabulário de recusa da célula `identidade` (LICOES.md dela: "o
# vocabulário de recusa é CONTRATO com o funil") — toda recusa da porta volta
# para esta página com `?erro=<chave>`, e cada chave tem tradução própria em
# `traducoes/login.yaml`. Chave fora desta lista é ignorada em silêncio: query
# string é entrada de rede, nunca vira chave de catálogo sem passar na cerca.
def destino_local(cru: str | None, padrao: str) -> str:
    """Só caminho LOCAL deste site — nunca um endereço de fora.

    O `?next=` chega pela URL, então é entrada de rede. A célula `identidade`
    sanea de novo do lado dela (`views.destino_seguro`), e é lá que mora a
    defesa que importa — esta aqui é a segunda camada, para o valor que ESTE
    site monta no link nunca ser o vetor. `//outro-site` é o clássico: o
    navegador o lê como endereço absoluto sem esquema.
    """
    if not cru or not cru.startswith("/") or cru.startswith("//"):
        return padrao
    if "\\" in cru or any(ord(c) < 0x20 for c in cru):
        return padrao
    return cru


CHAVES_DE_RECUSA = {
    "interrompida",
    "nao-confere",
    "nao-configurada",
    "google-indisponivel",
    "email-nao-verificado",
    # [LOGIN-POR-SENHA] O vocabulário de recusa de /entrar/senha
    # (DECISAO-login-por-senha.md §6.1) — "senha-invalida" serve tanto para
    # "e-mail sem conta" quanto para "senha errada", de propósito.
    "senha-invalida",
    "muitas-tentativas",
}


@require_safe
def entrar(request):
    """A porta de entrada do site — `/login` em inglês, `/{idioma}/login` nos outros.

    Leis: DECISAO-onde-mora-a-sessao e, desde 25/08/2026,
    DECISAO-celula-de-identidade. Ela leva ao Google; a sessão nasce do outro
    lado, na célula `identidade`. **Esta view não abre sessão nenhuma e não lê
    cookie nenhum** — quem faz isso é quem tem a chave e o banco (Lei 2, Lei 3).

    O `?next=` diz à `identidade` aonde devolver a pessoa depois de entrar —
    a home do idioma desta página. E o `?erro=` é a volta do vocabulário de
    recusa: a porta de lá não renderiza página; quem explica a recusa, nos
    três idiomas, é esta tela.

    Fora do sitemap de propósito: página de entrada não é conteúdo que alguém
    procure no Google, e indexá-la só a faria concorrer com a própria marca.
    """
    if getattr(request, "idioma", None) is None:
        # Mesmo tratamento do cadastro: site fora do registro i18n não tem esta
        # página — 404, e não uma página em inglês servida por engano.
        raise Http404("login só existe em site registrado no i18n")
    erro = request.GET.get("erro") or ""
    if erro not in CHAVES_DE_RECUSA:
        erro = ""
    # A pessoa volta para ONDE ESTAVA, não para a home. O cabeçalho de sessão
    # de toda página manda o caminho atual no `?next=`; sem isso, quem clicava
    # "Entrar" no meio de um cadastro meio preenchido voltava para a home e
    # perdia o que tinha digitado.
    # O fallback é a home DESTE idioma, e ela sai do caminho_publico como
    # qualquer outra URL pública. Escrevê-la à mão aqui — f"/{idioma}/" — era a
    # QUARTA cópia da regra de prefixo, e a que mais doeria: no idioma padrão
    # ela devolveria a pessoa, depois de entrar, para /en/ — 404 desde o D1
    # revisto (25/08/2026). Quem não passa `?next=` é justamente quem clicou
    # "Entrar" na home.
    home = caminho_publico(request.i18n, request.idioma, "/")
    destino = destino_local(request.GET.get("next"), home)
    # `site` viaja junto com o `next` desde 31/08/2026 (degrau 1 do
    # PLANO-SEQUENCIAS-DE-MENSAGENS): a célula `identidade` cunha a pessoa e
    # anuncia o fato, e o fato precisa dizer de QUAL site alguém entrou. Ela não
    # resolve Host→Site (isso é do catálogo, e ela nem fala com ele), então quem
    # manda o site é quem já o resolveu — esta célula, aqui, com o valor que o
    # CONV-SITE pôs em `request.site`.
    #
    # Do outro lado ele é tratado como entrada de rede: saneado por forma, e
    # usado só para escolher a quem o cadastro pertence, nunca para autorizar.
    # Faltando, a pessoa entra igual e o fato não é anunciado.
    entrada = f"{url_de_entrada()}?" + urlencode(
        {"next": destino, "site": request.site["id"]}
    )
    # [LOGIN-POR-SENHA] O token que defende /entrar/senha de CSRF
    # (DECISAO-login-por-senha.md §3) — buscado aqui, fail-open na EXIBIÇÃO:
    # `None` faz o template simplesmente não desenhar o mini-formulário de
    # senha, e o botão do Google continua funcionando sozinho.
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


@require_safe
def sitemap_xml(request):
    """D6: rota de MÁQUINA — nunca se localiza. Desde a fase 4 ela PRECISA do
    Site: os idiomas vêm do catálogo, então o CONV-SITE resolve o Host aqui
    como em qualquer rota (mesmo cache de 60s) e a view lê `request.i18n`. As
    URLs saem absolutas com o **host canônico do Site** — nunca
    `request.get_host()` (D5: preview não vaza pro sitemap de produção). Site
    monolíngue: 404, o comportamento de hoje, intocado."""
    if getattr(request, "idioma", None) is not None or request.path != "/sitemap.xml":
        # /en/sitemap.xml e afins: rota de máquina nunca se localiza (D6).
        raise Http404("sitemap não tem prefixo de idioma")
    cfg = getattr(request, "i18n", None)
    if cfg is None:
        raise Http404("site sem sitemap")
    host = request.site["host"]

    urls = [
        # O caminho sai do caminho_publico, nunca de uma f-string local: desde o
        # D1 revisto (25/08/2026) o idioma padrão não leva prefixo, e um sitemap
        # anunciando /en/ mandaria o Google a 404 nossos.
        f"https://{host}{caminho_publico(cfg, codigo, pagina)}"
        for codigo, definicao in cfg["idiomas"].items()
        if definicao["indexavel"]  # D5: es (noindex) fica fora
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


# ---------------------------------------------------------------------------
# O app instalado na tela do celular (pedido do mantenedor, 31/08/2026)
# ---------------------------------------------------------------------------
# As duas rotas de MÁQUINA que fazem um site virar app instalável. Elas moram
# na raiz e não se localizam, como o /healthz, o /sitemap.xml e o /static/ —
# mas por motivos diferentes, e vale escrever qual é cada um:
#
#   · o manifesto é do SITE, não da página: um por origem, e o navegador o
#     relê para decidir se oferece a instalação;
#   · o service worker manda na PASTA de onde foi baixado. Servido de
#     `/static/funil/sw.js` ele só mandaria em `/static/`, e o app não teria
#     como abrir sem rede. Por isso ele tem rota própria na raiz.
#
# A cor, o fundo e o desenho do ícone são a marca do site nas mãos de quem
# instalou: o verde é o mesmo do botão principal das páginas, e os PNGs saem
# do desenho versionado em `tests/test_icones_do_app.py`.
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
    # O `maskable` é o mesmo desenho, menor: o Android recorta o ícone na forma
    # que o aparelho usar, e sem esta variante ele desenha o nosso dentro de um
    # quadrado branco. São dois arquivos porque são dois usos, não por capricho.
    {
        "src": "/static/funil/pwa/icone-maskable-512.png",
        "sizes": "512x512",
        "type": "image/png",
        "purpose": "maskable",
    },
]


@require_safe
def manifesto_do_app(request):
    """`/manifest.webmanifest` — a ficha de identidade do app instalado.

    Site FORA do registro i18n responde 404, pelo mesmo critério do cadastro e
    do login: o app é do site da escola, que tem gente entrando e avisos para
    mandar; os domínios monolíngues são vitrine, e instalar uma vitrine não
    serve a ninguém.

    **O idioma vem da query string, e é saneado como toda entrada de rede.**
    O `start_url` é a página que abre quando a pessoa toca no ícone: quem
    instalou em português tem de abrir em português, e um manifesto só por
    origem não saberia disso sozinho. Código desconhecido cai no idioma padrão
    do site em silêncio, como o `?erro=` da página de entrada faz com chave
    fora da lista — nunca vira caminho.
    """
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
            # O escopo é o site inteiro de propósito: quem instalou e toca num
            # link do fórum ou da Caixa continua DENTRO do app, em vez de o
            # celular abrir o navegador por cima.
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


# Os textos do aviso que aparece na tela do celular, por assunto. A frase nasce
# na LEITURA, no idioma de quem lê (`DECISAO-notificacoes` §5.1) — e a leitura,
# aqui, acontece no aparelho: por isso os textos viajam para dentro do
# `/sw.js` em vez de serem escolhidos na hora de enviar. O catálogo é o mesmo
# de todo texto do site (`traducoes/avisos.yaml`), nunca uma segunda casa.
#
# Assunto que esta versão do site não conhece cai no genérico — e isso não é
# defeito: o aviso pode chegar de uma parte nova antes de o aparelho ter
# recarregado o service worker, e um aviso honesto e vago é melhor que
# nenhum. **Esse ramo só protege enquanto for possível cair nele**: a
# tentação de escrever `assunto.startswith("gamificacao.")` para "cobrir os
# quatro de uma vez" é um erro, porque o contrato pode ganhar um quinto
# assunto amanhã e o prefixo guloso o mostraria com a frase errada em vez de
# admitir que não o conhece. Um assunto, uma linha, sempre.
#
# **NENHUMA destas frases recebe parâmetro, e isso é decisão de desenho.**
# Repare no `static/funil/sw.js`: ele pega `AVISOS.textos[carta.assunto]` e
# usa `titulo` e `corpo` como strings PRONTAS, sem interpolação nenhuma. Não é
# um pedaço que faltou terminar, e "consertar" isso quebraria duas coisas de
# uma vez. Primeiro, `carta.parametros` nem sempre chega: quase todo parâmetro
# do contrato é opcional (`familia`, `validador_papel`, `semana`), o push pode
# vir truncado, e uma frase montada com buraco é pior que uma frase curta e
# inteira. Segundo, a tela do celular é um CONVITE para abrir o site, não o
# lugar de contar a novidade toda — a frase completa, com o número do nível e
# a família da medalha, já existe no sininho (`sugestoes`, degrau 21a). Cada
# frase daqui é verdadeira sozinha, sem depender de dado que talvez não venha.
TEXTOS_DO_AVISO = {
    "sugestao.status-alterado": "sugestao",
    # As quatro cartas de celebração da gamificação (degrau 21b, 01/09/2026),
    # congeladas em `contracts/eventos/notificacao.devida.v1.json`. Até aqui
    # as quatro caíam no genérico "Você tem um aviso novo", que é honesto e
    # não diz nada: quem subiu de nível merece saber disso pela tela.
    "gamificacao.nivel-alcancado": "nivel",
    "gamificacao.conquista-concedida": "conquista",
    "gamificacao.marco-validado": "marco",
    "gamificacao.destaque-da-semana": "destaque",
}


@require_safe
def service_worker(request):
    """`/sw.js` — o mesmo arquivo de `static/funil/sw.js`, servido da RAIZ.

    Serve para qualquer site, inclusive os monolíngues: só chega aqui quem
    pede, e quem pede é o `instalar.js`, que só existe nas páginas do site
    multilíngue. Uma condição a mais aqui seria uma regra a manter sem nenhum
    comportamento a proteger.

    `Service-Worker-Allowed: /` é cinto e suspensório: o escopo da raiz já vem
    do endereço, e o cabeçalho mantém a promessa caso este arquivo um dia
    passe a ser servido de outro lugar. `Cache-Control: no-cache` é o que faz
    uma correção neste arquivo alcançar quem já instalou: sem ele o navegador
    pode guardar o service worker por até 24 horas.
    """
    if getattr(request, "idioma", None) is not None:
        raise Http404("service worker não tem prefixo de idioma")

    # O idioma vem da QUERY porque esta é rota de máquina e não carrega
    # prefixo: quem o passa é `static/funil/instalar.js`, no registro. Código
    # desconhecido cai no idioma fonte, como toda entrada de rede desta célula.
    idioma = request.GET.get("idioma") or ""
    if idioma not in cat.IDIOMAS_BASE:
        idioma = cat.IDIOMA_FONTE

    textos = {
        assunto: {
            "titulo": cat.t(f"avisos.js.{chave}_titulo", idioma),
            "corpo": cat.t(f"avisos.js.{chave}_corpo", idioma),
        }
        for assunto, chave in TEXTOS_DO_AVISO.items()
    }
    configuracao = {
        # Para onde o toque na notificação leva. O endereço público é
        # conhecimento DESTA célula (apps/core/enderecos.py), nunca da
        # `notificacoes` — é por isso que ele viaja daqui e não do envio.
        "caminho": url_dos_avisos(),
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


# ---------------------------------------------------------------------------
# Ligar e desligar o aviso na tela do celular (Fase 7, 31/08/2026)
# ---------------------------------------------------------------------------
# O navegador entrega a inscrição do aparelho para o JAVASCRIPT da página; ele
# a manda para cá, e é o SERVIDOR que fala com a `notificacoes`. Nunca o
# contrário: o token do par funil→notificacoes é segredo de servidor, e uma
# chamada direta do navegador o entregaria a qualquer pessoa que abrisse o
# site. É a mesma forma do `/leads` (RECEITA R2).
TETOS_DA_INSCRICAO = {"endpoint": 2048, "p256dh": 256, "auth": 64}


def _inscricao_do_corpo(request) -> dict:
    """As três partes que o navegador dá, conferidas antes de sair daqui.

    Os tetos são os do contrato (`contracts/notificacoes.openapi.yaml`).
    Conferir aqui não substitui a cerca do outro lado — ela existe e é a que
    manda; esta evita um salto de rede para mandar algo que já se sabe
    inválido, e transforma lixo em 422 legível em vez de 502 confuso.
    """
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
    """A pessoa disse sim para o aviso na tela, e o navegador já deu a
    permissão. Aqui o aparelho dela vira uma linha na `notificacoes`.

    Precisa de gente entrando: um aviso é de alguém, e sem `request.ator` não
    há a quem endereçar. Fail-CLOSED aqui, ao contrário do sino: o sino some
    quando não sabe, e esta rota não pode inventar um destinatário.
    """
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
    # 502 e não 200 quando a caixa não confirmou: a tela precisa poder dizer
    # "não deu, tente de novo" em vez de prometer avisos que nunca chegariam.
    # É a lição do "2xx não é sucesso" (RETROSPECTIVA-FASE-D §1).
    return JsonResponse({"ligado": ligado}, status=200 if ligado else 502)


@require_POST
def desligar_avisos(request):
    """A pessoa desligou os avisos deste aparelho.

    NÃO exige sessão, de propósito: desligar acontece justamente quando a
    pessoa está saindo, e um aparelho que não consegue se desinscrever
    continuaria recebendo aviso de uma conta que já não usa. O `endpoint` é a
    prova de posse do aparelho — quem o tem é ele.
    """
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
    """[RECEITA:R2 v1] O formulário nunca fala direto com leads: posta aqui, e o
    servidor repassa com o site_id resolvido pelo CONV-SITE (nunca do payload)."""
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
    return JsonResponse(resultado, status=200)


@require_http_methods(["GET", "POST"])
def ver_como_view(request):
    """A tela de "ver o site como outra pessoa ve" — e a gravacao da escolha.

    Pedido do mantenedor em 02/09/2026, depois do PR #897: a conta dele entra
    pela porta da EQUIPE e nao tem matricula, entao o site nunca lhe mostrava a
    tela que um aluno ve — nem para conferir a propria correcao.

    **404 para quem nao e da equipe, e nao 403.** A porta nao confirma que ela
    existe para quem nao pode usa-la, que e a mesma regra da area
    administrativa. E a guarda e conferida AQUI, alem de em `ver_como.py`: uma
    trava so na leitura do cookie deixaria esta rota gravando disfarce para
    qualquer um — inofensivo hoje, e exatamente o tipo de porta esquecida que
    alguem encontra depois.

    O que ela grava e um cookie de EXIBICAO, que nao autoriza nada. O que ela
    NAO faz e mexer em sessao: sair do disfarce e apagar um cookie, nunca um
    logout — quem se disfarcou continua sendo quem era o tempo inteiro.
    """
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
                # Sem `max_age`: o disfarce morre quando o navegador fecha. Uma
                # previa que sobrevivesse a semana viraria o mantenedor vendo o
                # site errado dias depois sem lembrar por que.
                httponly=True,
                samesite="Lax",
                secure=request.is_secure(),
            )
        else:
            # Valor fora da lista tambem cai aqui, e volta ao normal de
            # proposito: a unica coisa pior que um disfarce errado e um
            # disfarce errado do qual nao se sai.
            destino.delete_cookie(ver_como.COOKIE)
        return destino

    return render(
        request,
        "funil/ver_como.html",
        {"disfarces": ver_como.DISFARCES, "atual": ator.ver_como},
    )
