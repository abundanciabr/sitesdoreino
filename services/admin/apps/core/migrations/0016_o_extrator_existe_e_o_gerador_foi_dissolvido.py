"""A página dos documentos volta a dizer a verdade sobre os sete agentes.

A página nasceu em 06/09/2026 (PR #1168) e envelheceu no mesmo dia, porque o
dia mudou dois dos sete agentes dela: o **Extrator** saiu de "registrado, não
construído" e passou a existir em duas telas de colar, nenhuma delas com IA
(PR #1177, o sumário; PR #1240, o capítulo); e o **Gerador de derivados** foi
dissolvido, porque o mantenedor disse em 06/09/2026 que os textos das 34 aulas
já estão escritos. Com isso o placar de agentes de IA de verdade DIMINUIU: dos
sete previstos, sobram dois.

POR QUE UMA MIGRAÇÃO, SE O ARQUIVO JÁ ESTÁ NO REPOSITÓRIO
----------------------------------------------------------
Porque corrigir a receita não muda o bolo já assado. A pasta `documentos/` é
SEMENTE e a semeadura é `get_or_create`: ela **cria**, nunca atualiza. O texto
que o mantenedor lê vem do BANCO (`armadilhas/253`, a irmã da `347`). Sem esta
migração, o arquivo corrigido entra no repositório, o `deploy-celula` termina
verde, e a página continua afirmando que o Extrator não foi construído, sem
nada vermelho em lugar nenhum.

É o mesmo desenho da `0014`, que trouxe a 2ª e a 3ª leitura para esta mesma
página, e pela mesma razão.

POR QUE ELA CASA A IMPRESSÃO DIGITAL ANTES DE TROCAR
-----------------------------------------------------
`sha256(corpo) == CORPO_SEMEADO` em vez de trocar direto. O mantenedor pode ter
editado a página pela tela, e uma migração de texto que sobrescreve trabalho
dele é a pior troca possível: ela desfaz o que ele escreveu para instalar o que
eu escrevi. Casando a impressão digital, o pior desfecho vira "a página
continua com o texto dele", que é visível e reversível por ele mesmo.

Se ele editou, esta migração não faz NADA e não avisa ninguém: a página é dele.
"""

import hashlib

from django.db import migrations

from apps.core import documentos

NOME = "como-criar-os-agentes-de-ia"

# O corpo exatamente como a `0014` o deixou, em 06/09/2026 (PR #1171): a versão
# com as três leituras e com o Extrator ainda "registrado, não construído".
# Medido com o mesmo recorte que `documentos.de_texto` faz (o arquivo sem o
# cabeçalho `---`, com as quebras de linha das pontas tiradas).
CORPO_SEMEADO = "1b6e580f189173839d897d1aaeb8dca69e98ef69f045ce57909c63b027be7028"


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


def o_extrator_existe_e_o_gerador_foi_dissolvido(apps, schema_editor):
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
    """Descer NÃO recoloca a versão que dizia o que já não é verdade.

    Um reverso que reinstalasse o texto velho faria um `migrate` para trás,
    coisa que se faz às pressas num rollback, voltar a afirmar que o Extrator
    não existe sem ninguém ler o código. O reverso honesto é não fazer nada: o
    texto correto fica.
    """


class Migration(migrations.Migration):
    dependencies = [("core", "0015_semear_a_segunda_opiniao_10x")]
    operations = [
        migrations.RunPython(o_extrator_existe_e_o_gerador_foi_dissolvido, nao_devolve)
    ]
