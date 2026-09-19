"""Quem é a pessoa, em que site ela está, e o que ela é na escola.

**Reconhecer não é assinar.** A `identidade` diz quem é; esta célula só PERGUNTA.
Não há `SessionMiddleware`, não há `SESSION_ENGINE`, e o cookie recebido é
repassado OPACO: a Fila não tem a chave que o assina e não pode ter ([INV-P12];
`DECISAO-fila-do-primeiro-dolar.md` §4). Duas células assinando o MESMO cookie
com chaves diferentes produzem um cabo-de-guerra invisível, sem erro, sem log e
sem alarme (`armadilhas/143`). Guarda:
`tests/test_inv_encomendas_nao_assina_sessao.py`.

**E reconhecer também não é autorizar.** A `identidade` devolve um `papel` junto
com o id, e ele é de EXIBIÇÃO. Quem decide o que alguém pode fazer aqui é
`apps/core/plantao.py`, sobre uma lista desta célula, fail-closed.

Molde: `services/gamificacao/apps/core/sessao.py`, copiado e não importado
(Lei 3). O que esta célula acrescenta é a terceira pergunta, e são estas três
que fazem `celulas.yml` passar a `consome: [alunos, identidade]` no MESMO PR
(`armadilhas/224`):

    quem_e()               identidade   quem é o dono do cookie
    pessoa_por_email()     identidade   o id opaco de quem tem este e-mail
    categoria_na_escola()  alunos       esta pessoa é aluna, e em que situação

Quem as usa é a tela do plantão: o professor escreve o e-mail, a `alunos` diz se
aquela pessoa é aluna, e a `identidade` traduz o e-mail no id opaco que vira o
perfil. Sem as duas, um título de Banca iria para um e-mail digitado errado e o
perfil nasceria pendurado em ninguém.

**As posturas diante da falha são OPOSTAS, de propósito.** `quem_e` falha ABERTO
(tropeço vira visitante): página sem selo é página, página quebrada não é. As
outras duas falham FECHADO, porque quem as chama está prestes a CONCEDER, e "não
consegui perguntar" lido como "não é aluna" recusaria em silêncio um título que
o professor acabou de decidir dar.

**Nada aqui é lido no import** (`armadilhas/097`): env lido no carregamento do
módulo transforma variável ausente em HTTP 500 em toda página, com deploy verde.
"""

from __future__ import annotations

import logging
import os
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

# Curto de propósito: este salto está no caminho de alguém esperando uma página.
TIMEOUT = 5.0

# "Ainda não perguntei nesta requisição", que é diferente de "perguntei e é
# visitante" (`{}`, resposta legítima e a mais comum numa página pública).
_NAO_PERGUNTEI = object()

_cliente: httpx.Client | None = None

# A única categoria que dá acesso à Fila, na palavra da porta das cinco
# categorias (`DECISAO-categorias-de-usuario.md`). Uma segunda régua aqui seriam
# duas verdades sobre quem é aluno, e elas divergiriam no primeiro status novo.
CATEGORIA_DE_ALUNO = "aluno"


def http() -> httpx.Client:
    """Um cliente por processo. `httpx.get()` constrói um `SSLContext` por
    chamada (`armadilhas/082`); o `respx` troca o transporte na classe, então o
    dublê dos testes continua valendo."""
    global _cliente
    if _cliente is None:
        _cliente = httpx.Client(timeout=TIMEOUT)
    return _cliente


class ConfiguracaoAusente(RuntimeError):
    """Falta uma variável de ambiente. A mensagem sempre a NOMEIA: quem lê é o
    mantenedor num terminal, e "configuração ausente" sem o nome custa a noite."""


class VizinhaIndisponivel(RuntimeError):
    """A vizinha não respondeu, ou respondeu fora do contrato. *Não consegui
    perguntar* e *perguntei e a resposta é não* são fatos diferentes, e nenhum
    caminho daqui confunde os dois em silêncio."""


def exigir(nome: str) -> str:
    valor = (os.environ.get(nome) or "").strip()
    if not valor:
        raise ConfiguracaoAusente(
            f"variavel de ambiente ausente: {nome}. Ponha-a no env desta celula "
            "(infra/env/encomendas.env) e reinicie o container; ate la este "
            "caminho responde fechado."
        )
    return valor


def site_desta_instalacao() -> str:
    """O `site_id` desta instalação, ou a recusa com o nome da variável.

    Env, e não parâmetro: o contrato em papel não tem `site_id` em operação
    nenhuma, e acrescentar um por conta própria seria emendar contrato fora do
    Rito (`RITOS.md` §3).

    **Falha FECHADO, e aqui é diferente da gamificação**, onde `SITE_ID` ausente
    só tira o selo da página. Parâmetros, fila e peças são todos por site:
    responder "nenhum parâmetro" e "esta pessoa não está na fila" seria a porta
    mentindo com 200. Ela responde 503 dizendo a variável, que é o que se
    conserta.
    """
    return exigir("SITE_ID")


def quem_e(request) -> str | None:
    """O id OPACO do dono da sessão, ou `None` para visitante.

    Cookie repassado, `getSession`, id. **Falhar em qualquer degrau devolve
    VISITANTE, nunca outra pessoa.** Nunca levanta: visitante não é erro, e a
    tela do plantão responde "esta área é do plantão" em vez de um 500.
    """
    corpo = corpo_da_sessao(request)
    if not corpo.get("autenticado"):
        return None
    # Autenticado sem id é resposta fora de forma: não há a quem atribuir nada.
    return corpo.get("id") or None


def corpo_da_sessao(request) -> dict:
    """A resposta de `getSession` desta requisição, resolvida UMA vez.

    `{}` para visitante, para tropeço de rede e para env ausente: os três são o
    mesmo para quem desenha a tela, e nenhum pode derrubá-la.

    **A memória vive na REQUISIÇÃO, nunca em módulo**: ela morre com a resposta,
    e duas pessoas jamais dividem a mesma. Cache de sessão em variável de
    processo é exatamente como uma tela passa verde mostrando o nome de outra
    pessoa.
    """
    guardado = getattr(request, "_sessao_desta_requisicao", _NAO_PERGUNTEI)
    if guardado is not _NAO_PERGUNTEI:
        return guardado
    corpo = _resolver_sessao(request)
    try:
        request._sessao_desta_requisicao = corpo
    except AttributeError:
        # Dublê de teste que não aceita atributo novo: só paga o salto de novo.
        pass
    return corpo


def _resolver_sessao(request) -> dict:
    cookie = request.META.get("HTTP_COOKIE", "")
    if not cookie:
        return {}
    try:
        return _sessao(cookie)
    except (VizinhaIndisponivel, ConfiguracaoAusente) as erro:
        logger.warning("nao deu para reconhecer a sessao: %s", erro)
        return {}


def _sessao(cookie: str) -> dict:
    """`contracts/identidade.openapi.yaml`, operação `getSession`.

    **Duas credenciais viajam juntas e provam coisas diferentes:** o `Bearer` do
    par prova quem CHAMA; o `Cookie`, repassado opaco, prova quem é a PESSOA. O
    cookie nunca é interpretado aqui, e nunca é assinado aqui.
    """
    base = exigir("IDENTIDADE_API_URL").rstrip("/")
    token = exigir("IDENTIDADE_API_TOKEN")
    resposta = _pedir(
        "identidade",
        "GET",
        f"{base}/sessao",
        headers={"Authorization": f"Bearer {token}", "Cookie": cookie},
    )
    return _corpo_de(resposta, "identidade")


def pessoa_por_email(email: str) -> str | None:
    """O id OPACO de quem tem este e-mail, ou `None` quando ninguém tem.

    POST e não GET com o e-mail no caminho: caminho de URL entra em log de
    servidor, em proxy e em rastro de erro; corpo, não.

    **`None` diz UMA coisa só: a `identidade` respondeu que não conhece este
    e-mail.** Todo o resto levanta. 403 é o tropeço mais provável e o mais fácil
    de ler errado: significa que o token desta célula ainda não está em
    `TOKENS_COMPLETOS_ENCOMENDAS` no env dela, que é provisionamento e não
    defeito. Por isso a mensagem nomeia a variável.

    **Não normaliza o e-mail:** quem é dono do dado é dono da forma canônica
    dele, e uma segunda regra aqui viraria `None` para gente que existe.
    """
    base = exigir("IDENTIDADE_API_URL").rstrip("/")
    token = exigir("IDENTIDADE_API_TOKEN")
    resposta = _pedir(
        "identidade",
        "POST",
        f"{base}/pessoas/por-email",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": email},
    )
    if resposta.status_code == 403:
        raise VizinhaIndisponivel(
            "a celula identidade respondeu HTTP 403: o token desta celula ainda "
            "nao esta em TOKENS_COMPLETOS_ENCOMENDAS no env dela, e esse degrau "
            "e o que autoriza procurar uma pessoa por e-mail."
        )
    corpo = _corpo_de(resposta, "identidade")
    # `id: null` é RESPOSTA: quem foi cadastrado à mão e nunca entrou não tem
    # identidade nenhuma por lá.
    return (corpo.get("id") or "").strip() or None


def categoria_na_escola(email: str) -> str:
    """A categoria desta pessoa: `aluno`, `na_fila`, `ex_aluno`, `cadastrado`.

    `contracts/alunos.openapi.yaml`, operação `getStudentStanding`. Aquela porta
    responde 200 com `cadastrado` para quem não conhece, e nunca 404, então aqui
    um 404 é tropeço de verdade e levanta.

    **A Fila é dos alunos da escola, e quem sabe quem é aluno é a `alunos`.**
    Esta célula não guarda matrícula e não tem como adivinhar: o perfil que o
    plantão cria nasce desta resposta, nunca do que o professor supõe.
    """
    base = exigir("ALUNOS_API_URL").rstrip("/")
    token = exigir("ALUNOS_API_TOKEN")
    resposta = _pedir(
        "alunos",
        "GET",
        f"{base}/alunos/{quote(email, safe='')}/situacao",
        headers={"Authorization": f"Bearer {token}"},
    )
    return (_corpo_de(resposta, "alunos").get("categoria") or "").strip()


def _pedir(celula: str, metodo: str, url: str, **kwargs) -> httpx.Response:
    try:
        return http().request(metodo, url, **kwargs)
    except httpx.RequestError as erro:
        raise VizinhaIndisponivel(
            f"nao deu para falar com a celula {celula}: {erro}"
        ) from erro


def _corpo_de(resposta: httpx.Response, celula: str) -> dict:
    """*Status 200 não é sucesso*: sem este cuidado, um proxy devolvendo HTML
    com 200 viraria "esta pessoa não existe" com toda a confiança do mundo."""
    if resposta.status_code != 200:
        raise VizinhaIndisponivel(
            f"a celula {celula} respondeu HTTP {resposta.status_code}"
        )
    try:
        corpo = resposta.json()
    except ValueError as erro:
        raise VizinhaIndisponivel(
            f"a celula {celula} respondeu algo que nao e JSON: {erro}"
        ) from erro
    if not isinstance(corpo, dict):
        raise VizinhaIndisponivel(
            f"a celula {celula} respondeu fora do contrato: {type(corpo).__name__}"
        )
    return corpo
