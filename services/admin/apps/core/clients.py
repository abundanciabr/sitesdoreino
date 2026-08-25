# apps/core/clients.py  # [RECEITA:R2 v1]
# Fala SÓ o que está no contrato congelado da identidade
# (`contracts/identidade.openapi.yaml`). Nunca lê o banco dela (Lei 3).
import logging
import os

import httpx

logger = logging.getLogger("admin.porta")

_cliente: httpx.Client | None = None


def http() -> httpx.Client:
    """Um `httpx.Client` por processo, em vez de `httpx.get()` a cada chamada.

    A forma direta constrói um `Client` descartável — e com ele um
    `ssl.SSLContext` novo, que recarrega os certificados raiz do sistema — a
    cada chamada de rede interna (`armadilhas/082`, medido em 0,4s por
    chamada). `httpx.Client` é seguro entre threads, que é o que o uvicorn
    precisa.
    """
    global _cliente
    if _cliente is None:
        _cliente = httpx.Client()
    return _cliente


class IdentidadeIndisponivel(Exception):
    """Não deu para perguntar quem é a pessoa.

    Existe como exceção NOMEADA, e não como `None`, porque nesta célula as
    duas situações levam a respostas diferentes e a confusão entre elas é
    exatamente o modo de falha que a lei proíbe:

    - **"não há sessão"** ⇒ 302 para o login (a pessoa pode entrar e voltar);
    - **"não consegui perguntar"** ⇒ 503 (não adianta mandar para um login que
      provavelmente também está fora do ar — `DECISAO-celula-admin` §2).

    O `funil` funde as duas em `None` de propósito, e está certo: lá a resposta
    decide um nome no canto da tela (fail-OPEN). Aqui ela decide ACESSO, e
    `reconhecer não é autorizar` corta para o outro lado.
    """


class IdentidadeClient:
    """contracts/identidade.openapi.yaml — `getSessionFull` (somente-leitura)."""

    # Curto de propósito: isto está no caminho de alguém esperando uma página
    # abrir. A diferença para o `funil` (que também usa 2s) não é o número —
    # é o que acontece quando estoura: lá, "Entrar"; aqui, 503.
    TIMEOUT = 2.0

    def _configuracao(self) -> "tuple[str, str] | None":
        """Endereço e token do par, ou `None` se o env não os tiver.

        Lido NO PONTO DE USO, com `.get()` — nunca `os.environ[...]` no
        `__init__` (`armadilhas/097`). `KeyError` não é `httpx.HTTPError`:
        atravessaria intacto o `try` abaixo e o middleware, virando HTTP 500
        em vez do 503 nomeado — e falha de configuração é MAIS provável que
        falha de rede (basta uma variável não colada no servidor).
        """
        base = (os.environ.get("IDENTIDADE_API_URL") or "").strip().rstrip("/")
        token = (os.environ.get("IDENTIDADE_API_TOKEN") or "").strip()
        return (base, token) if base and token else None

    def sessao_completa(self, cookie: str) -> dict:
        """Quem é a pessoa desta requisição, COM e-mail.

        Devolve o corpo de `SessionFull`. **Levanta `IdentidadeIndisponivel`
        em qualquer falha** — rede, configuração, status inesperado, corpo
        fora do contrato. Nada aqui devolve "visitante" por omissão: quem
        decide o que fazer com a indisponibilidade é o middleware, e ele
        fecha.

        Usa `/sessao/completa` (e não `/sessao`) porque a autorização desta
        célula é por LISTA DE E-MAILS — o par está registrado em
        `TOKENS_COMPLETOS_ADMIN`, com o porquê escrito em
        `DECISAO-celula-de-identidade.md` §4.
        """
        config = self._configuracao()
        if config is None:
            # ERROR nomeando as variáveis: quem vai ler este log é o mantenedor.
            logger.error(
                "porta: IDENTIDADE_API_URL/IDENTIDADE_API_TOKEN ausentes no env "
                "desta célula — a área administrativa está fechada para todos"
            )
            raise IdentidadeIndisponivel("configuração ausente")
        base, token = config

        try:
            r = http().get(
                f"{base}/sessao/completa",
                headers={"Authorization": f"Bearer {token}", "Cookie": cookie},
                timeout=self.TIMEOUT,
            )
        except httpx.HTTPError as erro:
            logger.error("porta: não deu para perguntar à identidade: %s", erro)
            raise IdentidadeIndisponivel(str(erro)) from erro

        if r.status_code != 200:
            # 403 aqui significa que o par não está em TOKENS_COMPLETOS_ADMIN —
            # o modo de falha que o script de provisionamento confere, porque
            # de dentro ele é indistinguível de "você não está na lista".
            logger.error("porta: a identidade respondeu HTTP %s", r.status_code)
            raise IdentidadeIndisponivel(f"HTTP {r.status_code}")

        try:
            corpo = r.json()
        except ValueError as erro:
            # 200 com corpo que não é JSON: proxy interposto, resposta
            # truncada. `json.JSONDecodeError` é `ValueError`, NÃO é
            # `httpx.HTTPError` — sem este `except` ela viraria 500.
            # *Status 2xx não é sucesso* (RETROSPECTIVA §4).
            logger.error("porta: a identidade respondeu fora do contrato: %s", erro)
            raise IdentidadeIndisponivel("corpo fora do contrato") from erro

        if not isinstance(corpo, dict):
            logger.error("porta: a identidade respondeu um corpo que não é objeto")
            raise IdentidadeIndisponivel("corpo fora do contrato")
        return corpo
