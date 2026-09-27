"""Semeia a foto privada da Comunidade sem alterar edição do mantenedor."""

from django.db import migrations

from apps.core.documentos import de_texto, diretorio, semear_documento

NOME = "roadmap-da-comunidade"


def semear_roadmap_da_comunidade(apps, schema_editor):
    Documento = apps.get_model("core", "Documento")
    criado = semear_documento(Documento, NOME)
    pasta = diretorio()
    if pasta is None:
        return
    caminho = pasta / f"{NOME}.md"
    if not caminho.is_file():
        return
    campos = de_texto(NOME, caminho.read_text(encoding="utf-8"))
    documento = Documento.objects.filter(nome=NOME).first()
    if documento is None:
        return
    # A 0003 também semeia este arquivo numa instalação nova, ainda como texto.
    # Só essa semente intacta pode ganhar formato; edição pela tela fica inteira.
    if (
        documento.corpo != campos.corpo
        or documento.titulo != campos.titulo
        or documento.ordem != campos.ordem
        or documento.publico
        or documento.arquivado
        or documento.formato != "texto"
    ):
        return
    VersaoDoDocumento = apps.get_model("core", "VersaoDoDocumento")
    if (
        not criado
        and VersaoDoDocumento.objects.filter(documento_id=documento.pk).exists()
    ):
        return
    documento.formato = "pagina"
    documento.save(update_fields=["formato"])


def nao_desfaz(apps, schema_editor):
    """O rollback preserva o documento e as edições feitas pela tela."""


class Migration(migrations.Migration):
    dependencies = [("core", "0031_atualizar_a_comunidade_na_rodada_2")]
    operations = [migrations.RunPython(semear_roadmap_da_comunidade, nao_desfaz)]
