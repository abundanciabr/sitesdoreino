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

import logging

from django.conf import settings
from django.http import HttpResponse, HttpResponseNotFound, HttpResponseRedirect
from django.template.loader import render_to_string
from django.urls import reverse

from .clients import IdentidadeClient, IdentidadeIndisponivel

logger = logging.getLogger("admin.porta")

# Os únicos caminhos que respondem sem crachá. É `frozenset` e é conferido por
# igualdade EXATA em `tests/test_caminhos_isentos.py`: rota nova não escapa em
# silêncio — ou ela está aqui de propósito, ou a porta a protege.
#
# Compara-se `request.path_info`, NUNCA `request.path`: pela borda pública o
# Traefik não remove o prefixo, e `request.path` chega como `/admin/healthz`
# (`armadilhas/029`, medido ao vivo em duas células). `path_info` é `/healthz`
# nos dois caminhos de entrada.
#
# `/healthz` é o único, e por um motivo estrutural: é rota de MÁQUINA, exigida
# pelo healthcheck do compose, que não tem cookie nenhum para apresentar.
CAMINHOS_ISENTOS = frozenset({"/healthz"})


def _emails_autorizados() -> frozenset[str]:
    """A lista de quem entra, lida NO PONTO DE USO e normalizada.

    `ADMIN_EMAILS` é a ÚNICA fonte de "pode entrar" (`DECISAO-celula-admin`
    §2). A resposta da identidade — inclusive o campo `papel` — nunca
    autoriza nada aqui.

    Normaliza com `strip().lower()` dos dois lados (aqui e na comparação),
    copiando o que a `identidade` já faz ao cunhar a pessoa: sem isso, um
    espaço a mais na variável do servidor tranca o mantenedor para fora, e o
    que ele vê é um 404 indistinguível de erro de rota.

    Env ausente ⇒ conjunto VAZIO ⇒ ninguém entra. Fail-closed por construção,
    e sem derrubar o boot: o container sobe, o `/healthz` responde, e só a
    área fica fechada até a variável existir.
    """
    cru = getattr(settings, "ADMIN_EMAILS", "") or ""
    return frozenset(p.strip().lower() for p in cru.split(",") if p.strip())


class PortaAdministrativa:
    """Middleware que decide quem passa. Único ponto de autorização da célula."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.identidade = IdentidadeClient()

    def __call__(self, request):
        if request.path_info in CAMINHOS_ISENTOS:
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
        return self._com_seguranca(self.get_response(request))

    # ---------------------------------------------------------------- respostas

    def _para_o_login(self, request):
        destino = f"{settings.URL_DE_ENTRADA}?next={request.path}"
        return self._com_seguranca(HttpResponseRedirect(destino))

    def _nao_existe(self):
        return self._com_seguranca(
            HttpResponseNotFound(render_to_string("admin/404.html"))
        )

    def _indisponivel(self):
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
        """
        resposta.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; object-src 'none'; base-uri 'none'; "
            "form-action 'self'; frame-ancestors 'self'",
        )
        resposta.setdefault("Referrer-Policy", "same-origin")
        return resposta
