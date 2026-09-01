"""Quem é a pessoa desta requisição — e em que site ela está jogando.

**A regra que organiza este arquivo: reconhecer não é assinar.** A `identidade`
diz quem é; esta célula só PERGUNTA. Não há `SessionMiddleware`, não há
`SESSION_ENGINE`, e o cookie recebido é repassado OPACO — a gamificação não tem
a chave que o assina e não pode ter ([INV-P12];
`DECISAO-celula-de-identidade.md` §6.4; guarda em
`tests/test_inv_gamificacao_nao_assina_sessao.py`).

Duas células assinando o MESMO cookie com chaves diferentes produzem um
cabo-de-guerra invisível: abrir a página de conquistas deslogaria do site, e
vice-versa, sem erro em lugar nenhum (`armadilhas/143`).

O molde é `services/forum/apps/core/clients.py`, o consumidor de referência da
plataforma — copiado, não importado (Lei 3). No caminho da PÁGINA basta
`getSession`: a gamificação precisa do **id opaco**, nunca do e-mail, e pedir
`getSessionFull` seria receber um dado que esta célula não tem o que fazer com
ele.

**Há um segundo caminho aqui desde 01/09/2026, e ele é de linha de comando, não
de página:** `pessoa_por_email`, a tradução que `conceder_fundador --emails`
usa. A célula que sabe quem pediu entrada na escola (`alunos`) conhece as
pessoas por e-mail, e a medalha se concede por id opaco. A ponte é
`findPersonByEmail`, no contrato congelado da `identidade`, e ela **exige o
degrau `TOKENS_COMPLETOS_GAMIFICACAO`** no env da `identidade` — o mesmo de
`getSessionFull`, porque quem manda um e-mail para aquela porta descobre se ele
existe. Sem o degrau a resposta é 403, com Bearer válido; quem instala o degrau
é `infra/conceder-fundador-aos-alunos.sh`.

**As duas funções têm posturas OPOSTAS diante da falha, e isso é deliberado.**
`quem_e` falha ABERTO (tropeço vira visitante), porque uma página sem selo é uma
página e uma página quebrada não é. `pessoa_por_email` falha FECHADO (tropeço
vira exceção), porque quem a chama está prestes a CONCEDER: "não consegui
perguntar" lido como "esta pessoa não existe" faria a medalha deixar de sair
para quem a merece, e o relatório afirmaria, com todas as letras, que aquelas
pessoas não foram encontradas. Ali o silêncio é caro; aqui a exceção alta é
barata, porque do outro lado há um humano lendo a tela e podendo rodar de novo.

**Nada aqui é lido no import.** Toda variável de ambiente é buscada no ponto de
uso, com falha fechada e o nome da variável na mensagem: cliente que lê env no
`__init__` transforma env ausente em HTTP 500 em TODA página, com o deploy
verde (`armadilhas/097`).
"""

from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

# Timeout SEMPRE explícito. Curto de propósito: este salto está no caminho de
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
    """Falta uma variável de ambiente que ESTE caminho precisa."""


class IdentidadeIndisponivel(RuntimeError):
    """A `identidade` não respondeu, ou respondeu fora do contrato.

    **Isto NUNCA vira "então ninguém entrou" sem deixar rastro.** Para a
    pergunta "quem é?", *não consegui perguntar* e *perguntei e é visitante*
    são fatos diferentes. Esta porta trata os dois como visitante — porque o
    contrato manda responder 200 e nunca quebrar a tela de quem chama — mas
    registra o primeiro no log, alto, com o motivo.
    """


def exigir(nome: str) -> str:
    """Lê uma variável de ambiente NO PONTO DE USO, ou falha fechado e alto."""
    valor = (os.environ.get(nome) or "").strip()
    if not valor:
        raise ConfiguracaoAusente(
            f"variável de ambiente ausente: {nome}. "
            "A porta de máquina da gamificação responde SEM etiqueta até ela "
            "existir no env desta célula."
        )
    return valor


def site_atual() -> str | None:
    """O `site_id` desta instalação, ou `None` quando o env não o declara.

    **Por que env, e não parâmetro da chamada:** o contrato congelado
    (`contracts/gamificacao.openapi.yaml`) não tem `site_id` em nenhuma das duas
    operações, e o contrato manda — acrescentar um parâmetro aqui seria emenda
    de contrato por conta própria, o que o Rito (`RITOS.md` §3) proíbe. E não
    dá para resolver o site pelo Host como a `sugestoes` faz: aquele caminho é o
    CONV-SITE, um middleware que pergunta ao `catalogo`, e esta célula ainda não
    tem middleware nenhum — ele nasce com a primeira tela (PR 7 da escada).

    **Ausente ⇒ ninguém tem etiqueta, e o log diz o nome da variável.** É a
    falha ABERTA que o contrato pede em letras: "página sem selo, nunca página
    quebrada". Mas é uma falha que se esconde bem, então ela grita no log: sem
    `SITE_ID` no `infra/env/gamificacao.env`, todo aluno da escola some do mapa
    de perfis de uma vez, e nenhuma tela quebra para avisar.
    """
    try:
        return exigir("SITE_ID")
    except ConfiguracaoAusente as erro:
        logger.warning("porta de máquina sem site: %s", erro)
        return None


def quem_e(request) -> str | None:
    """O id OPACO do dono da sessão desta requisição, ou `None` para visitante.

    A cadeia é curta: cookie repassado → `identidade` (`getSession`) → id.
    **Falhar em qualquer degrau devolve VISITANTE, nunca outra pessoa.**

    Nunca levanta: `getMyStatus` responde 200 sempre por contrato, e visitante
    não é erro. Obrigar o consumidor a traduzir 401 em "ninguém logado" é como
    o widget da home acabaria mostrando tela de erro para quem só não entrou.
    """
    cookie = request.META.get("HTTP_COOKIE", "")
    if not cookie:
        return None

    try:
        corpo = _sessao(cookie)
    except (IdentidadeIndisponivel, ConfiguracaoAusente) as erro:
        logger.warning("não deu para reconhecer a sessão: %s", erro)
        return None

    if not corpo.get("autenticado"):
        return None
    # Autenticado sem id é resposta fora de forma: não há a quem atribuir XP.
    return corpo.get("id") or None


def _sessao(cookie: str) -> dict:
    """`contracts/identidade.openapi.yaml`, operação `getSession`.

    **Duas credenciais viajam juntas e provam coisas diferentes:** o `Bearer` do
    par prova quem CHAMA; o cabeçalho `Cookie`, repassado opaco, prova quem é a
    PESSOA. O cookie nunca é interpretado aqui.
    """
    base = exigir("IDENTIDADE_API_URL").rstrip("/")
    token = exigir("IDENTIDADE_API_TOKEN")
    try:
        resposta = http().get(
            f"{base}/sessao",
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
        raise IdentidadeIndisponivel(
            f"a célula identidade respondeu algo que não é JSON: {erro}"
        ) from erro
    if not isinstance(corpo, dict):
        raise IdentidadeIndisponivel(
            f"a célula identidade respondeu fora do contrato: {type(corpo).__name__}"
        )
    return corpo


def pessoa_por_email(email: str) -> str | None:
    """O id OPACO de quem tem este e-mail, ou `None` quando ninguém tem.

    `contracts/identidade.openapi.yaml`, operação `findPersonByEmail`. POST e
    não GET com o e-mail no caminho: caminho de URL entra em log de servidor, em
    histórico de proxy e em rastro de erro; corpo, não.

    **`None` significa UMA coisa só: a `identidade` respondeu, e disse que não
    conhece este e-mail.** Todo o resto levanta. É a metade que separa esta
    função da vizinha `quem_e`, e é a razão de ela existir separada: quem chama
    está prestes a conceder uma medalha, e um "não encontrei" que na verdade era
    "não consegui perguntar" tiraria a medalha de gente que a merece, num
    relatório que afirma o contrário.

    **Não normaliza o e-mail.** Quem é dono do dado é dono da forma canônica
    dele, e a `identidade` já faz isso do lado dela. Uma segunda regra aqui
    divergiria da primeira algum dia, e a divergência apareceria como `None`
    para uma pessoa que existe.

    Levanta `ConfiguracaoAusente` se o par não está no env, e
    `IdentidadeIndisponivel` para rede, status fora de 200 e corpo fora do
    contrato. 403 é o caso mais provável dos três, e o mais fácil de
    diagnosticar errado: ele quer dizer que o token da gamificação ainda não
    está em `TOKENS_COMPLETOS_GAMIFICACAO` no env da `identidade`, que é passo
    de provisionamento e não defeito de código. Por isso a mensagem nomeia a
    variável em vez de dizer só o número.
    """
    base = exigir("IDENTIDADE_API_URL").rstrip("/")
    token = exigir("IDENTIDADE_API_TOKEN")
    try:
        resposta = http().post(
            f"{base}/pessoas/por-email",
            json={"email": email},
            headers={"Authorization": f"Bearer {token}"},
        )
    except httpx.RequestError as erro:
        raise IdentidadeIndisponivel(
            f"não deu para falar com a célula identidade: {erro}"
        ) from erro

    if resposta.status_code == 403:
        raise IdentidadeIndisponivel(
            "a célula identidade respondeu HTTP 403: o token desta célula ainda "
            "não está em TOKENS_COMPLETOS_GAMIFICACAO no env dela. Esse degrau é "
            "o que autoriza procurar uma pessoa por e-mail, e quem o instala é "
            "infra/conceder-fundador-aos-alunos.sh, dentro da VPS."
        )
    if resposta.status_code != 200:
        raise IdentidadeIndisponivel(
            f"a célula identidade respondeu HTTP {resposta.status_code}"
        )

    try:
        corpo = resposta.json()
    except ValueError as erro:
        # *Status 200 não é sucesso*: fora deste `try`, um proxy devolvendo HTML
        # com 200 viraria "não conheço esta pessoa" para a lista inteira.
        raise IdentidadeIndisponivel(
            f"a célula identidade respondeu algo que não é JSON: {erro}"
        ) from erro
    if not isinstance(corpo, dict):
        raise IdentidadeIndisponivel(
            f"a célula identidade respondeu fora do contrato: {type(corpo).__name__}"
        )
    # `id: null` é RESPOSTA, e a mais comum de todas: quem foi cadastrado à mão
    # e ainda não entrou uma vez sequer não tem identidade nenhuma por lá.
    return (corpo.get("id") or "").strip() or None
