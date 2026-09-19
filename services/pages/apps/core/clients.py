"""O que esta casa pergunta ao resto da plataforma, e nada além disso.

Três conversas, e a divisão de trabalho é lei:

- **a `identidade` prova QUEM É** (`getSessionFull`, a resposta com e-mail);
- **a `alunos` diz se a pessoa TEM MATRÍCULA** (`getStudentStanding`), e é
  esta resposta, e só ela, que decide se a Prancheta abre (fail-CLOSED);
- **a `admin` diz se a pessoa é ADMINISTRADORA da escola** (`isAdministrator`),
  e é esta resposta, e só ela, que abre a fila da conferência (fail-CLOSED).

**O mesmo e-mail serve às duas últimas perguntas, e continua sem ser guardado
nem exibido.** Ele chega na resposta da `identidade`, vai nas duas perguntas e
morre ali: nenhuma tela desta casa o mostra, e nenhuma tabela o grava.

A casa não lê banco de ninguém (Lei 3): pergunta por HTTP, pelo contrato
congelado, com Bearer do par e **timeout sempre explícito**.

**Nada aqui é lido no import.** Toda variável de ambiente é buscada no ponto de
uso: cliente que lê env no `__init__` transforma env ausente em HTTP 500 em
TODA página, com o deploy verde (`armadilhas/097`). Faltando a variável, quem
falha é o CAMINHO que precisa dela, com o nome da variável na mensagem, e a
porta fecha em vez de abrir.

Molde: `services/cursos/apps/core/clients.py`, copiado e nunca importado
(Lei 3).
"""

from __future__ import annotations

import logging
import os
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

# Timeout SEMPRE explícito. Curto de propósito: estes saltos estão no caminho de
# um aluno esperando a Prancheta abrir, e a resposta certa para "demorou" é
# falhar depressa, não pendurar a requisição dele.
TIMEOUT = 5.0

_cliente: httpx.Client | None = None


def http() -> httpx.Client:
    """Um `httpx.Client` por processo, em vez de `httpx.get()` a cada chamada.

    `httpx.get()` constrói um cliente novo por chamada, e com ele um
    `ssl.SSLContext` (`armadilhas/082`). `httpx.Client` é seguro entre threads,
    e o `respx` troca o transporte na classe, então o dublê dos testes continua
    valendo.
    """
    global _cliente
    if _cliente is None:
        _cliente = httpx.Client(timeout=TIMEOUT)
    return _cliente


class ConfiguracaoAusente(RuntimeError):
    """Falta uma variável de ambiente que ESTE caminho precisa.

    Quem trata FECHA a porta: env ausente nunca é "então deixa entrar".
    """


class IdentidadeIndisponivel(RuntimeError):
    """A `identidade` não respondeu, ou respondeu fora do contrato."""


class AlunosIndisponivel(RuntimeError):
    """A `alunos` não respondeu, ou respondeu fora do contrato.

    **Nunca vira "deixa entrar porque não deu para conferir".** Quem trata esta
    exceção fecha a porta (`apps/core/porta.py`).
    """


class AdminIndisponivel(RuntimeError):
    """A `admin` não respondeu, ou respondeu fora do contrato.

    **Nunca vira "então deixa conferir".** Quem trata esta exceção devolve 503,
    e não 403: os dois fatos são diferentes, e a porta desta casa já os separa
    em respostas diferentes (`apps/core/porta.py`).
    """


def exigir(nome: str) -> str:
    """Lê uma variável de ambiente NO PONTO DE USO, ou falha fechado e alto.

    A frase nomeia a variável e diz o tamanho do estrago, que não é o mesmo para
    as três conversas desta casa: sem o par da `identidade` ou o da `alunos` a
    Prancheta fecha; sem o par da `admin` fecha só a fila da equipe, e o aluno
    não perde nada. Uma mensagem que dissesse "a Prancheta fechou" nos três casos
    mandaria quem lê o log procurar um estrago que não existe.
    """
    valor = (os.environ.get(nome) or "").strip()
    if not valor:
        raise ConfiguracaoAusente(
            f"variável de ambiente ausente: {nome}. "
            "O caminho que precisa dela fica FECHADO até ela existir no env "
            "desta célula; os outros continuam respondendo."
        )
    return valor


class IdentidadeClient:
    """`contracts/identidade.openapi.yaml`, operação `getSessionFull`.

    **Duas credenciais viajam juntas e provam coisas diferentes:** o `Bearer`
    do par prova **quem chama**; o cabeçalho `Cookie`, repassado OPACO, prova
    **quem é a pessoa** do outro lado do navegador. O cookie nunca é
    interpretado aqui: esta célula não tem a chave que o assina, e não pode
    ter ([INV-P12], `armadilhas/143`).

    Por que a resposta COMPLETA, e não a `getSession`: a Prancheta precisa do
    **e-mail** para perguntar à `alunos` se a pessoa está matriculada. O degrau
    que permite isso é o token do par estar também em `TOKENS_COMPLETOS_PAGES`
    no env da `identidade`, registrado por escrito em
    `DECISAO-celula-de-identidade.md` §6.3 antes de entrar no env. O e-mail é
    usado nessa pergunta e descartado: nunca é guardado nem exibido.
    """

    def sessao_completa(self, cookie: str) -> dict:
        """Quem é a pessoa desta requisição, no corpo do contrato, ou exceção."""
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
            # `200` com corpo que não é JSON: página de erro de um proxy,
            # resposta truncada. `json.JSONDecodeError` é `ValueError`, NÃO é
            # `httpx.RequestError`; fora deste `try` ela viraria 500
            # (RETROSPECTIVA-FASE-D §4: 2xx não é sucesso).
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

    A porta única que responde a categoria da pessoa: 200 sempre, nunca 404, e
    **sem dado pessoal** na resposta. `ALUNOS_API_URL` é o `servers:` do
    contrato (`http://alunos:8000/api/alunos`) e o caminho da operação é
    `/alunos/{email}/situacao`: os dois se SOMAM. Sem o segmento `/alunos` do
    meio a chamada dá 404, o 404 vira `AlunosIndisponivel`, e o fail-closed
    fecha a Prancheta para TODO MUNDO, com o deploy verde (`armadilhas/111`).
    Por isso o dublê dos testes confere a URL inteira.
    """

    def categoria_de(self, email: str) -> str:
        """`cadastrado` | `na_fila` | `pausado` | `ex_aluno` | `reembolsado` |
        `aluno`. Nunca inventa: fora do contrato é `AlunosIndisponivel`, e
        quem trata FECHA a porta."""
        base = exigir("ALUNOS_API_URL").rstrip("/")
        token = exigir("ALUNOS_API_TOKEN")
        try:
            resposta = http().get(
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

        categoria = corpo.get("categoria") if isinstance(corpo, dict) else None
        if not isinstance(categoria, str) or not categoria:
            raise AlunosIndisponivel("a célula alunos respondeu sem `categoria`")
        return categoria


class AdminClient:
    """`contracts/admin.openapi.yaml`, operação `isAdministrator`.

    Entra e-mail, sai sim ou não. `ADMIN_API_URL` é o `servers:` do contrato
    (`http://admin:8000/interno`) e o caminho da operação é
    `/administradores/consultar`: os dois se SOMAM, e é por isso que o dublê dos
    testes confere a URL inteira (`armadilhas/111`).

    **É POST, e não GET, e isso não é gosto:** caminho de URL entra em log de
    servidor, em histórico de proxy e em rastro de erro; corpo, não. E-mail não
    viaja em URL nesta casa.

    **`false` é RESPOSTA, e nunca erro.** É o que esta pergunta devolve para
    quase todo mundo, porque quase todo mundo é aluno. O que vira exceção é a
    `admin` calada ou falando fora do contrato, e aí quem trata devolve 503:
    *não deu para perguntar* não é *perguntei e a resposta foi não*.
    """

    def e_administrador(self, email: str) -> bool:
        """Esta pessoa é administradora da escola? Ou exceção, nunca um chute."""
        base = exigir("ADMIN_API_URL").rstrip("/")
        token = exigir("ADMIN_API_TOKEN")
        try:
            resposta = http().post(
                f"{base}/administradores/consultar",
                headers={"Authorization": f"Bearer {token}"},
                json={"email": email},
            )
        except httpx.RequestError as erro:
            raise AdminIndisponivel(
                f"não deu para falar com a célula admin: {erro}"
            ) from erro

        if resposta.status_code != 200:
            raise AdminIndisponivel(
                f"a célula admin respondeu HTTP {resposta.status_code}"
            )

        try:
            corpo = resposta.json()
        except ValueError as erro:
            raise AdminIndisponivel(
                f"a célula admin respondeu fora do contrato: {erro}"
            ) from erro

        resposta_da_consulta = (
            corpo.get("e_administrador") if isinstance(corpo, dict) else None
        )
        # `is True` e `is False`, e nunca a verdade frouxa do Python: o contrato
        # promete um booleano, e uma cadeia como "nao" é VERDADEIRA num `if`.
        # Uma resposta fora de forma tem de fechar a fila, não abri-la.
        if not isinstance(resposta_da_consulta, bool):
            raise AdminIndisponivel(
                "a célula admin respondeu sem `e_administrador` booleano"
            )
        return resposta_da_consulta
