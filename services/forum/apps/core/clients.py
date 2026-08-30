"""O que o fórum fala com o resto da plataforma — e nada além disso.

Duas conversas, e a divisão de trabalho é lei:
**a `identidade` prova QUEM É; a `alunos` diz em que CATEGORIA a pessoa está.**
O fórum não lê banco de ninguém (Lei 3) — pergunta por HTTP, pelo contrato
congelado, com Bearer do par e **timeout sempre explícito**.

**Nada aqui é lido no import.** Toda variável de ambiente é buscada no ponto de
uso, via `exigir()`: o container não pode morrer no boot porque um token ainda
não foi colado no servidor (`armadilhas/097` — env ausente vira HTTP 500 em
TODA página, com o deploy verde). Faltando a variável, quem falha é o CAMINHO
que precisa dela, fechado e com o nome da variável na mensagem.

O molde é o de `services/sugestoes/apps/core/clients.py`, o consumidor de
referência da plataforma. Reaproveitado de propósito — foi recomendação
explícita da rodada de consultoria ("adaptador de sessão reaproveitado, não
reescrito").
"""

import logging
import os
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

# Timeout SEMPRE explícito. Curto de propósito: estes saltos estão no caminho de
# uma pessoa esperando uma página abrir, e a resposta certa para "demorou" é
# falhar fechado depressa, não pendurar a requisição dela.
TIMEOUT = 5.0

_cliente: httpx.Client | None = None


def http() -> httpx.Client:
    """Um `httpx.Client` por processo, em vez de `httpx.get()` a cada chamada.

    Não é micro-otimização (`armadilhas/082`): `httpx.get()` constrói um cliente
    novo por chamada, e com ele um `ssl.SSLContext`. `httpx.Client` é seguro
    entre threads, e o `respx` troca o transporte na classe, então o dublê dos
    testes continua valendo.
    """
    global _cliente
    if _cliente is None:
        _cliente = httpx.Client(timeout=TIMEOUT)
    return _cliente


class ConfiguracaoAusente(RuntimeError):
    """Falta uma variável de ambiente que ESTE caminho precisa.

    Não é levantada no import — só quando alguém tenta atravessar a porta. A
    mensagem nomeia a variável porque quem vai ler o log é o mantenedor.
    """


class IdentidadeIndisponivel(RuntimeError):
    """A `identidade` não respondeu, ou respondeu fora do contrato.

    **Isto NUNCA vira "então ninguém entrou".** Para a pergunta "quem é?",
    *não consegui perguntar* e *perguntei e é visitante* são fatos diferentes,
    com telas diferentes.
    """


class AlunosIndisponivel(RuntimeError):
    """A `alunos` não respondeu, ou respondeu fora do contrato.

    **Nunca pode virar "deixa entrar porque não deu para conferir".** Não
    conseguir perguntar não é sinônimo de resposta positiva; quem trata esta
    exceção fecha a porta (`apps/core/sessao.py`).
    """


def exigir(nome: str) -> str:
    """Lê uma variável de ambiente NO PONTO DE USO, ou falha fechado e alto."""
    valor = (os.environ.get(nome) or "").strip()
    if not valor:
        raise ConfiguracaoAusente(
            f"variável de ambiente ausente: {nome}. "
            "O fórum fica FECHADO até ela existir no env desta célula."
        )
    return valor


class IdentidadeClient:
    """`contracts/identidade.openapi.yaml`, operação `getSessionFull`.

    **Duas credenciais viajam juntas e provam coisas diferentes** — confundi-las
    é o erro caro: o `Bearer` do par prova **quem chama**; o cabeçalho `Cookie`,
    repassado OPACO, prova **quem é a pessoa** do outro lado do navegador. O
    cookie nunca é interpretado aqui — esta célula não tem a chave que o assina,
    e não pode ter ([INV-P12]).

    Por que a resposta COMPLETA, e não a `getSession`: o fórum precisa do
    **e-mail** para perguntar à `alunos` em que categoria a pessoa está. O
    degrau que permite isso é o token do par estar também em
    `TOKENS_COMPLETOS_FORUM` no env da `identidade` — registrado por escrito em
    `DECISAO-celula-de-identidade.md` §6.3 antes de entrar no env.
    """

    def sessao_completa(self, cookie: str) -> dict:
        """Quem é a pessoa desta requisição — corpo do contrato, ou exceção."""
        base = exigir("IDENTIDADE_API_URL").rstrip("/")
        token = exigir("IDENTIDADE_API_TOKEN")
        try:
            resposta = http().get(
                f"{base}/sessao/completa",
                headers={"Authorization": f"Bearer {token}", "Cookie": cookie},
            )
        except httpx.RequestError as erro:
            raise IdentidadeIndisponivel(
                f"não deu para falar com a célula identidade: {erro}"
            ) from erro

        if resposta.status_code != 200:
            raise IdentidadeIndisponivel(
                f"a célula identidade respondeu HTTP {resposta.status_code}"
            )

        try:
            corpo = resposta.json()
        except ValueError as erro:
            # `200` com corpo que não é JSON — página de erro de um proxy
            # interposto, resposta truncada. `json.JSONDecodeError` é
            # `ValueError`, NÃO é `httpx.RequestError`: fora deste `try` ela
            # subiria crua e viraria 500, em vez da explicação honesta. É a
            # família do *2xx não é sucesso* (RETROSPECTIVA-FASE-D §4).
            raise IdentidadeIndisponivel(
                f"a célula identidade respondeu fora do contrato: {erro}"
            ) from erro

        if not isinstance(corpo, dict) or "autenticado" not in corpo:
            raise IdentidadeIndisponivel(
                "a célula identidade respondeu fora do contrato"
            )
        return corpo


class AlunosClient:
    """`contracts/alunos.openapi.yaml`, operação `getStudentStanding`.

    A porta única que responde a categoria da pessoa — 200 sempre, nunca 404, e
    **sem dado pessoal** na resposta. `ALUNOS_API_URL` aponta para a rede
    interna do Docker, nunca para a borda pública.
    """

    def categoria_de(self, email: str) -> str:
        """`visitante` | `cadastrado` | `na_fila` | `aluno` — nunca inventa.

        Qualquer coisa fora do contrato vira `AlunosIndisponivel`, e quem trata
        FECHA a porta. Não conseguir conferir nunca é "pode entrar".
        """
        base = exigir("ALUNOS_API_URL").rstrip("/")
        token = exigir("ALUNOS_API_TOKEN")
        try:
            resposta = http().get(
                # O `/alunos` do meio NÃO é decorativo, e a falta dele foi um bug
                # real desta célula até 29/08/2026. `ALUNOS_API_URL` é o `servers:`
                # do contrato (`http://alunos:8000/api/alunos`) e o caminho da
                # operação `getStudentStanding` é `/alunos/{email}/situacao` — os
                # dois se somam. Sem o segmento, a chamada dava 404, o 404 virava
                # `AlunosIndisponivel`, e o fail-closed devolvia `eh_aluno=False`
                # para TODO MUNDO, para sempre, com o deploy verde. Fail-closed
                # por bug é indistinguível de fail-closed por decisão
                # (`armadilhas/111`) — e é por isso que o dublê dos testes passou
                # a conferir a URL inteira, não só o hostname.
                f"{base}/alunos/{quote(email, safe='')}/situacao",
                headers={"Authorization": f"Bearer {token}"},
            )
        except httpx.RequestError as erro:
            raise AlunosIndisponivel(
                f"não deu para falar com a célula alunos: {erro}"
            ) from erro

        if resposta.status_code != 200:
            raise AlunosIndisponivel(
                f"a célula alunos respondeu HTTP {resposta.status_code}"
            )

        try:
            corpo = resposta.json()
        except ValueError as erro:
            raise AlunosIndisponivel(
                f"a célula alunos respondeu fora do contrato: {erro}"
            ) from erro

        categoria = (corpo or {}).get("categoria") if isinstance(corpo, dict) else None
        if not isinstance(categoria, str) or not categoria:
            raise AlunosIndisponivel("a célula alunos respondeu sem `categoria`")
        return categoria
