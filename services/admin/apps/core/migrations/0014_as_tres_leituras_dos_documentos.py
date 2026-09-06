"""A página dos documentos do Meshcraft ganha a 2ª e a 3ª leitura.

Em 06/09/2026 o mantenedor mandou ler mais dois documentos e disse que virão
cerca de sete. A página nasceu com uma leitura só; agora ela tem placar, uma
seção por documento e uma síntese, para CRESCER sem ser reescrita a cada
documento novo.

POR QUE UMA MIGRAÇÃO, SE O ARQUIVO JÁ ESTÁ NO REPOSITÓRIO
----------------------------------------------------------
Porque corrigir a receita não muda o bolo já assado. A pasta `documentos/` é
SEMENTE e a semeadura é `get_or_create`: ela **cria**, nunca atualiza. O texto
que o mantenedor lê vem do BANCO, e lá está a versão de ontem
(`armadilhas/253`, a irmã da `347`). Sem esta migração, o arquivo novo entra no
repositório, o `deploy-celula` termina verde, e a página continua mostrando o
texto velho, sem nada vermelho em lugar nenhum.

POR QUE ELA CASA A IMPRESSÃO DIGITAL ANTES DE TROCAR
-----------------------------------------------------
`sha256(corpo) == CORPO_SEMEADO` em vez de trocar direto. O mantenedor pode ter
editado a página pela tela desde ontem, e uma migração de texto que sobrescreve
trabalho dele é a pior troca possível: ela desfaz o que ele escreveu para
instalar o que eu escrevi. Casando a impressão digital, o pior desfecho vira
"a página continua com o texto dele", que é visível e reversível por ele
mesmo. É o mesmo desenho de `forum/migrations/0003`, que casa o texto inteiro
antes de trocar.

Se ele editou, esta migração não faz NADA e não avisa ninguém: a página é dele.
"""

import hashlib

from django.db import migrations

from apps.core import documentos

NOME = "como-criar-os-agentes-de-ia"

# O corpo exatamente como a `0013` o semeou, em 06/09/2026 (PR #1168): a versão
# com uma leitura só. Medido com o mesmo recorte que `documentos.de_texto` faz
# (o arquivo sem o cabeçalho `---`, com as quebras de linha das pontas tiradas).
CORPO_SEMEADO = "700a499aaf12eed3e78dbac482a7e66c109841b54f341de40eb00bef563cec3a"


def _impressao(corpo: str) -> str:
    return hashlib.sha256(corpo.encode("utf-8")).hexdigest()


def _do_arquivo():
    """Os campos do ARQUIVO, não os do banco.

    `documentos.ler` lê o BANCO, que é justamente o lado velho desta troca. O
    caminho é o mesmo de `semear_documento`: a pasta da imagem, o arquivo pelo
    nome, e o mesmo recorte de cabeçalho que a semeadura usa.
    """
    pasta = documentos.diretorio()
    if pasta is None:
        return None
    caminho = pasta / f"{NOME}.md"
    if not caminho.is_file():
        return None
    return documentos.de_texto(NOME, caminho.read_text(encoding="utf-8"))


def as_tres_leituras(apps, schema_editor):
    Documento = apps.get_model("core", "Documento")
    campos = _do_arquivo()
    if campos is None:  # sem a pasta na imagem, não faz nada (a lição H18)
        return
    documento = Documento.objects.filter(nome=NOME).first()
    if documento is None or _impressao(documento.corpo) != CORPO_SEMEADO:
        return  # ele editou pela tela, ou a página nem existe: não encosto
    documento.titulo = campos.titulo
    documento.corpo = campos.corpo
    documento.save(update_fields=["titulo", "corpo"])


def nao_devolve(apps, schema_editor):
    """Descer NÃO recoloca a versão de uma leitura só.

    Um reverso que reinstalasse o texto velho faria um `migrate` para trás,
    coisa que se faz às pressas num rollback, apagar duas leituras sem ninguém
    ler o código. O reverso honesto é não fazer nada: o texto mais completo
    fica.
    """


class Migration(migrations.Migration):
    dependencies = [("core", "0013_semear_como_criar_os_agentes")]
    operations = [migrations.RunPython(as_tres_leituras, nao_devolve)]
