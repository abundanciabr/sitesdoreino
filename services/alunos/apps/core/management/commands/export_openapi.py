# apps/core/management/commands/export_openapi.py  # [RECEITA:R1 v1]
import json

from django.core.management.base import BaseCommand

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


def _strip_empty_component_schemas(schema: dict) -> None:
    """Esta célula não usa ninja.Schema nomeado nos endpoints (o contrato congelado
    não tem components.schemas — tudo inline nos paths). django-ninja sempre inclui
    "schemas": {} em components; o contrato à mão omite a chave quando vazia."""
    components = schema.get("components", {})
    if components.get("schemas") == {}:
        del components["schemas"]


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
        _strip_empty_component_schemas(schema)
        # ensure_ascii=True (padrão) evita depender da codepage do terminal (Windows
        # cp1252 quebra em caracteres como "→"); o conteúdo semântico é idêntico —
        # \uXXXX decodifica para o mesmo unicode na leitura via yaml.safe_load.
        self.stdout.write(json.dumps(schema))
