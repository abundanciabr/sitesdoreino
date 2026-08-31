"""A escola é 18+: saem as travas que só existiam por causa de menores.

O §9 da `DECISAO-gamificacao.md` se chamava *"Menores, e o que isso obriga"* e
construía Modo Júnior como trava de sistema. Em 30/08/2026 o mantenedor
declarou: *"Só temos alunos acima de 18 anos, não temos e nem teremos alunos
menores de idade, registre isso."* A lei foi emendada no mesmo dia (PR #677); o
esquema nasceu antes e ficou para trás.

O QUE SAI, e por quê:

- `PerfilJogador.modo` (júnior/teen). Numa escola sem menores, todo perfil
  nascia marcado como "abaixo de 13 anos": o default fechado deixou de proteger
  alguém e passou a ser só uma afirmação falsa sobre quem estuda aqui.
- `ConquistaDefinicao.faixa_etaria` (todas/13mais). "13 anos ou mais" não separa
  ninguém de ninguém quando a escola inteira é 18+.
- A metade etária da restrição `marco_de_dinheiro_e_13mais_e_so_adulto_valida`.

O QUE FICA, mudando de razão e não de força: marco que envolve dinheiro só é
validado por quem tem autoridade. Era proteção de menor; hoje é qualidade e
confiança no que a escola afirma. Por isso o campo virou
`exige_validador_da_equipe` (RENAME, não drop): aqui todo mundo é adulto,
inclusive o aluno, e `validador_papel` aceita `par`. O que a trava separa é
autoridade, não idade.

QUANDO ISTO RODA PELA PRIMEIRA VEZ o banco desta célula está VAZIO: ela ainda
não tinha subido quando a migração foi escrita (o `infra/docker-compose.yml` a
ganha no degrau seguinte da escada). Nenhum perfil existia, nenhuma conquista
tinha sido semeada, e por isso não há migração de DADOS aqui.

Se a escola um dia admitir menores, o caminho é o que a lei escreve: a trava
volta ao §9 ANTES de a funcionalidade que a exige ser ligada.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("gamificacao", "0001_initial"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="conquistadefinicao",
            name="marco_de_dinheiro_e_13mais_e_so_adulto_valida",
        ),
        migrations.RenameField(
            model_name="conquistadefinicao",
            old_name="exige_validador_adulto",
            new_name="exige_validador_da_equipe",
        ),
        migrations.RemoveField(
            model_name="conquistadefinicao",
            name="faixa_etaria",
        ),
        migrations.RemoveField(
            model_name="perfiljogador",
            name="modo",
        ),
        migrations.AddConstraint(
            model_name="conquistadefinicao",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("envolve_dinheiro", True), _negated=True),
                    ("exige_validador_da_equipe", True),
                    _connector="OR",
                ),
                name="marco_de_dinheiro_so_a_equipe_valida",
            ),
        ),
    ]
