# apps/core/clients.py
"""A única conversa que esta célula tem com outra célula.

Até 29/08/2026 ela não tinha nenhuma: `celulas.yml` a declarava com
`consome: []`, e era verdade. Ela ganhou uma porque ganhou voz — e para
endereçar uma carta é preciso saber o id de plataforma de quem vai recebê-la,
que só a `identidade` sabe (`findPersonByEmail`, Rito de Contrato do PR #524).

**Fail-ABERTO, e a direção é a decisão.** Esta consulta alimenta um AVISO, não
uma autorização. Se ela falhar, a pessoa deixa de receber uma carta — e
continua vendo a mudança no site na próxima vez que abrir. Se ela fizesse a
LIBERAÇÃO falhar, o mantenedor clicaria em "Liberar" e nada aconteceria por
causa de uma peça de notificação. Os dois erros não têm o mesmo preço, e é por
isso que todo tropeço aqui vira `None`.

`None` significa *"não sei quem é"*, e quem chama trata isso como "não há carta
a enviar" — nunca como "esta pessoa não existe".
"""

import logging
import os

import httpx

logger = logging.getLogger(__name__)


def http() -> httpx.Client:
    """Cliente novo por chamada — sem pool compartilhado entre threads.

    O volume aqui é ínfimo (uma consulta por liberação, e liberação é gesto
    humano); um pool de longa vida seria complexidade sem ganho, e é o tipo de
    coisa que guarda um socket morto depois de um reinício do vizinho.
    """
    return httpx.Client()


class IdentidadeClient:
    """`contracts/identidade.openapi.yaml` — quem é a pessoa deste e-mail."""

    # Curto de propósito: isto roda no caminho de alguém esperando o clique de
    # "Liberar" responder. Estourou ⇒ a decisão acontece do mesmo jeito, e o
    # aviso é o que se perde.
    TIMEOUT = 2.0

    def _configuracao(self) -> "tuple[str, str] | None":
        """Endereço e token do par, lidos NO PONTO DE USO (`armadilhas/097`).

        Enquanto o par `alunos→identidade` não estiver provisionado na VPS,
        estas variáveis não existem — e este é um caminho NORMAL, não um erro:
        a célula se comporta como antes desta mudança, sem enviar cartas.
        """
        base = (os.environ.get("IDENTIDADE_API_URL") or "").strip().rstrip("/")
        token = (os.environ.get("IDENTIDADE_API_TOKEN") or "").strip()
        return (base, token) if base and token else None

    def id_por_email(self, email: str) -> "str | None":
        """O id de plataforma de quem tem este e-mail, ou `None`.

        **Nunca levanta.** Quem chama está no meio de uma decisão do
        mantenedor, e essa decisão não pode depender desta resposta.

        A normalização do e-mail é da `identidade`, não daqui: quem é dono do
        dado é dono da forma canônica dele. Repeti-la deste lado criaria uma
        segunda regra, e a primeira que divergisse devolveria `None` para uma
        pessoa que existe — um aviso que nunca chega, sem erro no caminho.
        """
        config = self._configuracao()
        if config is None:
            logger.info(
                "aviso: IDENTIDADE_API_URL/IDENTIDADE_API_TOKEN ausentes no env "
                "desta célula — nenhuma carta será endereçada"
            )
            return None
        base, token = config

        try:
            r = http().post(
                f"{base}/pessoas/por-email",
                json={"email": email},
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.TIMEOUT,
            )
        except httpx.HTTPError as erro:
            logger.error("aviso: não deu para perguntar à identidade: %s", erro)
            return None

        if r.status_code != 200:
            # 403 aqui significa que o par não está em `TOKENS_COMPLETOS_*` do
            # lado da identidade — um passo de provisionamento, não um defeito
            # de código. O log nomeia o status para o diagnóstico não exigir
            # entrar no servidor.
            logger.error("aviso: a identidade respondeu HTTP %s", r.status_code)
            return None

        try:
            corpo = r.json()
        except ValueError as erro:
            # *Status 2xx não é sucesso*: fora deste `try`, um proxy devolvendo
            # HTML com 200 furaria o fail-aberto e derrubaria a liberação.
            logger.error("aviso: a identidade respondeu fora do contrato: %s", erro)
            return None

        if not isinstance(corpo, dict):
            logger.error("aviso: a identidade respondeu um corpo fora do contrato")
            return None
        # `id: null` é RESPOSTA — "não conheço esta pessoa", que é o caso comum
        # de quem foi cadastrado à mão e ainda não entrou com o Google.
        return (corpo.get("id") or "").strip() or None
