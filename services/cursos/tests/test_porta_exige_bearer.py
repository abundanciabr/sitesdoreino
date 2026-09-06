"""O cadeado da porta de máquina: 401 em TODAS as operações, sem exceção.

Nesta célula o Bearer é o ÚNICO cadeado. A célula roda sob `SCRIPT_NAME=/cursos`
e o corte do prefixo é do Django, não do Traefik (`armadilhas/186`), então
`meshcraft.top/cursos/api/cursos/aulas` chega aqui pela internet. Se alguém um
dia remover o `auth=` de uma rota, o texto das aulas (obra não lançada do
mantenedor) passa a responder 200 para o mundo, sem mudar uma linha de
`infra/` e sem nada no roteador para segurar. É por isso que este arquivo é o
guarda, e não a topologia.

Três coisas ficam provadas, para cada uma das onze operações: sem token é 401,
com token errado é 401, e com o conjunto de tokens VAZIO (o env ausente) é 401
mesmo com o token certo. E uma quarta, sobre o próprio guarda: a lista
percorrida aqui é a lista INTEIRA da porta, medida na fonte; uma operação nova
que entrasse sem passar por aqui reprovaria.
"""

from __future__ import annotations

import json

import pytest
from django.test import Client

from config.api import api

pytestmark = pytest.mark.django_db

TOKEN = "token-do-editor-do-admin"
SITE = "escola-a"
BASE = "/api/cursos"

CORPO_DA_AULA = {
    "pedido": "Um cubo com bordas suaves para a vitrine.",
    "cliente": "Dona Lúcia",
    "instrumento": None,
    "minimo": "Um cubo fechado.",
    "aceito_quando": ["o cubo é fechado"],
    "quiz": [],
    "video_url": "",
    "e_boss": False,
    "banca_nivel": None,
    "pecas": [],
    "pausas": [],
}
CORPO_DO_INSTRUMENTO = {
    "escala": {},
    "minimo_exercicio": "",
    "minimo_contrato": "",
    "secao_do_padrao": "",
    "descritores": {},
}

# As onze, uma a uma: (operationId, método, caminho, corpo). Os caminhos são os
# reais, com `site_id`, curso, parte e corpo válido, para que o 401 prove o
# cadeado e nunca um 404 ou 422 disfarçado. As quatro que sabem de curso entram
# aqui pelo mesmo motivo que as outras: quem passa pela borda pública é a
# ROTA, e uma rota nova sem cadeado abre o texto das aulas para o mundo.
AS_ONZE = [
    ("listSiteLessons", "get", f"/aulas?site_id={SITE}", None),
    ("getSiteLesson", "get", f"/aulas/E00?site_id={SITE}", None),
    ("putSiteLesson", "put", f"/aulas/E00?site_id={SITE}", CORPO_DA_AULA),
    ("publishSiteLesson", "post", f"/aulas/E00/publicar?site_id={SITE}", None),
    ("listLessons", "get", f"/cursos/profissional/aulas?site_id={SITE}", None),
    (
        "getLesson",
        "get",
        f"/cursos/profissional/aulas/E00?site_id={SITE}&parte=1",
        None,
    ),
    (
        "putLesson",
        "put",
        f"/cursos/profissional/aulas/E00?site_id={SITE}&parte=1",
        CORPO_DA_AULA,
    ),
    (
        "publishLesson",
        "post",
        f"/cursos/profissional/aulas/E00/publicar?site_id={SITE}&parte=1",
        None,
    ),
    ("listInstruments", "get", "/instrumentos", None),
    ("getInstrument", "get", "/instrumentos/studs", None),
    ("putInstrument", "put", "/instrumentos/studs", CORPO_DO_INSTRUMENTO),
]
IDS = [operacao for operacao, *_ in AS_ONZE]


@pytest.fixture(autouse=True)
def par_autorizado(settings):
    settings.TOKENS_ACEITOS = {TOKEN}


def chamar(metodo: str, caminho: str, corpo=None, token: str | None = TOKEN):
    cabecalhos = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
    pedir = getattr(Client(), metodo)
    if corpo is None:
        return pedir(f"{BASE}{caminho}", **cabecalhos)
    return pedir(
        f"{BASE}{caminho}",
        data=json.dumps(corpo),
        content_type="application/json",
        **cabecalhos,
    )


@pytest.mark.parametrize(("operacao", "metodo", "caminho", "corpo"), AS_ONZE, ids=IDS)
def test_sem_token_e_401(operacao, metodo, caminho, corpo):
    assert chamar(metodo, caminho, corpo, token=None).status_code == 401


@pytest.mark.parametrize(("operacao", "metodo", "caminho", "corpo"), AS_ONZE, ids=IDS)
def test_token_errado_e_401(operacao, metodo, caminho, corpo):
    resposta = chamar(metodo, caminho, corpo, token="token-de-outra-celula")
    assert resposta.status_code == 401


@pytest.mark.parametrize(("operacao", "metodo", "caminho", "corpo"), AS_ONZE, ids=IDS)
def test_conjunto_de_tokens_vazio_recusa_mesmo_o_token_certo(
    settings, operacao, metodo, caminho, corpo
):
    """Env ausente ⇒ conjunto vazio ⇒ ninguém entra. Fail-closed por construção.

    O modo de falha que isto mata: a célula sobe sem `TOKENS_ACEITOS_ADMIN` no
    env e a porta fica ABERTA porque "não havia nada com que comparar".
    """
    settings.TOKENS_ACEITOS = set()
    assert chamar(metodo, caminho, corpo).status_code == 401


@pytest.mark.parametrize(("operacao", "metodo", "caminho", "corpo"), AS_ONZE, ids=IDS)
def test_o_token_certo_abre_a_porta(esqueleto, operacao, metodo, caminho, corpo):
    """O cenário tem dente: com o esqueleto semeado e o token do par, as onze
    respondem 200. Sem isto, um caminho digitado errado daria 404 sem token e
    401 com token errado, e os três guardas acima ficariam verdes medindo uma
    rota que não existe."""
    assert chamar(metodo, caminho, corpo).status_code == 200


def test_o_guarda_percorre_todas_as_operacoes_da_porta():
    """Medido na fonte (`api._routers`), como faz a sonda do freeze de contrato:
    o conjunto de operationIds da porta é EXATAMENTE o que a lista acima
    percorre. Uma operação nova entra aqui ou não entra."""
    na_porta = {
        operacao.operation_id
        for _, roteador in api._routers
        for view in roteador.path_operations.values()
        for operacao in view.operations
    }
    assert na_porta == set(IDS)
