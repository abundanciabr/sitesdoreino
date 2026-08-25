# apps/core/middleware.py  # [RECEITA:CONV-SITE v1] + resolver de idioma
# (PLANO-I18N §2 D1 — matriz HTTP; site sem idiomas = fluxo de hoje).
import re
import time

from django.http import Http404, HttpResponseRedirect
from django.utils import translation
from django.utils.cache import patch_vary_headers

from apps.core import enderecos
from apps.core.clients import CatalogoClient, IdentidadeClient
from apps.i18n.idiomas import dados_seo, idiomas_do_site

_CACHE: dict = {}
TTL_SEGUNDOS = 60

# ---------------------------------------------------------------------------
# Quem é a pessoa desta requisição (DECISAO-onde-mora-a-sessao)
# ---------------------------------------------------------------------------
# Cache por cabeçalho `Cookie` inteiro, e não pelo cookie de sessão isolado: o
# `funil` NÃO conhece o nome do cookie da outra célula, e não deve conhecer —
# saber o nome é o primeiro passo para tentar ler o conteúdo, que é justamente
# o que a Lei 3 proíbe. Ele repassa o cabeçalho opaco e pergunta.
_CACHE_DE_SESSAO: dict = {}
TTL_DA_SESSAO = 60
# Teto de segurança: sem ele, um robô mandando cookies diferentes a cada
# requisição faria o dicionário crescer sem fim dentro do processo. Estourou,
# esvazia — perder cache custa um salto interno, vazar memória custa a célula.
MAXIMO_DE_SESSOES_EM_CACHE = 500


def limpar_cache_de_sessao() -> None:
    _CACHE_DE_SESSAO.clear()


def _consultar_sessao(cookie: str) -> "dict | None":
    agora = time.time()
    hit = _CACHE_DE_SESSAO.get(cookie)
    if hit and hit[0] > agora:
        return hit[1]
    dados = IdentidadeClient().obter_sessao(cookie)
    if len(_CACHE_DE_SESSAO) >= MAXIMO_DE_SESSOES_EM_CACHE:
        _CACHE_DE_SESSAO.clear()
    # O `None` também é cacheado: visitante com cookie de outra coisa (ou sessão
    # expirada) não pode custar um salto interno por página que ele abrir.
    _CACHE_DE_SESSAO[cookie] = (agora + TTL_DA_SESSAO, dados)
    return dados


class AtorDaRequisicao:
    """Quem está vendo esta página — resolvido na PRIMEIRA leitura, nunca antes.

    Preguiçoso de propósito: a esmagadora maioria das requisições desta célula
    é de visitante anônimo em página de marketing, e nenhuma delas pode pagar um
    salto de rede para descobrir que não há ninguém. Página que não mostra o
    cabeçalho de sessão não pergunta nada.

    `identificado` é o que decide o cabeçalho de cache da resposta: página que
    mostrou o nome de ALGUÉM não pode ser guardada por proxy nenhum — é a
    diferença entre um detalhe de performance e o Cloudflare servindo o nome de
    uma pessoa para outra. Note que é `identificado`, e não "foi consultado":
    quase toda página consulta (o template pergunta "tem alguém?") e não
    identifica ninguém, e marcar as duas iguais tiraria o cache do site inteiro.
    """

    def __init__(self, cookie: str) -> None:
        self._cookie = cookie
        self._resolvido = False
        self._dados: "dict | None" = None

    @property
    def identificado(self) -> bool:
        """Alguém foi RECONHECIDO nesta requisição — não apenas consultado.

        A diferença decide o cabeçalho de cache, e ela não é sutil: quase toda
        página lida por um visitante anônimo *consulta* (o template pergunta se
        há alguém) e não *identifica* ninguém. Marcar as duas iguais tiraria o
        cache da vitrine inteira do site, que ninguém pediu.

        Não resolve nada por conta própria: é lida DEPOIS da resposta pronta,
        quando o template já decidiu se precisava ou não da sessão.
        """
        return self._resolvido and self._dados is not None

    def _resolver(self) -> "dict | None":
        if not self._resolvido:
            self._resolvido = True
            # Sem cookie nenhum não há o que perguntar. É o caminho de quase
            # todo visitante, e ele não toca a rede.
            self._dados = _consultar_sessao(self._cookie) if self._cookie else None
        return self._dados

    def __bool__(self) -> bool:
        """`{% if request.ator %}` — entrou ou não."""
        return self._resolver() is not None

    @property
    def nome(self) -> str:
        """Pode ser vazio: `nome_exibido` é editável pela pessoa. Quem exibe
        decide o que fazer com vazio — o template cai no rótulo genérico."""
        return (self._resolver() or {}).get("nome_exibido") or ""

    @property
    def papel(self) -> str:
        """Para EXIBIÇÃO apenas (mostrar ou não um atalho). Nunca para liberar
        coisa alguma: autorização é fail-closed, na célula dona do recurso
        (DECISAO-onde-mora-a-sessao §4)."""
        return (self._resolver() or {}).get("papel") or ""


# /healthz é sonda do container e do gateway — chega sem Host de site e não pode
# depender do catálogo estar de pé. Estáticos idem. A isenção roda ANTES de
# QUALQUER lógica.
CAMINHOS_SEM_SITE = ("/healthz", "/static/")

# Rota de MÁQUINA (D6): precisa do Site — desde a fase 4 os idiomas vêm do
# catálogo, e o sitemap é feito deles — mas NUNCA se localiza (nenhum prefixo
# de idioma, nenhum redirect da matriz D1). Custo do dado ter virado contrato:
# o sitemap deixou de ser servível com o catálogo fora do ar; em compensação
# usa o MESMO cache de 60s de qualquer outra rota.
CAMINHOS_DE_MAQUINA = ("/sitemap.xml",)

# D6: TODA rota de máquina desta célula — as isentas de Site e a que precisa
# dele. Nenhuma delas se localiza. As duas listas acima são conferidas no
# path_info CRU, no topo do __call__; esta é conferida DE NOVO depois de
# decapar o prefixo de idioma — é o único ponto em que dá para ver que
# /pt-br/healthz é a rota de máquina /healthz (desvio medido em 24/08/2026).
ROTAS_DE_MAQUINA = CAMINHOS_SEM_SITE + CAMINHOS_DE_MAQUINA

# D1/D6: primeiro segmento com FORMA de idioma (2-3 letras ± região, qualquer
# caixa/separador) que NÃO seja código habilitado ⇒ 404 fail-closed — cobre
# /fr/, /PT-BR/, /pt_br/ de uma vez. Caminho sem forma de idioma é "caminho nu".
RE_FORMA_DE_IDIOMA = re.compile(r"[A-Za-z]{2,3}([_-][A-Za-z0-9]{2,8})?\Z")

# O redirect é determinístico por decisão (nunca varia por usuário) ⇒ cacheável;
# max-age curto propaga troca de default em minutos (D1).
CACHE_DO_REDIRECT = "max-age=300"
METODOS_SEGUROS = ("GET", "HEAD")


def limpar_cache_de_sites() -> None:
    _CACHE.clear()


class SiteResolutionMiddleware:
    """[INV-P11] Resolve Host→Site UMA vez por requisição, via catálogo (com cache).
    Host não cadastrado ⇒ 404 — nunca um site padrão. Site que o catálogo serve
    com `languages` ⇒ resolve também o idioma do prefixo (fase 4: a fonte dos
    idiomas é o Site, não mais um arquivo local)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # ARMADILHAS §4.10: SEMPRE path_info, nunca path — request.path inclui
        # o script name/prefixo de gateway e a isenção deixaria de casar.
        if request.path_info.startswith(CAMINHOS_SEM_SITE):
            return self.get_response(request)
        host = request.get_host().split(":")[0].lower()
        site, cfg = self._resolver(host)
        if site is None:
            raise Http404("site desconhecido")
        request.site = site  # todo o resto da célula lê daqui
        request.i18n = cfg  # idiomas do site — None = monolíngue
        if cfg is None or request.path_info.startswith(CAMINHOS_DE_MAQUINA):
            # Monolíngue (fluxo de hoje, intocado) ou rota de máquina (D6).
            return self.get_response(request)
        return self._com_idioma(request, site, cfg)

    def _resolver(self, host: str):
        hit = _CACHE.get(host)
        if hit and hit[0] > time.time():
            return hit[1], hit[2]
        site = CatalogoClient().obter_site_por_host(host)
        # Os idiomas são derivados UMA vez por janela de cache, junto com o
        # Site: zero trabalho por request, e o ERROR de dado inválido não vira
        # enxurrada de log a cada acesso.
        cfg = idiomas_do_site(site)
        # Cacheia inclusive o 404 (site None).
        _CACHE[host] = (time.time() + TTL_SEGUNDOS, site, cfg)
        return site, cfg

    def _com_idioma(self, request, site, cfg):
        caminho = request.path_info
        seguro = request.method in METODOS_SEGUROS

        # Raiz: 302 fixo p/ /{default}/ — nunca 301 (301 cacheado travaria a
        # troca de default). Só GET/HEAD; POST perderia o corpo no redirect.
        if caminho == "/":
            if not seguro:
                raise Http404("raiz de site multilíngue não aceita método não-seguro")
            return self._redirect(f"/{cfg['default']}/", request)

        segmento, barra, resto = caminho[1:].partition("/")
        if segmento in cfg["idiomas"]:
            if not barra:  # /en → /en/ (uma forma canônica por página)
                if not seguro:
                    raise Http404("prefixo de idioma sem caminho")
                return self._redirect(f"/{segmento}/", request)
            caminho_sem_prefixo = f"/{resto}"
            if caminho_sem_prefixo.startswith(ROTAS_DE_MAQUINA):
                # D6: a isenção do topo casa o path_info CRU, e para
                # /pt-br/healthz ela NÃO casa — sem esta guarda o urlconf
                # resolveria a view e devolveria 200 numa URL que não
                # deveria existir. Cobre /healthz, /static/** e
                # /sitemap.xml de uma vez, e a próxima rota de máquina que
                # entrar nas listas, sem tocar neste método de novo.
                raise Http404(f"rota de máquina não se localiza: {caminho}")
            definicao = cfg["idiomas"][segmento]
            request.idioma = segmento
            request.i18n_seo = dados_seo(site, cfg, segmento, caminho_sem_prefixo)
            # O urlconf da célula continua sem prefixo: o resolver decapa o
            # idioma ANTES da resolução de URL (path_info é o que o Django
            # resolve; request.path segue completo p/ canonical/logs).
            request.path_info = caminho_sem_prefixo
            # Quem está vendo a página. Objeto preguiçoso: construí-lo não custa
            # nada, e só a leitura no template dispara a pergunta à Caixa. Fica
            # SÓ no regime prefixado, que é onde o login existe — site
            # monolíngue (os domínios antigos) segue byte-idêntico ao de antes.
            request.ator = AtorDaRequisicao(request.META.get("HTTP_COOKIE", ""))
            # O destino do link de quem já entrou. Fica no request (e não no
            # contexto de cada view) porque a peça `_sessao.html` aparece em
            # TODA página multilíngue: passá-lo view a view seria a mesma linha
            # repetida em cada uma, e a próxima view nasceria sem ela.
            request.url_da_caixa = enderecos.url_da_caixa()
            translation.activate(definicao["tag"])  # D2.4: runtime do Django LIGADO
            try:
                resposta = self.get_response(request)
            finally:
                translation.deactivate()
            return self._marcar_variacao_por_pessoa(request, resposta)

        if RE_FORMA_DE_IDIOMA.fullmatch(segmento):
            # /fr/…, /PT-BR/…, /pt_br/… — forma de idioma não habilitada:
            # 404 fail-closed, nunca redirect, nunca fallback (D1).
            raise Http404(f"idioma não habilitado para este site: {segmento}")

        # Caminho nu (/cadastro): preserva link curto de marketing via 302;
        # métodos não-seguros ⇒ 404 (redirect converteria POST em GET e
        # descartaria o corpo em silêncio — D1).
        if not seguro:
            raise Http404("caminho sem prefixo de idioma não aceita método não-seguro")
        return self._redirect(f"/{cfg['default']}{caminho}", request)

    @staticmethod
    def _marcar_variacao_por_pessoa(request, resposta):
        """Página que mostrou QUEM É a pessoa não pode ser guardada por ninguém.

        Sem isto, a página de um visitante logado é indistinguível — para um
        proxy — da de qualquer outro: mesma URL, mesmo status, corpo diferente.
        Há Cloudflare na frente de domínio desta plataforma
        (`armadilhas/017`), e um cache compartilhado servindo o nome de uma
        pessoa para outra é o pior bug possível desta entrega.

        Marca-se **apenas quando alguém foi RECONHECIDO** — não quando o
        template apenas perguntou. Visitante anônimo recebe a página genérica,
        e ela continua cacheável como sempre foi; senão o preço desta entrega
        seria a vitrine inteira deixar de ser cacheável.

        A assimetria é deliberada e vale escrever, porque parece um buraco e
        não é. Sem `Vary` na resposta anônima, um cache compartilhado pode
        servir a versão "Entrar" para alguém que já entrou. Isso é **feio, não
        perigoso**: a pessoa vê um botão a mais e um clique a devolve. A
        direção perigosa — conteúdo pessoal guardado num cache compartilhado —
        está fechada por completo, porque a resposta de quem foi reconhecido
        leva `no-store` e nunca chega a ser guardada por ninguém.

        `patch_vary_headers` acrescenta ao `Vary` existente em vez de
        sobrescrevê-lo.
        """
        ator = getattr(request, "ator", None)
        if ator is None or not ator.identificado:
            return resposta
        patch_vary_headers(resposta, ("Cookie",))
        resposta["Cache-Control"] = "private, no-store"
        return resposta

    @staticmethod
    def _redirect(destino: str, request) -> HttpResponseRedirect:
        query = request.META.get("QUERY_STRING", "")
        if query:
            destino = f"{destino}?{query}"
        resposta = HttpResponseRedirect(destino)
        resposta["Cache-Control"] = CACHE_DO_REDIRECT
        return resposta
