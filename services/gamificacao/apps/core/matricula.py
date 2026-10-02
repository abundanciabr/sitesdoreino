"""A matrícula de quem pede para assumir tarefa, PERGUNTADA na hora do gesto.

Decisão do mantenedor de 27/09/2026: só quem tem matrícula ativa assume tarefa
no quadro de contribuições. Quem sabe disso é a célula `alunos`
(`getStudentStanding`, `contracts/alunos.openapi.yaml`), e ela conhece as
pessoas por E-MAIL.

**Por que o e-mail vem da identidade, e não do espelho `Pessoa`.** Aqui o
espelho nasce com `<id>@desconhecido.invalid` em toda visita (`perfil_de`), e
nada o corrige. Perguntar à `alunos` com esse endereço responderia `visitante`
para todo aluno de verdade: o quadro fecharia para todos, por defeito, e o
defeito seria indistinguível da regra (`armadilhas/111`). O e-mail real só a
`identidade` dá, por `getSessionFull`, com o cookie repassado OPACO ([INV-P12]),
e só para o par que está também em `TOKENS_COMPLETOS_GAMIFICACAO` no env dela.

**A postura é FECHADA.** Par ausente, célula fora do ar, status fora de 200 ou
resposta fora do contrato levantam `MatriculaNaoConferida`, e quem chama diz à
pessoa que não deu para conferir agora. Não conseguir perguntar nunca é "pode
assumir".

**O e-mail não fica em lugar nenhum.** Ele é lido da identidade, usado na
pergunta à `alunos` e descartado: não é gravado em `Pessoa` nem em campo algum,
e não vai para a tela nem para o log. Por isso a falha de rede leva ao log só o
NOME do erro do httpx, nunca o texto dele, que pode trazer a URL, e a URL da
`alunos` carrega o e-mail.

**Nada aqui é lido no import** (`armadilhas/097`): as quatro variáveis dos dois
pares são lidas no ponto de uso, e a falta de qualquer uma desiste sem tocar a
rede. O molde é `services/forum/apps/core/clients.py`, copiado, não importado
(célula não importa código de outra).
"""

from __future__ import annotations

import os
from urllib.parse import quote

import httpx

from apps.core.sessao import http


class MatriculaNaoConferida(RuntimeError):
    """Não deu para saber a categoria da pessoa. Quem trata FECHA a porta."""


def _variavel(nome: str) -> str:
    valor = (os.environ.get(nome) or "").strip()
    if not valor:
        raise MatriculaNaoConferida(
            f"variável de ambiente ausente: {nome}. Ninguém assume tarefa no "
            "quadro até ela existir no env desta célula."
        )
    return valor


def _json_de(resposta: httpx.Response, celula: str):
    if resposta.status_code != 200:
        raise MatriculaNaoConferida(
            f"a célula {celula} respondeu HTTP {resposta.status_code}"
        )
    try:
        return resposta.json()
    except ValueError as erro:
        # *Status 200 não é sucesso* (RETROSPECTIVA-FASE-D, padrão 4): um proxy
        # devolvendo HTML com 200 subiria cru e viraria 500 na tela do aluno.
        raise MatriculaNaoConferida(
            f"a célula {celula} respondeu algo que não é JSON: {erro}"
        ) from erro


def _email_de(cookie: str, base: str, token: str) -> str:
    """`getSessionFull`: o e-mail do dono do cookie, ou a exceção."""
    try:
        resposta = http().get(
            f"{base}/sessao/completa",
            headers={"Authorization": f"Bearer {token}", "Cookie": cookie},
        )
    except httpx.RequestError as erro:
        raise MatriculaNaoConferida(
            f"não deu para falar com a célula identidade: {type(erro).__name__}"
        ) from erro
    if resposta.status_code == 403:
        raise MatriculaNaoConferida(
            "a célula identidade respondeu HTTP 403: o token desta célula ainda "
            "não está em TOKENS_COMPLETOS_GAMIFICACAO no env dela, e sem esse "
            "grau ela não entrega o e-mail que a matrícula precisa."
        )
    corpo = _json_de(resposta, "identidade")
    email = corpo.get("email") if isinstance(corpo, dict) else None
    if not (isinstance(corpo, dict) and corpo.get("autenticado") is True):
        raise MatriculaNaoConferida("a identidade não reconhece mais esta sessão")
    if not isinstance(email, str) or not email.strip():
        raise MatriculaNaoConferida("a identidade respondeu sem e-mail")
    return email


def _categoria_de(email: str, base: str, token: str) -> str:
    """`getStudentStanding`: `visitante` | `cadastrado` | `na_fila` | `aluno`."""
    try:
        resposta = http().get(
            # `ALUNOS_API_URL` é o `servers:` do contrato
            # (`http://alunos:8000/api/alunos`) e o caminho da operação é
            # `/alunos/{email}/situacao`: os dois se somam. Sem o `/alunos` do
            # meio a chamada dá 404 e o fail-closed recusa todo mundo.
            f"{base}/alunos/{quote(email, safe='')}/situacao",
            headers={"Authorization": f"Bearer {token}"},
        )
    except httpx.RequestError as erro:
        raise MatriculaNaoConferida(
            f"não deu para falar com a célula alunos: {type(erro).__name__}"
        ) from erro
    corpo = _json_de(resposta, "alunos")
    categoria = corpo.get("categoria") if isinstance(corpo, dict) else None
    if not isinstance(categoria, str) or not categoria:
        raise MatriculaNaoConferida("a célula alunos respondeu sem `categoria`")
    return categoria


def categoria_de_quem_pede(request) -> str:
    """A categoria do dono do cookie desta requisição, ou `MatriculaNaoConferida`."""
    # Os dois pares são lidos ANTES da primeira chamada: com o da `alunos`
    # ausente, perguntar o e-mail à `identidade` seria uma viagem inútil.
    identidade = _variavel("IDENTIDADE_API_URL").rstrip("/")
    token_identidade = _variavel("IDENTIDADE_API_TOKEN")
    alunos = _variavel("ALUNOS_API_URL").rstrip("/")
    token_alunos = _variavel("ALUNOS_API_TOKEN")
    cookie = request.META.get("HTTP_COOKIE", "")
    if not cookie:
        raise MatriculaNaoConferida("o pedido chegou sem cookie de sessão")
    email = _email_de(cookie, identidade, token_identidade)
    return _categoria_de(email, alunos, token_alunos)
