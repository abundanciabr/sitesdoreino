"""O qualificador de status, e a linha que já existe em produção sendo corrigida.

`sugestao.status-alterado` é UM assunto para SEIS fatos (um por status). Sem
qualificador, a regra `sugestao-implementada` casava só pelo `evento_gatilho` e
pagava 40 XP em CADA passo do funil — em_analise → planejado →
em_desenvolvimento → implementado dá 160 XP por uma sugestão só, sem teto diário
e sem quarentena. Medido em 31/08/2026, ANTES de a regra ser ligada.

**A SEGUNDA OPERAÇÃO É O PONTO DESTA MIGRAÇÃO, e não um detalhe.** Consertar o
`semear_economia.py` NÃO conserta a linha que já está no banco: o semeador é
`get_or_create` e, de propósito, não altera o que existe (é o que preserva as
edições do mantenedor). A regra já foi semeada em produção com o campo vazio, e
sem este `UPDATE` o conserto valeria só num banco novo — exatamente a armadilha
que o `CLAUDE.md` descreve ("corrigir um semeador não corrige a linha que ele
criou"), e que já deixou um travessão vivo no fórum depois de uma varredura que
se declarou completa.

Por que é seguro: mexe em UMA regra, pelo slug, e só onde o campo ainda está
vazio — não pisa em edição humana. E a volta atrás devolve o campo ao vazio, que
é o estado anterior exato.
"""

from django.db import migrations, models

SLUG = "sugestao-implementada"
STATUS = "implementado"


def qualificar(apps, schema_editor):
    Regra = apps.get_model("gamificacao", "RegraDePontuacao")
    Regra.objects.filter(slug=SLUG, quando_status_novo="").update(
        quando_status_novo=STATUS
    )


def desqualificar(apps, schema_editor):
    Regra = apps.get_model("gamificacao", "RegraDePontuacao")
    Regra.objects.filter(slug=SLUG, quando_status_novo=STATUS).update(
        quando_status_novo=""
    )


class Migration(migrations.Migration):

    dependencies = [
        ("gamificacao", "0003_data_de_vigencia_da_regra"),
    ]

    operations = [
        migrations.AddField(
            model_name="regradepontuacao",
            name="quando_status_novo",
            field=models.CharField(blank=True, default="", max_length=30),
        ),
        migrations.RunPython(qualificar, desqualificar),
    ]
