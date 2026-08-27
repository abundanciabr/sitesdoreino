# apps/core/clients.py  # [RECEITA:R2 v1]
# Fala SÓ o que está nos contratos congelados de catalogo, leads e identidade.
# Em dev, aponte CATALOGO_API_URL/LEADS_API_URL/IDENTIDADE_API_URL para os mocks
# prism (make mocks) — nunca suba a outra célula, nunca leia o banco dela.
import logging
import os

import httpx

logger = logging.getLogger("funil.sessao")

_cliente: httpx.Client | None = None


def http() -> httpx.Client:
    """Um `httpx.Client` por processo, em vez de `httpx.get()`/`httpx.post()` a
    cada chamada. A forma direta constrói um `Client` descartável — e com ele
    um `ssl.SSLContext` novo, que recarrega os certificados raiz do sistema —
    a cada chamada de rede interna (armadilhas/082, medido em 0,4s por
    chamada). `httpx.Client` é seguro entre threads, que é o que o uvicorn
    precisa.
    """
    global _cliente
    if _cliente is None:
        _cliente = httpx.Client()
    return _cliente


class CatalogoClient:
    """contracts/catalogo.openapi.yaml (somente-leitura)."""

    def __init__(self) -> None:
        self.base = os.environ["CATALOGO_API_URL"].rstrip("/")
        self.token = os.environ["TOKEN_CATALOGO"]

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    def obter_site_por_host(self, host: str) -> dict | None:
        """[INV-P11] 404 do catálogo é 'site desconhecido', nunca um site padrão."""
        r = http().get(
            f"{self.base}/sites/by-host/{host}",
            headers=self._headers(),
            timeout=5.0,  # timeout SEMPRE explícito
        )
        return r.json() if r.status_code == 200 else None

    def obter_oferta(self, site_id: str, slug: str) -> dict | None:
        """Slugs são únicos POR site — o site_id na rota é o que impede vazamento."""
        r = http().get(
            f"{self.base}/sites/{site_id}/ofertas/{slug}",
            headers=self._headers(),
            timeout=5.0,
        )
        return r.json() if r.status_code == 200 else None


class LeadsClient:
    """contracts/leads.openapi.yaml (somente-escrita, do ponto de vista do funil)."""

    def __init__(self) -> None:
        self.base = os.environ["LEADS_API_URL"].rstrip("/")
        self.token = os.environ["TOKEN_LEADS"]

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    def upsert_lead(self, payload: dict) -> dict:
        r = http().post(
            f"{self.base}/leads",
            json=payload,
            headers=self._headers(),
            timeout=10.0,
        )
        r.raise_for_status()
        return r.json()


class IdentidadeClient:
    """`contracts/identidade.openapi.yaml`, operação `getSession` — leitura pura.

    Lei do assunto: `docs/decisoes/DECISAO-onde-mora-a-sessao.md`. O site não lê
    o cookie de sessão: ele **pergunta** quem é o dono dele. O cookie é assinado
    com a chave da `identidade` e aponta para uma linha no banco DELA — o `funil`
    não tem chave nem banco (Lei 2, Lei 3). Perguntar é a única forma legal, e é
    também a que faz a identidade poder mudar de casa um dia sem que este
    arquivo mude: troca-se o endereço no env.

    **Duas credenciais viajam juntas, e provam coisas diferentes:**

    - o `Bearer` do par prova que **quem chama** é esta célula;
    - o `Cookie` repassado prova quem é **a pessoa** do outro lado do navegador.

    Nenhuma das duas substitui a outra, e o cookie **nunca** é interpretado
    aqui — ele é carregado de um lado para o outro, opaco.
    """

    TIMEOUT = 2.0

    def _configuracao(self) -> "tuple[str, str] | None":
        """Endereço e token do par, ou `None` se o env não os tiver.

        Lido NO PONTO DE USO, com `.get()` — nunca `os.environ[...]` no
        `__init__`. A diferença é a linha que separa esta célula de cair:
        `os.environ["X"]` levanta `KeyError`, que **não** é `httpx.HTTPError`
        e portanto atravessaria intacto o `try` de `obter_sessao`, o
        middleware e o `{% if request.ator %}` — virando **HTTP 500 em toda
        página multilíngue** para qualquer visitante que carregue um cookie
        qualquer (o de idioma, o de analytics, um do Cloudflare).

        A auditoria de 25/08/2026 achou isso em quatro cadeiras independentes,
        e o modo de falha era pior do que o nome sugere: falha de configuração
        é MAIS provável que falha de rede (basta uma variável não colada no
        servidor), e é invisível para quem testa num navegador limpo — só
        quem já tem cookie recebe o erro.
        """
        base = (os.environ.get("IDENTIDADE_API_URL") or "").strip().rstrip("/")
        token = (os.environ.get("IDENTIDADE_API_TOKEN") or "").strip()
        return (base, token) if base and token else None

    def obter_sessao(self, cookie: str) -> dict | None:
        """Quem é a pessoa desta requisição, ou `None`.

        **Falha ⇒ `None`, e isso é DELIBERADO** (DECISAO-onde-mora-a-sessao §4:
        *reconhecer não é autorizar*). Não conseguir perguntar significa que o
        site mostra "Entrar" e a página abre normal — a vitrine não pode cair
        porque a Caixa está reiniciando. É o oposto exato do
        `AlunosIndisponivel` da outra ponta, que fecha a porta quando não
        consegue perguntar: lá a resposta decide ACESSO, aqui decide um nome no
        canto da tela.

        Quem quiser autorizar alguma coisa um dia **não pode** partir daqui:
        autorização é fail-closed, na célula dona do recurso.

        Timeout curto (2s, contra os 5s do catálogo): isto está no caminho de
        alguém esperando uma página abrir, e a resposta certa para "demorou" é
        desistir depressa e mostrar "Entrar" — nunca pendurar a página.
        """
        config = self._configuracao()
        if config is None:
            # Nem tenta a rede: sem endereço ou sem token não há pergunta a
            # fazer, e esperar um timeout de 2s para descobrir isso atrasaria
            # toda página. ERROR nomeando as variáveis, porque o leitor do log
            # vai ser o mantenedor.
            logger.error(
                "sessao: IDENTIDADE_API_URL/IDENTIDADE_API_TOKEN ausentes no "
                "env desta célula — mostrando 'Entrar' para todo mundo"
            )
            return None
        base, token = config

        try:
            r = http().get(
                f"{base}/sessao",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Cookie": cookie,
                },
                timeout=self.TIMEOUT,
            )
        except httpx.HTTPError as erro:
            # ERROR e não silêncio: fail-open é decisão de produto, não licença
            # para a Caixa cair sem ninguém saber (RETROSPECTIVA §1).
            logger.error("sessao: não deu para perguntar à identidade: %s", erro)
            return None

        if r.status_code != 200:
            logger.error("sessao: a identidade respondeu HTTP %s", r.status_code)
            return None

        try:
            corpo = r.json()
        except ValueError as erro:
            # `200` com corpo que não é JSON — página de erro de um proxy
            # interposto, resposta truncada, `Content-Length` mentiroso.
            # `json.JSONDecodeError` é `ValueError`, NÃO é `httpx.HTTPError`:
            # fora deste `try` ela furaria o fail-open e derrubaria a vitrine.
            # É a família do bug mais caro da Fase D — *status 2xx não é
            # sucesso* (RETROSPECTIVA §4).
            logger.error("sessao: a identidade respondeu fora do contrato: %s", erro)
            return None

        # O contrato garante o campo; um corpo fora do contrato é tratado como
        # visitante, nunca como "provavelmente logado".
        if not isinstance(corpo, dict) or not corpo.get("autenticado"):
            return None
        return corpo


class NotificacoesClient:
    """`contracts/notificacoes.openapi.yaml`, operação `obterResumo` — leitura pura.

    Lei do assunto: `docs/decisoes/DECISAO-fase-4-do-sininho.md` (Escolha 1) e a
    Fase 5 de `docs/notificacoes/PLANO-MESTRE.md` — **falha ABERTA, sem
    exceção**: *"notificações fora do ar ⇒ o site mostra o nome sem sino e a
    página abre normal"*. Cópia peça por peça do padrão de
    `IdentidadeClient.obter_sessao` (Lei 7 — copia-se o PADRÃO, nunca o
    arquivo): mesma forma de ler config, mesmo timeout curto, mesma separação
    entre `httpx.HTTPError` e `ValueError` no `.json()`.

    Auth: Bearer estático do par `funil→notificacoes`
    (`services/notificacoes/apps/core/auth.py`, `TOKENS_ACEITOS_FUNIL` do lado
    de lá) — o MESMO mecanismo de par que `IdentidadeClient` já usa.
    """

    TIMEOUT = 2.0

    def _configuracao(self) -> "tuple[str, str] | None":
        """Ver o comentário gêmeo em `IdentidadeClient._configuracao` — a mesma
        razão de ser, a mesma forma: `.get()`, nunca `os.environ[...]`, lido NO
        PONTO DE USO. Falta de config é MAIS provável que falha de rede (basta
        uma variável não colada no servidor) e não pode furar o fail-open
        (RETROSPECTIVA-FASE-D §1/§4)."""
        base = (os.environ.get("NOTIFICACOES_API_URL") or "").strip().rstrip("/")
        token = (os.environ.get("NOTIFICACOES_API_TOKEN") or "").strip()
        return (base, token) if base and token else None

    def obter_resumo(self, destinatario_id: str, site_id: str) -> "int | None":
        """Quantos avisos não lidos esta pessoa tem NESTE site, ou `None`.

        `None` é o sinal de "não sei" — quem chama (o sino) não desenha nada.
        É DIFERENTE de `0`, que é "perguntei e a resposta é zero". Confundir
        os dois transformaria uma `notificacoes` fora do ar num "sem avisos"
        mentiroso — a mesma família do bug mais caro da Fase D (*2xx não é
        sucesso*: o corpo tem de descrever o que foi pedido, ou é erro).
        """
        config = self._configuracao()
        if config is None:
            # Nem tenta a rede — mesmo raciocínio de `IdentidadeClient`: sem
            # endereço ou token não há pergunta a fazer, e esperar 2s de
            # timeout para descobrir isso atrasaria toda página do site.
            logger.error(
                "resumo: NOTIFICACOES_API_URL/NOTIFICACOES_API_TOKEN ausentes "
                "no env desta célula — sino não aparece"
            )
            return None
        base, token = config

        try:
            r = http().get(
                f"{base}/resumo",
                params={"destinatario_id": destinatario_id, "site_id": site_id},
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.TIMEOUT,
            )
        except httpx.HTTPError as erro:
            logger.error("resumo: não deu para perguntar à notificacoes: %s", erro)
            return None

        if r.status_code != 200:
            logger.error("resumo: a notificacoes respondeu HTTP %s", r.status_code)
            return None

        try:
            corpo = r.json()
        except ValueError as erro:
            # `json.JSONDecodeError` é `ValueError`, NÃO `httpx.HTTPError` — a
            # mesma distinção que furou o fail-open na Fase D se ficasse fora
            # deste `try`.
            logger.error("resumo: a notificacoes respondeu fora do contrato: %s", erro)
            return None

        if not isinstance(corpo, dict):
            return None
        valor = corpo.get("nao_lidas")
        # O contrato promete inteiro ≥0 (`nao_lidas: {type: integer, minimum:
        # 0}`). `bool` é subclasse de `int` em Python — excluí-lo explicitamente
        # evita que um `true`/`false` fora do contrato vire "1 aviso"/"0 avisos"
        # por acidente de tipagem. Fora do contrato é tratado como "não sei",
        # nunca como um número adivinhado.
        if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
            return None
        return valor
