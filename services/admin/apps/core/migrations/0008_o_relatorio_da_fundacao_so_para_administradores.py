"""O relatório da fundação sai da pasta aberta e fica só para administradores.

Pedido do mantenedor em 05/09/2026, à tarde, com estas palavras: "deixe assim:
só admin pode ver, ler". O relatório tinha nascido PÚBLICO no deploy do PR #1092
naquela mesma tarde, e a decisão dele mudou depois de o ver no ar.

**Por que é uma migração, e não uma edição no arquivo.** Desde 31/08/2026 o
texto dos documentos mora no BANCO, e a pasta `documentos/` é só a semente
(`DECISAO-o-editor-de-documentos.md`). Trocar `publico: true` por `false` no
`.md` corrige a semente para uma instalação nova e não encosta na linha que já
existe em produção: o deploy ficaria verde e a página continuaria aberta
(`armadilhas/253`). Quem muda o banco que existe é esta migração.

**O que ela faz, e só isto:** fecha o documento (`publico=False`) e troca a
frase de abertura que prometia ao leitor um link público por uma que diz onde
o texto mora agora. A troca de texto segue o molde da `0005`: só onde a frase
ANTIGA está literalmente presente. Se o mantenedor já reescreveu aquele
parágrafo pela tela, o corpo dele fica como ele deixou, e o documento fecha
mesmo assim, porque fechar foi o pedido.

**Sem o documento no banco, não faz nada.** É o banco de uma instalação nova
antes da `0007`, ou um banco em que ele apagou o documento de vez; falhar por
isso derrubaria a célula no `migrate` por um passo de conteúdo (H18).
"""

from django.db import migrations

NOME = "relatorio-da-fundacao"

ANTES = (
    "Este documento mora em `meshcraft.top/docs/relatorio-da-fundacao` e pode ser "
    "editado pelo mantenedor: se você o leu em papel ou em cópia, o endereço tem a "
    "versão mais nova."
)
DEPOIS = (
    "Este documento mora na área de administração do site, onde só o mantenedor e a "
    "equipe o abrem e editam; a cópia que você recebeu é a versão da data acima."
)


def fechar_o_relatorio(apps, schema_editor):
    Documento = apps.get_model("core", "Documento")
    documento = Documento.objects.filter(nome=NOME).first()
    if documento is None:
        return
    campos = []
    if documento.publico:
        documento.publico = False
        campos.append("publico")
    if ANTES in documento.corpo:
        documento.corpo = documento.corpo.replace(ANTES, DEPOIS, 1)
        campos.append("corpo")
    if campos:
        documento.save(update_fields=campos)


def nao_reabre(apps, schema_editor):
    """Descer NÃO devolve o documento ao público.

    Um `migrate` para trás se faz às pressas, num rollback, sem ninguém lendo o
    código; reabrir aqui publicaria de novo um texto que o mantenedor mandou
    fechar. O reverso honesto é não fazer nada (a mesma escolha da `0005`).
    """


class Migration(migrations.Migration):
    dependencies = [("core", "0007_semear_o_relatorio_da_fundacao")]
    operations = [migrations.RunPython(fechar_o_relatorio, nao_reabre)]
