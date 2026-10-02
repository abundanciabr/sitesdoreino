"""Recupera detalhes do acervo JS sem executar código nem alterar edições."""

import ast
import re

from django.db import migrations


CAMPO = re.compile(
    r"^\s*detalhe\s*:\s*(.*?)(?=^\s*[A-Za-z_]\w*\s*:|^\s*\}\)\s*;)",
    re.M | re.S,
)
LITERAL = re.compile(r'"(?:\\.|[^"\\])*"', re.S)


def detalhe_original(texto):
    """Concatena somente literais de string JS; qualquer outra expressão é ignorada."""
    achado = CAMPO.search(texto or "")
    if not achado:
        return None
    expressao = achado.group(1).strip().rstrip(",").strip()
    partes = []
    posicao = 0
    for literal in LITERAL.finditer(expressao):
        separador = expressao[posicao:literal.start()].strip()
        if separador != ("+" if partes else ""):
            return None
        try:
            parte = ast.literal_eval(literal.group())
        except (SyntaxError, ValueError):
            return None
        if not isinstance(parte, str):
            return None
        partes.append(parte)
        posicao = literal.end()
    if not partes or expressao[posicao:].strip():
        return None
    return "".join(partes)


def preencher_detalhes(apps, schema_editor):
    Registro = apps.get_model("core", "RegistroDoPlacar")
    for registro in Registro.objects.using(schema_editor.connection.alias).all().iterator():
        # Uma edição pelo painel sempre escreve esta chave, inclusive se vazia.
        if "detalhe" in registro.dados:
            continue
        detalhe = detalhe_original(registro.texto_original)
        if detalhe is None:
            continue
        registro.dados = {**registro.dados, "detalhe": detalhe}
        registro.save(update_fields=["dados"])


class Migration(migrations.Migration):
    dependencies = [("core", "0041_placar_persistente")]

    operations = [migrations.RunPython(preencher_detalhes, migrations.RunPython.noop)]
