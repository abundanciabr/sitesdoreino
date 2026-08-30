"""EM PÁGINA PÚBLICA, SÓ A ESCOLA FALA — o cadeado descendo sobre o dado.

Mandato do mantenedor em 30/08/2026 (registro
`painel/registros/20260830-021-voce-decidiu-como-o-forum-vai-aceitar-escrita.js`;
a §6 de `docs/decisoes/DECISAO-forum-da-escola.md` aponta para lá).

Esta migração faz TRÊS coisas, e a ordem entre elas não é decorativa:

1. **Fecha o que já está aberto.** Em produção o fórum nasceu com `duvidas` e
   `mostre-seu-trabalho` PÚBLICAS e com escrita de aluno. A restrição do passo 3
   recusaria essas duas linhas e a migração morreria no meio — em produção, com
   o deploy vermelho e o banco a meio caminho. Fechar primeiro é o que faz a
   restrição poder existir.
2. **Muda o default de `quem_escreve` para `equipe`**, o lado fechado: onde
   ninguém disser quem escreve, quem escreve é a escola.
3. **Instala a restrição** que torna a combinação proibida IMPOSSÍVEL — não
   "desaconselhada", não "conferida na view": impossível.

**Por que uma migração de dados, se a casa diz que semear é conteúdo.** Porque
isto não é semear: é fechar uma porta que já está aberta na produção. O comando
`semear_areas` é idempotente e de propósito NÃO altera o que já existe (ele não
pisa em edição humana), então ele não alcança as áreas que já nasceram. E, num
banco de teste recém-criado, o passo 1 é um `UPDATE` que não encontra linha
nenhuma — nenhum teste fica sabendo que ele passou por ali.
"""

from django.db import migrations, models


def fechar_o_que_ja_esta_aberto(apps, schema_editor):
    """Toda área PÚBLICA onde não é a equipe que escreve vira área de ALUNOS.

    O lado seguro do erro: quem já lia continua lendo depois de entrar, e
    ninguém de fora passa a ler nada que não lia antes.
    """
    Area = apps.get_model("forum", "Area")
    Area.objects.filter(visibilidade="publica").exclude(quem_escreve="equipe").update(
        visibilidade="alunos"
    )


def nao_reabre(apps, schema_editor):
    """Descer esta migração NÃO devolve as áreas ao estado público.

    Um `RunPython` reverso que reabrisse transformaria um `migrate` para trás —
    coisa que se faz às pressas, num rollback, sem ninguém lendo o código —
    numa exposição de mensagens de menores de idade a estranhos. O reverso
    honesto aqui é não fazer nada: a restrição sai (o passo 3 é reversível
    sozinho), e as áreas continuam fechadas até alguém decidir o contrário
    conscientemente.
    """


class Migration(migrations.Migration):
    dependencies = [("forum", "0001_initial")]

    operations = [
        migrations.RunPython(fechar_o_que_ja_esta_aberto, nao_reabre),
        migrations.AlterField(
            model_name="area",
            name="quem_escreve",
            field=models.CharField(
                choices=[
                    ("aluno", "Alunos e acima"),
                    ("equipe", "Só professor ou administrador"),
                    ("cadastrado", "Qualquer pessoa com login"),
                ],
                default="equipe",
                max_length=12,
            ),
        ),
        migrations.AddConstraint(
            model_name="area",
            constraint=models.CheckConstraint(
                condition=models.Q(("visibilidade", "publica"), _negated=True)
                | models.Q(("quem_escreve", "equipe")),
                name="pagina_publica_so_a_escola_fala",
            ),
        ),
    ]
