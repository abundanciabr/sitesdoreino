# apps/core/management/commands/export_openapi.py
#
# Copia do PADRAO de `gamificacao`/`alunos`/`catalogo` (Lei 3: copia-se o padrao
# entre celulas, nunca se importa codigo de uma na outra). As tres funcoes de
# limpeza abaixo existem porque o django-ninja emite ruido que um contrato
# escrito a mao nao tem, e o freeze compara os dois byte a byte: ruido cosmetico
# reprova o CI exatamente como uma divergencia real.
#
# Este comando e o que torna o contrato desta celula um PORTAO em vez de
# documentacao. E a ORDEM importa: esta celula esta em `not-applicable` no
# manifesto de contratos, e so vira `required` no degrau 2.8, DEPOIS de a porta
# existir e exportar. Congelar antes deixaria todo PR da celula morrendo com
# "Unknown command: export_openapi" (`armadilhas/228` e `243`).
#
# LEIA A SAIDA ANTES DE CONGELAR (`armadilhas/324`). A prosa tambem vira pedra:
# o `info.description` da porta e a `description` de cada operacao entram no
# congelado e passam a valer como contrato. Nenhuma maquina sabe se uma frase em
# portugues descreve o que o codigo faz, e o freeze da PASS com as duas pontas
# igualmente erradas.

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
    nível raiz do documento: a "security" (auth global, dois pares consumidores
    por Bearer) e a "description" copiada para dentro de "schema" de cada
    parâmetro que já tem "description" no próprio parâmetro. O contrato
    congelado só declara essas informações uma vez."""
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


# A quarta funcao de limpeza do molde de `notificacoes` NAO foi copiada, e a
# ausencia e decisao: `_strip_empty_component_schemas` existe la porque aquele
# contrato nao nomeia componente nenhum (tudo inline nos paths), e o django-ninja
# emite `"schemas": {}` vazio. Esta porta nomeia quatorze componentes, entao
# aquela funcao nunca teria o que apagar. Copia-la seria carregar codigo morto
# com um comentario que mente sobre esta celula.


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
        # ensure_ascii=True (padrão) evita depender da codepage do terminal (Windows
        # cp1252 quebra em caracteres como "→"); o conteúdo semântico é idêntico —
        # \uXXXX decodifica para o mesmo unicode na leitura via yaml.safe_load.
        self.stdout.write(json.dumps(schema))
