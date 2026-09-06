"""O que a sala de aula fala com o resto da plataforma, e nada além disso.

Três conversas, e a divisão de trabalho é lei:

- **a `identidade` prova QUEM É** (`getSessionFull`, a resposta com e-mail);
- **a `alunos` diz EM QUE PRODUTOS a pessoa está matriculada**
  (`listEnrollments`), e é esta resposta, e só ela, que decide se a sala abre
  (fail-CLOSED);
- **o `catalogo` entrega o MENU do topo** (`getSiteByHost`), e ele é enfeite
  de navegação: qualquer tropeço vira "sem menu", nunca tela quebrada
  (fail-OPEN).

A sala não lê banco de ninguém (Lei 3): pergunta por HTTP, pelo contrato
congelado, com Bearer do par e **timeout sempre explícito**.

**Nada aqui é lido no import.** Toda variável de ambiente é buscada no ponto de
uso: cliente que lê env no `__init__` transforma env ausente em HTTP 500 em
TODA página, com o deploy verde (`armadilhas/097`). Faltando a variável, quem
falha é o CAMINHO que precisa dela, com o nome da variável na mensagem.

Molde: `services/forum/apps/core/clients.py` (os dois primeiros) e
`services/gamificacao/apps/core/menu.py` (o terceiro), copiados e nunca
importados.
"""

from __future__ import annotations

import logging
import os
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

# Timeout SEMPRE explícito. Curto de propósito: estes saltos estão no caminho de
# uma pessoa esperando uma página abrir, e a resposta certa para "demorou" é
# falhar depressa, não pendurar a requisição dela.
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
    """Falta uma variável de ambiente que ESTE caminho precisa."""


class IdentidadeIndisponivel(RuntimeError):
    """A `identidade` não respondeu, ou respondeu fora do contrato.

    Para a pergunta "quem é?", *não consegui perguntar* e *perguntei e é
    visitante* são fatos diferentes. A sala trata os dois como visitante,
    porque uma página que convida a entrar é uma página e uma página quebrada
    não é, mas registra o primeiro no log.
    """


class AlunosIndisponivel(RuntimeError):
    """A `alunos` não respondeu, ou respondeu fora do contrato.

    **Nunca vira "deixa entrar porque não deu para conferir".** Quem trata esta
    exceção fecha a porta (`apps/core/sessao.py`).
    """


def exigir(nome: str) -> str:
    """Lê uma variável de ambiente NO PONTO DE USO, ou falha fechado e alto."""
    valor = (os.environ.get(nome) or "").strip()
    if not valor:
        raise ConfiguracaoAusente(
            f"variável de ambiente ausente: {nome}. "
            "A sala de aula fica FECHADA até ela existir no env desta célula."
        )
    return valor


class IdentidadeClient:
    """`contracts/identidade.openapi.yaml`, operação `getSessionFull`.

    **Duas credenciais viajam juntas e provam coisas diferentes:** o `Bearer`
    do par prova **quem chama**; o cabeçalho `Cookie`, repassado OPACO, prova
    **quem é a pessoa** do outro lado do navegador. O cookie nunca é
    interpretado aqui: esta célula não tem a chave que o assina, e não pode
    ter ([INV-P12]).

    Por que a resposta COMPLETA, e não a `getSession`: a sala precisa do
    **e-mail** para perguntar à `alunos` se a pessoa está matriculada. O
    degrau que permite isso é o token do par estar também em
    `TOKENS_COMPLETOS_CURSOS` no env da `identidade`, registrado por escrito em
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
    """`contracts/alunos.openapi.yaml`, operação `listEnrollments`.

    **Pergunta as MATRÍCULAS, e não a categoria** (TAR-227). Até 06/09/2026 a
    pergunta era `getStudentStanding`, que responde uma palavra só: a pessoa é
    `aluno`, ou não é. Isso bastava enquanto havia um curso, e virou defeito no
    dia do segundo: aluno é aluno DE UM PRODUTO
    (`DECISAO-cursos-matriculas-e-alunos.md` §1), e a palavra não diz de qual.
    Esta operação diz: uma linha por matrícula, cada uma com `site_id` e
    `product_id`.

    **Nenhuma mudança de contrato foi precisa**: a operação já existia, já
    devolvia os dois campos, e o `enum` do `status` já contém SÓ os status que
    valem como acesso — quem está na fila, pausado ou reembolsado não aparece
    aqui. Filtrar por status desta ponta seria uma segunda lista de permissão,
    e ela discordaria da primeira no dia em que um status nascesse.

    `ALUNOS_API_URL` é o `servers:` do contrato (`http://alunos:8000/api/alunos`)
    e o caminho da operação é `/alunos/{email}/matriculas`: os dois se SOMAM.
    Sem o segmento `/alunos` do meio a chamada dá 404, e o 404 desta porta
    significa "nenhuma matrícula" — o fail-closed continuaria fechando a sala,
    mas com a frase errada, e com o deploy verde (`armadilhas/111`). Por isso o
    dublê dos testes confere a URL inteira.
    """

    def matriculas_de(self, email: str) -> list[dict]:
        """As matrículas ATIVAS desta pessoa, no corpo do contrato.

        Lista vazia quando não há nenhuma: **404 é resposta, não falha.** É o
        que a porta responde para quem ela não conhece e para quem só está na
        fila, e traduzi-lo em `AlunosIndisponivel` diria "não consegui
        conferir" a quem foi conferido e não tem matrícula. As duas fecham a
        sala; a tela diz frases diferentes, e a frase certa importa.

        Qualquer outra resposta fora do contrato é `AlunosIndisponivel`, e quem
        trata FECHA a porta.
        """
        base = exigir("ALUNOS_API_URL").rstrip("/")
        token = exigir("ALUNOS_API_TOKEN")
        try:
            resposta = http().get(
                f"{base}/alunos/{quote(email, safe='')}/matriculas",
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

        try:
            corpo = resposta.json()
        except ValueError as erro:
            raise AlunosIndisponivel(
                f"a célula alunos respondeu fora do contrato: {erro}"
            ) from erro

        if not isinstance(corpo, list) or not all(
            isinstance(linha, dict) for linha in corpo
        ):
            raise AlunosIndisponivel(
                "a célula alunos respondeu fora do contrato: esperava uma lista "
                "de matrículas"
            )
        return corpo


class CatalogoClient:
    """`contracts/catalogo.openapi.yaml`, operação `getSiteByHost`: o site deste
    host, com o menu do topo dentro. Fail-OPEN, e é o único cliente daqui que
    não levanta: o menu é enfeite, e a sala abre igual sem ele.

    O nome da variável do token é `TOKEN_CATALOGO`, o mesmo que o `forum`, a
    `sugestoes` e a `gamificacao` leem e que `infra/provisionar-par-do-menu.sh`
    escreve: um nome próprio aqui exigiria um roteiro só para esta célula.
    """

    def site_por_host(self, host: str) -> dict:
        """O site deste host, ou `{}`. Nunca levanta: quem chama desenha a página."""
        base = (os.environ.get("CATALOGO_API_URL") or "").strip().rstrip("/")
        token = (os.environ.get("TOKEN_CATALOGO") or "").strip()
        if not base or not token:
            # Sem o par de tokens a sala abre igual e sem menu, sem custar uma
            # tentativa de rede por página. É o estado enquanto o passo do
            # mantenedor não roda.
            return {}
        try:
            resposta = http().get(
                f"{base}/sites/by-host/{host}",
                headers={"Authorization": f"Bearer {token}"},
            )
        except httpx.RequestError as erro:
            logger.warning("menu: o catálogo não respondeu: %s", erro)
            return {}
        if resposta.status_code != 200:
            # 404 aqui é resposta legítima: host que o catálogo não conhece.
            return {}
        try:
            corpo = resposta.json()
        except ValueError as erro:
            logger.warning("menu: resposta fora do contrato: %s", erro)
            return {}
        return corpo if isinstance(corpo, dict) else {}
