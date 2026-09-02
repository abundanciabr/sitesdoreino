---
schema_version: 2
armadilha: 274
estado: guardada
degrau: 4
confianca: alta
custo_por_queda: alto
guarda:
  tipo: teste
  detector: services/mensageria/tests/test_jornadas_travas.py
  motivo: "test_o_banco_recusa_inscricao_cuja_versao_e_de_outra_jornada e test_a_chave_composta_sobrevive_a_um_queryset_update reprovam se a chave estrangeira composta sair: com o RunSQL removido, os dois viram 'DID NOT RAISE' — medido."
sinal:
  - "models.E012"
  - "'constraints' refers to the nonexistent field"
  - "UniqueConstraint"
---

# `UniqueConstraint` não atravessa chave estrangeira, e a coluna que resolve isso precisa de uma chave COMPOSTA, não de um `save()`

**Sintoma.** Você quer uma trava de unicidade que envolva um campo de uma tabela
vizinha (*"uma inscrição andando por PESSOA por JORNADA"*, quando a inscrição
aponta para a VERSÃO da jornada). A grafia natural não existe:

```
models.E012 | 'constraints' refers to the nonexistent field 'jornada_versao__jornada'.
```

**Causa.** `UniqueConstraint` (e `Index`) só enxerga campos LOCAIS da tabela.
Uma restrição de banco é um índice sobre colunas daquela tabela — atravessar a
chave estrangeira exigiria um `JOIN`, e índice não faz `JOIN`.

A saída óbvia é **denormalizar**: guardar `jornada_id` ao lado de
`jornada_versao_id`, e trancar sobre a coluna local. E é aí que nasce o defeito
de verdade, que não é o `E012` — é o que vem depois. A coluna denormalizada
**pode mentir**: nada impede alguém de gravar a versão da jornada A dizendo
pertencer à jornada B. E, quando ela mente, quem cai é a trava que você
construiu: ela compara pela coluna errada e deixa passar exatamente o que
existia para impedir.

**A correção que parece bastar e não basta.** Preencher a coluna no
`Model.save()` a partir da relação. É o reflexo, e é uma guarda de papel:
`armadilhas/023` já custou caro aqui — `QuerySet.update()` **não passa** por
`save()`, e `update()` é justamente o caminho de uma varredura periódica, de uma
migração de dados e de um `psql`. Medido nesta casa: com a guarda só em Python,
o teste que escreve o par incoerente por `update()` **não levanta nada**.

**Solução — a chave estrangeira COMPOSTA, que o Django 5.1 não sabe escrever mas
o Postgres impõe igual.** Duas peças, e nenhuma sozinha resolve:

```python
# 1. Na tabela APONTADA: o índice único que torna o PAR referenciável.
#    Sozinho ele parece redundante (o `id` já é único) — e é essa aparência que
#    faz alguém apagá-lo um dia, derrubando a guarda sem que nada pareça errado.
class JornadaVersao(models.Model):
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["id", "jornada"], name="uniq_versao_id_com_jornada"),
        ]
```

```python
# 2. Na migração, o SQL que o ORM não tem vocabulário para escrever:
FK_COMPOSTA = """
ALTER TABLE jornadas_inscricao
    ADD CONSTRAINT inscricao_versao_pertence_a_jornada
    FOREIGN KEY (jornada_versao_id, jornada_id)
    REFERENCES jornadas_jornadaversao (id, jornada_id);
"""
migrations.RunSQL(sql=[FK_COMPOSTA], reverse_sql=[APAGAR_FK_COMPOSTA])
```

A partir daí o par `(jornada_versao_id, jornada_id)` **só existe se existir na
tabela apontada** — e a recusa vale para o ORM, para `queryset.update()`, para
`psql` e para qualquer código futuro que não conheça a classe.

**O detalhe que decide se a guarda é legível: NÃO ponha `DEFERRABLE`.** As chaves
estrangeiras que o Django cria são `DEFERRABLE INITIALLY DEFERRED`, e uma FK
adiada só reclama no `COMMIT` — longe da linha que causou o erro, e fora do
`with pytest.raises(...)` de qualquer teste escrito do jeito normal. Imediata, o
erro nasce no `INSERT`/`UPDATE` errado e diz o nome da restrição.

**O `save()` continua existindo, e agora com o papel certo:** preencher a coluna
quando ninguém a informou, por conveniência. A diferença entre conveniência e
garantia é a que este projeto já pagou para aprender — e escrever qual é qual no
próprio método evita que a próxima sessão leia a conveniência como a guarda.

**Onde isto já morde.** `services/mensageria/apps/jornadas/` (o motor das
sequências, TAR-071): a trava de "uma inscrição andando por pessoa por jornada" é
parcial E depende de uma coluna denormalizada — as duas coisas ao mesmo tempo, e
a segunda é a que ninguém vê.

**Origem:** TAR-071, o modelo de dados das jornadas
(`docs/decisoes/PLANO-SEQUENCIAS-DE-MENSAGENS.md` §5).
