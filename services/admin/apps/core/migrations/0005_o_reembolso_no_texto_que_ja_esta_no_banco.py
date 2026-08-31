"""O TEXTO DO REEMBOLSO SAI DOS DOCUMENTOS QUE JÁ ESTÃO NO BANCO.

Decisão do mantenedor em 31/08/2026 (`docs/decisoes/DECISAO-reembolso-tira-o-acesso.md`):
o reembolso desfaz a compra e tira o acesso. A lei entrou, o código entrou, e os
dois `.md` de `documentos/` foram corrigidos no PR #764 — **e a página no ar
continuou dizendo o contrário.**

Medido, não suposto: com o `deploy-celula` do #764 já **verde**,
`curl https://meshcraft.top/docs/como-funciona-a-entrada` ainda devolvia
*"você devolveu o dinheiro e continua entrando"*.

O MOTIVO, e é a armadilha que o `CLAUDE.md` avisa em letras grandes
------------------------------------------------------------------
Desde 31/08/2026 (`DECISAO-o-editor-de-documentos.md`) a fonte de `/docs/…` é o
**BANCO**, não os arquivos: o mantenedor edita por uma tela, e o disco do
container é remontado a cada atualização. Os `.md` viraram **semente**, e a
semeadura é `get_or_create` na migração `0003` — de propósito, para nunca pisar
numa edição dele.

**Corrigir a receita não muda o bolo que já foi assado.** É exatamente a lição
que a `forum/0003` pagou em 30/08 com o travessão, e este arquivo é o mesmo
molde. O portão vigia ARQUIVOS; texto gravado no banco ele não vê, e nunca verá.

O teste também não veria: em banco recém-criado estes `UPDATE` não encontram
linha nenhuma.

POR QUE ELE CASA O TRECHO INTEIRO ANTES DE TROCAR
--------------------------------------------------
A troca só acontece onde o texto ANTIGO está literalmente presente. Se o
mantenedor já tiver reescrito aquele parágrafo pela tela do editor, a migração
não encontra nada e **não faz nada** — e o resto do documento, que ele pode ter
editado em outro ponto, fica intacto, porque a substituição é do TRECHO e não do
corpo inteiro.

O pior desfecho de uma migração de correção de texto é ela sobrescrever texto
melhor. Casar o valor exato é o que torna isso impossível, e não só improvável.
"""

from django.db import migrations

# ---------------------------------------------------------------- os trechos
#
# Cada par é `(nome do documento, texto ANTES, texto DEPOIS)`, copiado
# literalmente do diff do PR #764. As quebras de linha são as do arquivo
# semeado: LF, porque quem leu o `.md` foi o container Linux.

TROCAS = [
    (
        "como-funciona-a-entrada",
        "- **Reembolsado**: você devolveu o dinheiro e **continua entrando**. Foi uma\n"
        "  decisão da escola: quem já foi aluno mantém a voz na Caixa de Sugestões.\n"
        "- **Pausado**: o acesso está desligado por enquanto, e **volta sozinho** quando\n"
        "  a equipe religar. Você não precisa fazer nada, e não há o que pedir.\n"
        "- **Ex-aluno**: o acesso acabou. Sua ficha continua guardada, e **se você quiser\n"
        "  voltar, é só pedir de novo** (o mesmo formulário do começo).",
        "- **Pausado**: o acesso está desligado por enquanto, e **volta sozinho** quando\n"
        "  a equipe religar. Você não precisa fazer nada, e não há o que pedir.\n"
        "- **Ex-aluno**: o acesso acabou. Sua ficha continua guardada, e **se você quiser\n"
        "  voltar, é só pedir de novo** (o mesmo formulário do começo).\n"
        "- **Reembolsado**: o dinheiro da sua compra foi devolvido, e a matrícula foi\n"
        "  desfeita junto. **Você não entra mais**, nem no curso nem na Caixa de\n"
        "  Sugestões. Sua ficha continua guardada, mas aqui não há o botão de pedir de\n"
        "  novo: se quiser voltar a estudar, fale com a escola ou faça uma nova compra.",
    ),
    (
        "jornada-do-aluno",
        "**Reembolsado**: devolveu o dinheiro e **continua entrando**. Foi a sua decisão\n"
        "de 24 de agosto: quem já foi aluno mantém a voz na Caixa.\n\n"
        "### Depois",
        "### Depois",
    ),
    (
        "jornada-do-aluno",
        "**Ex-aluno**: saiu da escola, e a ficha continua aqui inteira. Vê que o acesso\n"
        "acabou e o botão *Pedir para voltar*. Sai daqui de dois jeitos: ela pedindo para\n"
        "voltar (nasce uma ficha nova), ou você pondo a situação em Ativo na ficha antiga.",
        "**Ex-aluno**: saiu da escola, e a ficha continua aqui inteira. Vê que o acesso\n"
        "acabou e o botão *Pedir para voltar*. Sai daqui de dois jeitos: ela pedindo para\n"
        "voltar (nasce uma ficha nova), ou você pondo a situação em Ativo na ficha antiga.\n\n"
        "**Reembolsado**: o dinheiro voltou, e a matrícula foi desfeita junto. **Não\n"
        "entra mais**, e a ficha continua aqui. Vê uma tela que nomeia o reembolso e diz\n"
        "o que fazer para voltar, **sem** o botão *Pedir para voltar* que o ex-aluno tem.\n"
        "Sai daqui de um jeito só: você pondo a situação em Ativo.",
    ),
    (
        "jornada-do-aluno",
        "- **Aluno → Reembolsado** (*você*): situação **Reembolsado**. O acesso continua:\n"
        "  é sobre o dinheiro, não sobre a porta.",
        "- **Aluno → Reembolsado** (*você*): situação **Reembolsado**. O acesso acaba\n"
        "  junto, porque o reembolso desfaz a compra. Ela não pede para voltar sozinha,\n"
        "  e a volta é você pondo a situação em Ativo.",
    ),
]


def corrigir_o_reembolso(apps, schema_editor):
    Documento = apps.get_model("core", "Documento")
    for nome, antes, depois in TROCAS:
        documento = Documento.objects.filter(nome=nome).first()
        if documento is None or antes not in documento.corpo:
            # Documento ausente (banco novo) ou já reescrito pelo mantenedor:
            # não fazer nada é o comportamento certo nos dois casos.
            continue
        documento.corpo = documento.corpo.replace(antes, depois, 1)
        documento.save(update_fields=["corpo"])


def nao_devolve(apps, schema_editor):
    """Descer esta migração NÃO recoloca a promessa errada no site.

    Um reverso que reescrevesse *"continua entrando"* faria um `migrate` para
    trás — coisa que se faz às pressas, num rollback, sem ninguém lendo o
    código — publicar de novo uma frase que o mantenedor mandou corrigir. O
    reverso honesto é não fazer nada: o texto correto fica.
    """


class Migration(migrations.Migration):
    dependencies = [("core", "0004_versoes_do_documento")]
    operations = [migrations.RunPython(corrigir_o_reembolso, nao_devolve)]
