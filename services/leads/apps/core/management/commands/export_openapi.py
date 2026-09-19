# apps/core/management/commands/export_openapi.py  # [RECEITA:R1 v1]
import json

from django.core.management.base import BaseCommand

from apps.core import contrato_oportunidades as contrato
from config.api import api


def _strip_titles(node) -> None:
    """Remove os "title" que o pydantic injeta em todo schema/parametro gerado —
    ruído cosmético que não existe no contrato congelado."""
    if isinstance(node, dict):
        for key in list(node.keys()):
            if key == "title":
                del node[key]
            else:
                _strip_titles(node[key])
    elif isinstance(node, list):
        for item in node:
            _strip_titles(item)


def _strip_redundant_operation_noise(schema: dict) -> None:
    """O django-ninja repete por operação o que já está declarado uma vez no
    nível raiz do documento: a "security" (auth global, único par consumidor por
    Bearer) e a "description" copiada para dentro de "schema" de cada parâmetro
    de path. O contrato congelado só declara essas informações uma vez."""
    for path_item in schema.get("paths", {}).values():
        for operation in path_item.values():
            operation.pop("security", None)
            for param in operation.get("parameters", []):
                if "description" in param and "description" in param.get("schema", {}):
                    del param["schema"]["description"]


def _strip_empty_parameters(schema: dict) -> None:
    """O django-ninja sempre emite "parameters": [] mesmo quando a operação não
    tem nenhum parâmetro de path/query — o contrato congelado, escrito à mão,
    simplesmente omite a chave nesse caso."""
    for path_item in schema.get("paths", {}).values():
        for operation in path_item.values():
            if operation.get("parameters") == []:
                del operation["parameters"]


def _declarar_componentes(schema: dict) -> None:
    """Publica os componentes que esta célula declara em código.

    As duas portas de lead (upsert e tags) não usam `ninja.Schema` nomeado: os
    schemas delas são inline nos paths, e por isso o django-ninja devolve
    `"schemas": {}`, chave que o contrato escrito à mão simplesmente omite.

    O CRM humano é o contrário: o congelado nomeia 29 schemas e uma resposta
    reaproveitada (`AcaoNaoAutorizada`). Eles vêm de
    `apps/core/contrato_oportunidades.py`, que é código desta célula, e são
    injetados aqui porque o `openapi_extra` do django-ninja só alcança a
    operação, nunca a raiz do documento.
    """
    componentes = schema.setdefault("components", {})
    schemas = {**componentes.get("schemas", {}), **contrato.SCHEMAS}
    if schemas:
        componentes["schemas"] = schemas
    else:
        componentes.pop("schemas", None)
    componentes["responses"] = contrato.RESPOSTAS


def _ancorar_parametros_de_caminho(schema: dict) -> None:
    """Move para a ROTA o parâmetro que é da rota, não da operação.

    O django-ninja emite o parâmetro de path em cada operação; o congelado o
    declara uma vez por caminho, que é onde o OpenAPI recomenda pôr o que vale
    para todos os métodos. As operações envolvidas mandam `"parameters": []` no
    `openapi_extra` (a chave vazia some em `_strip_empty_parameters`), e a lista
    volta aqui, no lugar certo, a partir da mesma declaração em código.
    """
    for caminho, parametros in contrato.PARAMETROS_DE_CAMINHO.items():
        item = schema.get("paths", {}).get(caminho)
        if item is not None:
            item["parameters"] = parametros


class Command(BaseCommand):
    help = "Imprime o schema OpenAPI vivo (o freeze de contrato compara com contracts/)"

    def handle(self, *args, **kwargs):
        schema = api.get_openapi_schema(path_prefix="")
        _strip_titles(
            {
                "paths": schema.get("paths", {}),
                "components": schema.get("components", {}),
            }
        )
        _strip_redundant_operation_noise(schema)
        _strip_empty_parameters(schema)
        _declarar_componentes(schema)
        _ancorar_parametros_de_caminho(schema)
        # ensure_ascii=True (padrão) evita depender da codepage do terminal (Windows
        # cp1252 quebra em caracteres como "→"); o conteúdo semântico é idêntico —
        # \uXXXX decodifica para o mesmo unicode na leitura via yaml.safe_load.
        self.stdout.write(json.dumps(schema))
