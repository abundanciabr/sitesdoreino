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

import logging
import os
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

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

        try:
            corpo = resposta.json()
        except ValueError as erro:
            # `200` com corpo que não é JSON — página de erro de um proxy
            # interposto, resposta truncada, `Content-Length` mentiroso.
            # `json.JSONDecodeError` é `ValueError`, NÃO é `httpx.RequestError`:
            # fora deste `try` ela subiria crua até a view e viraria 500, em vez
            # do 503 que explica. É a família do *2xx não é sucesso*
            # (RETROSPECTIVA §4), achada pela auditoria de 25/08/2026.
            raise IdentidadeIndisponivel(
                f"a célula identidade respondeu fora do contrato: {erro}"
            ) from erro

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

    # -- a fila de liberação (DECISAO-fila-de-liberacao.md, 27/08/2026) -------

    NA_FILA = "na-fila"
    JA_TEM_MATRICULA = "ja-tem-matricula"

    def pedir_entrada_na_fila(
        self,
        *,
        site_id: str,
        email: str,
        nome_completo: str,
        whatsapp: str,
        comprou_em: str = "",
        turma: str = "",
    ) -> str:
        """`createPreEnrollment` — a pessoa pede entrada e fica AGUARDANDO.

        Devolve `NA_FILA` (o contrato responde 201 na primeira vez e 200 no
        reenvio — para quem está do lado de cá os dois significam a mesma coisa:
        *seu pedido está registrado*) ou `JA_TEM_MATRICULA` (409: quem já entra
        não precisa de fila). Qualquer outra resposta FECHA, pelo mesmo motivo
        de `matriculas_de`: "não consegui registrar" não pode virar "registrei".

        **Escreve**, ao contrário de tudo o mais que esta célula pede à
        `alunos` — e é por isso que a idempotência importa: o par (site_id,
        email) é a chave do outro lado, então o duplo-clique de uma pessoa
        ansiosa não vira duas linhas na fila do mantenedor.

        Os opcionais só viajam quando têm valor: o contrato declara
        `additionalProperties: false`, e mandar `null` onde a pessoa não
        escreveu nada seria pedir para depender de um detalhe de aceitação que
        não precisamos exercitar.
        """
        base = exigir("ALUNOS_API_URL").rstrip("/")
        token = exigir("ALUNOS_API_TOKEN")
        corpo = {
            "site_id": site_id,
            "email": email,
            "nome_completo": nome_completo,
            "whatsapp": whatsapp,
        }
        if comprou_em:
            corpo["comprou_em"] = comprou_em
        if turma:
            corpo["turma"] = turma

        try:
            resposta = http().post(
                f"{base}/pre-matriculas",
                json=corpo,
                headers={"Authorization": f"Bearer {token}"},
            )
        except httpx.RequestError as erro:
            raise AlunosIndisponivel(
                f"não deu para falar com a célula alunos: {erro}"
            ) from erro

        if resposta.status_code in (200, 201):
            return self.NA_FILA
        if resposta.status_code == 409:
            return self.JA_TEM_MATRICULA
        # 422 incluído aqui de propósito: a tela valida antes de mandar, então
        # um payload recusado é desacordo NOSSO com o contrato — problema de
        # quem escreveu o código, não da pessoa. A tela diz "é problema nosso",
        # que é a verdade, e nada é dado como registrado.
        raise AlunosIndisponivel(
            f"a célula alunos respondeu HTTP {resposta.status_code} ao pedido de entrada"
        )


class NotificacoesClient:
    """`contracts/notificacoes.openapi.yaml` — a caixa central de avisos.

    Lei do assunto: `docs/decisoes/DECISAO-fase-4-do-sininho.md` (Escolha 2) e
    `docs/decisoes/DECISAO-fase-2-do-sininho.md` §3 — a tela de avisos da Caixa
    passa a ler daqui. Cópia peça por peça do padrão de
    `services/funil/apps/core/clients.py::NotificacoesClient` (Lei 3: copia-se
    o PADRÃO, nunca o arquivo por import cruzado entre células): `.get()` no
    ponto de uso (nunca `os.environ[...]`, nunca `exigir()` — ver abaixo o
    porquê), timeout curto e explícito, `httpx.HTTPError` separado de
    `ValueError` no `.json()`.

    **Por que este cliente NUNCA levanta exceção — ao contrário de
    `AlunosClient`/`IdentidadeClient`, os dois vizinhos acima.** Aqueles dois
    alimentam AUTORIZAÇÃO (fail-CLOSED: quem não consegue perguntar fecha a
    porta — `exigir()` propositalmente falha alto). Este cliente alimenta DUAS
    telas com regras OPOSTAS (`DECISAO-fase-4-do-sininho.md` Escolha 2): o sino
    (`avisos.sino`, fail ABERTA, em toda página) e a tela de avisos
    (`avisos.ver_avisos`, fail VISÍVEL, só naquela página). Nenhuma exceção
    única poderia servir às duas ao mesmo tempo — por isso todo método aqui
    devolve `None` em qualquer tropeço (config ausente, rede, HTTP fora de
    200, JSON fora do contrato), e quem chama decide o que `None` significa
    PARA A TELA DELE: o sino traduz como "não mostra número"; `ver_avisos`
    traduz como "mostra a frase de falha". `None` nunca se confunde com uma
    resposta real vazia (`nao_lidas: 0`, `itens: []`) — são estados
    DIFERENTES, exatamente como a Escolha 2 exige.

    A ÚNICA exceção a "sempre `None`" é `marcar_uma_como_lida`, que distingue
    um terceiro caso (`False`) — ver a docstring dela.

    Auth: Bearer estático do par `sugestoes→notificacoes`
    (`services/notificacoes/apps/core/auth.py`, `TOKENS_ACEITOS_SUGESTOES` do
    lado de lá).
    """

    TIMEOUT = 2.0

    def _configuracao(self) -> "tuple[str, str] | None":
        """Ver o comentário gêmeo em `IdentidadeClient._configuracao` do
        `funil` — mesma razão, mesma forma: `.get()`, nunca
        `os.environ[...]`, lido NO PONTO DE USO. Falta de config é MAIS
        provável que falha de rede (basta uma variável não colada no
        servidor), e não pode furar nem o fail-open do sino nem o
        fail-visible da tela — as duas precisam continuar respondendo.
        """
        base = (os.environ.get("NOTIFICACOES_API_URL") or "").strip().rstrip("/")
        token = (os.environ.get("NOTIFICACOES_API_TOKEN") or "").strip()
        return (base, token) if base and token else None

    def obter_resumo(self, *, destinatario_id: str, site_id: str) -> "int | None":
        """Quantos avisos não lidos esta pessoa tem NESTE site, ou `None`.

        `None` é "não sei" (config ausente, rede, HTTP≠200, JSON fora do
        contrato) — quem chama (o sino) não desenha número nenhum. É
        DIFERENTE de `0`, que é "perguntei e a resposta é zero".
        """
        config = self._configuracao()
        if config is None:
            logger.error(
                "notificacoes: NOTIFICACOES_API_URL/NOTIFICACOES_API_TOKEN "
                "ausentes no env desta célula — resumo indisponível"
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
            logger.error("resumo: a notificacoes respondeu fora do contrato: %s", erro)
            return None

        if not isinstance(corpo, dict):
            return None
        valor = corpo.get("nao_lidas")
        # `bool` é subclasse de `int` em Python — excluí-lo explicitamente
        # evita que um `true`/`false` fora do contrato vire "1 aviso"/"0
        # avisos" por acidente de tipagem.
        if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
            return None
        return valor

    def listar_avisos(
        self, *, destinatario_id: str, site_id: str, cursor: str = ""
    ) -> "dict | None":
        """Uma página de `{"itens": [...], "proximo_cursor": ...}`, ou `None`.

        `None` é "não sei" — nunca confundido com `{"itens": [], ...}`
        (página real, zero avisos DE VERDADE). É essa distinção que permite a
        `ver_avisos` mostrar a frase de falha em vez de uma lista vazia
        disfarçada (Escolha 2, `DECISAO-fase-4-do-sininho.md`).
        """
        config = self._configuracao()
        if config is None:
            logger.error(
                "notificacoes: NOTIFICACOES_API_URL/NOTIFICACOES_API_TOKEN "
                "ausentes no env desta célula — avisos indisponíveis"
            )
            return None
        base, token = config
        params = {"destinatario_id": destinatario_id, "site_id": site_id}
        if cursor:
            params["cursor"] = cursor
        try:
            r = http().get(
                f"{base}/avisos",
                params=params,
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.TIMEOUT,
            )
        except httpx.HTTPError as erro:
            logger.error("avisos: não deu para perguntar à notificacoes: %s", erro)
            return None

        if r.status_code != 200:
            logger.error("avisos: a notificacoes respondeu HTTP %s", r.status_code)
            return None

        try:
            corpo = r.json()
        except ValueError as erro:
            logger.error("avisos: a notificacoes respondeu fora do contrato: %s", erro)
            return None

        if not isinstance(corpo, dict) or not isinstance(corpo.get("itens"), list):
            logger.error(
                "avisos: a notificacoes respondeu fora do contrato (sem 'itens')"
            )
            return None
        return corpo

    def marcar_uma_como_lida(
        self, *, destinatario_id: str, site_id: str, id: str
    ) -> "bool | None":
        """Marca UM aviso como lido — três respostas, e as três importam.

        `True`: marcado agora, ou já estava lido (o contrato é idempotente).
        `False`: a notificacoes respondeu **404** — `id` não existe ou não é
        deste `destinatario_id`/`site_id`. Isto NÃO é "não sei": é uma
        resposta definitiva, e quem chama (`avisos.marcar_lido`) precisa
        devolver 404 — nunca 403, para não confirmar a existência do aviso
        alheio a quem chutou um valor (o mesmo cuidado que a leitura local já
        tinha, agora do lado da notificacoes).
        `None`: não sei — config ausente, rede, qualquer outro HTTP≠200,
        JSON fora do contrato.
        """
        config = self._configuracao()
        if config is None:
            logger.error(
                "marcar-lida: NOTIFICACOES_API_URL/NOTIFICACOES_API_TOKEN "
                "ausentes no env desta célula"
            )
            return None
        base, token = config
        try:
            r = http().post(
                f"{base}/marcar-lida",
                json={
                    "destinatario_id": destinatario_id,
                    "site_id": site_id,
                    "id": id,
                },
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.TIMEOUT,
            )
        except httpx.HTTPError as erro:
            logger.error("marcar-lida: não deu para chamar a notificacoes: %s", erro)
            return None

        if r.status_code == 404:
            return False
        if r.status_code != 200:
            logger.error("marcar-lida: a notificacoes respondeu HTTP %s", r.status_code)
            return None

        try:
            r.json()
        except ValueError as erro:
            logger.error(
                "marcar-lida: a notificacoes respondeu fora do contrato: %s", erro
            )
            return None
        return True

    def marcar_todas_como_lidas(
        self, *, destinatario_id: str, site_id: str
    ) -> "int | None":
        """Quantos avisos foram marcados agora, ou `None` (não sei).

        `0` é resposta válida (ninguém tinha aviso pendente) — DIFERENTE de
        `None` (não consegui perguntar), pela mesma razão de sempre.
        """
        config = self._configuracao()
        if config is None:
            logger.error(
                "marcar-lidas: NOTIFICACOES_API_URL/NOTIFICACOES_API_TOKEN "
                "ausentes no env desta célula"
            )
            return None
        base, token = config
        try:
            r = http().post(
                f"{base}/marcar-lidas",
                json={"destinatario_id": destinatario_id, "site_id": site_id},
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.TIMEOUT,
            )
        except httpx.HTTPError as erro:
            logger.error("marcar-lidas: não deu para chamar a notificacoes: %s", erro)
            return None

        if r.status_code != 200:
            logger.error(
                "marcar-lidas: a notificacoes respondeu HTTP %s", r.status_code
            )
            return None

        try:
            corpo = r.json()
        except ValueError as erro:
            logger.error(
                "marcar-lidas: a notificacoes respondeu fora do contrato: %s", erro
            )
            return None

        if not isinstance(corpo, dict):
            return None
        valor = corpo.get("marcados")
        if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
            return None
        return valor
