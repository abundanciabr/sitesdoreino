# apps/core/management/commands/export_openapi.py  # [RECEITA:R1 v1]
#
# Cópia do PADRÃO de `gamificacao`/`notificacoes`/`pages` (Lei 3: copia-se o
# padrão entre células, nunca se importa código de uma na outra). As três
# funções de limpeza existem porque o django-ninja emite ruído que o contrato
# escrito à mão não tem, e o freeze compara os dois byte a byte: "ruído
# cosmético" reprova o CI exatamente como uma divergência real.
#
# AQUI A ORDEM FOI A INVERSA DA QUE `armadilhas/228` RECOMENDA, e não por
# descuido. O PR do Rito de Contrato desta célula (#1238) foi aberto antes deste
# e ficou VERMELHO de propósito: `ci/celulas.yml` atribui `painel/` à `admin`, e
# o recibo do livro que todo PR carrega mora em `painel/`, então o próprio PR do
# Rito acorda o `ci-celula (admin)` e cobra um freeze que ainda não tinha o que
# exportar. A cerca (`ci/cerca-de-celula.sh`) proíbe congelar e implementar no
# mesmo PR, então a saída foi esta: o contrato espera, e este comando (com a
# porta) é o próximo PR da célula, exatamente como a `228` manda consertar quem
# já congelou fora de ordem.
#
# O QUE SE LÊ ANTES DE CONGELAR O QUE ELE IMPRIME (`armadilhas/324`): o
# `info.description` do documento e o `summary`/`description` de cada operação
# são a única parte do contrato escrita para uma PESSOA, e nenhuma máquina
# confere se eles descrevem o que o código faz. Depois do congelamento, corrigir
# uma frase dessas exige outro Rito de Contrato.
#
# `management/` e `commands/` não levam `__init__.py`, de propósito: pacote de
# namespace funciona para comandos do Django, e a `gamificacao` já roda assim
# (`armadilhas/022`).
import json

from django.core.management.base import BaseCommand

from config.api import api


def _strip_titles(node) -> None:
    """Remove os "title" que o pydantic injeta em todo schema/parâmetro gerado:
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
    nível raiz do documento: a "security" (auth global, Bearer por par) e a
    "description" copiada para dentro de "schema" de cada parâmetro que já tem
    "description" no próprio parâmetro. O contrato congelado só declara essas
    informações uma vez. A autenticação EFETIVA de cada operação o freeze não
    lê daqui: ele sonda `auth_callbacks` na fonte (`ci/contract_freeze.py`)."""
    for path_item in schema.get("paths", {}).values():
        for operation in path_item.values():
            operation.pop("security", None)
            for param in operation.get("parameters", []):
                if "description" in param and "description" in param.get("schema", {}):
                    del param["schema"]["description"]


def _strip_empty_parameters(schema: dict) -> None:
    """O django-ninja sempre emite "parameters": [] mesmo quando a operação não
    tem nenhum parâmetro de path/query; o contrato congelado, escrito à mão,
    simplesmente omite a chave nesse caso."""
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
        # ensure_ascii=True (padrão) evita depender da codepage do terminal
        # (Windows cp1252 quebra em caracteres como "→"); o conteúdo semântico é
        # idêntico: \uXXXX decodifica para o mesmo unicode via yaml.safe_load.
        self.stdout.write(json.dumps(schema))
