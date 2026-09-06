# apps/core/middleware.py  # [RECEITA:CONV-SITE v1] + resolver de idioma
# (PLANO-I18N §2 D1 — matriz HTTP; site sem idiomas = fluxo de hoje).
#
# D1 REVISTO em 25/08/2026 (docs/decisoes/DECISAO-raiz-sem-prefixo-do-idioma-padrao.md):
# o idioma PADRÃO do site é servido na raiz nua, sem prefixo; `/{padrão}/…` é 404.
import time

from django.http import Http404, HttpResponseRedirect
from django.utils import translation
from django.utils.cache import patch_vary_headers

from apps.core import enderecos, ver_como
from apps.core.clients import (
    AlunosClient,
    CatalogoClient,
    GamificacaoClient,
    IdentidadeClient,
    NotificacoesClient,
)
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


# ---------------------------------------------------------------------------
# O sino (Fase 5 de docs/notificacoes/PLANO-MESTRE.md): quantos avisos não
# lidos a pessoa tem. Falha ABERTA, sem exceção — a mesma lei do bloco acima.
# ---------------------------------------------------------------------------
# Cache por (destinatario_id, site_id) — um sino em TODA página não pode custar
# uma consulta HTTP por página vista pela mesma pessoa numa rajada. TTL mais
# curto que o da sessão de propósito: a contagem muda por AÇÃO DE OUTRA pessoa
# (alguém comentou na ideia dela), então servir stale por um minuto inteiro
# custa mais aqui do que custa na sessão (que só muda quando a própria pessoa
# entra ou sai).
_CACHE_DE_AVISOS: dict = {}
TTL_DOS_AVISOS = 30
# Mesmo teto de segurança do cache de sessão, e pelo mesmo motivo (§ acima):
# estourou, esvazia — perder cache custa um salto de rede, vazar memória custa
# a célula.
MAXIMO_DE_AVISOS_EM_CACHE = 500


def limpar_cache_de_avisos() -> None:
    _CACHE_DE_AVISOS.clear()


def _consultar_avisos(destinatario_id: str, site_id: str) -> "int | None":
    chave = (destinatario_id, site_id)
    agora = time.time()
    hit = _CACHE_DE_AVISOS.get(chave)
    if hit and hit[0] > agora:
        return hit[1]
    contagem = NotificacoesClient().obter_resumo(destinatario_id, site_id)
    if len(_CACHE_DE_AVISOS) >= MAXIMO_DE_AVISOS_EM_CACHE:
        _CACHE_DE_AVISOS.clear()
    # `None` (= "não sei") também é cacheado: uma `notificacoes` fora do ar não
    # pode custar uma tentativa de rede por página vista, na mesma rajada.
    _CACHE_DE_AVISOS[chave] = (agora + TTL_DOS_AVISOS, contagem)
    return contagem


# ---------------------------------------------------------------------------
# A CATEGORIA da pessoa (DECISAO-categorias-de-usuario, 28/08/2026): visitante,
# cadastrado, na fila ou aluno. Falha ABERTA — a mesma lei dos dois blocos
# acima: não saber a categoria mostra a home de quem ainda não pediu nada, e a
# vitrine nunca cai porque uma célula de produto caiu.
# ---------------------------------------------------------------------------
# Cache por `id` DA PLATAFORMA, e nunca pelo e-mail. São duas razões, e as duas
# importam: o e-mail é dado pessoal e não fica guardado nesta célula (§4 da
# decisão), e o `id` é o mesmo identificador que o cache do sino já usa.
#
# TTL curto pelo mesmo motivo do sino: a categoria muda por AÇÃO DE OUTRA
# pessoa — o mantenedor liberando alguém —, e quem acabou de ser aprovado não
# pode esperar um minuto inteiro para ver a porta abrir.
_CACHE_DE_CATEGORIA: dict = {}
# TTL ASSIMÉTRICO, e a assimetria é a lição de 28/08/2026 — a mesma que a Caixa
# aprendeu no mesmo dia (`services/sugestoes/LICOES.md`), aplicada aqui pelo
# mesmo motivo e com o mesmo número, de propósito: é uma regra só.
#
# `aluno` pode envelhecer: um "sim" velho custa o atalho aparecer por mais
# alguns segundos para quem deixou de ser aluno — irrelevante.
TTL_DA_CATEGORIA = 30
# Tudo que NÃO é aluno — inclusive o `None` de "não consegui perguntar" — vale
# por pouco. Um "ainda não" velho é a home dizendo "seu pedido está em análise"
# para quem ACABOU de ser liberado, e a Caixa acabou de mandar a pessoa para cá
# justamente para ela ver que entrou. Errar aqui é errar no instante da
# comemoração.
TTL_AINDA_NAO_E_ALUNO = 5
MAXIMO_DE_CATEGORIAS_EM_CACHE = 500


def limpar_cache_de_categoria() -> None:
    _CACHE_DE_CATEGORIA.clear()


def _consultar_categoria(cookie: str, id_da_pessoa: str) -> "dict | None":
    """A situação desta pessoa, pela `alunos`. `None` = não deu para saber.

    Duas idas à rede na primeira leitura (o e-mail na `identidade`, a situação
    na `alunos`) e nenhuma nas seguintes, dentro do TTL. A home de quem entrou
    é UMA página por sessão na esmagadora maioria das visitas — e visitante
    anônimo nunca chega aqui, porque quem chama já conferiu `bool(ator)`.
    """
    agora = time.time()
    hit = _CACHE_DE_CATEGORIA.get(id_da_pessoa)
    if hit and hit[0] > agora:
        return hit[1]

    alunos = AlunosClient()
    # A ORDEM importa, e por dois motivos. Desempenho: sem o par `funil→alunos`
    # ligado não há a quem perguntar a categoria, e buscar o e-mail primeiro
    # seria um salto de rede jogado fora em TODA página de quem entrou.
    # Privacidade: o e-mail é o dado mais sensível que atravessa esta célula, e
    # não se pede o que não se vai usar (§4 da decisão).
    if alunos._configuracao() is None:
        situacao = None
    else:
        email = IdentidadeClient().obter_email(cookie)
        # O e-mail morre nesta variável local: não entra no cache, não vai para
        # o template e não entra em log.
        situacao = alunos.situacao_de(email) if email else None

    if len(_CACHE_DE_CATEGORIA) >= MAXIMO_DE_CATEGORIAS_EM_CACHE:
        _CACHE_DE_CATEGORIA.clear()
    # `None` também é cacheado: uma `alunos` fora do ar não pode custar duas
    # tentativas de rede por página vista na mesma rajada. Mas ele vale POUCO,
    # como todo "ainda não" — ver os dois TTLs acima.
    e_aluno = bool(situacao) and situacao.get("categoria") == "aluno"
    validade = TTL_DA_CATEGORIA if e_aluno else TTL_AINDA_NAO_E_ALUNO
    _CACHE_DE_CATEGORIA[id_da_pessoa] = (agora + validade, situacao)
    return situacao


# ---------------------------------------------------------------------------
# O QUADRINHO DE PROGRESSO da home (degrau 20 do PLANO-CELULA-GAMIFICACAO).
# Falha ABERTA, como os três blocos acima: a gamificação fora do ar custa o
# quadrinho, nunca a home.
# ---------------------------------------------------------------------------
# **Sem cache de módulo, e a ausência é deliberada.** O sino, a sessão e a
# categoria têm cache porque são lidos em TODA página multilíngue (o
# `_sessao.html` entra em todas elas): sem cache, uma rajada de páginas da mesma
# pessoa viraria uma consulta HTTP por página. Este quadrinho vive numa página
# só, a home, e a leitura já é memoizada dentro da requisição pelo próprio
# `AtorDaRequisicao` — um dicionário de módulo aqui guardaria progresso de gente
# entre requisições para economizar um salto que quase nunca se repete, e
# estado global compartilhado entre pessoas é a superfície do pior bug possível
# desta plataforma. Se um dia o quadrinho aparecer em mais de uma página, o
# cache entra JUNTO com a função de limpeza no `conftest.py` (`armadilhas/026`:
# cache de módulo vaza entre testes).


def _progresso_da_tela(status: "dict | None") -> "dict | None":
    """Traduz o corpo de `getMyStatus` no que a tela desenha, ou `None`.

    `None` significa "não desenhe o quadrinho", e ele cobre TRÊS situações que
    o código distingue de propósito, ainda que a tela as trate igual:

      1. **não sei** — `status is None`: env ausente, rede fora, corpo fora do
         contrato. É o fail-open do cliente chegando aqui.
      2. **a gamificação não reconheceu esta pessoa** — `autenticado: false`.
         Acontece se o par estiver ligado mas a sessão não for resolvível do
         lado de lá; o funil não adivinha o motivo.
      3. **entrou e ainda não jogou** — `autenticado: true` com os números em
         `null`, porque a linha de perfil da gamificação é preguiçosa e nasce
         no primeiro XP. É o caso NORMAL, e hoje é o de todo mundo: a economia
         inteira está desligada até o mantenedor ligar a primeira regra em
         `/admin/economia/`. Barra em zero aqui seria dado fingido.

      4. **a escada ainda não foi montada** — `xp_para_proximo: null` com a
         pessoa no primeiro degrau. Não há próximo degrau porque a escola ainda
         não ligou nenhum, e não porque alguém subiu a trilha inteira. Ver
         abaixo: é o caso que fazia a home parabenizar quem nunca fez nada.

    Quando há progresso, devolve `nivel` mais UM de dois desfechos:

      · `no_topo=True` — `xp_para_proximo` é `null` E a pessoa já saiu do
        primeiro degrau. Mostra o degrau e uma frase própria, SEM barra: barra
        cheia que nunca vira nada é promessa que ninguém vai cumprir. `null` e
        `0` dizem coisas diferentes e o contrato aceita os dois.
      · `no_topo=False` — há um próximo degrau, e a barra mede o caminho já
        andado até ele.

    **`nivel <= 1` sem próximo degrau NÃO é topo, e essa é a correção de
    01/09/2026** (`armadilhas/271`). O `null` responde a duas perguntas
    opostas: "venceu a escada inteira" e "não existe escada". Com a economia
    desligada — o estado de hoje —, todo aluno que já tivesse aberto
    `/conquistas` uma vez (o que faz a linha de perfil nascer) via na home
    "Nível 1" e, embaixo, "você chegou ao último degrau da trilha". Ninguém
    chega ao topo de uma trilha estando no primeiro degrau dela: enquanto for
    assim, o quadrinho não se desenha, exatamente como no caso 3.

    **O que a barra mede, escrito porque é fácil ler errado:** a porta entrega
    o XP TOTAL e quanto FALTA, nunca o piso do degrau atual. Então a fração é
    `xp / (xp + falta)` — "quanto do caminho até o próximo degrau já foi
    andado, contando desde zero" — e não "quanto deste degrau já foi vencido".
    As duas crescem juntas e as duas chegam a 100% no mesmo instante (quando
    falta 0); a segunda exigiria um campo que o contrato não tem, e pedi-lo
    seria Rito de Contrato. Não "conserte" isto subtraindo um piso que não
    viaja por aqui.
    """
    if not status or not status.get("autenticado"):
        return None
    nivel = status.get("nivel")
    xp = status.get("xp")
    if nivel is None or xp is None:
        return None
    falta = status.get("xp_para_proximo")
    if falta is None:
        # Primeiro degrau e nenhum acima: escada não montada, não topo.
        if nivel <= 1:
            return None
        return {
            "nivel": nivel,
            "no_topo": True,
            "falta": None,
            "proximo": None,
            "percentual": None,
        }
    alvo = xp + falta
    # `alvo <= 0` é o único jeito de a divisão estourar, e ele é alcançável: um
    # degrau seguinte que exija 0 XP com a pessoa em 0 XP dá 0/0. Barra cheia é
    # a leitura certa desse caso — não falta nada.
    percentual = 100 if alvo <= 0 else min(100, round(100 * xp / alvo))
    return {
        "nivel": nivel,
        "no_topo": False,
        "falta": falta,
        "proximo": nivel + 1,
        "percentual": percentual,
    }


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

    def __init__(self, cookie: str, site_id: str, disfarce_pedido: str = "") -> None:
        self._cookie = cookie
        self._site_id = site_id
        # O valor CRU do cookie de "ver como". Cru de propósito: quem decide se
        # ele vale é `ver_como` abaixo, e ela precisa do `papel` — que ainda
        # nao foi resolvido nesta altura, porque este objeto e preguicoso.
        self._disfarce_pedido = disfarce_pedido
        self._resolvido = False
        self._dados: "dict | None" = None
        self._avisos_resolvido = False
        self._avisos: "int | None" = None
        self._categoria_resolvida = False
        self._situacao: "dict | None" = None
        self._progresso_resolvido = False
        self._progresso: "dict | None" = None

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
    def id(self) -> "str | None":
        """O id da PLATAFORMA desta pessoa (`contracts/identidade.openapi.yaml`,
        schema `Session` — o campo sempre esteve lá; esta célula só nunca tinha
        lido). É o `destinatario_id` que a Fase 5 do sininho passa à
        `notificacoes` (ver `avisos_nao_lidos` abaixo) — nunca o e-mail, que
        não atravessa esta fronteira."""
        return (self._resolver() or {}).get("id") or None

    @property
    def papel(self) -> str:
        """Para EXIBIÇÃO apenas (mostrar ou não um atalho). Nunca para liberar
        coisa alguma: autorização é fail-closed, na célula dona do recurso
        (DECISAO-onde-mora-a-sessao §4)."""
        return (self._resolver() or {}).get("papel") or ""

    @property
    def ver_como(self) -> str:
        """A categoria que esta pessoa PEDIU para simular, ou `""`.

        Pedido do mantenedor em 02/09/2026 ("como aquela opcao do Facebook de
        Ver como"). A lei inteira do disfarce, e o porque de cada guarda, esta
        em `apps/core/ver_como.py` — aqui fica so a leitura.

        **So vale para quem a `identidade` reconhece como equipe.** Sem essa
        condicao, qualquer visitante que escrevesse o cookie no proprio
        navegador veria a home oferecer o caminho da Caixa e levaria um "nao"
        na cara ao clicar: o defeito de 28/08/2026 ressuscitado por um cookie.

        **Nao custa consulta nova.** Le `papel`, que sai da MESMA resposta de
        sessao que o "Ola, Fulano" do topo ja resolveu — e visitante anonimo
        nunca chega aqui, porque `papel` devolve vazio sem sessao.

        E o que ele NAO faz: nada. Disfarce e EXIBICAO. A Caixa, o forum e a
        area administrativa continuam conferindo as listas deles, e nenhuma
        delas olha para este cookie.
        """
        if not self._disfarce_pedido:
            return ""
        return ver_como.disfarce_de(self.papel, self._disfarce_pedido)

    @property
    def avisos_nao_lidos(self) -> "int | None":
        """Quantos avisos não lidos esta pessoa tem — o número do sino (Fase 5,
        `docs/notificacoes/PLANO-MESTRE.md`). `None` = "não sei" (config
        ausente, rede fora, corpo fora do contrato): o `_sessao.html` NÃO
        desenha o sino nesse caso — é o fail-open virando "o site mostra o
        nome sem sino". Um `int` — inclusive `0` — é "sei a resposta": os dois
        são estados DIFERENTES, nunca o mesmo caminho de template.

        Preguiçosa como o resto desta classe, e em DOIS níveis: só chega aqui
        se ALGUÉM foi reconhecido (`bool(self)`), e só consulta a rede na
        PRIMEIRA leitura. Visitante anônimo — a esmagadora maioria do tráfego
        — nunca avalia esta property (o template só a lê dentro do
        `{% if request.ator %}`), e mesmo quem entrou não paga a consulta em
        página que não desenha o sino.
        """
        if not self:
            return None
        if not self._avisos_resolvido:
            self._avisos_resolvido = True
            id_da_pessoa = self.id
            self._avisos = (
                _consultar_avisos(id_da_pessoa, self._site_id) if id_da_pessoa else None
            )
        return self._avisos

    @property
    def progresso(self) -> "dict | None":
        """O degrau desta pessoa na trilha da escola, ou `None`.

        `None` = "não desenhe o quadrinho", e ele cobre tanto o "não sei"
        (config ausente, rede fora, corpo fora do contrato) quanto o "entrou e
        ainda não jogou" — os três casos estão escritos em
        `_progresso_da_tela`. Um dicionário é "sei a resposta e há o que
        mostrar": os dois são estados DIFERENTES, nunca o mesmo caminho de
        template. É o fail-open virando "a home abre igual, sem o quadrinho".

        Preguiçosa como o resto desta classe, e em DOIS níveis, exatamente como
        `avisos_nao_lidos`: só chega à rede se ALGUÉM foi reconhecido
        (`bool(self)`), e só consulta na PRIMEIRA leitura. Visitante anônimo, a
        esmagadora maioria do tráfego, nunca avalia esta property — o template
        só a lê dentro do `{% if request.ator %}` —, e mesmo quem entrou não
        paga a consulta em página que não desenha o quadrinho, que hoje é toda
        página menos a home.

        Guardas dos dois níveis:
        `tests/test_quadrinho_de_progresso.py`. Sem eles, a preguiça é desfeita
        de boa-fé pelo próximo agente que "simplificar" esta classe.
        """
        if not self:
            return None
        if not self._progresso_resolvido:
            self._progresso_resolvido = True
            self._progresso = _progresso_da_tela(
                GamificacaoClient().obter_meu_status(self._cookie)
            )
        return self._progresso

    def _resolver_categoria(self) -> "dict | None":
        """A situação desta pessoa, resolvida na PRIMEIRA leitura.

        Preguiçosa em dois níveis, como `avisos_nao_lidos`: só chega à rede se
        alguém foi reconhecido, e só na primeira leitura. Página que não
        pergunta a categoria não paga nada — e nenhuma página de visitante
        anônimo pergunta.
        """
        if not self:
            return None
        if not self._categoria_resolvida:
            self._categoria_resolvida = True
            id_da_pessoa = self.id
            self._situacao = (
                _consultar_categoria(self._cookie, id_da_pessoa)
                if id_da_pessoa
                else None
            )
        return self._situacao

    @property
    def categoria(self) -> str:
        """`visitante` · `cadastrado` · `na_fila` · `aluno`.

        NUNCA `administrador`: esse crachá não está nesta escada e é calculado
        pela lista da célula `admin`, na hora, na porta dela
        (`DECISAO-categorias-de-usuario` §2.1). Se esta property pudesse
        respondê-lo, a autorização da área administrativa passaria a depender
        da vitrine.

        **Não saber vira `cadastrado`, nunca `aluno`.** A direção do fail-open
        é a decisão: o pior caso é alguém não ver o próprio atalho por alguns
        segundos. O inverso — mostrar o atalho de aluno para quem não é —
        seria a home fazendo promessa que a Caixa vai desmentir na cara da
        pessoa, que é o defeito que esta mudança existe para consertar.
        """
        if not self:
            return "visitante"
        if self.ver_como:
            # A prevoa da equipe (02/09/2026, apps/core/ver_como.py). Vem ANTES
            # da consulta, e por isso ver como aluno nao pergunta nada a
            # `alunos`: a resposta dela nao mudaria a tela, e perguntar seria
            # um salto de rede para jogar fora.
            return self.ver_como
        situacao = self._resolver_categoria()
        if not situacao:
            return "cadastrado"
        return situacao.get("categoria") or "cadastrado"

    @property
    def categoria_conferida(self) -> bool:
        """A `alunos` RESPONDEU sobre esta pessoa? — a diferença entre "sei que
        ela nunca pediu nada" e "não consegui saber".

        Existe porque `categoria` colapsa as duas em `cadastrado` (fail-open,
        e a direção continua certa), e desde 29/08/2026 a home OFERECE algo a
        quem é `cadastrado`: o convite para pedir entrada
        (`DECISAO-o-beco-de-quem-entrou-e-nunca-pediu.md`). Sem esta property,
        a `alunos` fora do ar faria a home convidar um aluno a pedir a entrada
        que ele já tem — o mesmo defeito de 28/08 de cabeça para baixo: uma
        tela prometendo o que a outra célula desmente.

        Nunca dispara consulta por conta própria além da que `categoria` já
        faz: quem lê as duas paga uma rodada, não duas.
        """
        if not self:
            return False
        if self.ver_como:
            # Sob disfarce a categoria nao veio da `alunos`: foi ESCOLHIDA. Ela
            # e conhecida por definicao, e sem este `True` o ramo `cadastrado`
            # da home (que exige resposta conferida) nao desenharia nada, e a
            # previa mostraria uma tela vazia sem explicar por que.
            return True
        return self._resolver_categoria() is not None

    @property
    def na_fila(self) -> "dict | None":
        """O andamento do pedido — `estado`, `esperando_ha_dias`, `motivo_recusa`.

        `None` para quem não está na fila. Vem da `alunos` já calculado: quem
        tem o relógio e a linha é ela, e um consumidor que subtraísse datas
        erraria de um jeito diferente em cada célula.
        """
        if self.ver_como:
            # Nenhum disfarce previsto e `na_fila`, e a ausencia e deliberada:
            # ela exigiria um "esperando ha N dias" que nao existe para quem
            # nao esta na fila. Ver `DISFARCES` em apps/core/ver_como.py.
            return None
        if self.categoria != "na_fila":
            return None
        return (self._resolver_categoria() or {}).get("na_fila")


# /healthz é sonda do container e do gateway — chega sem Host de site e não pode
# depender do catálogo estar de pé. Estáticos idem. A isenção roda ANTES de
# QUALQUER lógica.
# `/sw.js` entra aqui, e não na lista de baixo: o arquivo do service worker é
# o mesmo para todo site, não lê nada do catálogo, e é pedido de novo pelo
# navegador de quem já instalou o app. Fazê-lo depender do catálogo seria pôr
# uma consulta de rede no caminho de um arquivo estático servido da raiz.
# `/google0e78b54775677e95.html` (31/08/2026) é o arquivo de verificação do
# Google Search Console: conteúdo fixo, e o Google bate nele sem conhecer o
# catálogo de sites — mesma razão do /healthz.
CAMINHOS_SEM_SITE = ("/healthz", "/static/", "/sw.js", "/google0e78b54775677e95.html")

# Rota de MÁQUINA (D6): precisa do Site — desde a fase 4 os idiomas vêm do
# catálogo, e o sitemap é feito deles — mas NUNCA se localiza (nenhum prefixo
# de idioma, nenhum redirect da matriz D1). Custo do dado ter virado contrato:
# o sitemap deixou de ser servível com o catálogo fora do ar; em compensação
# usa o MESMO cache de 60s de qualquer outra rota.
# O manifesto do app, ao contrário, PRECISA do Site: o nome do app é o nome do
# site e o `start_url` sai dos idiomas do catálogo. Mesmo cache de 60s de
# qualquer outra rota, e nenhum prefixo de idioma (o idioma dele vai na query,
# não no caminho).
CAMINHOS_DE_MAQUINA = ("/sitemap.xml", "/manifest.webmanifest")

# D6: TODA rota de máquina desta célula — as isentas de Site e a que precisa
# dele. Nenhuma delas se localiza. As duas listas acima são conferidas no
# path_info CRU, no topo do __call__; esta é conferida DE NOVO depois de
# decapar o prefixo de idioma — é o único ponto em que dá para ver que
# /pt-br/healthz é a rota de máquina /healthz (desvio medido em 24/08/2026).
ROTAS_DE_MAQUINA = CAMINHOS_SEM_SITE + CAMINHOS_DE_MAQUINA


def _forma_canonica(segmento: str) -> str:
    """`PT-BR` → `pt-br`, `pt_br` → `pt-br`. A forma como o código se escreve na URL.

    Serve para uma coisa só: reconhecer o segmento que QUERIA ser um idioma
    habilitado e foi escrito na caixa/separador errado, para recusá-lo
    fail-closed em vez de redirecionar (D1 — nada nunca linkou para essas formas).

    Note o que ela deliberadamente NÃO faz: adivinhar que um segmento tem "cara
    de idioma". Até 25/08/2026 uma regex de 2-3 letras cumpria esse papel, e ela
    recusava `/faq`, `/api` e `/pro` como se fossem idiomas — o que só não doeu
    porque o inglês vivia atrás de `/en/`. Com o padrão na raiz nua esses são
    endereços de página legítimos, e quem decide se existem é o urlconf.
    """
    return segmento.lower().replace("_", "-")


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
        """A matriz HTTP do D1, em quatro ramos — e **a ordem deles é a regra**.

        Desde 25/08/2026 o idioma padrão não tem prefixo, o que torna o primeiro
        segmento da URL ambíguo: `/es` é "espanhol" ou "página chamada es"? Aqui o
        **idioma vence sempre** (ramo 2 antes do 4). Uma rota do urlconf que
        colida com um código de idioma ficaria inalcançável em silêncio — quem
        impede isso de nascer é `tests/test_d6_roteamento.py`, não este método.
        """
        caminho = request.path_info
        segmento, barra, resto = caminho[1:].partition("/")

        # ── 1. O prefixo do idioma PADRÃO não existe (D1 revisto) ──────────
        # Primeiro de todos, e isso importa: se este ramo viesse depois da
        # decapagem, `/en/healthz` seria reescrito para `/healthz` e devolveria a
        # sonda com 200 (armadilhas/086 — middleware que reescreve caminho tem
        # DOIS caminhos na mesma requisição). Morrendo aqui, morre para toda rota
        # de máquina de uma vez, inclusive a que nascer amanhã.
        if segmento == cfg["default"]:
            raise Http404(f"o idioma padrão não tem prefixo: {caminho}")

        # ── 2. Idioma não-padrão habilitado: serve prefixado ───────────────
        if segmento in cfg["idiomas"]:
            if not barra:  # /pt-br → /pt-br/ (uma forma canônica por página)
                if request.method not in METODOS_SEGUROS:
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
            # O urlconf da célula continua sem prefixo: o resolver decapa o
            # idioma ANTES da resolução de URL (path_info é o que o Django
            # resolve; request.path segue completo p/ canonical/logs).
            request.path_info = caminho_sem_prefixo
            return self._servir(request, site, cfg, segmento, caminho_sem_prefixo)

        # ── 3. Idioma habilitado escrito na forma errada: 404 fail-closed ────
        # /PT-BR/, /pt_br/, /EN/, /Es/ — nunca redirect, nunca fallback (D1).
        if _forma_canonica(segmento) in cfg["idiomas"]:
            raise Http404(f"forma não canônica de idioma: {segmento}")

        # ── 4. Todo o resto — inclusive "/" — é o idioma PADRÃO, sem prefixo ─
        # Não há path_info a reescrever: o caminho JÁ é o que o urlconf resolve.
        # Endereço que não existe (`/fr/cadastro`, `/qualquer-coisa`) cai no 404
        # natural do urlconf, e não numa regex que adivinha idioma.
        #
        # Ramo sem redirect ⇒ **método nenhum se perde**: POST /leads e
        # POST /cadastro passaram a funcionar aqui (na matriz antiga eram 404,
        # porque o 302 do caminho nu converteria POST em GET e descartaria o
        # corpo em silêncio).
        return self._servir(request, site, cfg, cfg["default"], caminho)

    def _servir(self, request, site, cfg, codigo: str, caminho_sem_prefixo: str):
        """Serve uma página NUM idioma — o mesmo preparo para os ramos 2 e 4.

        Extraído, e não copiado, de propósito: a metade fácil de esquecer é o
        `request.ator`. Sem ele a página não sabe quem está vendo, e o cabeçalho
        de sessão ("Entrar" / o nome de quem entrou) desaparece **só** no idioma
        padrão — que é a versão que alguém abre para conferir. Falha silenciosa e
        assimétrica é exatamente o que uma cópia produz.
        """
        request.idioma = codigo
        request.i18n_seo = dados_seo(site, cfg, codigo, caminho_sem_prefixo)
        # Quem está vendo a página. Objeto preguiçoso: construí-lo não custa
        # nada, e só a leitura no template dispara a pergunta à Caixa. Fica
        # SÓ no regime multilíngue, que é onde o login existe — site
        # monolíngue (os domínios antigos) segue byte-idêntico ao de antes.
        # `site["id"]` já está resolvido nesta altura ([INV-P11], `__call__`
        # acima) — é o `site_id` que a Fase 5 do sino precisa para perguntar à
        # `notificacoes` (ela escopa por site: CONSTITUICAO.md Lei 9).
        request.ator = AtorDaRequisicao(
            request.META.get("HTTP_COOKIE", ""),
            site["id"],
            request.COOKIES.get(ver_como.COOKIE, ""),
        )
        # Os dois destinos de link de quem já entrou. Ficam no request (e não
        # no contexto de cada view) porque a peça `_sessao.html` aparece em
        # TODA página multilíngue: passá-los view a view seria a mesma linha
        # repetida em cada uma, e a próxima view nasceria sem ela.
        request.url_da_caixa = enderecos.url_da_caixa()
        request.url_dos_avisos = enderecos.url_dos_avisos()
        request.url_da_prancheta = enderecos.url_da_prancheta()
        translation.activate(cfg["idiomas"][codigo]["tag"])  # D2.4: runtime LIGADO
        try:
            resposta = self.get_response(request)
        finally:
            translation.deactivate()
        return self._marcar_variacao_por_pessoa(request, resposta)

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
