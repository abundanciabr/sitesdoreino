"""A PORTA da área administrativa — fail-CLOSED, o inverso do site público.

Lei: `docs/decisoes/DECISAO-celula-admin.md` §2. A tabela que este arquivo
implementa, e cada linha tem teste-guarda em
`tests/test_inv_porta_fail_closed.py`:

| Situação                          | Site público (`funil`) | Aqui                  |
|-----------------------------------|------------------------|-----------------------|
| `identidade` fora do ar           | abre, mostra "Entrar"  | **503, não abre**     |
| sessão válida, e-mail fora da lista | —                    | **404**, não 403      |
| sem sessão                        | —                      | 302 para o login      |

**Por que o inverso é o certo, e não excesso de zelo:** o invariante
*reconhecer não é autorizar* (`DECISAO-onde-mora-a-sessao.md` §4) tem duas
metades, e a segunda é esta. Reconhecimento falha ABERTO porque não conseguir
saber o nome de alguém não pode derrubar a vitrine. Autorização falha FECHADO
porque não conseguir saber QUEM é alguém não pode virar permissão.

**Por que 503 e não 302 quando a identidade cai:** mandar para o login seria
mandar a pessoa para a porta que provavelmente também está fora do ar — e a
área administrativa é justamente onde ela vai olhar quando algo está errado.
Um 503 nomeado diz o que está acontecendo; um 302 para uma tela quebrada
esconde.

**Por que 404 e não 403 para quem não está na lista:** para quem não é da
casa, `/admin` não existe. É decisão registrada na lei (§2), não improviso.
"""

import base64
import hashlib
import logging
import re

from django.conf import settings
from django.db import DatabaseError
from django.http import HttpResponse, HttpResponseNotFound, HttpResponseRedirect
from django.template.loader import render_to_string
from django.urls import reverse

from . import medidor
from .clients import IdentidadeClient, IdentidadeIndisponivel
from .models import Administrador

logger = logging.getLogger("admin.porta")

# O bloco `<style>` embutido do `admin/base.html`. Ver `_hashes_de_estilo`.
_ESTILO_EMBUTIDO = re.compile(rb"<style[^>]*>(.*?)</style>", re.DOTALL | re.IGNORECASE)

# Os únicos caminhos que respondem sem crachá. É `frozenset` e é conferido por
# igualdade EXATA em `tests/test_inv_porta_fail_closed.py`: rota nova não
# escapa em silêncio — ou ela está aqui de propósito, ou a porta a protege.
#
# Compara-se `request.path_info`, NUNCA `request.path`: pela borda pública o
# Traefik não remove o prefixo, e `request.path` chega como `/admin/healthz`
# (`armadilhas/029`, medido ao vivo em duas células). `path_info` é `/healthz`
# nos dois caminhos de entrada.
#
# `/healthz` é rota de MÁQUINA, exigida pelo healthcheck do compose, que não
# tem cookie nenhum para apresentar.
#
# [INV-P14] Os `/mapa-ia/*` são a segunda exceção, e a única pensada para
# gente de fora: o mantenedor pediu (28/08/2026) um link público do mapa
# técnico do projeto (`painel/ia/`, escrito para IA auditar o projeto) para
# poder mandar a IAs externas sem exigir login. Cada caminho aqui é um
# arquivo `.md` exato de `painel/ia/` — nenhum outro caminho desta célula
# muda de comportamento. `apps/core/mapa_ia.py` serve como texto puro, nunca
# HTML, e confere de novo (por disco) que o arquivo pedido existe dentro da
# pasta antes de ler — esta lista NÃO é a única trava, é a primeira.
CAMINHOS_ISENTOS = frozenset(
    {
        "/healthz",
        "/mapa-ia/",
        "/mapa-ia/INDICE.md",
        "/mapa-ia/01-leis-ritos-e-invariantes.md",
        "/mapa-ia/02-armadilhas-e-padroes-recorrentes.md",
        "/mapa-ia/03-sistema-do-painel-e-livro.md",
        "/mapa-ia/04-arquitetura-de-celulas-e-contratos.md",
        "/mapa-ia/05-infraestrutura-ci-e-deploy.md",
        "/mapa-ia/06-produto-decisoes-e-roadmap.md",
        "/mapa-ia/07-oportunidades-e-fronteiras.md",
    }
)

#: [DOCUMENTOS] O prefixo público da área de documentos
#: (`DECISAO-a-area-de-documentos.md`, 29/08/2026).
#:
#: **Por que aqui é PREFIXO e no `/mapa-ia/` é lista exata.** Lá, a decisão de
#: "isto é público" mora nesta lista e em lugar nenhum mais — arquivo novo em
#: `painel/ia/` não fica público sozinho. Aqui a decisão mora no PRÓPRIO
#: documento (`publico: true` no cabeçalho, fail-closed), e enumerar os
#: endereços aqui criaria uma SEGUNDA lista sobre o mesmo fato: no dia em que as
#: duas discordassem, ou um documento público ficaria inacessível, ou — o lado
#: caro — alguém tiraria o `publico: true` achando que bastava.
#:
#: O que impede o prefixo de virar uma fresta: sob `/docs/` existem EXATAMENTE
#: duas rotas, as duas de leitura, e as duas conferem `publico` antes de
#: responder. Rota nova aqui embaixo não escapa em silêncio — há um guarda que
#: varre o urlconf e reprova
#: (`tests/test_area_de_documentos.py::test_o_prefixo_publico_tem_so_as_duas_rotas`).
PREFIXO_PUBLICO_DOS_DOCUMENTOS = "/docs/"

#: [PLANOS PARA IA] O prefixo público dos planos e decisões (31/08/2026).
#:
#: Nasceu de um atrito medido: o mantenedor mandou a IAs externas o link de um
#: artefato hospedado fora, e NENHUMA conseguiu abrir — artefato é privado e
#: exige sessão. O conteúdo nunca foi segredo (este repositório é público de
#: propósito); faltava um endereço do próprio site que uma IA pudesse ler.
#:
#: **Prefixo, e não lista exata — ao contrário do `/mapa-ia/` logo acima.** As
#: duas áreas moram sob o mesmo prefixo de roteamento e têm posturas
#: deliberadamente diferentes, porque a pergunta "quem decide que isto é
#: público" tem resposta diferente em cada uma:
#:
#:   `/mapa-ia/…`         a decisão mora AQUI, arquivo por arquivo. São sete
#:                        arquivos de um mapa curado, e a raridade da mudança é
#:                        o que torna a lista exata barata.
#:   `/mapa-ia/planos/…`  a decisão mora NO PRÓPRIO DOCUMENTO
#:                        (`publico-para-ia: true`, fail-closed), escolha do
#:                        mantenedor em 31/08/2026. Enumerar os endereços aqui
#:                        criaria uma SEGUNDA lista sobre o mesmo fato — o
#:                        mesmo argumento que `/docs/` já usa acima.
#:
#: **Não afrouxei a lista do `/mapa-ia/` de carona**: aquilo é o INV-P14 e é
#: outra decisão. Área nova ganha prefixo novo.
#:
#: O que impede o prefixo de virar uma fresta: sob `/mapa-ia/planos/` existem
#: EXATAMENTE duas rotas, as duas de leitura, e as duas conferem
#: `publico-para-ia` antes de responder. Guarda que varre o urlconf e reprova
#: rota nova aqui embaixo:
#: `tests/test_planos_para_ia.py::test_o_prefixo_dos_planos_tem_so_as_duas_rotas`.
PREFIXO_PUBLICO_DOS_PLANOS = "/mapa-ia/planos/"

#: [PORTA DE MAQUINA] O prefixo que tem cadeado PROPRIO, e mais forte que este.
#:
#: `/interno/` responde a outra celula, maquina para maquina, e o que a fecha e
#: o Bearer do par (`apps/core/auth.py`): conjunto de tokens vazio recusa todo
#: mundo, e o guarda e o 401 em TODAS as operacoes
#: (`tests/test_porta_de_maquina.py`). Uma maquina nao tem cookie de navegador
#: para apresentar, entao passa-la por esta porta trocaria aquele 401 por um 302
#: para a tela de login, afrouxando a porta e quebrando o contrato congelado no
#: mesmo gesto.
#:
#: **Nao entrou em `CAMINHOS_ISENTOS`, e a diferenca e a razao de ser das duas.**
#: Aquele conjunto e uma lista EXATA de caminhos que respondem ao publico sem
#: cracha nenhum, e a exatidao dele e o que impede rota nova de escapar em
#: silencio. Aqui e o inverso: tudo que nascer sob `/interno/` nasce atras do
#: Bearer, que e um cadeado, e nao uma isencao. Prefixo, e nao `startswith` cru,
#: pelo mesmo motivo que a `pages` escreveu: uma rota futura chamada
#: `/internosecreto` nao herda nada daqui.
PREFIXO_DA_PORTA_DE_MAQUINA = "/interno"


def _sob_a_porta_de_maquina(caminho: str) -> bool:
    """O caminho e `/interno`, ou esta debaixo dele?"""
    return caminho == PREFIXO_DA_PORTA_DE_MAQUINA or caminho.startswith(
        PREFIXO_DA_PORTA_DE_MAQUINA + "/"
    )


def _emails_autorizados() -> frozenset[str]:
    """A lista de quem entra, lida NO PONTO DE USO e normalizada.

    **Duas fontes desde 28/08/2026**, e a ordem entre elas é lei:
    `ADMIN_EMAILS` (servidor) ∪ os ativos da tabela `Administrador` (promovidos
    pela tela). Ver `apps/core/models.py` e
    `docs/decisoes/DECISAO-administradores-e-apagar.md` §3.

    A resposta da identidade — inclusive o campo `papel` — continua não
    autorizando nada aqui.

    Normaliza com `strip().lower()` dos dois lados (aqui e na comparação),
    copiando o que a `identidade` já faz ao cunhar a pessoa: sem isso, um
    espaço a mais na variável do servidor tranca o mantenedor para fora, e o
    que ele vê é um 404 indistinguível de erro de rota.

    Env ausente ⇒ conjunto VAZIO ⇒ ninguém entra. Fail-closed por construção,
    e sem derrubar o boot: o container sobe, o `/healthz` responde, e só a
    área fica fechada até a variável existir.
    """
    cru = getattr(settings, "ADMIN_EMAILS", "") or ""
    do_servidor = frozenset(p.strip().lower() for p in cru.split(",") if p.strip())

    # [ADMINS] A metade que a TELA promove (`DECISAO-administradores-e-apagar`
    # §3.1). O env é o CHÃO: quem está nele entra sempre, e o botão de remover
    # se recusa a mexer nele — é isso que torna impossível se trancar para
    # fora, e o que faz um banco vazio ou restaurado de backup não fechar a
    # porta.
    try:
        do_banco = frozenset(
            Administrador.objects.filter(ativo=True).values_list("email", flat=True)
        )
    except DatabaseError:
        # [ADMINS] §3.2 — falha de banco vale SÓ o env. Erro nunca AMPLIA quem
        # entra: a direção do fail é o que separa uma indisponibilidade de uma
        # brecha. ERROR e não silêncio: quem vai ler é o mantenedor, e ele
        # precisa saber por que um administrador promovido pela tela sumiu.
        logger.error(
            "porta: não deu para ler a lista de administradores do banco — "
            "vale só ADMIN_EMAILS do servidor até o banco voltar"
        )
        do_banco = frozenset()

    return do_servidor | do_banco


def _anota(registrar, *args) -> None:
    """Medir JAMAIS derruba a porta. Nem por defeito, nem por assinatura.

    O `try` de dentro do medidor cobre um erro no corpo dele. Não cobre a
    chamada em si: se um dia alguém acrescentar um parâmetro obrigatório lá, a
    chamada estoura ANTES de entrar na função, e um TypeError sobe pelo
    middleware — transformando um 302 para o login num 500. Numa área
    fail-closed isso é o mantenedor trancado para fora das próprias ferramentas
    por causa de um contador.

    Por isso a fronteira é guardada AQUI, no lado que sofre a consequência.
    Provado em `tests/test_medidor.py::test_medidor_quebrado_nao_muda_a_porta`,
    que substitui o medidor por um que explode e exige a mesma resposta.
    """
    try:
        registrar(*args)
    except Exception:  # noqa: BLE001 — observar não pode derrubar quem decide
        logger.warning("porta: a medição falhou e foi ignorada", exc_info=True)


class PortaAdministrativa:
    """Middleware que decide quem passa. Único ponto de autorização da célula."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.identidade = IdentidadeClient()

    def __call__(self, request):
        if _sob_a_porta_de_maquina(request.path_info):
            # A porta de MAQUINA tem cadeado proprio (o Bearer) e nao usa a
            # moldura de navegador: sai sem CSP e sem `Cache-Control` de tela,
            # porque quem consome e outra celula, nunca um navegador.
            return self.get_response(request)

        if request.path_info in CAMINHOS_ISENTOS or request.path_info.startswith(
            (PREFIXO_PUBLICO_DOS_DOCUMENTOS, PREFIXO_PUBLICO_DOS_PLANOS)
        ):
            return self._com_seguranca(self.get_response(request))

        cookie = request.META.get("HTTP_COOKIE", "")
        if not cookie:
            # Sem cookie nenhum não há o que perguntar — e perguntar custaria
            # uma ida à rede para receber "visitante".
            return self._para_o_login(request)

        try:
            sessao = self.identidade.sessao_completa(cookie)
        except IdentidadeIndisponivel:
            # NÃO redireciona: ver o cabeçalho deste arquivo.
            return self._indisponivel()

        if not sessao.get("autenticado"):
            return self._para_o_login(request)

        email = (sessao.get("email") or "").strip().lower()
        if not email or email not in _emails_autorizados():
            # WARNING, e não silêncio: tentativa de entrar na área de operação
            # por conta que não está na lista é coisa que o dono precisa poder
            # ver. Sem e-mail no log — o id opaco identifica sem espalhar dado
            # pessoal por arquivo de log.
            logger.warning(
                "porta: acesso negado para a sessão %s em %s",
                sessao.get("id") or "?",
                request.path_info,
            )
            return self._nao_existe()

        # A partir daqui a pessoa está dentro. O que as páginas recebem é o
        # necessário para exibição — nunca um objeto de permissão: quem decide
        # o que ela pode é cada recurso, na hora.
        request.admin = {
            "id": sessao.get("id"),
            "nome": sessao.get("nome_exibido") or email,
            "email": email,
        }
        _anota(medidor.registrar_resposta, "entrou")
        return self._com_seguranca(self.get_response(request))

    # ---------------------------------------------------------------- respostas

    def _para_o_login(self, request):
        _anota(medidor.registrar_resposta, "mandou_para_o_login")
        destino = f"{settings.URL_DE_ENTRADA}?next={request.path}"
        return self._com_seguranca(HttpResponseRedirect(destino))

    def _nao_existe(self):
        _anota(medidor.registrar_resposta, "nao_existe_para_voce")
        return self._com_seguranca(
            HttpResponseNotFound(render_to_string("admin/404.html"))
        )

    def _indisponivel(self):
        # O contador que fecha o caso de 27/08: durante um incidente, 503 por
        # minuto deveria bater com quantos registros o painel deixou de
        # carregar. Depois do conserto, zero — e se sobrarem 503 com o painel
        # pedindo pouco, a identidade está doente por conta própria.
        _anota(medidor.registrar_resposta, "indisponivel_503")
        resposta = HttpResponse(render_to_string("admin/503.html"), status=503)
        # Diz ao navegador (e a qualquer cache no caminho) que isto é
        # temporário e não deve ser guardado — 503 sem isto pode ser cacheado.
        resposta["Retry-After"] = "30"
        resposta["Cache-Control"] = "no-store"
        return self._com_seguranca(resposta)

    def _com_seguranca(self, resposta):
        """CSP em TODA resposta desta célula, inclusive nas de recusa.

        `frame-ancestors 'self'` e **nunca `'none'`**: `'none'` proíbe
        enquadramento inclusive de mesma origem, e a galeria de painéis (fase
        3) serve painel em iframe a partir da própria área. Este erro já foi
        cometido uma vez, no papel, e pego na revisão (`armadilhas/109`). O
        `X-Frame-Options: SAMEORIGIN` correspondente vem do Traefik
        (`seguranca-admin`) — as duas precisam concordar.

        O resto é o que fecha a porta do lado do navegador: sem `script-src`
        de terceiro, sem `object-src`, sem `<base>` sequestrado, e formulário
        que só posta para a própria origem.

        **`style-src` leva o HASH do estilo da casa** — ver `_hashes_de_estilo`.
        """
        resposta.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; "
            f"style-src 'self'{self._hashes_de_estilo(resposta)}; "
            "img-src 'self' data:; object-src 'none'; base-uri 'none'; "
            "form-action 'self'; frame-ancestors 'self'",
        )
        resposta.setdefault("Referrer-Policy", "same-origin")
        # NENHUMA TELA DESTA ÁREA PODE FICAR GUARDADA NO NAVEGADOR (06/09/2026).
        #
        # Até aqui a resposta saía SEM instrução de cache nenhuma, e o navegador
        # ficava livre para decidir sozinho — inclusive para reexibir a cópia
        # que já tinha ao voltar, ao restaurar uma aba ou ao trocar de aba. Numa
        # área cujo conteúdo INTEIRO é calculado do estado de agora (quem pediu
        # acesso, quanto entrou, o que os robôs fizeram, que endereços o site
        # tem), uma cópia velha não é uma tela desatualizada: é uma tela que
        # MENTE, e mente exatamente como uma tela certa. O dono não tem como
        # perceber a diferença — só percebe que "continua do jeito antigo".
        #
        # `setdefault` de propósito, e não atribuição: `/mapa-ia/` e
        # `/mapa-ia/planos/` mandam `public, max-age=300` porque são texto
        # público que uma IA de fora lê, e essas duas continuam decidindo por si.
        #
        # É a mesma família do `no-store` que a resposta 503 já levava, e pelo
        # mesmo motivo: resposta que não deve sobreviver ao momento em que
        # nasceu precisa DIZER isso, senão alguém no caminho a guarda.
        resposta.setdefault("Cache-Control", "no-store")
        return resposta

    @staticmethod
    def _hashes_de_estilo(resposta) -> str:
        """O `sha256` de cada `<style>` embutido desta resposta, para o CSP.

        **O buraco que isto fecha, medido em produção em 30/08/2026.** O estilo
        desta área mora embutido no `<head>` (`admin/base.html` explica por quê:
        célula sob `SCRIPT_NAME` que serve estático por tag monta endereço da
        célula errada — `armadilhas/083` e `/102`). E a política que este mesmo
        método mandava dizia `style-src 'self'`, que **proíbe estilo embutido**.
        Resultado: TODA tela desta área — visão geral, escola, alunos, Caixa,
        documentos, o mapa do site — chegava ao navegador do dono **sem estilo
        nenhum**. As duas exceções eram `/admin/painel/` e a aba "Os robôs",
        que mandam CSP própria e por isso nunca sofreram.

        Ninguém viu porque nada media: o teste do Django não executa CSP, e o
        `curl` baixa o HTML inteiro (com o `<style>` lá dentro) e não o aplica.
        A prova veio de fora, de um Chrome de verdade batendo em
        `https://meshcraft.top/docs/`:

            "Applying inline style violates the following Content Security
             Policy directive 'style-src 'self''. ... The action has been
             blocked."

        **Hash, e nunca `'unsafe-inline'`** — o mesmo desenho de `painel.py`
        para o script embutido, e pelo mesmo motivo: `'unsafe-inline'` liberaria
        QUALQUER estilo injetado, inclusive um vindo de conteúdo de terceiro. O
        hash libera exatamente estes bytes. E, por ser calculado da resposta
        servida, ninguém precisa lembrar de atualizá-lo quando o CSS mudar —
        que é a diferença entre um mecanismo e uma promessa.

        Resposta sem corpo (302, 404 de redirecionamento) simplesmente não tem
        `<style>`: a política sai igual à de antes, sem hash nenhum.
        """
        if "text/html" not in resposta.get("Content-Type", ""):
            return ""
        # `.content` não existe em resposta em streaming — e ali não há o que
        # hashear de qualquer forma.
        corpo = getattr(resposta, "content", b"")
        if not corpo:
            return ""
        hashes = {
            "'sha256-"
            + base64.b64encode(hashlib.sha256(m.group(1)).digest()).decode()
            + "'"
            for m in _ESTILO_EMBUTIDO.finditer(corpo)
        }
        return "".join(f" {h}" for h in sorted(hashes))
