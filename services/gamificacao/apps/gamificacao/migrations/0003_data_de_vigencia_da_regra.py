"""A data em que cada regra passou a valer — o mecanismo do "nunca retroativo".

A lei §10.5 sempre disse que ajustar a economia é *"UPDATE + versão, anunciado e
nunca retroativo"*. Até aqui as três palavras tinham peso muito diferente:
`ativa` e `versao` eram colunas, e o "nunca retroativo" era só uma frase no topo
do `motor.py`. Um evento antigo reentregue depois de alguém ligar a regra pagava
como se a regra sempre tivesse valido, e ninguém descobriria olhando a tela — é
a "garantia sem mecanismo" da `RETROSPECTIVA-FASE-D`.

Esta migração fecha o buraco com o BANCO, não com disciplina:

- `vigente_desde` guarda o instante em que a regra foi LIGADA (nulo = nunca foi);
- a `CheckConstraint` recusa a combinação impossível — ligada e sem data —, que
  é exatamente o estado em que o motor voltaria a pagar retroativo em silêncio.

**Nenhuma linha existente precisa de conversão.** Toda a economia foi semeada
`ativa=False` (`semear_economia`), nenhuma regra jamais foi ligada em produção, e
`ativa=False` satisfaz a restrição com `vigente_desde` nulo. Se um dia esta
migração rodar num banco onde já exista regra ligada, ela FALHA — e falhar é o
comportamento certo: seria uma regra valendo sem data de início.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("gamificacao", "0002_escola_18_mais"),
    ]

    operations = [
        migrations.AddField(
            model_name="regradepontuacao",
            name="vigente_desde",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="regradepontuacao",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("ativa", False), ("vigente_desde__isnull", False), _connector="OR"
                ),
                name="regra_ligada_tem_data_de_vigencia",
            ),
        ),
    ]
