"""O NORMALIZADOR — o que ele preserva, o que ele apaga, e onde a informação
contratual realmente se perde.

O controle negativo original mudava `version: 1.0.0` para `9.9.9`. Isso prova
que o mecanismo detecta *uma* diferença — não que ele preserva TODAS as
diferenças que importam num contrato. Um normalizador que apagasse, digamos,
`required` continuaria passando naquele teste e deixaria de proteger o contrato.

Este arquivo responde três perguntas com evidência:

1. O normalizador remove alguma informação?  (`test_normalizador_e_lossless`)
2. Que diferenças contratuais ele preserva?  (os mutation tests)
3. Que diferenças ele ignora de propósito?   (`test_diferencas_irrelevantes_*`)

E registra, com teste, onde a informação SE PERDE de verdade: não aqui, e sim
no exportador de cada célula — ver `test_autenticacao_*` e a docstring de
`contract_freeze.checar_seguranca`.
"""

from __future__ import annotations

import copy
import json
from typing import Any, Callable

import pytest

import contract_freeze
from _nucleo import Estado

from conftest import RepoFalso

# Um contrato com TODAS as dimensões que o freeze precisa proteger: caminho,
# método, status, parâmetro, requestBody, response, $ref, tipo, required e
# requisito de segurança por operação.
CONTRATO_RICO: dict[str, Any] = {
    "openapi": "3.1.0",
    "info": {"title": "Rica API", "version": "1.0.0"},
    "security": [{"bearerAuth": []}],
    "paths": {
        "/pedidos": {
            "post": {
                "operationId": "criarPedido",
                "parameters": [
                    {
                        "in": "header",
                        "name": "X-Idempotency-Key",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["amount_cents", "currency"],
                                "properties": {
                                    "amount_cents": {"type": "integer", "minimum": 1},
                                    "currency": {"type": "string", "const": "BRL"},
                                },
                            }
                        }
                    },
                },
                "responses": {
                    "201": {
                        "description": "criado",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Pedido"}
                            }
                        },
                    },
                    "422": {"description": "payload viola o schema"},
                },
            }
        },
        "/pedidos/{order_id}": {
            "get": {
                "operationId": "obterPedido",
                "security": [],
                "parameters": [
                    {
                        "in": "path",
                        "name": "order_id",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "responses": {"200": {"description": "ok"}},
            }
        },
    },
    "components": {
        "schemas": {
            "Pedido": {
                "type": "object",
                "required": ["id", "total_cents"],
                "properties": {
                    "id": {"type": "string"},
                    "total_cents": {"type": "integer"},
                },
            }
        },
        "securitySchemes": {"bearerAuth": {"type": "http", "scheme": "bearer"}},
    },
}

# A autenticação que CONTRATO_RICO declara: POST /pedidos herda o `security` da
# raiz (exige credencial); GET /pedidos/{order_id} sobrescreve com [] (pública).
AUTENTICACAO_RICA = {"POST /pedidos": True, "GET /pedidos/{order_id}": False}


# ---------------------------------------------------------------------------
# 1. O normalizador não apaga nada
# ---------------------------------------------------------------------------


def test_normalizador_e_lossless() -> None:
    """`_normalizar` não remove informação: ele só ordena chaves e formata.

    Esta é a resposta formal a "quais campos o normalizador remove?" — nenhum.
    O documento sobrevive à ida e à volta byte a byte na estrutura. Ordenar
    chaves de objeto é seguro porque, em JSON e OpenAPI, ordem de chave não
    carrega significado.

    Se alguém no futuro adicionar um strip aqui (para "estabilizar" a
    comparação), este teste fica vermelho e obriga a justificar a remoção.
    """
    texto = contract_freeze._normalizar(CONTRATO_RICO, "teste")
    assert json.loads(texto) == CONTRATO_RICO


def test_normalizador_e_deterministico() -> None:
    a = contract_freeze._normalizar(copy.deepcopy(CONTRATO_RICO), "teste")
    b = contract_freeze._normalizar(copy.deepcopy(CONTRATO_RICO), "teste")
    assert a == b


# ---------------------------------------------------------------------------
# 2. Mutation tests — cada mudança semanticamente contratual precisa dar FAIL
# ---------------------------------------------------------------------------


def _mutar(fn: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    doc = copy.deepcopy(CONTRATO_RICO)
    fn(doc)
    assert doc != CONTRATO_RICO, "a mutação não mudou nada — o teste seria vazio"
    return doc


def _renomear_caminho(d: dict[str, Any]) -> None:
    d["paths"]["/orders"] = d["paths"].pop("/pedidos")


def _trocar_metodo(d: dict[str, Any]) -> None:
    d["paths"]["/pedidos"]["put"] = d["paths"]["/pedidos"].pop("post")


def _trocar_status(d: dict[str, Any]) -> None:
    op = d["paths"]["/pedidos"]["post"]
    op["responses"]["200"] = op["responses"].pop("201")


def _afrouxar_required(d: dict[str, Any]) -> None:
    esquema = d["paths"]["/pedidos"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]
    esquema["required"].remove("currency")


def _trocar_tipo_de_campo(d: dict[str, Any]) -> None:
    esquema = d["paths"]["/pedidos"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]
    esquema["properties"]["amount_cents"]["type"] = "string"


def _afrouxar_request_body(d: dict[str, Any]) -> None:
    d["paths"]["/pedidos"]["post"]["requestBody"]["required"] = False


def _trocar_schema_de_resposta(d: dict[str, Any]) -> None:
    resposta = d["paths"]["/pedidos"]["post"]["responses"]["201"]
    resposta["content"]["application/json"]["schema"] = {
        "$ref": "#/components/schemas/Outro"
    }


def _remover_parametro(d: dict[str, Any]) -> None:
    d["paths"]["/pedidos"]["post"]["parameters"] = []


def _afrouxar_parametro(d: dict[str, Any]) -> None:
    d["paths"]["/pedidos"]["post"]["parameters"][0]["required"] = False


def _tornar_endpoint_autenticado(d: dict[str, Any]) -> None:
    d["paths"]["/pedidos/{order_id}"]["get"]["security"] = [{"bearerAuth": []}]


def _trocar_esquema_de_seguranca(d: dict[str, Any]) -> None:
    d["security"] = [{"apiKeyAuth": []}]


def _afrouxar_componente(d: dict[str, Any]) -> None:
    d["components"]["schemas"]["Pedido"]["required"].remove("total_cents")


def _remover_constante(d: dict[str, Any]) -> None:
    esquema = d["paths"]["/pedidos"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]
    del esquema["properties"]["currency"]["const"]


MUTACOES = [
    ("caminho renomeado", _renomear_caminho),
    ("método HTTP trocado", _trocar_metodo),
    ("status code trocado", _trocar_status),
    ("campo saiu de required", _afrouxar_required),
    ("tipo de campo trocado", _trocar_tipo_de_campo),
    ("requestBody deixou de ser obrigatório", _afrouxar_request_body),
    ("schema da resposta apontando para outro $ref", _trocar_schema_de_resposta),
    ("parâmetro removido", _remover_parametro),
    ("parâmetro deixou de ser obrigatório", _afrouxar_parametro),
    ("rota pública virou autenticada", _tornar_endpoint_autenticado),
    ("esquema de segurança trocado", _trocar_esquema_de_seguranca),
    ("componente perdeu um required", _afrouxar_componente),
    ("const de moeda removido", _remover_constante),
]


def _preparar(repo: RepoFalso, vivo: dict[str, Any]) -> None:
    """Congela CONTRATO_RICO e faz o exportador devolver `vivo`."""
    repo.criar_celula("falsa")
    repo.congelar("falsa", CONTRATO_RICO)
    repo.declarar(
        {
            "falsa": {
                "freeze": "required",
                "frozen": "contracts/falsa.openapi.yaml",
                "exportador": repo.exportador_que_imprime("falsa", vivo),
                # A sonda reflete o CONGELADO em todos os casos: assim o
                # veredito isola a comparação documental, sem que a checagem de
                # autenticação some ruído ao resultado.
                "sonda_auth": repo.sonda_auth("falsa", AUTENTICACAO_RICA),
            }
        }
    )


def _veredito(repo: RepoFalso) -> Estado:
    return contract_freeze.rodar(
        celula="falsa", raiz=repo.raiz, manifesto=repo.manifesto
    ).estado


@pytest.mark.parametrize(
    "descricao,mutacao", MUTACOES, ids=[m[0][:40] for m in MUTACOES]
)
def test_mutacao_contratual_reprova(
    repo: RepoFalso, descricao: str, mutacao: Callable[[dict[str, Any]], None]
) -> None:
    """Toda mudança semanticamente contratual precisa chegar ao veredito.

    Se alguma destas ficar verde, o normalizador está apagando informação que
    deveria participar do freeze — e o portão estaria protegendo menos do que
    o handoff afirma.
    """
    _preparar(repo, _mutar(mutacao))
    assert _veredito(repo) is Estado.FAIL, descricao


def test_controle_positivo_do_contrato_rico(repo: RepoFalso) -> None:
    """Sem mutação, o mesmo arranjo passa — senão os testes acima provariam nada."""
    _preparar(repo, copy.deepcopy(CONTRATO_RICO))
    assert _veredito(repo) is Estado.PASS


# ---------------------------------------------------------------------------
# 3. O que o normalizador ignora de propósito
# ---------------------------------------------------------------------------


def test_ordem_de_chaves_e_irrelevante(repo: RepoFalso) -> None:
    """Ordem de chave de objeto não é semântica em JSON/OpenAPI: não pode dar FAIL.

    É por isso que `_normalizar` usa `sort_keys=True`. Sem isso, o freeze
    ficaria vermelho por reordenação cosmética do gerador de schema — e portão
    que grita à toa é portão que as pessoas aprendem a ignorar.
    """
    embaralhado = json.loads(json.dumps(CONTRATO_RICO))
    embaralhado["paths"]["/pedidos"]["post"] = dict(
        reversed(list(embaralhado["paths"]["/pedidos"]["post"].items()))
    )
    _preparar(repo, embaralhado)
    assert _veredito(repo) is Estado.PASS


def test_ordem_de_lista_e_preservada(repo: RepoFalso) -> None:
    """Ordem DENTRO de lista é preservada — escolha conservadora, documentada.

    Em `required` e `enum` a ordem não carrega significado pela especificação,
    então este FAIL é conservador: o freeze reclama de uma mudança que talvez
    não seja semântica. É o lado certo para errar — reordenar `enum` num diff
    aparece para revisão humana em vez de passar batido junto com um valor novo.
    """
    reordenado = copy.deepcopy(CONTRATO_RICO)
    esquema = reordenado["paths"]["/pedidos"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]
    esquema["required"] = list(reversed(esquema["required"]))
    _preparar(repo, reordenado)
    assert _veredito(repo) is Estado.FAIL


# ---------------------------------------------------------------------------
# 4. Onde a informação REALMENTE se perde: a autenticação efetiva
# ---------------------------------------------------------------------------


def test_autenticacao_divergente_reprova(repo: RepoFalso) -> None:
    """Endpoint que fica público sem mudar o documento exportado ⇒ FAIL.

    Este é o furo medido em 2026-08: o django-ninja omite `security` das rotas
    com `auth=None` (em vez de emitir `[]`), e os exportadores de catalogo,
    checkout, alunos e leads ainda apagam `security` por operação. Resultado: a
    comparação documental passava verde para um endpoint interno virando
    público. A sonda de autenticação mede na fonte e reprova.
    """
    _preparar(repo, copy.deepcopy(CONTRATO_RICO))
    repo.declarar(
        {
            "falsa": {
                "freeze": "required",
                "frozen": "contracts/falsa.openapi.yaml",
                "exportador": repo.exportador_que_imprime("falsa", CONTRATO_RICO),
                # O código diz: POST /pedidos ficou PÚBLICO. O contrato diz o
                # contrário — e o documento exportado não mostra diferença.
                "sonda_auth": repo.sonda_auth(
                    "falsa", {**AUTENTICACAO_RICA, "POST /pedidos": False}
                ),
            }
        }
    )
    relatorio = contract_freeze.rodar(
        celula="falsa", raiz=repo.raiz, manifesto=repo.manifesto
    )
    assert relatorio.estado is Estado.FAIL
    documental = [r for r in relatorio.resultados if r.nome.startswith("contrato/")]
    seguranca = [r for r in relatorio.resultados if r.nome.startswith("seguranca/")]
    assert documental[0].estado is Estado.PASS, (
        "a comparação documental é cega para isto — se um dia deixar de ser, "
        "atualize a docstring de checar_seguranca"
    )
    assert seguranca[0].estado is Estado.FAIL


def test_sonda_de_autenticacao_quebrada_da_error(repo: RepoFalso) -> None:
    """Não conseguir sondar a autenticação é ERROR, nunca PASS.

    Não saber se um endpoint ficou público não é o mesmo que saber que não
    ficou. Não existe `sonda_auth: desativada`.
    """
    _preparar(repo, copy.deepcopy(CONTRATO_RICO))
    for quebra in (
        ["sonda-que-nao-existe"],
        repo.script("falsa", "sonda_quebrada.py", "import sys; sys.exit(1)"),
        repo.script("falsa", "sonda_muda.py", "pass"),
        repo.script("falsa", "sonda_lixo.py", "print('nao sou json')"),
        # JSON válido com a forma errada: o portão precisa devolver ERROR, não
        # estourar. Foi assim que uma colisão de nome de arquivo neste teste
        # derrubou o processo com exit 1 — semântica de FAIL para o que era
        # instrumentação quebrada.
        repo.script("falsa", "sonda_forma.py", 'print(\'{"GET /x": {"a": 1}}\')'),
        repo.script("falsa", "sonda_lista.py", "print('[1, 2, 3]')"),
    ):
        repo.declarar(
            {
                "falsa": {
                    "freeze": "required",
                    "frozen": "contracts/falsa.openapi.yaml",
                    "exportador": repo.exportador_que_imprime("falsa", CONTRATO_RICO),
                    "sonda_auth": quebra,
                }
            }
        )
        assert _veredito(repo) is Estado.ERROR, quebra


def test_sonda_sem_operacoes_da_error(repo: RepoFalso) -> None:
    """Sonda que não acha rota nenhuma não pode ser lida como 'tudo certo'."""
    _preparar(repo, copy.deepcopy(CONTRATO_RICO))
    repo.declarar(
        {
            "falsa": {
                "freeze": "required",
                "frozen": "contracts/falsa.openapi.yaml",
                "exportador": repo.exportador_que_imprime("falsa", CONTRATO_RICO),
                "sonda_auth": repo.sonda_auth("falsa", {}),
            }
        }
    )
    assert _veredito(repo) is Estado.ERROR


def test_heranca_de_seguranca_do_openapi() -> None:
    """A leitura do congelado respeita a herança da especificação."""
    exigencia = contract_freeze.exige_autenticacao_no_congelado(CONTRATO_RICO)
    assert exigencia == AUTENTICACAO_RICA

    sem_raiz = copy.deepcopy(CONTRATO_RICO)
    del sem_raiz["security"]
    # Sem `security` na raiz e sem override, a operação é pública.
    assert (
        contract_freeze.exige_autenticacao_no_congelado(sem_raiz)["POST /pedidos"]
        is False
    )
