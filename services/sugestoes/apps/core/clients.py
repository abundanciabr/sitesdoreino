# apps/core/clients.py  # [RECEITA:R2 v1]
"""O que esta célula fala com o mundo lá fora — e nada além disso.

Duas conversas, e a `DECISAO-celula-de-identidade` (25/08/2026) reorganizou a
primeira: **a célula `identidade` prova QUEM É; a célula `alunos` decide SE
PODE.** O Google saiu deste arquivo — a dança do OAuth mudou de casa junto com
a sessão, e quem a executa hoje é a `identidade`. O que a Caixa faz é
PERGUNTAR, pelo contrato congelado (`contracts/identidade.openapi.yaml`,
operação `getSessionFull` — a resposta COM e-mail, que esta célula precisa
para conferir as listas DELA).

**Lei 3:** a `sugestoes` NUNCA lê banco alheio. Pergunta por HTTP, pelo
contrato, com Bearer do par e **timeout sempre explícito**.

**Nada aqui é lido no import.** Toda variável de ambiente é buscada no ponto de
uso, via `exigir()`: o container web não pode morrer no boot porque um token
ainda não foi colado no servidor. Faltando a variável, quem falha é o CAMINHO
que precisa dela, fechado e com o nome da variável na mensagem.

Em dev e no CI **nada disto chega à rede**: `tests/conftest.py` dubla as duas
URLs com `respx`.
"""

import os
from urllib.parse import quote

import httpx

# Timeout SEMPRE explícito (R2). Curto de propósito: estes saltos estão no
# caminho de uma pessoa esperando uma página abrir, e a resposta certa para
# "demorou" é falhar fechado depressa, não pendurar a requisição dela.
TIMEOUT = 5.0

_cliente: httpx.Client | None = None


def http() -> httpx.Client:
    """Um `httpx.Client` por processo, em vez de `httpx.get()` a cada chamada.

    Não é micro-otimização (`armadilhas/082`): `httpx.get()` constrói um
    cliente novo por chamada, e com ele um `ssl.SSLContext` — 0,4 s por
    chamada, medido nesta máquina. `httpx.Client` é seguro entre threads, e o
    `respx` troca o transporte na classe, então o dublê continua valendo.
    """
    global _cliente
    if _cliente is None:
        _cliente = httpx.Client(timeout=TIMEOUT)
    return _cliente


class ConfiguracaoAusente(RuntimeError):
    """Falta uma variável de ambiente que ESTE caminho precisa.

    Não é levantada no import — só quando alguém tenta atravessar a porta. A
    mensagem nomeia a variável porque o leitor do log vai ser o mantenedor.
    """


class IdentidadeIndisponivel(RuntimeError):
    """A célula `identidade` não respondeu, ou respondeu fora do contrato.

    **Isto NUNCA vira "então ninguém entrou".** Para a pergunta "quem é?",
    "não consegui perguntar" e "perguntei e é visitante" são fatos diferentes:
    o segundo mostra a porta; o primeiro mostra uma explicação honesta e fecha
    a participação (fail-closed — a resposta daqui alimenta AUTORIZAÇÃO local,
    ao contrário do reconhecimento de exibição do `funil`, que falha aberto).
    """


class AlunosIndisponivel(RuntimeError):
    """A célula `alunos` não respondeu, ou respondeu fora do contrato.

    **Isto NUNCA pode virar "deixa entrar porque não deu para conferir".** Não
    conseguir perguntar não é sinônimo de resposta positiva; quem trata esta
    exceção fecha a porta (ver `apps/core/sessao.py`).
    """


def exigir(nome: str) -> str:
    """Lê uma variável de ambiente NO PONTO DE USO, ou falha fechado e alto."""
    valor = (os.environ.get(nome) or "").strip()
    if not valor:
        raise ConfiguracaoAusente(
            f"variável de ambiente ausente: {nome}. "
            "A entrada pela Caixa fica FECHADA até ela existir no env desta célula."
        )
    return valor


class IdentidadeClient:
    """`contracts/identidade.openapi.yaml`, operação `getSessionFull`.

    Duas credenciais viajam juntas e provam coisas diferentes — confundi-las é
    o erro caro (a lição veio da outra ponta desta mesma pergunta): o `Bearer`
    do par prova **quem chama**; o cabeçalho `Cookie`, repassado OPACO, prova
    **quem é a pessoa** do outro lado do navegador. O cookie nunca é
    interpretado aqui — esta célula não tem a chave que o assina (Lei 2).

    Por que a resposta completa, e não a `getSession` que o `funil` usa: esta
    célula precisa do **e-mail** para conferir as listas DELA (matrícula na
    `alunos`, staff no env) — autorização local sobre dado que a resposta de
    exibição, por desenho, não carrega. O degrau que permite isso é o token do
    par estar também em `TOKENS_COMPLETOS_SUGESTOES` no env da `identidade`.
    """

    def sessao_completa(self, cookie: str) -> dict:
        """Quem é a pessoa desta requisição — corpo do contrato, ou exceção.

        200 fora de forma, não-200 e erro de rede viram
        `IdentidadeIndisponivel`: quem chama precisa distinguir "visitante"
        (corpo com `autenticado: false`) de "não deu para perguntar" — as duas
        situações têm telas diferentes na porta.
        """
        base = exigir("IDENTIDADE_API_URL").rstrip("/")
        token = exigir("IDENTIDADE_API_TOKEN")
        try:
            resposta = http().get(
                f"{base}/sessao/completa",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Cookie": cookie,
                },
            )
        except httpx.RequestError as erro:
            raise IdentidadeIndisponivel(
                f"não deu para falar com a célula identidade: {erro}"
            ) from erro

        if resposta.status_code != 200:
            raise IdentidadeIndisponivel(
                f"a célula identidade respondeu HTTP {resposta.status_code}"
            )
        corpo = resposta.json()
        if not isinstance(corpo, dict) or "autenticado" not in corpo:
            raise IdentidadeIndisponivel(
                "a célula identidade respondeu fora do contrato"
            )
        return corpo


class AlunosClient:
    """`contracts/alunos.openapi.yaml`, operação `listEnrollments` — leitura pura.

    `ALUNOS_API_URL` aponta para a rede interna do Docker
    (`http://alunos:8000/api/alunos`, o `servers` do contrato), nunca para a
    borda pública. O token é o do PAR `sugestoes→alunos`: do outro lado ele
    entra como mais uma variável `TOKENS_ACEITOS_*` no env da `alunos` (Lote 2),
    sem uma linha de código lá.
    """

    def matriculas_de(self, email: str) -> list[dict]:
        """As matrículas deste e-mail. Lista vazia = não tem. Erro = FECHA.

        O contrato responde **404** para "aluno inexistente" — este é o único
        não-200 que significa uma resposta, e por isso é o único traduzido para
        lista vazia. Qualquer outro (401 de token errado, 500, timeout, conexão
        recusada) sobe como `AlunosIndisponivel`, porque "não consegui
        perguntar" e "perguntei e não tem" são fatos diferentes e merecem telas
        diferentes.
        """
        base = exigir("ALUNOS_API_URL").rstrip("/")
        token = exigir("ALUNOS_API_TOKEN")
        try:
            resposta = http().get(
                f"{base}/alunos/{quote(email, safe='@')}/matriculas",
                headers={"Authorization": f"Bearer {token}"},
            )
        except httpx.RequestError as erro:
            raise AlunosIndisponivel(
                f"não deu para falar com a célula alunos: {erro}"
            ) from erro

        if resposta.status_code == 404:
            return []
        if resposta.status_code != 200:
            raise AlunosIndisponivel(
                f"a célula alunos respondeu HTTP {resposta.status_code}"
            )

        corpo = resposta.json()
        if not isinstance(corpo, list):
            raise AlunosIndisponivel(
                "a célula alunos respondeu fora do contrato (esperava uma lista)"
            )
        return corpo
