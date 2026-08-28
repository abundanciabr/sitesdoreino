# apps/core/clients.py  # [RECEITA:R2 v1]
# Fala SÓ o que está no contrato congelado da identidade
# (`contracts/identidade.openapi.yaml`). Nunca lê o banco dela (Lei 3).
import logging
import os
import time

import httpx

from . import medidor

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


def _anota(registrar, *args) -> None:
    """Medir JAMAIS derruba esta chamada. Nem por defeito, nem por assinatura.

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
            _anota(medidor.registrar_chamada, "sem_configuracao", 0.0)
            raise IdentidadeIndisponivel("configuração ausente")
        base, token = config

        # A partir daqui, cada saída ANOTA o próprio desfecho. Os cinco são
        # contadores diferentes de propósito: "estourou o tempo" e "a identidade
        # recusou" chegam idênticos na tela (503 nos dois casos), e foi essa
        # indistinção que fez o diagnóstico de 27/08/2026 levar um dia inteiro.
        # Anotar é tudo o que acontece aqui — nenhuma decisão muda.
        comeco = time.perf_counter()
        try:
            r = http().get(
                f"{base}/sessao/completa",
                headers={"Authorization": f"Bearer {token}", "Cookie": cookie},
                timeout=self.TIMEOUT,
            )
        except httpx.HTTPError as erro:
            _anota(
                medidor.registrar_chamada,
                "estourou_o_tempo",
                (time.perf_counter() - comeco) * 1000,
            )
            logger.error("porta: não deu para perguntar à identidade: %s", erro)
            raise IdentidadeIndisponivel(str(erro)) from erro

        decorrido_ms = (time.perf_counter() - comeco) * 1000

        if r.status_code != 200:
            # 403 aqui significa que o par não está em TOKENS_COMPLETOS_ADMIN —
            # o modo de falha que o script de provisionamento confere, porque
            # de dentro ele é indistinguível de "você não está na lista".
            logger.error("porta: a identidade respondeu HTTP %s", r.status_code)
            _anota(medidor.registrar_chamada, "recusou", decorrido_ms)
            raise IdentidadeIndisponivel(f"HTTP {r.status_code}")

        try:
            corpo = r.json()
        except ValueError as erro:
            # 200 com corpo que não é JSON: proxy interposto, resposta
            # truncada. `json.JSONDecodeError` é `ValueError`, NÃO é
            # `httpx.HTTPError` — sem este `except` ela viraria 500.
            # *Status 2xx não é sucesso* (RETROSPECTIVA §4).
            logger.error("porta: a identidade respondeu fora do contrato: %s", erro)
            _anota(medidor.registrar_chamada, "fora_do_contrato", decorrido_ms)
            raise IdentidadeIndisponivel("corpo fora do contrato") from erro

        if not isinstance(corpo, dict):
            logger.error("porta: a identidade respondeu um corpo que não é objeto")
            _anota(medidor.registrar_chamada, "fora_do_contrato", decorrido_ms)
            raise IdentidadeIndisponivel("corpo fora do contrato")

        _anota(medidor.registrar_chamada, "respondeu", decorrido_ms)
        return corpo


class AlunosClient:
    """`contracts/alunos.openapi.yaml` — a fila de liberação (somente leitura).

    **Fail-OPEN, e é o inverso do `IdentidadeClient` deste mesmo arquivo.** A
    diferença não é gosto: aquele decide ACESSO (quem entra na área), e por
    isso qualquer dúvida fecha. Este decide o que UMA TELA mostra, dentro de
    uma área em que a pessoa já entrou — e uma tela que não abre porque uma
    célula vizinha caiu é o oposto do que a área administrativa serve para
    fazer (`PLANO-AREA-ADMIN.md` §5: fail-open por tile, com orçamento de
    tempo).

    Por isso os métodos aqui devolvem `None` em vez de levantar: `None` é
    *"não consegui perguntar"*, e a tela diz isso com todas as letras — nunca
    lista vazia, que se leria como *"não há ninguém esperando"*.
    """

    # Mesmo orçamento do `IdentidadeClient`, e pelo mesmo motivo: alguém está
    # esperando uma página abrir. A diferença é o que acontece ao estourar —
    # lá, 503; aqui, um aviso no lugar da lista.
    TIMEOUT = 2.0

    def _configuracao(self) -> "tuple[str, str] | None":
        """Endereço e token do par, ou `None` se o env não os tiver.

        Lido NO PONTO DE USO, com `.get()` — `armadilhas/097`. Enquanto o
        mantenedor não rodar `infra/provisionar-pares-de-categorias.sh`, estas
        duas variáveis simplesmente não existem, e este é o caminho normal por
        onde a célula passa: sem elas a área abre igual, e só a lista da fila
        diz que ainda não consegue perguntar.
        """
        base = (os.environ.get("ALUNOS_API_URL") or "").strip().rstrip("/")
        token = (os.environ.get("ALUNOS_API_TOKEN") or "").strip()
        return (base, token) if base and token else None

    def fila(self, status: str) -> "list[dict] | None":
        """Quem está na fila, de TODAS as escolas (`site_id` omitido de propósito).

        Devolve a lista, ou `None` quando não deu para perguntar. **Nunca
        levanta** — quem chama é uma view, e a página tem de abrir.

        `site_id` fica de fora porque o painel do dono é plataforma-inteira
        (Lei 9), e cada linha já diz de qual escola veio
        (`DECISAO-categorias-de-usuario`).
        """
        config = self._configuracao()
        if config is None:
            logger.info(
                "fila: ALUNOS_API_URL/ALUNOS_API_TOKEN ainda não estão no env "
                "desta célula — a tela da fila vai dizer que não consegue "
                "perguntar. Rode infra/provisionar-pares-de-categorias.sh."
            )
            return None
        base, token = config

        try:
            r = http().get(
                f"{base}/pre-matriculas",
                params={"status": status},
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.TIMEOUT,
            )
        except httpx.HTTPError as erro:
            logger.error("fila: não deu para perguntar à alunos: %s", erro)
            return None

        if r.status_code != 200:
            # 401 aqui significa que o par não está em `TOKENS_ACEITOS_ADMIN` do
            # lado da `alunos` — de fora, indistinguível de "não há fila".
            logger.error("fila: a alunos respondeu HTTP %s", r.status_code)
            return None

        try:
            corpo = r.json()
        except ValueError as erro:
            # 200 com corpo que não é JSON: proxy interposto, resposta
            # truncada. *Status 2xx não é sucesso* (RETROSPECTIVA §4).
            logger.error("fila: a alunos respondeu fora do contrato: %s", erro)
            return None

        if not isinstance(corpo, list):
            logger.error("fila: a alunos respondeu um corpo que não é lista")
            return None
        return corpo
