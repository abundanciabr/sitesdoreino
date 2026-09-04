# apps/core/management/commands/export_openapi.py  # [RECEITA:R1 v1]
#
# Cópia do PADRÃO de `mensageria`/`gamificacao`/`alunos` (Lei 3: copia-se o
# padrão entre células, nunca se importa código de uma na outra). As três
# funções de limpeza existem porque o django-ninja emite ruído que um contrato
# escrito à mão não tem, e o freeze compara os dois byte a byte: "ruído
# cosmético" reprova o CI exatamente como uma divergência real.
#
# ESTE COMANDO NASCE ANTES DO CONTRATO, E ESSA ORDEM É A RAZÃO DE ELE EXISTIR
# AGORA. A `metricas` é `not-applicable` em `ci/manifesto-de-contratos.json`, e
# continua sendo depois deste PR. O contrato entra pelo `RITOS.md` §3, em PR à
# parte, com a etiqueta `contrato` e o mantenedor presente; é a saída DESTE
# comando que vira o `contracts/metricas.openapi.yaml` daquele PR.
#
# A ordem inversa já custou uma rodada nesta casa: a `gamificacao` congelou o
# contrato antes de ter a porta, o portão respondeu "Unknown command:
# 'export_openapi'" (ERROR, não FAIL), e TODO PR que tocasse aquela célula
# morreu no `make ci` até a porta subir. Ver `armadilhas/228` e `243`.
import json

from django.core.management.base import BaseCommand

from config.api import api


def _strip_titles(node) -> None:
    """Remove os "title" que o pydantic injeta em todo schema e parametro
    gerado: ruido cosmetico que nao existe num contrato escrito a mao."""
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
    """O django-ninja repete por operacao o que ja esta declarado uma vez na
    raiz do documento: a "security" (auth global) e a "description" copiada
    para dentro do "schema" de um parametro que ja tem "description" proprio."""
    for path_item in schema.get("paths", {}).values():
        for operation in path_item.values():
            operation.pop("security", None)
            for param in operation.get("parameters", []):
                if "description" in param and "description" in param.get("schema", {}):
                    del param["schema"]["description"]


def _strip_empty_parameters(schema: dict) -> None:
    """O django-ninja sempre emite "parameters": [] mesmo quando a operacao nao
    tem parametro nenhum de path ou query; um contrato escrito a mao omite a
    chave nesse caso."""
    for path_item in schema.get("paths", {}).values():
        for operation in path_item.values():
            if operation.get("parameters") == []:
                del operation["parameters"]


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
        # ensure_ascii=True (padrao) evita depender da codepage do terminal (o
        # cp1252 do Windows quebra em caracteres como a seta); o conteudo
        # semantico e identico, porque \uXXXX decodifica para o mesmo unicode na
        # leitura via yaml.safe_load.
        self.stdout.write(json.dumps(schema))
